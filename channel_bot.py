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
# НАСТРОЙКИ (ВЫНЕСЕНЫ В ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ)
# ============================================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
ADMIN_IDS = [8746212340]

AGNES_API_KEY = "sk-8nqC897jST7vx1brGMUTNLRsVGPXgP7Bcpuwmbl5quaCLN5c"
AGNES_API_URL = "https://apihub.agnes-ai.com/v1/images/generations"

TIMEZONE = ZoneInfo("Asia/Novokuznetsk")

BOT_VERSION = "14.0.0"
BOT_NAME = "Жизнь+ Про (FIXED)"

DB_PATH = 'channel.db'
LOG_PATH = 'bot_logs.txt'
DB_LOCK = threading.RLock()  # Для потокобезопасности SQLite

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
# СОЗДАНИЕ БОТА (ПЕРЕНЕСЕНО ВВЕРХ)
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================================
# AI-ПРОВАЙДЕРЫ
# ============================================================

AI_PROVIDERS = [
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
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
# УБИЙЦА 409 (ОДИН РАЗ)
# ============================================================

def super_kill_409():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        requests.post(url, json={"drop_pending_updates": True}, timeout=10)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
        logger.info("🔥 409 УНИЧТОЖЕН")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

super_kill_409()
time.sleep(2)

# ============================================================
# ПОТОКОБЕЗОПАСНАЯ РАБОТА С БАЗОЙ
# ============================================================

def db_query(query, params=None, fetch=False):
    """Потокобезопасный запрос к БД"""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            if params:
                c.execute(query, params)
            else:
                c.execute(query)
            if fetch:
                result = c.fetchall()
            else:
                result = None
            conn.commit()
            return result
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")
            return None
        finally:
            conn.close()

def db_insert(query, params=None):
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            if params:
                c.execute(query, params)
            else:
                c.execute(query)
            conn.commit()
            return c.lastrowid
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")
            return None
        finally:
            conn.close()

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
                
                start = time.time()
                response = requests.post(
                    provider["url"],
                    headers=headers,
                    json=payload,
                    timeout=30,
                    verify=False
                )
                elapsed = time.time() - start
                logger.info(f"⏱ Ответ за {elapsed:.2f} сек")
                logger.info(f"📡 Статус: {response.status_code}")
                
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
# СУПЕР-КАРТИНКИ
# ============================================================

def generate_image(prompt, width=1024, height=768):
    try:
        logger.info("🖼 Генерация супер-картинки через Agnes AI...")
        
        full_prompt = f"""Hyper-realistic, cinematic photography. {prompt}
Subject: European, Caucasian, light skin, natural glow, warm smile, relaxed, positive energy, open body language.
Environment: Sunny, golden hour, warm sunlight, soft lens flare, lush green, peaceful, joyful.
Lighting: Soft golden backlight, warm skin tones, natural shadows.
Style: Photorealistic, high detail, natural texture, no airbrushing, magazine quality, warm amber tones.
Negative prompt: Asian, anime, cartoon, 3D render, plastic, blurry, stiff, cold, dark, sad.
Quality: 8K, masterpiece."""
        
        headers = {
            "Authorization": f"Bearer {AGNES_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "agnes-image-2.0-flash",
            "prompt": full_prompt,
            "size": f"{width}x{height}",
            "extra_body": {
                "response_format": "url"
            }
        }
        
        response = requests.post(
            AGNES_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
            verify=False
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
                    logger.warning("⚠️ Не удалось скачать картинку")
            else:
                logger.warning("⚠️ URL картинки не найден в ответе")
        else:
            logger.error(f"❌ Ошибка Agnes AI: {response.status_code}")
            logger.debug(f"📄 Текст: {response.text[:200]}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации картинки: {e}")
    
    logger.info("🔄 Переключаюсь на резервный генератор Pollinations...")
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
        else:
            logger.error(f"❌ Ошибка Pollinations: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return None

def generate_post_image(theme):
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational, masterpiece",
        f"beautiful landscape {theme}, sunrise, hope, positive energy, 4k",
        f"minimalist illustration {theme}, soft pastel, calm, self discovery, art"
    ]
    return generate_image(random.choice(prompts))

# ============================================================
# БАЗА ДАННЫХ (ИНИЦИАЛИЗАЦИЯ)
# ============================================================

def init_database():
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT, first_name TEXT, last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tests_passed INTEGER DEFAULT 0,
            consultations INTEGER DEFAULT 0,
            last_activity TIMESTAMP,
            referrer_id INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            bonus_tests INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER, referred_id INTEGER,
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
            chat_id INTEGER, questions TEXT, answers TEXT,
            current_q INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            is_paid INTEGER DEFAULT 0,
            is_analyzed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS consultation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER, session_id INTEGER,
            questions TEXT, answers TEXT, analysis TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER, amount INTEGER,
            product TEXT, status TEXT DEFAULT 'pending',
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
            content TEXT, topic TEXT, image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS daily_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT, questions TEXT,
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
            chat_id INTEGER, session_id INTEGER,
            checkin_date TIMESTAMP,
            is_done INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
        logger.info("✅ БАЗА ДАННЫХ ИНИЦИАЛИЗИРОВАНА")

init_database()

# ============================================================
# ГЕНЕРАТОРЫ КОНТЕНТА
# ============================================================

def generate_post(topic):
    system = f"Ты — автор канала о психологии. Напиши пост на тему '{topic}'. Минимум 600 символов. Без пафоса. Добавь вопрос в конце."
    user = f"Тема: {topic}."
    return ask_ai(system, user, 3000)

def generate_test_questions(topic, count=10):
    if count == 10:
        depth = "диагностика личности"
    else:
        depth = "полный психологический разбор"
    
    system = f"""ТЫ — КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ.

    Составь {count} глубоких, НО ПРОСТЫХ вопросов для {depth} на тему "{topic}".

    ВАЖНО: вопросы должны быть ПОНЯТНЫМИ и ПРОСТЫМИ по форме, но МОЩНЫМИ по смыслу.
    Используй НЛП-язык. БЕЗ сложных терминов.
    Верни ТОЛЬКО JSON.

    ФОРМАТ:
    [{{"question": "простой, но бьющий в точку вопрос?", "options": {{"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"}}, "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}}}]
    
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

    ВАЖНО:
    - Вопросы должны быть ПРОСТЫМИ по форме (понятны 12-летнему)
    - Но МОЩНЫМИ по смыслу (бьют в точку)
    - БЕЗ психологических терминов
    - Используй НЛП-техники

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
    except:
        return None

def generate_consultation_analysis(answers, chat_id, session_id):
    system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-КОУЧ.
    Проведи полный разбор личности.
    Структура: главная рана, как управляет, корень, 3 шага, заключение.
    Объем: 1500+ знаков."""
    
    user = f"Ответы:\n{answers}"
    response = ask_ai(system, user, 4000)
    if response:
        db_query("""INSERT INTO consultation_history (chat_id, session_id, questions, answers, analysis) VALUES (?, ?, ?, ?, ?)""",
                 (chat_id, session_id, "", answers, response))
        db_query("UPDATE stats SET consultations_count = consultations_count + 1")
        
        checkin_date = datetime.now(TIMEZONE) + timedelta(days=3)
        db_query("INSERT INTO checkins (chat_id, session_id, checkin_date) VALUES (?, ?, ?)",
                 (chat_id, session_id, checkin_date.isoformat()))
        
        return response
    return None

# ============================================================
# РЕФЕРАЛКА
# ============================================================

def generate_referral_code(chat_id):
    return f"REF{chat_id}{random.randint(1000,9999)}"[:10]

def get_referral_link(chat_id):
    result = db_query("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,), fetch=True)
    if result and result[0][0]:
        code = result[0][0]
    else:
        code = generate_referral_code(chat_id)
        db_query("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
    bot_info = bot.get_me()
    return f"https://t.me/{bot_info.username}?start=ref_{code}"

def process_referral(referral_code, new_user_id):
    result = db_query("SELECT chat_id FROM users WHERE referral_code = ?", (referral_code,), fetch=True)
    if result:
        referrer_id = result[0][0]
        if referrer_id != new_user_id:
            # Проверяем, не было ли уже реферала
            check = db_query("SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, new_user_id), fetch=True)
            if not check:
                db_query("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, new_user_id))
                db_query("UPDATE stats SET referrals_count = referrals_count + 1")
                db_query("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (referrer_id,))
                try:
                    bot.send_message(referrer_id, "🎉 По твоей ссылке пришёл новый пользователь! Ты получил БЕСПЛАТНЫЙ тест из 20 вопросов.")
                except:
                    pass
                return True
    return False

# ============================================================
# ОПЛАТА ЧЕРЕЗ TELEGRAM STARS
# ============================================================

def send_invoice(chat_id, product, amount):
    if product == "test_20":
        title, desc = "🧠 Тест из 20 вопросов", "Полный психологический разбор личности"
    elif product == "coach":
        title, desc = "🎯 Коуч-сеанс", "25 вопросов + полный разбор + план действий + задания"
    else:
        return
    try:
        bot.send_invoice(chat_id=chat_id, title=title, description=desc, provider_token="", currency="XTR",
                         prices=[{"label": title, "amount": amount}], invoice_payload=product,
                         need_name=False, need_phone_number=False, need_email=False, need_shipping_address=False, is_flexible=False)
    except Exception as e:
        logger.error(f"Ошибка инвойса: {e}")

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
        
        db_query("INSERT INTO payments (chat_id, amount, product, status) VALUES (?, ?, ?, 'completed')",
                 (chat_id, payment.total_amount, product))
        
        if product == "test_20":
            # ВЫДАЁМ ДОСТУП — ДОБАВЛЯЕМ БОНУСНЫЙ ТЕСТ
            db_query("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (chat_id,))
            db_query("UPDATE stats SET paid_test_count = paid_test_count + 1")
            
            # Отправляем подтверждение и кнопку для запуска
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Пройти платный тест", callback_data="start_paid_test"))
            bot.send_message(chat_id, "✅ Оплата прошла успешно!\n\nТы получил доступ к платному тесту из 20 вопросов. Нажми кнопку ниже, чтобы начать.", reply_markup=mk)
            
        elif product == "coach":
            db_query("UPDATE stats SET coach_count = coach_count + 1")
            
            # КНОПКА ДЛЯ ЗАПУСКА КОУЧ-СЕАНСА ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Начать коуч-сеанс", callback_data="start_coach"))
            bot.send_message(chat_id, "✅ Оплата прошла успешно!\n\nТы получил доступ к коуч-сеансу. Нажми кнопку ниже, чтобы начать.", reply_markup=mk)
            
    except Exception as e:
        logger.error(f"Ошибка оплаты: {e}")

# ============================================================
# ПЛАНИРОВЩИК (С ЗАЩИТОЙ ОТ ДУБЛЕЙ)
# ============================================================

LAST_RUN = {}

def get_schedule():
    now = datetime.now(TIMEZONE)
    tasks = []
    key = now.strftime('%Y-%m-%d %H')
    
    for hour in [10, 16, 20]:
        if now.hour == hour and now.minute == 0:
            if LAST_RUN.get('post') != key:
                LAST_RUN['post'] = key
                result = db_query("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 10", fetch=True)
                used = [row[0] for row in result] if result else []
                available = [t for t in CHANNEL_THEMES if t not in used]
                if not available:
                    db_query("DELETE FROM used_topics")
                    available = CHANNEL_THEMES
                topic = random.choice(available)
                db_query("INSERT INTO used_topics (topic) VALUES (?)", (topic,))
                tasks.append({"type": "post", "topic": topic})
    
    if now.hour == 13 and now.minute == 0 and LAST_RUN.get('test') != key:
        LAST_RUN['test'] = key
        tasks.append({"type": "test", "topic": random.choice(CHANNEL_THEMES), "count": 10})
    
    if now.minute == 0:
        # Проверяем чек-ины
        checkins = db_query("SELECT chat_id, session_id FROM checkins WHERE is_done = 0 AND checkin_date <= ?", (now.isoformat(),), fetch=True)
        if checkins:
            for chat_id, session_id in checkins:
                tasks.append({"type": "checkin", "chat_id": chat_id, "session_id": session_id})
                db_query("UPDATE checkins SET is_done = 1 WHERE chat_id = ? AND session_id = ?", (chat_id, session_id))
    
    return tasks

def scheduler_loop():
    while True:
        try:
            for task in get_schedule():
                if task["type"] == "post":
                    post = generate_post(task["topic"])
                    if post:
                        img = generate_post_image(task["topic"])
                        if img:
                            with open(img, 'rb') as photo:
                                # Обрезаем caption до 1024 символов
                                caption = post[:1024] + "..." if len(post) > 1024 else post
                                bot.send_photo(CHANNEL_ID, photo, caption=caption)
                            os.remove(img)
                            if len(post) > 1024:
                                bot.send_message(CHANNEL_ID, post)
                        else:
                            bot.send_message(CHANNEL_ID, post)
                elif task["type"] == "test":
                    q = generate_test_questions(task["topic"], 10)
                    if q:
                        bot_info = bot.get_me()
                        test_text = f"🔮 ТЕСТ ДНЯ: «{task['topic'].title()}» (10 вопросов)\n\n"
                        for i, qq in enumerate(q[:3], 1):
                            test_text += f"{i}. {qq['question']}\n"
                        test_text += f"\n🎯 Пройти полный тест: @{bot_info.username}?start=test_daily"
                        bot.send_message(CHANNEL_ID, test_text)
                elif task["type"] == "checkin":
                    try:
                        bot.send_message(task["chat_id"], "🧠 Привет! Прошло 3 дня после нашего сеанса. Как ты себя чувствуешь? Что изменилось? Напиши мне — я здесь.")
                    except:
                        pass
            time.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
            time.sleep(60)

# ============================================================
# TELEGRAM БОТ
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
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

threading.Thread(target=run_flask, daemon=True).start()
logger.info("✅ Веб-сервер запущен")

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
    code = generate_referral_code(chat_id)
    db_query("INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name, referral_code) VALUES (?, ?, ?, ?, ?)",
             (chat_id, username, first_name, last_name, code))
    db_query("UPDATE stats SET users_count = (SELECT COUNT(*) FROM users)")

# ============================================================
# ВСЕ КНОПКИ (ИСПРАВЛЕНЫ)
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    try:
        chat_id = message.chat.id
        user = message.from_user
        save_user(chat_id, user.username, user.first_name, user.last_name)
        
        # Обработка диплинка
        if ' ' in message.text:
            param = message.text.split(' ', 1)[1]
            if param.startswith('ref_'):
                process_referral(param.replace('ref_', ''), chat_id)
            elif param.startswith('test_'):
                # Запуск теста по диплинку
                bot.send_message(chat_id, "🔮 Запускаю тест...")
                show_topics(message, 'free', 10)
                return
        
        bot.send_message(chat_id, "🌟 Добро пожаловать в Жизнь+!", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка start: {e}")

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    try:
        text = """🧠 ЖИЗНЬ+ — канал о том, что внутри.

Мы не даём ответов. Мы даём вопросы, которые меняют.

Здесь ты не найдёшь:
— мотивационных лозунгов
— «ты уникален, просто поверь»
— воды и пустых советов

Здесь ты найдёшь:
— честные мысли без прикрас
— посты, которые застревают в голове
— тесты, которые вскрывают то, что ты прятал
— сеансы, которые работают глубже, чем ты готов

Автор — не психолог, не коуч.
Он — человек, который прошёл через своё дерьмо.

Он говорит с тобой как с равным.
Без ролей. Без масок. Без «я тебя научу».

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
        link = get_referral_link(chat_id)
        bot.send_message(chat_id,
                         f"🧠 Я прохожу тесты в боте Жизнь+ и узнаю о себе новое.\n\nПрисоединяйся: {link}\n\n#жизньплюс #психология")
        bot.send_message(chat_id, "✅ Поделился! Спасибо!")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    try:
        chat_id = message.chat.id
        result = db_query("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,), fetch=True)
        if result and result[0][0] > 0:
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
    start(message)

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный (10 вопросов)')
def free_test(message):
    show_topics(message, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов) — 50 Stars')
def paid_test(message):
    chat_id = message.chat.id
    result = db_query("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,), fetch=True)
    if result and result[0][0] > 0:
        db_query("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
        show_topics(message, 'paid', 20)
    else:
        send_invoice(chat_id, "test_20", PRICE_TEST_20)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов) — БЕСПЛАТНО (бонус)')
def paid_test_bonus(message):
    chat_id = message.chat.id
    result = db_query("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,), fetch=True)
    if result and result[0][0] > 0:
        db_query("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
        show_topics(message, 'paid', 20)
    else:
        bot.send_message(chat_id, "❌ Нет бонусных тестов.", reply_markup=test_type_menu())

def show_topics(message, test_type, count):
    try:
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for topic in CHANNEL_THEMES:
            mk.add(telebot.types.InlineKeyboardButton(topic.title(), callback_data=f"{test_type}_{topic}_{count}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
        bot.send_message(message.chat.id, f"🔮 Выбери тему:\n\n{count} вопросов", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid, count = test_type == 'paid', int(count)
        chat_id = c.message.chat.id
        
        # Отвечаем сразу, чтобы не было спиннера
        c.answer()
        
        bot.send_message(chat_id, "⏳ Генерация теста...\n⏱ Ожидание до 30 сек")
        
        # Тяжёлая генерация в фоне
        def generate():
            questions = generate_test_questions(topic, count)
            if not questions:
                bot.send_message(chat_id, "❌ AI не ответил. Попробуй позже.")
                return
            
            sessions[chat_id] = {'topic': topic, 'questions': questions, 'answers': [], 'q': 0, 'scores': [], 'is_paid': is_paid}
            send_question(chat_id)
        
        threading.Thread(target=generate, daemon=True).start()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, "❌ Отменено", reply_markup=get_main_menu(c.message.chat.id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    c.answer()

def send_question(chat_id):
    s = sessions.get(chat_id)
    if not s or s['q'] >= len(s['questions']):
        finish_test(chat_id) if s else bot.send_message(chat_id, "❌ Сессия не найдена.")
        return
    q = s['questions'][s['q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for opt, txt in q['options'].items():
        mk.add(f"{opt}) {txt}")
    mk.add('⏹ Прервать тест')
    bot.send_message(chat_id, f"🔮 Вопрос {s['q']+1}/{len(s['questions'])}\n\n{q['question']}", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text and m.text[0].upper() in 'ABCD')
def handle_answer(message):
    chat_id, s = message.chat.id, sessions.get(message.chat.id)
    if not s or s['q'] >= len(s['questions']):
        return
    letter = message.text[0].upper()
    q = s['questions'][s['q']]
    # Защита от KeyError
    score = q['scores'].get(letter, 0)
    s['answers'].append(letter)
    s['scores'].append(score)
    s['q'] += 1
    send_question(chat_id)

def finish_test(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    score = sum(s['scores'])
    total = len(s['questions']) * 3
    answers = ', '.join(s['answers'])
    is_paid = s.get('is_paid', False)
    
    if is_paid:
        db_query("UPDATE stats SET paid_test_count = paid_test_count + 1")
    else:
        db_query("UPDATE stats SET free_count = free_count + 1")
    
    bot.send_message(chat_id, f"📊 Тест завершен!\nРезультат: {score} из {total}\n⏳ Анализирую...\n⏱ Ожидание до 30 сек")
    analysis = generate_analysis(s['topic'], answers, score, total, is_paid)
    
    if analysis:
        # Отправляем с fallback на случай ошибки Markdown
        try:
            bot.send_message(chat_id, f"🔍 АНАЛИЗ\n\n{analysis}", reply_markup=get_main_menu(chat_id), parse_mode='Markdown')
        except:
            bot.send_message(chat_id, f"🔍 АНАЛИЗ\n\n{analysis}", reply_markup=get_main_menu(chat_id))
        
        if is_paid:
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Коуч-сеанс за 100 Stars", callback_data="buy_coach"))
            bot.send_message(chat_id, "🎯 Хочешь разобраться глубже? Пройди коуч-сеанс.", reply_markup=mk)
    else:
        bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=get_main_menu(chat_id))
    del sessions[chat_id]

@bot.callback_query_handler(func=lambda c: c.data == 'buy_coach')
def buy_coach(c):
    send_invoice(c.message.chat.id, "coach", PRICE_COACH)
    c.answer()

# ============================================================
# АДМИН-ПАНЕЛЬ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

# -------------------- ПОСТЫ --------------------

@bot.message_handler(func=lambda m: m.text == '📝 Новый пост')
def new_post_menu(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📝 Что отправляем в канал?", reply_markup=post_type_menu())

@bot.message_handler(func=lambda m: m.text == '📝 Пост без картинки')
def post_without_image(message):
    if message.chat.id in ADMIN_IDS:
        sessions[message.chat.id] = {"action": "post_without_image"}
        bot.send_message(message.chat.id, "📝 Выбери тему:", reply_markup=theme_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def post_with_image(message):
    if message.chat.id in ADMIN_IDS:
        sessions[message.chat.id] = {"action": "post_with_image"}
        bot.send_message(message.chat.id, "📝 Выбери тему для поста с супер-картинкой:", reply_markup=theme_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Только картинка')
def only_image(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📝 Введи описание для супер-картинки:")
        bot.register_next_step_handler(message, process_only_image)

def process_only_image(message):
    chat_id = message.chat.id
    prompt = message.text
    bot.send_message(chat_id, "🖼 Генерация супер-картинки...")
    img = generate_image(prompt)
    if img:
        with open(img, 'rb') as photo:
            bot.send_photo(CHANNEL_ID, photo, caption=f"🖼 {prompt}")
        os.remove(img)
        db_query("UPDATE stats SET images_generated = images_generated + 1")
        bot.send_message(chat_id, "✅ Супер-картинка отправлена!", reply_markup=admin_menu())
    else:
        bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())

# -------------------- СТАТИСТИКА (ИСПРАВЛЕНА) --------------------

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id in ADMIN_IDS:
        result = db_query("SELECT free_count, paid_test_count, coach_count, promo_used, users_count, posts_count, tests_created, images_generated, consultations_count, referrals_count, gifts_used FROM stats", fetch=True)
        row = result[0] if result else (0,0,0,0,0,0,0,0,0,0,0)
        users_result = db_query("SELECT COUNT(*) FROM users", fetch=True)
        users = users_result[0][0] if users_result else 0
        gifts_result = db_query("SELECT COUNT(*) FROM gifts", fetch=True)
        gifts = gifts_result[0][0] if gifts_result else 0
        checkins_result = db_query("SELECT COUNT(*) FROM checkins WHERE is_done = 0", fetch=True)
        checkins = checkins_result[0][0] if checkins_result else 0
        
        bot.send_message(message.chat.id,
                         f"📊 СТАТИСТИКА\n\n"
                         f"👥 Пользователей: {users}\n"
                         f"🧠 Бесплатных тестов: {row[0]}\n"
                         f"💎 Платных тестов: {row[1]}\n"
                         f"🎯 Коуч-сеансов: {row[2]}\n"
                         f"🎫 Промокодов: {row[3]}\n"
                         f"📤 Постов: {row[5]}\n"
                         f"🧠 Тестов создано: {row[6]}\n"
                         f"🖼 Супер-картинок: {row[7]}\n"
                         f"🎯 Консультаций: {row[8]}\n"
                         f"👥 Рефералов: {row[9]}\n"
                         f"🎁 Подарков активировано: {row[10]}\n"
                         f"🎁 Подарков создано: {gifts}\n"
                         f"⏳ Чек-инов: {checkins}",
                         reply_markup=admin_menu())

# -------------------- РАСПИСАНИЕ --------------------

@bot.message_handler(func=lambda m: m.text == '⏰ Расписание')
def show_schedule(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "⏰ РАСПИСАНИЕ (Юрга UTC+7)\n\n📝 ПОСТЫ: 10:00, 16:00, 20:00\n🧠 ТЕСТ: 13:00\n🧠 ЧЕК-ИН: через 3 дня после сеанса", reply_markup=admin_menu())

# -------------------- ЛОГИ --------------------

@bot.message_handler(func=lambda m: m.text == '📋 Логи')
def show_logs(message):
    if message.chat.id in ADMIN_IDS and os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            logs = ''.join(f.readlines()[-50:])
        bot.send_message(message.chat.id, f"📋 ПОСЛЕДНИЕ 50 СТРОК:\n\n{logs[-4000:]}", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "❌ Логов нет.", reply_markup=admin_menu())

# -------------------- КАРТИНКИ В КАНАЛ --------------------

@bot.message_handler(func=lambda m: m.text == '🖼 Картинка в канал')
def image_to_channel(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📝 Введи описание для супер-картинки:")
        bot.register_next_step_handler(message, process_image_only_standalone)

def process_image_only_standalone(message):
    chat_id = message.chat.id
    prompt = message.text
    bot.send_message(chat_id, "🖼 Генерация супер-картинки...")
    img = generate_image(prompt)
    if img:
        with open(img, 'rb') as photo:
            bot.send_photo(CHANNEL_ID, photo, caption=f"🖼 {prompt}")
        os.remove(img)
        db_query("UPDATE stats SET images_generated = images_generated + 1")
        bot.send_message(chat_id, "✅ Супер-картинка отправлена!", reply_markup=admin_menu())
    else:
        bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())

# -------------------- ТЕСТЫ В КАНАЛ --------------------

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def test_to_channel_start(message):
    if message.chat.id in ADMIN_IDS:
        sessions[message.chat.id] = {"action": "test_to_channel"}
        bot.send_message(message.chat.id, "🧠 Выбери тему для теста:", reply_markup=theme_menu())

# -------------------- ОБЩИЙ ОБРАБОТЧИК ТЕМ --------------------

@bot.message_handler(func=lambda m: m.text in [t.title() for t in CHANNEL_THEMES] and m.chat.id in ADMIN_IDS)
def handle_theme_selection(message):
    try:
        chat_id = message.chat.id
        theme = message.text.lower()
        action = sessions.get(chat_id, {}).get("action")
        
        if action == "test_to_channel":
            bot.send_message(chat_id, f"⏳ Генерация теста...")
            q = generate_test_questions(theme, 10)
            if q:
                db_query("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?, ?, ?)",
                         (theme, json.dumps(q), datetime.now().isoformat()))
                test_text = f"🔮 ТЕСТ: «{theme.title()}» (10 вопросов)\n\n"
                for i, qq in enumerate(q[:5], 1):
                    test_text += f"{i}. {qq['question']}\n"
                    for opt, txt in qq['options'].items():
                        test_text += f"   {opt}) {txt}\n"
                    test_text += "\n"
                test_text += f"... и ещё {len(q)-5} вопросов\n\n🎯 Пройти полный тест: @{bot.get_me().username}?start=test_daily"
                bot.send_message(CHANNEL_ID, test_text)
                bot.send_message(chat_id, "✅ Тест отправлен!", reply_markup=admin_menu())
            else:
                bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())
            sessions[chat_id] = {}
            
        elif action == "post_without_image":
            post = generate_post(theme)
            if post:
                db_query("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
                db_query("UPDATE stats SET posts_count = posts_count + 1")
                bot.send_message(CHANNEL_ID, post)
                bot.send_message(chat_id, "✅ Пост отправлен!", reply_markup=admin_menu())
            else:
                bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())
            sessions[chat_id] = {}
            
        elif action == "post_with_image":
            post = generate_post(theme)
            if post:
                img = generate_post_image(theme)
                db_query("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", (post, theme, img or ""))
                db_query("UPDATE stats SET posts_count = posts_count + 1")
                if img:
                    db_query("UPDATE stats SET images_generated = images_generated + 1")
                if img:
                    caption = post[:900] + "..." if len(post) > 900 else post
                    with open(img, 'rb') as photo:
                        bot.send_photo(CHANNEL_ID, photo, caption=caption)
                    os.remove(img)
                    if len(post) > 900:
                        bot.send_message(CHANNEL_ID, post)
                else:
                    bot.send_message(CHANNEL_ID, post)
                bot.send_message(chat_id, "✅ Пост с супер-картинкой отправлен!", reply_markup=admin_menu())
            else:
                bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())
            sessions[chat_id] = {}
        else:
            bot.send_message(chat_id, "❌ Сначала выбери действие в админке.", reply_markup=admin_menu())
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}", reply_markup=admin_menu())

# ============================================================
# 🎫 ПРОМОКОДЫ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🎫 Введите код (латиница, 3+ символов):")
        bot.register_next_step_handler(message, process_create_promo)

def process_create_promo(message):
    chat_id, code = message.chat.id, message.text.strip().upper()
    if code == "ОТМЕНА" or len(code) < 3:
        bot.send_message(chat_id, "❌ Отменено или слишком короткий.", reply_markup=admin_menu())
        return
    try:
        db_query("INSERT INTO promocodes (code, created_by, created_at) VALUES (?, ?, ?)",
                 (code, chat_id, datetime.now().isoformat()))
        bot.send_message(chat_id, f"✅ Промокод создан!\n\n📌 Код: {code}\nДаёт 1 бесплатный тест из 20 вопросов.", reply_markup=admin_menu())
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Уже существует.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(message.chat.id, "🎫 Введите промокод:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    chat_id, code = message.chat.id, message.text.strip().upper()
    result = db_query("SELECT id, used_by FROM promocodes WHERE code = ?", (code,), fetch=True)
    if not result:
        bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id))
        return
    if result[0][1] != 0:
        bot.send_message(chat_id, "❌ Уже использован.", reply_markup=get_main_menu(chat_id))
        return
    db_query("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?",
             (chat_id, datetime.now().isoformat(), result[0][0]))
    db_query("UPDATE stats SET promo_used = promo_used + 1")
    db_query("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (chat_id,))
    bot.send_message(chat_id, "🎉 Промокод активирован! Ты получил 1 бесплатный тест из 20 вопросов. Нажми «🎯 Пройти тест» и выбери платный.", reply_markup=get_main_menu(chat_id))

# ============================================================
# 🎁 ПОДАРКИ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎁 Создать подарок')
def create_gift(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🎁 Введите количество сеансов (1-10):")
        bot.register_next_step_handler(message, process_gift_max_uses)

def process_gift_max_uses(message):
    try:
        max_uses = int(message.text.strip())
        if max_uses < 1 or max_uses > 10:
            raise ValueError
        sessions[message.chat.id] = {'gift_max_uses': max_uses}
        bot.send_message(message.chat.id, "📅 Введите срок действия (дней):")
        bot.register_next_step_handler(message, process_gift_expires)
    except:
        bot.send_message(message.chat.id, "❌ Введите число от 1 до 10.", reply_markup=admin_menu())

def process_gift_expires(message):
    try:
        days = int(message.text.strip())
        if days < 1 or days > 365:
            raise ValueError
        chat_id = message.chat.id
        max_uses = sessions.get(chat_id, {}).get('gift_max_uses', 1)
        code = "GIFT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        expires_at = (datetime.now(TIMEZONE) + timedelta(days=days)).isoformat()
        db_query("INSERT INTO gifts (code, created_by, max_uses, expires_at) VALUES (?, ?, ?, ?)",
                 (code, chat_id, max_uses, expires_at))
        bot.send_message(chat_id,
                         f"✅ ПОДАРОК СОЗДАН!\n\n🎁 Код: {code}\n📊 Сеансов: {max_uses}\n📅 Действует до: {expires_at[:10]}\nДаёт бесплатный коуч-сеанс.",
                         reply_markup=admin_menu())
        if chat_id in sessions:
            del sessions[chat_id]
    except:
        bot.send_message(message.chat.id, "❌ Введите число от 1 до 365.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎁 Активировать подарок')
def activate_gift_start(message):
    bot.send_message(message.chat.id, "🎁 Введите код подарка:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_gift_activation)

def process_gift_activation(message):
    chat_id, code = message.chat.id, message.text.strip().upper()
    result = db_query("SELECT id, max_uses, used_count, expires_at FROM gifts WHERE code = ?", (code,), fetch=True)
    if not result:
        bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id))
        return
    gift_id, max_uses, used_count, expires_at = result[0]
    if expires_at and datetime.now(TIMEZONE).isoformat() > expires_at:
        bot.send_message(chat_id, "❌ Срок истёк.", reply_markup=get_main_menu(chat_id))
        return
    if used_count >= max_uses:
        bot.send_message(chat_id, "❌ Код использован.", reply_markup=get_main_menu(chat_id))
        return
    db_query("UPDATE gifts SET used_count = used_count + 1 WHERE id = ?", (gift_id,))
    db_query("UPDATE stats SET gifts_used = gifts_used + 1")
    db_query("INSERT INTO payments (chat_id, amount, product, status) VALUES (?, 0, 'coach_gift', 'completed')", (chat_id,))
    bot.send_message(chat_id, "🎉 ПОДАРОК АКТИВИРОВАН!\n\nТы получил бесплатный коуч-сеанс.\nНажми кнопку ниже, чтобы начать.",
                     reply_markup=telebot.types.InlineKeyboardMarkup().add(telebot.types.InlineKeyboardButton("🎯 Начать коуч-сеанс", callback_data="start_coach")))

# ============================================================
# 🎯 КОУЧ-СЕАНС (ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ)
# ============================================================

@bot.callback_query_handler(func=lambda c: c.data == 'start_coach')
def start_coach_from_callback(c):
    chat_id = c.message.chat.id
    c.answer()
    # Проверяем оплату
    result = db_query("SELECT id FROM payments WHERE chat_id = ? AND (product = 'coach' OR product = 'coach_gift') AND status = 'completed'", (chat_id,), fetch=True)
    if not result:
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    start_consultation_logic(chat_id)

@bot.message_handler(func=lambda m: m.text == '🎯 Сеанс коучинга')
def start_consultation(message):
    chat_id = message.chat.id
    # Проверяем оплату
    result = db_query("SELECT id FROM payments WHERE chat_id = ? AND (product = 'coach' OR product = 'coach_gift') AND status = 'completed'", (chat_id,), fetch=True)
    if not result:
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    start_consultation_logic(chat_id)

def start_consultation_logic(chat_id):
    bot.send_message(chat_id,
                     "🧠 ПЕРЕД СЕАНСОМ\n\n"
                     "Как ты себя чувствуешь прямо сейчас?\n"
                     "Это поможет мне подобрать правильные вопросы.",
                     reply_markup=session_diagnostic_menu())

@bot.message_handler(func=lambda m: m.text in ['😔 Подавленность', '😰 Тревога', '😡 Раздражение', '😌 Спокойствие', '😊 Радость'])
def handle_diagnostic(message):
    chat_id = message.chat.id
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

@bot.message_handler(func=lambda m: m.text == '❌ Отмена')
def cancel_consultation(message):
    chat_id = message.chat.id
    if chat_id in consultations:
        del consultations[chat_id]
    bot.send_message(chat_id, "❌ Отменено.", reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text == '✅ Начать')
def confirm_consultation(message):
    chat_id = message.chat.id
    
    # Проверяем оплату
    result = db_query("SELECT id FROM payments WHERE chat_id = ? AND (product = 'coach' OR product = 'coach_gift') AND status = 'completed'", (chat_id,), fetch=True)
    if not result:
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    
    diagnostic = consultations.get(chat_id, {}).get("diagnostic", "неизвестно")
    
    bot.send_message(chat_id,
                     f"🎯 Начинаем сеанс.\nТвоё состояние: {diagnostic}\n\n"
                     "Генерирую вопросы специально для тебя...\n⏱ Ожидание до 30 сек",
                     reply_markup=telebot.types.ReplyKeyboardRemove())
    
    questions = generate_consultation_questions()
    if not questions:
        bot.send_message(chat_id, "❌ Не удалось сгенерировать вопросы.", reply_markup=get_main_menu(chat_id))
        if chat_id in consultations:
            del consultations[chat_id]
        return
    
    session_id = db_query("INSERT INTO consultation_sessions (chat_id, questions, current_q, is_active, is_paid) VALUES (?, ?, ?, ?, 1)",
                          (chat_id, json.dumps(questions), 0, 1))
    
    consultations[chat_id] = {
        "session_id": session_id,
        "questions": questions,
        "answers": [],
        "q": 0,
        "diagnostic": diagnostic
    }
    
    send_consultation_question(chat_id)

def send_consultation_question(chat_id):
    s = consultations.get(chat_id)
    if not s or s['q'] >= len(s['questions']):
        finish_consultation(chat_id) if s else bot.send_message(chat_id, "❌ Сессия не найдена.", reply_markup=get_main_menu(chat_id))
        return
    q = s['questions'][s['q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    mk.add('⏹ Завершить сеанс')
    bot.send_message(chat_id, f"🔮 ВОПРОС {s['q']+1}/{len(s['questions'])}\n\n{q['question']}", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '⏹ Завершить сеанс')
def finish_consultation_manual(message):
    chat_id = message.chat.id
    if chat_id in consultations:
        finish_consultation(chat_id)
    else:
        bot.send_message(chat_id, "❌ Нет активного сеанса.", reply_markup=get_main_menu(chat_id))

def finish_consultation(chat_id):
    s = consultations.get(chat_id)
    if not s:
        return
    db_query("UPDATE consultation_sessions SET is_active = 0 WHERE id = ?", (s['session_id'],))
    if not s['answers']:
        bot.send_message(chat_id, "❌ Сеанс прерван.", reply_markup=get_main_menu(chat_id))
        del consultations[chat_id]
        return
    bot.send_message(chat_id, "📊 Обрабатываю ответы... ⏱ 1-2 минуты.", reply_markup=get_main_menu(chat_id))
    
    def background():
        answers_text = "\n".join([f"{i+1}. {a}" for i, a in enumerate(s['answers'])])
        analysis = generate_consultation_analysis(answers_text, chat_id, s['session_id'])
        tasks = "\n\n📋 ТВОИ ЗАДАНИЯ:\n🟢 Напиши 3 благодарности\n🟢 Скажи в зеркале: 'Я справлюсь'\n🟢 5 минут тишины"
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add('📤 Поделиться', '🚀 Старт')
        
        if analysis:
            try:
                bot.send_message(chat_id, f"🔮 ПОЛНЫЙ РАЗБОР\n\n{analysis}\n{tasks}", reply_markup=mk, parse_mode='Markdown')
            except:
                bot.send_message(chat_id, f"🔮 ПОЛНЫЙ РАЗБОР\n\n{analysis}\n{tasks}", reply_markup=mk)
        else:
            bot.send_message(chat_id, f"❌ Ошибка анализа.\n{tasks}", reply_markup=mk)
        del consultations[chat_id]
    
    threading.Thread(target=background, daemon=True).start()

# ============================================================
# ОБРАБОТЧИК ОТВЕТОВ НА КОНСУЛЬТАЦИЮ
# ============================================================

ADMIN_BUTTONS = [
    '✅ Начать', '❌ Отмена', '⏹ Завершить сеанс',
    '👑 Админ-панель', '👑 Главное меню',
    '📝 Новый пост', '🧠 Тест в канал', '🖼 Картинка в канал',
    '🎯 Сеанс коучинга', '🎁 Создать подарок', '🎫 Создать промокод',
    '📊 Статистика', '⏰ Расписание', '📋 Логи',
    '📝 Пост без картинки', '🖼 Пост с картинкой', '🖼 Только картинка',
    '🚀 Старт', '🎯 Пройти тест', '🎫 Активировать промокод',
    '🎁 Активировать подарок', '📤 Поделиться', '❤️ О канале',
    '🔙 Назад', '🧠 Бесплатный (10 вопросов)',
    '💎 Платный (20 вопросов) — 50 Stars',
    '💎 Платный (20 вопросов) — БЕСПЛАТНО (бонус)',
    '😔 Подавленность', '😰 Тревога', '😡 Раздражение',
    '😌 Спокойствие', '😊 Радость', '⏹ Прервать тест'
] + [t.title() for t in CHANNEL_THEMES]

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text not in ADMIN_BUTTONS)
def handle_consultation_answer(message):
    try:
        chat_id = message.chat.id
        if chat_id not in consultations:
            return
        s = consultations[chat_id]
        if s['q'] >= len(s['questions']):
            return
        s['answers'].append(message.text)
        s['q'] += 1
        db_query("UPDATE consultation_sessions SET current_q = ?, answers = ? WHERE id = ?",
                 (s['q'], json.dumps(s['answers']), s['session_id']))
        send_consultation_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================================
# ЗАПУСК БОТА (С ЦИКЛОМ ВМЕСТО РЕКУРСИИ)
# ============================================================

def run_bot():
    logger.info(f"🤖 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")
    while True:
        try:
            super_kill_409()
            time.sleep(2)
            bot.remove_webhook()
            logger.info("✅ Вебхук удален")
            bot.polling(none_stop=True, interval=0, timeout=20,
                       allowed_updates=['message', 'callback_query', 'pre_checkout_query'])
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            if "409" in str(e):
                logger.info("🔄 Обнаружена 409, жесткий перезапуск...")
                super_kill_409()
            time.sleep(5)

threading.Thread(target=scheduler_loop, daemon=True).start()
logger.info("✅ Планировщик запущен")

if __name__ == "__main__":
    run_bot()
