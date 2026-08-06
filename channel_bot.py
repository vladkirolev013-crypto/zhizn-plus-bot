import telebot
import sqlite3
import requests
import os
import json
import time
import logging
import threading
import random
import glob
import sys
import traceback
import string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
ADMIN_IDS = [8746212340]

AGNES_API_KEY = "sk-8nqC897jST7vx1brGMUTNLRsVGPXgP7Bcpuwmbl5quaCLN5c"
AGNES_API_URL = "https://apihub.agnes-ai.com/v1/images/generations"

TIMEZONE = ZoneInfo("Asia/Novokuznetsk")

BOT_VERSION = "12.0.0"
BOT_NAME = "Жизнь+ Про"

DB_PATH = 'channel.db'
LOG_PATH = 'bot_logs.txt'

CHANNEL_THEMES = [
    "психология",
    "отношения",
    "карьера",
    "здоровье",
    "финансы",
    "мотивация",
    "саморазвитие"
]

PRICE_TEST_20 = 50
PRICE_COACH = 100

# ============================================================
# AI-ПРОВАЙДЕРЫ
# ============================================================

AI_PROVIDERS = [
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openrouter/auto",  # исправлено: openrouter/free не существует
        "api_key": "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"
    },
    {
        "name": "G4F",
        "url": "https://api.g4f.icu/v1/chat/completions",
        "model": "gpt-4o-mini",
        "api_key": ""
    },
    {
        "name": "Pawan",
        "url": "https://api.pawan.krd/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "api_key": ""
    },
    {
        "name": "SHN",
        "url": "https://chatgpt-api.shn.hk/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "api_key": ""
    }
]

# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")

# ============================================================
# СОЗДАЁМ БОТА СРАЗУ — ДО ВСЕХ ДЕКОРАТОРОВ
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)
DB_LOCK = threading.RLock()  # потокобезопасность SQLite

# ============================================================
# УБИЙЦА 409
# ============================================================

def super_kill_409():
    try:
        for i in range(10):
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                requests.post(url, json={"drop_pending_updates": True}, timeout=10)
                time.sleep(0.1)
            except Exception:
                pass
        patterns = ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid']
        for pattern in patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                except Exception:
                    pass
        logger.info("🔥 409 УНИЧТОЖЕН")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

for _ in range(3):
    super_kill_409()
    time.sleep(2)

# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_database():
    conn = get_conn()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tests_passed INTEGER DEFAULT 0,
        consultations INTEGER DEFAULT 0,
        last_activity TIMESTAMP,
        referrer_id INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE,
        bonus_tests INTEGER DEFAULT 0,
        coach_credits INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        free_count INTEGER DEFAULT 0,
        paid_test_count INTEGER DEFAULT 0,
        coach_count INTEGER DEFAULT 0,
        promo_used INTEGER DEFAULT 0,
        users_count INTEGER DEFAULT 0,
        posts_count INTEGER DEFAULT 0,
        tests_created INTEGER DEFAULT 0,
        images_generated INTEGER DEFAULT 0,
        consultations_count INTEGER DEFAULT 0,
        referrals_count INTEGER DEFAULT 0,
        gifts_used INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO stats (free_count, paid_test_count, coach_count, promo_used, users_count, posts_count, tests_created, images_generated, consultations_count, referrals_count, gifts_used) VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)")
    
    c.execute('''CREATE TABLE IF NOT EXISTS consultation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        questions TEXT,
        answers TEXT,
        current_q INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_paid INTEGER DEFAULT 0,
        is_analyzed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS consultation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        session_id INTEGER,
        questions TEXT,
        answers TEXT,
        analysis TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        amount INTEGER,
        product TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used_by INTEGER DEFAULT 0,
        used_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        topic TEXT,
        image_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS daily_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT,
        questions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_paid INTEGER DEFAULT 0,
        message_id INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS used_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        created_by INTEGER,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS checkins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        session_id INTEGER,
        checkin_date TIMESTAMP,
        is_done INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    logger.info("✅ БАЗА ДАННЫХ ИНИЦИАЛИЗИРОВАНА")

init_database()

# ============================================================
# AI (ТЕКСТ)
# ============================================================

def ask_ai(system, user, max_tokens=3000, retries=2):
    if not user or len(user.strip()) == 0:
        user = "Сделай запрос."
    
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    
    for provider in AI_PROVIDERS:
        for attempt in range(retries):
            try:
                logger.info(f"🔄 Провайдер: {provider['name']}, попытка {attempt+1}/{retries}")
                
                headers = {"Content-Type": "application/json"}
                if provider.get("api_key"):
                    headers["Authorization"] = f"Bearer {provider['api_key']}"
                
                payload = {
                    "model": provider["model"],
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.85,
                    "stream": False
                }
                
                response = requests.post(
                    provider["url"],
                    headers=headers,
                    json=payload,
                    timeout=40,
                    verify=False
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if content and len(content) > 10:
                        logger.info(f"✅ ОТВЕТ ОТ {provider['name']} ({len(content)} символов)")
                        return content
                    else:
                        logger.warning(f"⚠️ Пустой ответ от {provider['name']}")
                else:
                    logger.warning(f"⚠️ Ошибка {provider['name']}: {response.status_code}")
                
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка {provider['name']}: {e}")
                time.sleep(0.5)
        
        logger.info(f"⏳ {provider['name']} не ответил, переключаюсь...")
    
    logger.error("❌ ВСЕ AI-ПРОВАЙДЕРЫ НЕ ОТВЕТИЛИ")
    return None

# ============================================================
# КАРТИНКИ (AGNES AI + Pollinations)
# ============================================================

def generate_image(prompt, width=1024, height=768):
    try:
        logger.info("🖼 Генерация супер-картинки через Agnes AI...")
        
        full_prompt = f"""Hyper-realistic, cinematic photography. {prompt}
Subject: European, Caucasian, light skin, natural glow, warm smile, relaxed, positive energy.
Environment: Sunny, golden hour, warm sunlight, lush green, peaceful.
Lighting: Soft golden backlight, warm skin tones.
Style: Photorealistic, high detail, natural texture, magazine quality, warm amber tones.
Quality: 8K, masterpiece."""
        
        headers = {
            "Authorization": f"Bearer {AGNES_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "agnes-image-2.0-flash",
            "prompt": full_prompt,
            "size": f"{width}x{height}",
            "extra_body": {"response_format": "url"}
        }
        
        response = requests.post(
            AGNES_API_URL, headers=headers, json=payload, timeout=60, verify=False
        )
        
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('data', [{}])[0].get('url')
            if image_url:
                img_response = requests.get(image_url, timeout=30)
                if img_response.status_code == 200:
                    filename = f"/tmp/image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
                    with open(filename, 'wb') as f:
                        f.write(img_response.content)
                    logger.info(f"✅ Супер-картинка создана")
                    return filename
        else:
            logger.error(f"❌ Ошибка Agnes AI: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Ошибка генерации картинки: {e}")
    
    logger.info("🔄 Переключаюсь на Pollinations...")
    return generate_image_pollinations(prompt)

def generate_image_pollinations(prompt):
    try:
        clean_prompt = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "").replace(',', '%2C')
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=768&nologo=true&seed={random.randint(1,999999)}"
        
        logger.info("🖼 Генерация через Pollinations...")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200 and len(response.content) > 1000:
            filename = f"/tmp/image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"✅ Картинка создана (Pollinations)")
            return filename
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    return None

def generate_post_image(theme):
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational, masterpiece",
        f"beautiful landscape {theme}, sunrise, hope, positive energy, 4k",
        f"minimalist illustration {theme}, soft pastel, calm, self discovery"
    ]
    return generate_image(random.choice(prompts))

def generate_test_image(topic):
    prompts = [
        f"psychological test illustration {topic}, introspection, deep colors",
        f"abstract psychology art {topic}, meditation, self reflection",
        f"mental health awareness {topic}, healing, balance"
    ]
    return generate_image(random.choice(prompts))

def generate_result_image(text, result):
    prompt = f"minimalist psychology illustration, {text}, {result}, inspirational"
    return generate_image(prompt)

# ============================================================
# ГЕНЕРАТОРЫ КОНТЕНТА
# ============================================================

def generate_post(topic):
    system = f"Ты — автор канала о психологии. Напиши пост на тему '{topic}'. Минимум 600 символов. Без пафоса. Добавь вопрос в конце."
    user = f"Тема: {topic}."
    return ask_ai(system, user, 3000)

def generate_test_questions(topic, count=10):
    depth = "диагностика личности" if count == 10 else "полный психологический разбор"
    
    system = f"""ТЫ — КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ.
Составь {count} глубоких, НО ПРОСТЫХ вопросов для {depth} на тему "{topic}".
Вопросы должны быть ПОНЯТНЫМИ по форме, но МОЩНЫМИ по смыслу. Без терминов.
Верни ТОЛЬКО JSON.
ФОРМАТ:
[{{"question": "простой вопрос?", "options": {{"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"}}, "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}}}]
НЕ ДОБАВЛЯЙ НИЧЕГО КРОМЕ JSON."""
    
    response = ask_ai(system, "", 4000)
    if not response:
        return None
    
    start = response.find('[')
    end = response.rfind(']') + 1
    if start == -1 or end == -1:
        return None
    
    try:
        questions = json.loads(response[start:end])
        for q in questions:
            if 'scores' not in q:
                q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        return questions[:count]
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        return None

def generate_analysis(topic, answers, score, total, is_paid):
    if is_paid:
        system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-КОУЧ.
Проведи полный разбор личности.
Структура: портрет, 2-3 инсайта, корень проблемы, план на неделю.
Объем: 1500+ знаков."""
        user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
    else:
        system = """ТЫ — ОПЫТНЫЙ ПСИХОЛОГ.
Дай краткий анализ.
Структура: главная проблема, 1 инсайт, вопрос, шаг.
Объем: 800+ знаков."""
        user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
    
    return ask_ai(system, user, 4000 if is_paid else 2000)

def generate_consultation_questions():
    system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-НЛП-ПРАКТИК.
Составь 25 вопросов для сеанса психотерапии.
Вопросы простые по форме, но сильные по смыслу. БЕЗ терминов. НЛП-техники.
Верни ТОЛЬКО JSON.
Формат: [{"question": "простой, но сильный вопрос?"}]
НЕ ДОБАВЛЯЙ НИЧЕГО КРОМЕ JSON."""
    
    response = ask_ai(system, "", 4000)
    if not response:
        return None
    start = response.find('[')
    end = response.rfind(']') + 1
    if start == -1 or end == -1:
        return None
    try:
        questions = json.loads(response[start:end])
        return questions[:25]
    except Exception:
        return None

def generate_consultation_analysis(answers, chat_id, session_id):
    system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-КОУЧ.
Проведи полный разбор личности.
Структура: главная рана, как управляет, корень, 3 шага, заключение.
Объем: 1500+ знаков."""
    
    user = f"Ответы:\n{answers}"
    response = ask_ai(system, user, 4000)
    if response:
        try:
            with DB_LOCK:
                c = get_conn().cursor()
                c.execute("""INSERT INTO consultation_history (chat_id, session_id, questions, answers, analysis) VALUES (?, ?, ?, ?, ?)""",
                          (chat_id, session_id, "", answers, response))
                c.execute("UPDATE stats SET consultations_count = consultations_count + 1")
                c.connection.commit()
                c.connection.close()
            
            checkin_date = datetime.now(TIMEZONE) + timedelta(days=3)
            with DB_LOCK:
                c = get_conn().cursor()
                c.execute("""INSERT INTO checkins (chat_id, session_id, checkin_date) VALUES (?, ?, ?)""",
                          (chat_id, session_id, checkin_date.isoformat()))
                c.connection.commit()
                c.connection.close()
        except Exception as e:
            logger.error(f"Ошибка сохранения консультации: {e}")
        return response
    return None

# ============================================================
# РЕФЕРАЛЬНАЯ СИСТЕМА
# ============================================================

BOT_USERNAME = None  # кеш

def get_bot_username():
    global BOT_USERNAME
    if BOT_USERNAME:
        return BOT_USERNAME
    try:
        BOT_USERNAME = bot.get_me().username
    except Exception:
        BOT_USERNAME = "bot"
    return BOT_USERNAME

def generate_referral_code(chat_id):
    return f"REF{chat_id}{random.randint(1000,9999)}"[:10]

def get_referral_link(chat_id):
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        if row and row[0]:
            code = row[0]
        else:
            code = generate_referral_code(chat_id)
            c.execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
            conn.commit()
        conn.close()
    return f"https://t.me/{get_bot_username()}?start=ref_{code}"

def process_referral(referral_code, new_user_id):
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT chat_id FROM users WHERE referral_code = ?", (referral_code,))
        row = c.fetchone()
        if row:
            referrer_id = row[0]
            if referrer_id != new_user_id:
                c.execute("SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, new_user_id))
                if not c.fetchone():
                    c.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, new_user_id))
                    c.execute("UPDATE stats SET referrals_count = referrals_count + 1")
                    c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (referrer_id,))
                    conn.commit()
                    conn.close()
                    try:
                        bot.send_message(referrer_id, 
                            "🎉 По твоей ссылке пришёл новый пользователь!\n"
                            "Ты получил БЕСПЛАТНЫЙ тест из 20 вопросов в подарок.\n"
                            "Нажми «🎯 Пройти тест» и выбери платный тест — он будет бесплатным!")
                    except Exception:
                        pass
                    return True
        conn.close()
    return False

# ============================================================
# ОПЛАТА (Telegram Stars)
# ============================================================

def send_invoice(chat_id, product, amount):
    if product == "test_20":
        title = "🧠 Тест из 20 вопросов"
        desc = "Полный психологический разбор личности. Результат через 30 секунд."
    elif product == "coach":
        title = "🎯 Коуч-сеанс"
        desc = "25 вопросов + полный разбор + план действий + задания на неделю."
    else:
        return False
    
    try:
        bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=desc,
            provider_token="",
            currency="XTR",
            prices=[{"label": title, "amount": amount}],
            invoice_payload=product,
            need_name=False, need_phone_number=False, need_email=False, need_shipping_address=False,
            is_flexible=False
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки инвойса: {e}")
        return False

@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(query):
    try:
        bot.answer_pre_checkout_query(query.id, ok=True)
    except Exception as e:
        logger.error(f"Ошибка pre_checkout: {e}")
        bot.answer_pre_checkout_query(query.id, ok=False, error_message="Ошибка оплаты")

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    try:
        chat_id = message.chat.id
        payment = message.successful_payment
        product = payment.invoice_payload
        
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("""INSERT INTO payments (chat_id, amount, product, status) VALUES (?, ?, ?, ?)""",
                      (chat_id, payment.total_amount, product, "completed"))
            conn.commit()
            conn.close()
        
        if product == "test_20":
            # Выдаём доступ (1 кредит платного теста)
            with DB_LOCK:
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (chat_id,))
                conn.commit()
                conn.close()
            
            bot.send_message(
                chat_id, 
                "✅ Оплата прошла успешно!\n\n"
                "Ты можешь пройти полный тест из 20 вопросов.\n"
                "Нажми «🎯 Пройти тест» и выбери «💎 Платный» — он будет бесплатным для тебя.",
                reply_markup=get_main_menu(chat_id)
            )
            
        elif product == "coach":
            # Выдаём кредит коуч-сеанса (для обычных пользователей)
            with DB_LOCK:
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE users SET coach_credits = coach_credits + 1 WHERE chat_id = ?", (chat_id,))
                c.execute("UPDATE stats SET coach_count = coach_count + 1")
                conn.commit()
                conn.close()
            
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Начать коуч-сеанс", callback_data="start_coach_now"))
            bot.send_message(
                chat_id,
                "✅ Оплата прошла успешно!\n\n"
                "У тебя активирован коуч-сеанс.\n"
                "Нажми кнопку ниже, чтобы начать.",
                reply_markup=mk
            )
    except Exception as e:
        logger.error(f"Ошибка обработки оплаты: {e}")

# ============================================================
# МЕНЮ
# ============================================================

def get_main_menu(chat_id):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🚀 Старт', '🎯 Пройти тест')
    mk.add('🎫 Активировать промокод', '🎁 Активировать подарок')
    mk.add('📤 Поделиться', '❤️ О канале')
    if chat_id in ADMIN_IDS:
        mk.add('👑 Админ-панель')
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('📝 Новый пост', '🧠 Тест в канал')
    mk.add('🖼 Картинка в канал', '🎯 Сеанс коучинга')
    mk.add('🎁 Создать подарок', '🎫 Создать промокод')
    mk.add('📊 Статистика', '⏰ Расписание')
    mk.add('📋 Логи', '👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов) — 50 Stars')
    mk.add('🔙 Назад')
    return mk

def theme_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for theme in CHANNEL_THEMES:
        mk.add(theme.title())
    mk.add('🔙 Назад')
    return mk

def post_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    mk.add('📝 Пост без картинки')
    mk.add('🖼 Пост с картинкой')
    mk.add('🖼 Только картинка')
    mk.add('🔙 Назад')
    return mk

def session_diagnostic_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('😔 Подавленность', '😰 Тревога')
    mk.add('😡 Раздражение', '😌 Спокойствие')
    mk.add('😊 Радость', '❌ Отмена')
    return mk

# ============================================================
# СЕССИИ
# ============================================================

sessions = {}
consultations = {}

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("""INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name, referral_code) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (chat_id, username, first_name, last_name, generate_referral_code(chat_id)))
            conn.commit()
            c.execute("UPDATE stats SET users_count = (SELECT COUNT(*) FROM users)")
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Ошибка save_user: {e}")

# ============================================================
# БЕЗОПАСНАЯ ОТПРАВКА С FALLBACK MARKDOWN
# ============================================================

def safe_send_message(chat_id, text, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
    except Exception:
        try:
            bot.send_message(chat_id, text)
        except Exception as e:
            logger.error(f"Ошибка safe_send: {e}")

def safe_send_photo(chat_id, photo, caption=None, **kwargs):
    try:
        cap = caption[:1024] if caption and len(caption) > 1024 else caption
        bot.send_photo(chat_id, photo, caption=cap, **kwargs)
    except Exception:
        try:
            bot.send_photo(chat_id, photo)
            if caption:
                bot.send_message(chat_id, caption)
        except Exception as e:
            logger.error(f"Ошибка safe_send_photo: {e}")

# ============================================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    try:
        chat_id = message.chat.id
        user = message.from_user
        save_user(chat_id, user.username, user.first_name, user.last_name)
        
        if ' ' in message.text:
            param = message.text.split(' ', 1)[1]
            if param.startswith('ref_'):
                process_referral(param.replace('ref_', ''), chat_id)
            elif param == 'test_daily':
                # Обработка диплинка теста из канала
                bot.send_message(chat_id, "🧠 Готов пройти тест дня?", reply_markup=get_main_menu(chat_id))
                return
        
        bot.send_message(chat_id, "🌟 Добро пожаловать в Жизнь+!", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    try:
        text = """🧠 ЖИЗНЬ+ — канал о том, что внутри.

Мы не даём ответы. Мы даём вопросы, которые меняют.

Здесь ты не найдёшь:
— мотивационных лозунгов
— «ты уникален, просто поверь»
— воды и пустых советов

Здесь ты найдёшь:
— честные мысли без прикрас
— посты, которые застревают в голове
— тесты, которые вскрывают то, что ты прятал

Подписывайся. Испытай на прочность свою честность.

@zhizn_plus"""
        
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Перейти в канал", url="https://t.me/zhizn_plus"))
        bot.send_message(message.chat.id, text, reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '📤 Поделиться')
def share_result(message):
    try:
        chat_id = message.chat.id
        referral_link = get_referral_link(chat_id)
        text = f"""🧠 Я прохожу тесты в боте Жизнь+ и узнаю о себе новое.

Присоединяйся — это честно, глубоко и без пафоса.

🎯 Пройти тест: {referral_link}

#жизньплюс #психология #саморазвитие"""
        bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    try:
        chat_id = message.chat.id
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
            row = c.fetchone()
            conn.close()
        
        if row and row[0] > 0:
            mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            mk.add('🧠 Бесплатный (10 вопросов)')
            mk.add('💎 Платный (20 вопросов) — БЕСПЛАТНО (бонус)')
            mk.add('🔙 Назад')
            bot.send_message(chat_id, "🎯 У тебя есть бонусный тест!", reply_markup=mk)
        else:
            bot.send_message(chat_id, "🎯 Выбери тест:", reply_markup=test_type_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🔙 Назад')
def back_to_main(message):
    bot.send_message(message.chat.id, "🏠 Главное меню", reply_markup=get_main_menu(message.chat.id))

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный (10 вопросов)')
def free_test(message):
    show_topics(message, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов) — 50 Stars')
def paid_test(message):
    chat_id = message.chat.id
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        conn.close()
    
    if row and row[0] > 0:
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
            conn.commit()
            conn.close()
        show_topics(message, 'paid', 20)
    else:
        send_invoice(chat_id, "test_20", PRICE_TEST_20)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов) — БЕСПЛАТНО (бонус)')
def paid_test_bonus(message):
    chat_id = message.chat.id
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        conn.close()
    
    if row and row[0] > 0:
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
            conn.commit()
            conn.close()
        show_topics(message, 'paid', 20)
    else:
        bot.send_message(chat_id, "❌ У тебя нет бонусных тестов.", reply_markup=test_type_menu())

def show_topics(message, test_type, count):
    try:
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for topic in CHANNEL_THEMES:
            mk.add(telebot.types.InlineKeyboardButton(topic.title(), callback_data=f"{test_type}_{topic}_{count}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
        bot.send_message(message.chat.id, f"🔮 Выбери тему:\n\n{count} вопросов", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free_', 'paid_')))
def topic_callback(c):
    try:
        c.answer()  # отвечаем сразу, пока идёт генерация
        test_type, topic, count = c.data.split('_', 2)
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        # Сначала обновляем UI
        try:
            bot.edit_message_text("⏳ Генерация теста...\n⏱ Ожидание до 40 сек", chat_id, c.message.message_id)
        except Exception:
            pass
        
        # Генерируем в отдельном потоке, чтобы не блокировать
        def _generate():
            questions = generate_test_questions(topic, count)
            if not questions:
                try:
                    bot.send_message(chat_id, "❌ AI не ответил. Попробуй позже.")
                except Exception:
                    pass
                return
            
            sessions[chat_id] = {
                'topic': topic,
                'questions': questions,
                'answers': [],
                'q': 0,
                'scores': [],
                'is_paid': is_paid
            }
            try:
                bot.delete_message(chat_id, c.message.message_id)
            except Exception:
                pass
            send_question(chat_id)
        
        threading.Thread(target=_generate, daemon=True).start()
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        try:
            c.answer()
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, "❌ Отменено", reply_markup=get_main_menu(c.message.chat.id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    c.answer()

def send_question(chat_id):
    try:
        s = sessions.get(chat_id)
        if not s:
            bot.send_message(chat_id, "❌ Сессия не найдена.")
            return
        if s['q'] >= len(s['questions']):
            finish_test(chat_id)
            return
        q = s['questions'][s['q']]
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for opt, txt in q['options'].items():
            mk.add(f"{opt}) {txt}")
        mk.add('⏹ Прервать тест')
        bot.send_message(chat_id, f"🔮 Вопрос {s['q']+1}/{len(s['questions'])}\n\n{q['question']}", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    try:
        chat_id = message.chat.id
        if chat_id in sessions:
            del sessions[chat_id]
        bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text and m.text[0].upper() in 'ABCD')
def handle_answer(message):
    try:
        chat_id = message.chat.id
        s = sessions.get(chat_id)
        if not s or s['q'] >= len(s['questions']):
            return
        letter = message.text[0].upper()
        q = s['questions'][s['q']]
        s['answers'].append(letter)
        s['scores'].append(q['scores'].get(letter, 0))
        s['q'] += 1
        send_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def finish_test(chat_id):
    try:
        s = sessions.get(chat_id)
        if not s:
            return
        score = sum(s['scores'])
        total = len(s['questions']) * 3
        answers = ', '.join(s['answers'])
        is_paid = s.get('is_paid', False)
        
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            if is_paid:
                c.execute("UPDATE stats SET paid_test_count = paid_test_count + 1")
            else:
                c.execute("UPDATE stats SET free_count = free_count + 1")
            conn.commit()
            conn.close()
        
        bot.send_message(chat_id, f"📊 Тест завершен!\nРезультат: {score} из {total}\n⏳ Анализирую...\n⏱ Ожидание до 40 сек")
        analysis = generate_analysis(s['topic'], answers, score, total, is_paid)
        
        if analysis:
            mk = telebot.types.InlineKeyboardMarkup()
            if is_paid:
                mk.add(telebot.types.InlineKeyboardButton("🎯 Коуч-сеанс за 100 Stars", callback_data="buy_coach"))
            safe_send_message(chat_id, f"🔍 АНАЛИЗ\n\n{analysis}", reply_markup=mk, parse_mode='Markdown')
            bot.send_message(chat_id, "Готово!", reply_markup=get_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ AI не ответил. Попробуй позже.", reply_markup=get_main_menu(chat_id))
        if chat_id in sessions:
            del sessions[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data == 'buy_coach')
def buy_coach(c):
    try:
        send_invoice(c.message.chat.id, "coach", PRICE_COACH)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    c.answer()

# ============================================================
# КОУЧ-СЕАНС (ОТКРЫТ ДЛЯ ВСЕХ, КТО ОПЛАТИЛ)
# ============================================================

def has_coach_credit(chat_id):
    """Проверяет, есть ли у пользователя доступ к коуч-сеансу (оплата/подарок/админ)."""
    if chat_id in ADMIN_IDS:
        return True
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT coach_credits FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        conn.close()
    return (row and row[0] and row[0] > 0)

def consume_coach_credit(chat_id):
    if chat_id in ADMIN_IDS:
        return True
    with DB_LOCK:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT coach_credits FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        if row and row[0] and row[0] > 0:
            c.execute("UPDATE users SET coach_credits = coach_credits - 1 WHERE chat_id = ?", (chat_id,))
            conn.commit()
            conn.close()
            return True
        conn.close()
    return False

@bot.callback_query_handler(func=lambda c: c.data == 'start_coach_now')
def start_coach_from_payment(c):
    chat_id = c.message.chat.id
    c.answer()
    if not has_coach_credit(chat_id):
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    _start_consultation_flow(chat_id)

def _start_consultation_flow(chat_id):
    """Общий вход в коуч-сеанс."""
    bot.send_message(
        chat_id,
        "🧠 ПЕРЕД СЕАНСОМ\n\n"
        "Как ты себя чувствуешь прямо сейчас?\n"
        "Это поможет мне подобрать правильные вопросы.",
        reply_markup=session_diagnostic_menu()
    )

@bot.message_handler(func=lambda m: m.text == '🎯 Сеанс коучинга')
def start_consultation(message):
    chat_id = message.chat.id
    # Админ: свободный доступ. Обычный: списываем кредит или просим оплатить.
    if chat_id not in ADMIN_IDS:
        if not has_coach_credit(chat_id):
            send_invoice(chat_id, "coach", PRICE_COACH)
            return
    _start_consultation_flow(chat_id)

@bot.message_handler(func=lambda m: m.text in ['😔 Подавленность', '😰 Тревога', '😡 Раздражение', '😌 Спокойствие', '😊 Радость'])
def handle_diagnostic(message):
    try:
        chat_id = message.chat.id
        # Защита: только если реально инициирован сеанс (есть кредит или админ)
        if not has_coach_credit(chat_id):
            return
        
        diagnostic = message.text
        consultations[chat_id] = {"diagnostic": diagnostic}
        
        warning = f"""⚠️ ВНИМАНИЕ

Ты выбрал: {diagnostic}

Эти вопросы могут задеть глубокие чувства.
Если станет тяжело — нажми «⏹ Завершить сеанс».

Начать сеанс?"""
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        mk.add('✅ Начать', '❌ Отмена')
        bot.send_message(chat_id, warning, reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '❌ Отмена' and m.chat.id in consultations)
def cancel_consultation(message):
    try:
        chat_id = message.chat.id
        if chat_id in consultations:
            del consultations[chat_id]
        bot.send_message(chat_id, "❌ Сеанс отменён.", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '✅ Начать' and m.chat.id in consultations)
def confirm_consultation(message):
    try:
        chat_id = message.chat.id
        
        # Списываем кредит (если не админ)
        if not consume_coach_credit(chat_id):
            bot.send_message(chat_id, "❌ Нет доступных сеансов.", reply_markup=get_main_menu(chat_id))
            if chat_id in consultations:
                del consultations[chat_id]
            return
        
        diagnostic = consultations.get(chat_id, {}).get("diagnostic", "неизвестно")
        
        bot.send_message(
            chat_id,
            f"🎯 Начинаем сеанс.\nТвоё состояние: {diagnostic}\n\n"
            "Генерирую вопросы специально для тебя...\n⏱ Ожидание до 40 сек",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        
        def _gen():
            questions = generate_consultation_questions()
            if not questions:
                try:
                    bot.send_message(chat_id, "❌ Не удалось сгенерировать вопросы.", reply_markup=get_main_menu(chat_id))
                except Exception:
                    pass
                if chat_id in consultations:
                    del consultations[chat_id]
                return
            
            with DB_LOCK:
                conn = get_conn()
                c = conn.cursor()
                c.execute("""INSERT INTO consultation_sessions (chat_id, questions, current_q, is_active, is_paid) VALUES (?, ?, ?, ?, ?)""",
                          (chat_id, json.dumps(questions), 0, 1, 1))
                conn.commit()
                session_id = c.lastrowid
                conn.close()
            
            consultations[chat_id] = {
                "session_id": session_id,
                "questions": questions,
                "answers": [],
                "q": 0,
                "diagnostic": diagnostic
            }
            send_consultation_question(chat_id)
        
        threading.Thread(target=_gen, daemon=True).start()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def send_consultation_question(chat_id):
    try:
        s = consultations.get(chat_id)
        if not s:
            bot.send_message(chat_id, "❌ Сессия не найдена.", reply_markup=get_main_menu(chat_id))
            return
        if s['q'] >= len(s['questions']):
            finish_consultation(chat_id)
            return
        q = s['questions'][s['q']]
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        mk.add('⏹ Завершить сеанс')
        bot.send_message(chat_id, f"🔮 ВОПРОС {s['q']+1}/{len(s['questions'])}\n\n{q['question']}", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '⏹ Завершить сеанс')
def finish_consultation_manual(message):
    try:
        chat_id = message.chat.id
        if chat_id in consultations:
            finish_consultation(chat_id)
        else:
            bot.send_message(chat_id, "❌ Нет активного сеанса.", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def finish_consultation(chat_id):
    try:
        s = consultations.get(chat_id)
        if not s:
            bot.send_message(chat_id, "❌ Сессия не найдена.", reply_markup=get_main_menu(chat_id))
            return
        
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE consultation_sessions SET is_active = 0 WHERE id = ?", (s['session_id'],))
            conn.commit()
            conn.close()
        
        if len(s['answers']) == 0:
            bot.send_message(chat_id, "❌ Сеанс прерван.", reply_markup=get_main_menu(chat_id))
            if chat_id in consultations:
                del consultations[chat_id]
            return
        
        bot.send_message(chat_id, "📊 Обрабатываю ответы...\n⏱ Это займёт 1–2 минуты.", reply_markup=get_main_menu(chat_id))
        
        def background_analysis():
            try:
                answers_text = "\n".join([f"{i+1}. {a}" for i, a in enumerate(s['answers'])])
                analysis = generate_consultation_analysis(answers_text, chat_id, s['session_id'])
                
                tasks = [
                    "🟢 Задание 1: Напиши 3 вещи, за которые ты благодарен сегодня",
                    "🟢 Задание 2: Скажи себе в зеркале: 'Я справлюсь'",
                    "🟢 Задание 3: 5 минут тишины без телефона"
                ]
                tasks_text = "\n\n📋 ТВОИ ЗАДАНИЯ НА СЕГОДНЯ:\n" + "\n".join(tasks)
                
                if analysis:
                    safe_send_message(chat_id, f"🔮 ПОЛНЫЙ РАЗБОР\n\n{analysis}\n\n{tasks_text}", parse_mode='Markdown')
                else:
                    safe_send_message(chat_id, f"❌ Не удалось сгенерировать анализ.\n\n{tasks_text}")
            except Exception as e:
                logger.error(f"Ошибка фонового анализа: {e}")
                bot.send_message(chat_id, "❌ Ошибка при анализе.", reply_markup=get_main_menu(chat_id))
        
        threading.Thread(target=background_analysis, daemon=True).start()
        
        if chat_id in consultations:
            del consultations[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# Обработчик ответов в коуч-сеансе (любое сообщение, пока активна сессия)
@bot.message_handler(func=lambda m: m.chat.id in consultations, content_types=['text'])
def handle_consultation_answer(message):
    try:
        chat_id = message.chat.id
        if chat_id not in consultations:
            return
        s = consultations[chat_id]
        # Игнорируем спец-команды
        if message.text in ['✅ Начать', '❌ Отмена', '⏹ Завершить сеанс']:
            return
        if s['q'] >= len(s['questions']):
            return
        s['answers'].append(message.text)
        s['q'] += 1
        with DB_LOCK:
            conn = get_conn()
            c = conn.cursor()
            c.execute("UPDATE consultation_sessions SET current_q = ?, answers = ? WHERE id = ?",
                      (s['q'], json.dumps(s['answers']), s['session_id']))
            conn.commit()
            conn.close()
        send_consultation_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================================
# АДМИН-ПАНЕЛЬ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

# -------------------- НОВЫЙ ПОСТ --------------------

@bot.message_handler(func=lambda m: m.text == '📝 Новый пост')
def new_post_menu(message):
    if message.chat.id not in ADMIN_IDS: return
    bot.send_message(message.chat.id, "📝 Что отправляем в канал?", reply_markup=post_type_menu())

@bot.message_handler(func=lambda m: m.text == '📝 Пост без картинки')
def post_without_image(message):
    if message.chat.id not in ADMIN_IDS: return
    sessions[message.chat.id] = {"action": "post_without_image"}
    bot.send_message(message.chat.id, "📝 Выбери тему для поста:", reply_markup=theme_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def post_with_image(message):
    if message.chat.id not in ADMIN_IDS: return
    sessions[message.chat.id] = {"action": "post_with_image"}
    bot.send_message(message.chat.id, "📝 Выбери тему для поста с супер-картинкой:", reply_markup=theme_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Только картинка')
def only_image(message):
    if message.chat.id not in ADMIN_IDS: return
    bot.send_message(message.chat.id, "📝 Введи описание для супер-картинки:")
    bot.register_next_step_handler(message, process_only_image)

def process_only_image(message):
    try:
        chat_id = message.chat.id
        prompt = message.text
        bot.send_message(chat_id, "🖼 Генерация супер-картинки...\n⏱ Ожидание до 40 сек")
        image_path = generate_image(prompt)
        if image_path:
            with open(image_path, 'rb') as photo:
                safe_send_photo(CHANNEL_ID, photo, caption=f"🖼 {prompt[:900]}")
            os.remove(image_path)
            with DB_LOCK:
                conn = get_conn(); c = conn.cursor()
                c.execute("UPDATE stats SET images_generated = images_generated + 1"); conn.commit(); conn.close()
            bot.send_message(chat_id, "✅ Супер-картинка отправлена в канал!", reply_markup=admin_menu())
        else:
            bot.send_message(chat_id, "❌ Не удалось создать картинку.", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- СТАТИСТИКА --------------------

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id not in ADMIN_IDS: return
    try:
        with DB_LOCK:
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT free_count, paid_test_count, coach_count, promo_used, users_count, posts_count, tests_created, images_generated, consultations_count, referrals_count, gifts_used FROM stats")
            stats_row = c.fetchone()
            c.execute("SELECT COUNT(*) FROM users"); users_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM gifts"); gifts_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM checkins WHERE is_done = 0"); pending_checkins = c.fetchone()[0]
            conn.close()
        
        if not stats_row:
            bot.send_message(message.chat.id, "❌ Статистика пуста.", reply_markup=admin_menu())
            return
        
        # Правильные индексы:
        # 0:free 1:paid 2:coach 3:promo 4:users 5:posts 6:tests_created 7:images 8:consult 9:referrals 10:gifts
        stats_text = f"""📊 СТАТИСТИКА

👥 Пользователей: {users_count}
🧠 Бесплатных тестов: {stats_row[0]}
💎 Платных тестов: {stats_row[1]}
🎯 Коуч-сеансов: {stats_row[2]}
🎫 Промокодов использовано: {stats_row[3]}
📤 Постов: {stats_row[5]}
🧠 Тестов создано: {stats_row[6]}
🖼 Супер-картинок: {stats_row[7]}
🎯 Консультаций: {stats_row[8]}
👥 Рефералов: {stats_row[9]}
🎁 Подарков использовано: {stats_row[10]}
🎁 Подарков создано: {gifts_count}
⏳ Чек-инов: {pending_checkins}"""
        bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- РАСПИСАНИЕ --------------------

@bot.message_handler(func=lambda m: m.text == '⏰ Расписание')
def show_schedule(message):
    if message.chat.id not in ADMIN_IDS: return
    schedule_text = """⏰ РАСПИСАНИЕ (Asia/Novokuznetsk)

📝 ПОСТЫ:
• 10:00 — утренний
• 16:00 — дневной
• 20:00 — вечерний

🧠 ТЕСТ:
• 13:00 — тест дня (10 вопросов)

🧠 ЧЕК-ИН:
• Через 3 дня после сеанса

Темы из 7 постоянных."""
    bot.send_message(message.chat.id, schedule_text, reply_markup=admin_menu())

# -------------------- ЛОГИ --------------------

@bot.message_handler(func=lambda m: m.text == '📋 Логи')
def show_logs(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS: return
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-50:] if len(lines) > 50 else lines
                logs = ''.join(last_lines)
                if len(logs) > 3800:
                    logs = logs[-3800:]
                bot.send_message(chat_id, f"📋 ПОСЛЕДНИЕ 50 СТРОК ЛОГОВ:\n\n```\n{logs}\n```", parse_mode='Markdown')
        except Exception as e:
            bot.send_message(chat_id, f"❌ Ошибка: {e}")
    else:
        bot.send_message(chat_id, "❌ Файл логов не найден.")

# -------------------- КАРТИНКИ В КАНАЛ --------------------

@bot.message_handler(func=lambda m: m.text == '🖼 Картинка в канал')
def image_to_channel(message):
    if message.chat.id not in ADMIN_IDS: return
    bot.send_message(message.chat.id, "📝 Введи описание для супер-картинки:")
    bot.register_next_step_handler(message, process_image_only_standalone)

def process_image_only_standalone(message):
    try:
        chat_id = message.chat.id
        prompt = message.text
        bot.send_message(chat_id, "🖼 Генерация супер-картинки...\n⏱ Ожидание до 40 сек")
        image_path = generate_image(prompt)
        if image_path:
            with open(image_path, 'rb') as photo:
                safe_send_photo(CHANNEL_ID, photo, caption=f"🖼 {prompt[:900]}")
            os.remove(image_path)
            with DB_LOCK:
                conn = get_conn(); c = conn.cursor()
                c.execute("UPDATE stats SET images_generated = images_generated + 1"); conn.commit(); conn.close()
            bot.send_message(chat_id, "✅ Супер-картинка отправлена в канал!", reply_markup=admin_menu())
        else:
            bot.send_message(chat_id, "❌ Не удалось создать картинку.", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- ТЕСТЫ В КАНАЛ --------------------

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def test_to_channel_start(message):
    if message.chat.id not in ADMIN_IDS: return
    sessions[message.chat.id] = {"action": "test_to_channel"}
    bot.send_message(message.chat.id, "🧠 Выбери тему для теста:", reply_markup=theme_menu())

# -------------------- ПРОМОКОДЫ --------------------

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id not in ADMIN_IDS: return
    bot.send_message(message.chat.id, "🎫 Введите код (латиница, 3+ символов):")
    bot.register_next_step_handler(message, process_create_promo)

def process_create_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        if code == "ОТМЕНА" or code == "CANCEL":
            bot.send_message(chat_id, "❌ Отменено")
            return
        if not code or len(code) < 3:
            bot.send_message(chat_id, "❌ Минимум 3 символа", reply_markup=admin_menu())
            return
        try:
            with DB_LOCK:
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO promocodes (code, created_by, created_at) VALUES (?, ?, ?)",
                          (code, chat_id, datetime.now().isoformat()))
                conn.commit(); conn.close()
            bot.send_message(chat_id, f"✅ Промокод создан!\n\n📌 Код: `{code}`\nДаёт 1 бесплатный тест из 20 вопросов.", parse_mode='Markdown', reply_markup=admin_menu())
        except sqlite3.IntegrityError:
            bot.send_message(chat_id, "❌ Уже существует", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(message.chat.id, "🎫 Введите промокод:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        with DB_LOCK:
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
            row = c.fetchone()
            if not row:
                conn.close()
                bot.send_message(chat_id, "❌ Неверный код", reply_markup=get_main_menu(chat_id)); return
            promo_id, used_by = row
            if used_by != 0:
                conn.close()
                bot.send_message(chat_id, "❌ Уже использован", reply_markup=get_main_menu(chat_id)); return
            c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
                      (chat_id, datetime.now().isoformat(), promo_id))
            c.execute("UPDATE stats SET promo_used = promo_used + 1")
            c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (chat_id,))
            conn.commit(); conn.close()
        bot.send_message(chat_id, "🎉 Промокод активирован! Ты получил 1 бесплатный тест из 20 вопросов. Нажми «🎯 Пройти тест» и выбери платный.", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- ПОДАРКИ --------------------

@bot.message_handler(func=lambda m: m.text == '🎁 Создать подарок')
def create_gift(message):
    if message.chat.id not in ADMIN_IDS: return
    bot.send_message(message.chat.id, "🎁 Введите количество сеансов (1-10):")
    bot.register_next_step_handler(message, process_gift_max_uses)

def process_gift_max_uses(message):
    try:
        chat_id = message.chat.id
        try:
            max_uses = int(message.text.strip())
            if max_uses < 1 or max_uses > 10: raise ValueError
        except Exception:
            bot.send_message(chat_id, "❌ Введите число от 1 до 10.", reply_markup=admin_menu()); return
        sessions.setdefault(chat_id, {})['gift_max_uses'] = max_uses
        bot.send_message(chat_id, "📅 Введите срок действия (дней):")
        bot.register_next_step_handler(message, process_gift_expires)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_gift_expires(message):
    try:
        chat_id = message.chat.id
        try:
            days = int(message.text.strip())
            if days < 1 or days > 365: raise ValueError
        except Exception:
            bot.send_message(chat_id, "❌ Введите число от 1 до 365.", reply_markup=admin_menu()); return
        max_uses = sessions.get(chat_id, {}).get('gift_max_uses', 1)
        code = "GIFT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()
        with DB_LOCK:
            conn = get_conn(); c = conn.cursor()
            c.execute("""INSERT INTO gifts (code, created_by, max_uses, expires_at) VALUES (?, ?, ?, ?)""",
                      (code, chat_id, max_uses, expires_at))
            conn.commit(); conn.close()
        bot.send_message(
            chat_id,
            f"✅ ПОДАРОК СОЗДАН!\n\n🎁 Код: `{code}`\n📊 Сеансов: {max_uses}\n📅 Действует до: {expires_at[:10]}\nДаёт бесплатный коуч-сеанс.",
            parse_mode='Markdown', reply_markup=admin_menu()
        )
        if chat_id in sessions: del sessions[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎁 Активировать подарок')
def activate_gift_start(message):
    bot.send_message(message.chat.id, "🎁 Введите код подарка:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_gift_activation)

def process_gift_activation(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        with DB_LOCK:
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT id, max_uses, used_count, expires_at FROM gifts WHERE code = ?", (code,))
            row = c.fetchone()
            if not row:
                conn.close()
                bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id)); return
            gift_id, max_uses, used_count, expires_at = row
            if expires_at and datetime.now().isoformat() > expires_at:
                conn.close()
                bot.send_message(chat_id, "❌ Срок истёк.", reply_markup=get_main_menu(chat_id)); return
            if used_count >= max_uses:
                conn.close()
                bot.send_message(chat_id, "❌ Код использован.", reply_markup=get_main_menu(chat_id)); return
            c.execute("UPDATE gifts SET used_count = used_count + 1 WHERE id = ?", (gift_id,))
            c.execute("UPDATE stats SET gifts_used = gifts_used + 1")
            # Добавляем кредит коуч-сеанса пользователю
            c.execute("UPDATE users SET coach_credits = COALESCE(coach_credits, 0) + 1 WHERE chat_id = ?", (chat_id,))
            conn.commit(); conn.close()
        
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🎯 Начать коуч-сеанс", callback_data="start_coach_now"))
        bot.send_message(chat_id, "🎉 ПОДАРОК АКТИВИРОВАН!\n\nТы получил бесплатный коуч-сеанс.", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, "❌ Ошибка при активации.", reply_markup=get_main_menu(chat_id))

# ============================================================
# ОБЩИЙ ОБРАБОТЧИК ДЛЯ ВЫБОРА ТЕМЫ (админ)
# ============================================================

@bot.message_handler(func=lambda m: m.text in [t.title() for t in CHANNEL_THEMES] and m.chat.id in ADMIN_IDS)
def handle_theme_selection(message):
    try:
        chat_id = message.chat.id
        theme = message.text.lower()
        action = sessions.get(chat_id, {}).get("action")
        
        if action == "test_to_channel":
            bot.send_message(chat_id, f"⏳ Генерация теста на тему '{theme}'...")
            def _gen():
                questions = generate_test_questions(theme, 10)
                if not questions:
                    bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=admin_menu()); return
                try:
                    with DB_LOCK:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("""INSERT INTO daily_tests (topic, questions, created_at, is_paid) VALUES (?, ?, ?, ?)""",
                                  (theme, json.dumps(questions), datetime.now().isoformat(), 0))
                        conn.commit(); conn.close()
                except Exception:
                    pass
                
                test_text = f"🔮 ТЕСТ: «{theme.title()}» (10 вопросов)\n\n"
                for i, q in enumerate(questions[:5], 1):
                    test_text += f"{i}. {q['question']}\n"
                    for opt, txt in q['options'].items():
                        test_text += f"   {opt}) {txt}\n"
                    test_text += "\n"
                test_text += f"... и ещё {len(questions)-5} вопросов\n\n"
                test_text += f"🎯 Пройди полный тест в боте: @{get_bot_username()}?start=test_daily"
                
                try:
                    bot.send_message(CHANNEL_ID, test_text)
                    bot.send_message(chat_id, "✅ Тест отправлен в канал!", reply_markup=admin_menu())
                except Exception as e:
                    bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
            threading.Thread(target=_gen, daemon=True).start()
            sessions[chat_id] = {}
            
        elif action == "post_without_image":
            bot.send_message(chat_id, f"⏳ Генерация поста на тему '{theme}'...")
            def _gen():
                post = generate_post(theme)
                if not post:
                    bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=admin_menu()); return
                try:
                    with DB_LOCK:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
                        c.execute("UPDATE stats SET posts_count = posts_count + 1"); conn.commit(); conn.close()
                except Exception:
                    pass
                bot.send_message(CHANNEL_ID, post)
                bot.send_message(chat_id, "✅ Пост отправлен в канал!", reply_markup=admin_menu())
            threading.Thread(target=_gen, daemon=True).start()
            sessions[chat_id] = {}
            
        elif action == "post_with_image":
            bot.send_message(chat_id, f"⏳ Генерация поста и супер-картинки на тему '{theme}'...")
            def _gen():
                post = generate_post(theme)
                if not post:
                    bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=admin_menu()); return
                image_path = generate_post_image(theme)
                try:
                    with DB_LOCK:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", (post, theme, image_path if image_path else ""))
                        c.execute("UPDATE stats SET posts_count = posts_count + 1")
                        if image_path: c.execute("UPDATE stats SET images_generated = images_generated + 1")
                        conn.commit(); conn.close()
                except Exception:
                    pass
                
                try:
                    if image_path:
                        with open(image_path, 'rb') as photo:
                            safe_send_photo(CHANNEL_ID, photo, caption=post)
                        os.remove(image_path)
                    else:
                        bot.send_message(CHANNEL_ID, post)
                    bot.send_message(chat_id, "✅ Пост с супер-картинкой отправлен в канал!", reply_markup=admin_menu())
                except Exception as e:
                    bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
            threading.Thread(target=_gen, daemon=True).start()
            sessions[chat_id] = {}
        else:
            bot.send_message(chat_id, "❌ Сначала выбери действие в админке", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================================
# ПЛАНИРОВЩИК (С ДЕДУПЛИКАЦИЕЙ)
# ============================================================

SCHEDULER_STATE = {"last_post_hour": None, "last_test_hour": None, "last_checkin_minute": None}

def scheduler_loop():
    while True:
        try:
            now = datetime.now(TIMEZONE)
            now_key = now.strftime('%Y-%m-%d')
            
            # Посты: 10, 16, 20 — один раз в час
            if now.hour in (10, 16, 20) and now.minute < 5 and SCHEDULER_STATE.get("last_post_hour") != (now_key, now.hour):
                SCHEDULER_STATE["last_post_hour"] = (now_key, now.hour)
                try:
                    with DB_LOCK:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 10")
                        used = [row[0] for row in c.fetchall()]
                        available = [t for t in CHANNEL_THEMES if t not in used]
                        if not available:
                            c.execute("DELETE FROM used_topics"); conn.commit()
                            available = CHANNEL_THEMES
                        topic = random.choice(available)
                        c.execute("INSERT OR IGNORE INTO used_topics (topic) VALUES (?)", (topic,))
                        conn.commit(); conn.close()
                    
                    def _gen():
                        post = generate_post(topic)
                        if post:
                            img = generate_post_image(topic)
                            try:
                                if img:
                                    with open(img, 'rb') as photo:
                                        safe_send_photo(CHANNEL_ID, photo, caption=post)
                                    os.remove(img)
                                else:
                                    bot.send_message(CHANNEL_ID, post)
                                with DB_LOCK:
                                    conn = get_conn(); c = conn.cursor()
                                    c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, topic))
                                    c.execute("UPDATE stats SET posts_count = posts_count + 1"); conn.commit(); conn.close()
                            except Exception as e:
                                logger.error(f"Ошибка пост: {e}")
                    threading.Thread(target=_gen, daemon=True).start()
                except Exception as e:
                    logger.error(f"Ошибка планировщика постов: {e}")
            
            # Тест: 13:00
            if now.hour == 13 and now.minute < 5 and SCHEDULER_STATE.get("last_test_hour") != (now_key, 13):
                SCHEDULER_STATE["last_test_hour"] = (now_key, 13)
                topic = random.choice(CHANNEL_THEMES)
                def _gen():
                    questions = generate_test_questions(topic, 10)
                    if questions:
                        test_text = f"🔮 ТЕСТ ДНЯ: «{topic.title()}» (10 вопросов)\n\n"
                        for i, q in enumerate(questions[:3], 1):
                            test_text += f"{i}. {q['question']}\n"
                        test_text += f"\n🎯 Пройти полный тест в боте: @{get_bot_username()}?start=test_daily"
                        try:
                            bot.send_message(CHANNEL_ID, test_text)
                        except Exception as e:
                            logger.error(f"Ошибка отправки теста: {e}")
                threading.Thread(target=_gen, daemon=True).start()
            
            # Чек-ины: раз в 10 минут
            minute_key = (now_key, now.hour, now.minute // 10)
            if SCHEDULER_STATE.get("last_checkin_minute") != minute_key:
                SCHEDULER_STATE["last_checkin_minute"] = minute_key
                try:
                    now_naive = datetime.now()
                    with DB_LOCK:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("""SELECT chat_id, session_id FROM checkins 
                                     WHERE is_done = 0 AND checkin_date <= ?""", 
                                  (now_naive.isoformat(),))
                        checkins = c.fetchall()
                        for chat_id, session_id in checkins:
                            c.execute("UPDATE checkins SET is_done = 1 WHERE chat_id = ? AND session_id = ?", (chat_id, session_id))
                        conn.commit(); conn.close()
                    for chat_id, _ in checkins:
                        try:
                            bot.send_message(
                                chat_id,
                                "🧠 Привет! Прошло 3 дня после нашего сеанса.\n\n"
                                "Как ты себя чувствуешь?\n"
                                "Что изменилось?\n"
                                "Напиши мне — я здесь."
                            )
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Ошибка чек-инов: {e}")
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
            time.sleep(60)

# ============================================================
# FLASK + ЗАПУСК (нерекурсивный)
# ============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"✅ {BOT_NAME} v{BOT_VERSION}"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

def run_flask():
    try:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Ошибка Flask: {e}")

def run_bot():
    logger.info(f"🤖 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")
    while True:
        try:
            super_kill_409()
            time.sleep(2)
            bot.remove_webhook()
            logger.info("✅ Вебхук удален")
            bot.polling(
                none_stop=True, 
                interval=1, 
                timeout=30, 
                allowed_updates=['message', 'callback_query', 'pre_checkout_query']
            )
        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}")
            if "409" in str(e):
                super_kill_409()
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("✅ Веб-сервер запущен")
    threading.Thread(target=scheduler_loop, daemon=True).start()
    logger.info("✅ Планировщик запущен")
    run_bot()
