import telebot
import sqlite3
import requests
import os
import json
import time
import logging
import threading
import random
import sys
import traceback
import string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# 🔐 КЛЮЧИ (ВСТАВЛЕНЫ ПРЯМО В КОД)
# ============================================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
ADMIN_IDS = [8746212340]

# КЛЮЧИ AGNES AI (для картинок)
AGNES_API_KEY = "sk-8nqC897jST7vx1brGMUTNLRsVGPXgP7Bcpuwmbl5quaCLN5c"
AGNES_API_URL = "https://apihub.agnes-ai.com/v1/images/generations"

# КЛЮЧ OPENROUTER (для текста)
OPENROUTER_API_KEY = "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"

# ============================================================
# ⚙️ НАСТРОЙКИ
# ============================================================

TIMEZONE = ZoneInfo("Asia/Novokuznetsk")
BOT_VERSION = "18.0.0"
BOT_NAME = "Жизнь+ Про (PERFECT)"
DB_PATH = 'channel.db'
LOG_PATH = 'bot_logs.txt'

PRICE_TEST_20 = 50  # 50 Stars
PRICE_COACH = 100   # 100 Stars

# ============================================================
# 📚 50+ ТЕМ
# ============================================================

CHANNEL_THEMES = [
    "психология", "отношения", "карьера", "здоровье", "финансы",
    "мотивация", "саморазвитие", "эмоции", "страхи", "любовь к себе",
    "благодарность", "осознанность", "прощение", "энергия", "выбор",
    "смысл жизни", "одиночество", "тревога", "депрессия", "самооценка",
    "уверенность", "принятие", "изменения", "цели", "привычки",
    "травмы", "детство", "родители", "партнерство", "доверие",
    "счастье", "покой", "сила", "мягкость", "интуиция",
    "творчество", "радость", "смех", "слезы", "обида",
    "вина", "стыд", "гордость", "надежда", "вера",
    "любовь", "дружба", "семья", "работа", "деньги",
    "искусство", "природа", "тишина", "движение"
]

# ============================================================
# 🤖 AI-ПРОВАЙДЕРЫ (С КЛЮЧОМ OPENROUTER)
# ============================================================

AI_PROVIDERS = [
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openrouter/auto",
        "api_key": OPENROUTER_API_KEY
    },
    {
        "name": "OpenRouter Llama",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.1-70b-instruct:free",
        "api_key": OPENROUTER_API_KEY
    },
    {
        "name": "OpenRouter DeepSeek",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "deepseek/deepseek-r1:free",
        "api_key": OPENROUTER_API_KEY
    },
    {
        "name": "OpenRouter Qwen",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "qwen/qwen-2.5-72b-instruct:free",
        "api_key": OPENROUTER_API_KEY
    },
    {
        "name": "G4F",
        "url": "https://api.g4f.icu/v1/chat/completions",
        "model": "gpt-4o-mini",
        "api_key": ""
    },
    {
        "name": "G4F Flash",
        "url": "https://api.g4f.icu/v1/chat/completions",
        "model": "gpt-4o",
        "api_key": ""
    },
    {
        "name": "Pawan",
        "url": "https://api.pawan.krd/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "api_key": ""
    },
    {
        "name": "Pawan Claude",
        "url": "https://api.pawan.krd/v1/chat/completions",
        "model": "claude-3-haiku",
        "api_key": ""
    }
]

# ============================================================
# 📝 ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")

# ============================================================
# 💀 УБИЙЦА 409
# ============================================================

def kill_409():
    """Полное уничтожение ошибки 409 Conflict"""
    try:
        # Удаляем вебхук
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        requests.post(url, json={"drop_pending_updates": True}, timeout=10)
        
        # Сбрасываем вебхук
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
        
        # Удаляем локальные файлы блокировок
        for pattern in ['*.lock', '*.session', '*.state', '*.pid']:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                except:
                    pass
        
        logger.info("🔥 409 УНИЧТОЖЕН")
        return True
    except Exception as e:
        logger.error(f"Ошибка убийцы 409: {e}")
        return False

# Убиваем 409 при старте
for i in range(3):
    kill_409()
    time.sleep(1)

# ============================================================
# 💾 БАЗА ДАННЫХ (ПРОСТАЯ, БЕЗ ПОТОКОБЕЗОПАСНОСТИ)
# ============================================================

def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # Пользователи
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
        bonus_tests INTEGER DEFAULT 0
    )''')
    
    # Рефералы
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Статистика
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
        avg_test_score REAL DEFAULT 0,
        total_revenue INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Добавляем начальную статистику
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO stats DEFAULT VALUES")
    
    # Сессии консультаций
    c.execute('''CREATE TABLE IF NOT EXISTS consultation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        questions TEXT,
        answers TEXT,
        current_q INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        is_paid INTEGER DEFAULT 0,
        is_analyzed INTEGER DEFAULT 0,
        diagnostic TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # История консультаций
    c.execute('''CREATE TABLE IF NOT EXISTS consultation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        session_id INTEGER,
        questions TEXT,
        answers TEXT,
        analysis TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Платежи
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        amount INTEGER,
        product TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Промокоды
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used_by INTEGER DEFAULT 0,
        used_at TIMESTAMP
    )''')
    
    # История постов
    c.execute('''CREATE TABLE IF NOT EXISTS posts_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        topic TEXT,
        image_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Ежедневные тесты
    c.execute('''CREATE TABLE IF NOT EXISTS daily_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT,
        questions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_paid INTEGER DEFAULT 0,
        message_id INTEGER DEFAULT 0
    )''')
    
    # Использованные темы
    c.execute('''CREATE TABLE IF NOT EXISTS used_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Подарки
    c.execute('''CREATE TABLE IF NOT EXISTS gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        created_by INTEGER,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Чек-ины
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

# Глобальные объекты БД
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ============================================================
# 🤖 БОТ
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================================
# 🌊 AI (ТЕКСТ)
# ============================================================

def ask_ai(system, user, max_tokens=3000, retries=2):
    """Запрос к AI с автоматическим переключением провайдеров"""
    if not user or not user.strip():
        user = "Сделай запрос."
    
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    
    for provider in AI_PROVIDERS:
        for attempt in range(retries):
            try:
                logger.info(f"🔄 {provider['name']} (попытка {attempt+1}/{retries})")
                
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
                    timeout=35,
                    verify=False
                )
                elapsed = time.time() - start
                logger.info(f"⏱ {elapsed:.2f}с | Статус: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if content and len(content) > 10:
                        logger.info(f"✅ {provider['name']} ответил ({len(content)} символов)")
                        return content
                    else:
                        logger.warning(f"⚠️ Пустой ответ от {provider['name']}")
                else:
                    logger.warning(f"⚠️ Ошибка {provider['name']}: {response.status_code}")
                
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"⚠️ {provider['name']}: {str(e)[:50]}")
                time.sleep(0.5)
        
        logger.info(f"⏳ Переключение с {provider['name']}...")
    
    logger.error("❌ ВСЕ AI-ПРОВАЙДЕРЫ НЕДОСТУПНЫ")
    return None

# ============================================================
# 🖼 ГЕНЕРАЦИЯ КАРТИНОК
# ============================================================

def generate_image(prompt, width=1024, height=768):
    """Генерация супер-картинки через Agnes AI"""
    try:
        logger.info("🖼 Генерация через Agnes AI...")
        
        full_prompt = f"""Hyper-realistic, cinematic photography. {prompt}
Subject: European, Caucasian, light skin, natural glow, warm smile, relaxed.
Environment: Sunny, golden hour, warm sunlight, soft lens flare.
Lighting: Soft golden backlight, warm skin tones.
Style: Photorealistic, high detail, magazine quality.
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
                    filename = f"/tmp/img_{int(time.time())}_{random.randint(1000,999999)}.jpg"
                    with open(filename, 'wb') as f:
                        f.write(img_response.content)
                    logger.info("✅ Картинка создана")
                    return filename
                else:
                    logger.warning("⚠️ Не удалось скачать")
            else:
                logger.warning("⚠️ URL не найден")
        else:
            logger.error(f"❌ Ошибка Agnes: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    
    # Резервный генератор
    logger.info("🔄 Переключение на Pollinations...")
    return generate_image_pollinations(prompt)

def generate_image_pollinations(prompt):
    """Резервный генератор через Pollinations"""
    try:
        clean = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "").replace(',', '%2C')
        url = f"https://image.pollinations.ai/prompt/{clean}?width=1024&height=768&nologo=true"
        
        response = requests.get(url, timeout=30)
        if response.status_code == 200 and len(response.content) > 1000:
            filename = f"/tmp/img_{int(time.time())}_{random.randint(1000,999999)}.jpg"
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info("✅ Картинка через Pollinations")
            return filename
        else:
            logger.error(f"❌ Ошибка Pollinations: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return None

def generate_post_image(theme):
    """Генерация картинки для поста"""
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational",
        f"beautiful landscape {theme}, sunrise, hope, positive energy",
        f"minimalist illustration {theme}, soft pastel, calm, art"
    ]
    return generate_image(random.choice(prompts))

# ============================================================
# 📝 ГЕНЕРАТОРЫ КОНТЕНТА
# ============================================================

def generate_post(topic):
    """Генерация поста"""
    system = f"Ты — автор канала о психологии. Напиши пост на тему '{topic}'. Минимум 600 символов. Без пафоса. Добавь вопрос в конце."
    return ask_ai(system, f"Тема: {topic}", 3000)

def generate_test_questions(topic, count=10):
    """Генерация вопросов для теста"""
    depth = "диагностика личности" if count == 10 else "полный психологический разбор"
    
    system = f"""ТЫ — КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ.

    Составь {count} глубоких, НО ПРОСТЫХ вопросов для {depth} на тему "{topic}".
    Верни ТОЛЬКО JSON.

    ФОРМАТ:
    [{{"question": "вопрос?", "options": {{"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"}}, "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}}}]
    
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
    """Генерация анализа результатов теста"""
    if is_paid:
        system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-КОУЧ.
        Проведи полный разбор личности.
        Структура: портрет, 2-3 инсайта, корень проблемы, план на неделю.
        Объем: 1500+ знаков."""
    else:
        system = """ТЫ — ОПЫТНЫЙ ПСИХОЛОГ.
        Дай краткий анализ.
        Структура: главная проблема, 1 инсайт, вопрос, шаг.
        Объем: 800+ знаков."""
    
    user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
    return ask_ai(system, user, 4000 if is_paid else 2000)

def generate_consultation_questions():
    """Генерация вопросов для консультации"""
    system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-НЛП-ПРАКТИК.

    Составь 25 глубоких, но ПРОСТЫХ вопросов для сеанса.
    Верни ТОЛЬКО JSON.
    Формат: [{"question": "вопрос?"}]
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
    """Генерация анализа консультации"""
    system = """ТЫ — ВЕДУЩИЙ ПСИХОЛОГ-КОУЧ.
    Проведи полный разбор личности.
    Структура: главная рана, как управляет, корень, 3 шага, заключение.
    Объем: 1500+ знаков."""
    
    response = ask_ai(system, f"Ответы:\n{answers}", 4000)
    if response:
        try:
            c.execute("""INSERT INTO consultation_history 
                         (chat_id, session_id, questions, answers, analysis) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (chat_id, session_id, "", answers, response))
            conn.commit()
            
            c.execute("UPDATE stats SET consultations_count = consultations_count + 1")
            conn.commit()
            
            # Добавляем чек-ин через 3 дня
            checkin_date = datetime.now(TIMEZONE) + timedelta(days=3)
            c.execute("""INSERT INTO checkins (chat_id, session_id, checkin_date) 
                         VALUES (?, ?, ?)""",
                      (chat_id, session_id, checkin_date.isoformat()))
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
        
        return response
    return None

# ============================================================
# 🔗 РЕФЕРАЛЬНАЯ СИСТЕМА
# ============================================================

def generate_referral_code(chat_id):
    return f"REF{chat_id}{random.randint(1000,9999)}"[:10]

def get_referral_link(chat_id):
    """Получение реферальной ссылки"""
    c.execute("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    if row and row[0]:
        code = row[0]
    else:
        code = generate_referral_code(chat_id)
        c.execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
        conn.commit()
    
    bot_info = bot.get_me()
    return f"https://t.me/{bot_info.username}?start=ref_{code}"

def process_referral(referral_code, new_user_id):
    """Обработка реферальной ссылки"""
    c.execute("SELECT chat_id FROM users WHERE referral_code = ?", (referral_code,))
    row = c.fetchone()
    if row:
        referrer_id = row[0]
        if referrer_id != new_user_id:
            # Проверяем, не был ли уже приглашён
            c.execute("SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?", 
                     (referrer_id, new_user_id))
            if not c.fetchone():
                c.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                         (referrer_id, new_user_id))
                conn.commit()
                
                c.execute("UPDATE stats SET referrals_count = referrals_count + 1")
                conn.commit()
                
                # Начисляем бонус
                c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?",
                         (referrer_id,))
                conn.commit()
                
                try:
                    bot.send_message(
                        referrer_id,
                        "🎉 По твоей ссылке пришёл новый пользователь!\n"
                        "Ты получил БЕСПЛАТНЫЙ тест из 20 вопросов."
                    )
                except:
                    pass
                return True
    return False

# ============================================================
# 💳 ОПЛАТА ЧЕРЕЗ TELEGRAM STARS
# ============================================================

def send_invoice(chat_id, product, amount):
    """Отправка инвойса"""
    if product == "test_20":
        title = "🧠 Тест из 20 вопросов"
        desc = "Полный психологический разбор личности"
    elif product == "coach":
        title = "🎯 Коуч-сеанс"
        desc = "25 вопросов + полный разбор + план действий"
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
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка инвойса: {e}")
        return False

@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout(query):
    """Обработка предоплаты"""
    try:
        bot.answer_pre_checkout_query(query.id, ok=True)
    except Exception as e:
        logger.error(f"Ошибка pre_checkout: {e}")
        bot.answer_pre_checkout_query(query.id, ok=False, error_message="Ошибка оплаты")

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    """Обработка успешной оплаты"""
    try:
        chat_id = message.chat.id
        payment = message.successful_payment
        product = payment.invoice_payload
        
        c.execute("""INSERT INTO payments (chat_id, amount, product, status) 
                     VALUES (?, ?, ?, 'completed')""",
                  (chat_id, payment.total_amount, product))
        conn.commit()
        
        c.execute("UPDATE stats SET total_revenue = total_revenue + ?", 
                 (payment.total_amount,))
        conn.commit()
        
        if product == "test_20":
            c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", 
                     (chat_id,))
            conn.commit()
            
            c.execute("UPDATE stats SET paid_test_count = paid_test_count + 1")
            conn.commit()
            
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Пройти платный тест", 
                     callback_data="start_paid_test"))
            bot.send_message(
                chat_id,
                "✅ Оплата прошла успешно!\n\n"
                "Ты получил доступ к платному тесту из 20 вопросов.\n"
                "Нажми кнопку ниже, чтобы начать.",
                reply_markup=mk
            )
            
        elif product == "coach":
            c.execute("UPDATE stats SET coach_count = coach_count + 1")
            conn.commit()
            
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Начать коуч-сеанс", 
                     callback_data="start_coach"))
            bot.send_message(
                chat_id,
                "✅ Оплата прошла успешно!\n\n"
                "Ты получил доступ к коуч-сеансу.\n"
                "Нажми кнопку ниже, чтобы начать.",
                reply_markup=mk
            )
            
    except Exception as e:
        logger.error(f"Ошибка оплаты: {e}")

# ============================================================
# ⏰ ПЛАНИРОВЩИК
# ============================================================

LAST_RUN = {}

def get_schedule():
    """Получение расписания задач"""
    now = datetime.now(TIMEZONE)
    tasks = []
    key = now.strftime('%Y-%m-%d %H')
    
    # Посты в 10, 16, 20 часов
    for hour in [10, 16, 20]:
        if now.hour == hour and now.minute == 0:
            if LAST_RUN.get('post') != key:
                LAST_RUN['post'] = key
                
                c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 20")
                used = [row[0] for row in c.fetchall()]
                available = [t for t in CHANNEL_THEMES if t not in used]
                if not available:
                    c.execute("DELETE FROM used_topics")
                    conn.commit()
                    available = CHANNEL_THEMES
                
                topic = random.choice(available)
                c.execute("INSERT INTO used_topics (topic) VALUES (?)", (topic,))
                conn.commit()
                tasks.append({"type": "post", "topic": topic})
    
    # Тест в 13:00
    if now.hour == 13 and now.minute == 0:
        if LAST_RUN.get('test') != key:
            LAST_RUN['test'] = key
            tasks.append({"type": "test", "topic": random.choice(CHANNEL_THEMES)})
    
    # Чек-ины каждый час
    if now.minute == 0:
        c.execute("""SELECT chat_id, session_id FROM checkins 
                     WHERE is_done = 0 AND checkin_date <= ?""",
                  (now.isoformat(),))
        checkins = c.fetchall()
        for chat_id, session_id in checkins:
            tasks.append({"type": "checkin", "chat_id": chat_id, "session_id": session_id})
            c.execute("UPDATE checkins SET is_done = 1 WHERE chat_id = ? AND session_id = ?",
                     (chat_id, session_id))
            conn.commit()
    
    return tasks

def scheduler_loop():
    """Цикл планировщика"""
    while True:
        try:
            for task in get_schedule():
                if task["type"] == "post":
                    post = generate_post(task["topic"])
                    if post:
                        img = generate_post_image(task["topic"])
                        if img:
                            with open(img, 'rb') as photo:
                                caption = post[:900] + "..." if len(post) > 900 else post
                                bot.send_photo(CHANNEL_ID, photo, caption=caption)
                            os.remove(img)
                            if len(post) > 900:
                                bot.send_message(CHANNEL_ID, post)
                        else:
                            bot.send_message(CHANNEL_ID, post)
                        
                        c.execute("UPDATE stats SET posts_count = posts_count + 1")
                        conn.commit()
                
                elif task["type"] == "test":
                    questions = generate_test_questions(task["topic"], 10)
                    if questions:
                        bot_info = bot.get_me()
                        test_text = f"🔮 ТЕСТ ДНЯ: «{task['topic'].title()}» (10 вопросов)\n\n"
                        for i, q in enumerate(questions[:3], 1):
                            test_text += f"{i}. {q['question']}\n"
                        test_text += f"\n🎯 Пройти полный тест: @{bot_info.username}?start=test_daily"
                        bot.send_message(CHANNEL_ID, test_text)
                
                elif task["type"] == "checkin":
                    try:
                        bot.send_message(
                            task["chat_id"],
                            "🧠 Привет! Прошло 3 дня после нашего сеанса.\n\n"
                            "Как ты себя чувствуешь? Что изменилось?\n"
                            "Напиши мне — я здесь."
                        )
                    except:
                        pass
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
            time.sleep(60)

# ============================================================
# 🌐 ВЕБ-СЕРВЕР
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
        logger.error(f"Ошибка веб-сервера: {e}")

threading.Thread(target=run_flask, daemon=True).start()
logger.info("✅ Веб-сервер запущен")

# ============================================================
# 📋 МЕНЮ
# ============================================================

def get_main_menu(chat_id):
    """Главное меню"""
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🚀 Старт', '🎯 Пройти тест')
    mk.add('🎯 Сеанс коучинга', '🎫 Активировать промокод')
    mk.add('🎁 Активировать подарок', '📤 Поделиться')
    mk.add('❤️ О канале')
    if chat_id in ADMIN_IDS:
        mk.add('👑 Админ-панель')
    return mk

def admin_menu():
    """Меню администратора"""
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('📝 Новый пост', '🧠 Тест в канал')
    mk.add('🖼 Картинка в канал', '🎯 Сеанс коучинга')
    mk.add('🎁 Создать подарок', '🎫 Создать промокод')
    mk.add('📊 Статистика', '⏰ Расписание')
    mk.add('📋 Логи', '🧪 Тест AI')
    mk.add('👑 Главное меню')
    return mk

def test_type_menu():
    """Меню выбора теста"""
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов) — 50 Stars')
    mk.add('🔙 Назад')
    return mk

def theme_menu():
    """Меню выбора темы"""
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for theme in CHANNEL_THEMES[:15]:
        mk.add(theme.title())
    mk.add('🔙 Назад')
    return mk

def post_type_menu():
    """Меню выбора типа поста"""
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    mk.add('📝 Пост без картинки')
    mk.add('🖼 Пост с картинкой')
    mk.add('🖼 Только картинка')
    mk.add('🔙 Назад')
    return mk

def session_diagnostic_menu():
    """Меню диагностики состояния"""
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('😔 Подавленность', '😰 Тревога')
    mk.add('😡 Раздражение', '😌 Спокойствие')
    mk.add('😊 Радость', '❌ Отмена')
    return mk

# ============================================================
# 💾 СЕССИИ
# ============================================================

sessions = {}  # Сессии тестов
consultations = {}  # Сессии консультаций

def save_user(chat_id, username=None, first_name=None, last_name=None):
    """Сохранение пользователя"""
    code = generate_referral_code(chat_id)
    c.execute("""INSERT OR IGNORE INTO users 
                 (chat_id, username, first_name, last_name, referral_code) 
                 VALUES (?, ?, ?, ?, ?)""",
              (chat_id, username, first_name, last_name, code))
    conn.commit()
    c.execute("UPDATE stats SET users_count = (SELECT COUNT(*) FROM users)")
    conn.commit()

# ============================================================
# 🚀 ОСНОВНЫЕ ОБРАБОТЧИКИ
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    try:
        chat_id = message.chat.id
        user = message.from_user
        save_user(chat_id, user.username, user.first_name, user.last_name)
        
        # Обработка параметров
        if ' ' in message.text:
            param = message.text.split(' ', 1)[1]
            if param.startswith('ref_'):
                process_referral(param.replace('ref_', ''), chat_id)
            elif param.startswith('test_'):
                test_id = param.replace('test_', '')
                c.execute("SELECT topic, questions FROM daily_tests WHERE id = ?", (test_id,))
                row = c.fetchone()
                if row:
                    topic, questions_json = row
                    questions = json.loads(questions_json)
                    sessions[chat_id] = {
                        'topic': topic,
                        'questions': questions,
                        'answers': [],
                        'q': 0,
                        'scores': [],
                        'is_paid': False
                    }
                    bot.send_message(chat_id, f"🔮 Загружаю тест: {topic}")
                    send_question(chat_id)
                    return
        
        bot.send_message(chat_id, "🌟 Добро пожаловать в Жизнь+!", 
                        reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка start: {e}")

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    """Информация о канале"""
    try:
        text = """🧠 ЖИЗНЬ+ — канал о том, что внутри.

Мы не даём ответов. Мы даём вопросы, которые меняют.

Автор — не психолог, не коуч.
Он — человек, который прошёл через своё дерьмо.

Подписывайся. Испытай на прочность свою честность.

@zhizn_plus"""
        
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Перейти в канал", 
                 url="https://t.me/zhizn_plus"))
        bot.send_message(message.chat.id, text, reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '📤 Поделиться')
def share_result(message):
    """Поделиться ссылкой"""
    try:
        chat_id = message.chat.id
        link = get_referral_link(chat_id)
        bot.send_message(
            chat_id,
            f"🧠 Я прохожу тесты в боте Жизнь+ и узнаю о себе новое.\n\n"
            f"Присоединяйся: {link}\n\n#жизньплюс #психология"
        )
        bot.send_message(chat_id, "✅ Поделился! Спасибо!")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================================
# 🎯 ТЕСТЫ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    """Выбор типа теста"""
    try:
        chat_id = message.chat.id
        c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
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
    start(message)

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный (10 вопросов)')
def free_test(message):
    show_topics(message, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов) — 50 Stars')
def paid_test(message):
    chat_id = message.chat.id
    c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    if row and row[0] > 0:
        c.execute("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        show_topics(message, 'paid', 20)
    else:
        send_invoice(chat_id, "test_20", PRICE_TEST_20)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов) — БЕСПЛАТНО (бонус)')
def paid_test_bonus(message):
    chat_id = message.chat.id
    c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    if row and row[0] > 0:
        c.execute("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        show_topics(message, 'paid', 20)
    else:
        bot.send_message(chat_id, "❌ Нет бонусных тестов.", reply_markup=test_type_menu())

@bot.callback_query_handler(func=lambda c: c.data == 'start_paid_test')
def start_paid_test_callback(c):
    chat_id = c.message.chat.id
    c.answer()
    c.execute("SELECT bonus_tests FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    if row and row[0] > 0:
        c.execute("UPDATE users SET bonus_tests = bonus_tests - 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        show_topics(c.message, 'paid', 20)
    else:
        bot.send_message(chat_id, "❌ У тебя нет бонусных тестов.", 
                        reply_markup=get_main_menu(chat_id))

def show_topics(message, test_type, count):
    """Показ тем для теста"""
    try:
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for topic in CHANNEL_THEMES[:15]:
            mk.add(telebot.types.InlineKeyboardButton(
                topic.title(), 
                callback_data=f"{test_type}_{topic}_{count}"
            ))
        mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
        bot.send_message(
            message.chat.id, 
            f"🔮 Выбери тему:\n\n{count} вопросов", 
            reply_markup=mk
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    """Обработчик выбора темы"""
    try:
        bot.answer_callback_query(c.id, "⏳ Генерация теста...")
        
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        bot.send_message(chat_id, "⏳ Генерация теста...\n⏱ Ожидание до 30 сек")
        
        def generate():
            try:
                questions = generate_test_questions(topic, count)
                if not questions:
                    bot.send_message(chat_id, "❌ AI не ответил. Попробуй позже.")
                    return
                
                sessions[chat_id] = {
                    'topic': topic,
                    'questions': questions,
                    'answers': [],
                    'q': 0,
                    'scores': [],
                    'is_paid': is_paid
                }
                send_question(chat_id)
            except Exception as e:
                logger.error(f"Ошибка генерации: {e}")
                bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")
        
        threading.Thread(target=generate, daemon=True).start()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, "❌ Отменено", 
                        reply_markup=get_main_menu(c.message.chat.id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    c.answer()

def send_question(chat_id):
    """Отправка вопроса теста"""
    s = sessions.get(chat_id)
    if not s or s['q'] >= len(s['questions']):
        finish_test(chat_id) if s else bot.send_message(
            chat_id, "❌ Сессия не найдена."
        )
        return
    
    q = s['questions'][s['q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for opt, txt in q['options'].items():
        mk.add(f"{opt}) {txt}")
    mk.add('⏹ Прервать тест')
    bot.send_message(
        chat_id, 
        f"🔮 Вопрос {s['q']+1}/{len(s['questions'])}\n\n{q['question']}", 
        reply_markup=mk
    )

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text and m.text[0].upper() in 'ABCD')
def handle_answer(message):
    """Обработка ответа на тест"""
    chat_id = message.chat.id
    s = sessions.get(chat_id)
    if not s or s['q'] >= len(s['questions']):
        return
    
    letter = message.text[0].upper()
    q = s['questions'][s['q']]
    score = q['scores'].get(letter, 0)
    s['answers'].append(letter)
    s['scores'].append(score)
    s['q'] += 1
    send_question(chat_id)

def finish_test(chat_id):
    """Завершение теста"""
    s = sessions.get(chat_id)
    if not s:
        return
    
    score = sum(s['scores'])
    total = len(s['questions']) * 3
    answers = ', '.join(s['answers'])
    is_paid = s.get('is_paid', False)
    
    # Обновляем статистику
    if is_paid:
        c.execute("UPDATE stats SET paid_test_count = paid_test_count + 1")
    else:
        c.execute("UPDATE stats SET free_count = free_count + 1")
    conn.commit()
    
    # Обновляем средний балл
    c.execute("SELECT avg_test_score FROM stats")
    row = c.fetchone()
    current_avg = row[0] if row else 0
    new_score = (score / total) * 100
    new_avg = (current_avg + new_score) / 2 if current_avg > 0 else new_score
    c.execute("UPDATE stats SET avg_test_score = ?", (new_avg,))
    conn.commit()
    
    bot.send_message(
        chat_id, 
        f"📊 Тест завершен!\nРезультат: {score} из {total}\n⏳ Анализирую...\n⏱ Ожидание до 30 сек"
    )
    
    analysis = generate_analysis(s['topic'], answers, score, total, is_paid)
    
    if analysis:
        try:
            bot.send_message(
                chat_id, 
                f"🔍 АНАЛИЗ\n\n{analysis}", 
                reply_markup=get_main_menu(chat_id), 
                parse_mode='Markdown'
            )
        except:
            bot.send_message(
                chat_id, 
                f"🔍 АНАЛИЗ\n\n{analysis}", 
                reply_markup=get_main_menu(chat_id)
            )
        
        if is_paid:
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton(
                "🎯 Коуч-сеанс за 100 Stars", 
                callback_data="buy_coach"
            ))
            bot.send_message(
                chat_id, 
                "🎯 Хочешь разобраться глубже? Пройди коуч-сеанс.", 
                reply_markup=mk
            )
    else:
        bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=get_main_menu(chat_id))
    
    if chat_id in sessions:
        del sessions[chat_id]

@bot.callback_query_handler(func=lambda c: c.data == 'buy_coach')
def buy_coach(c):
    send_invoice(c.message.chat.id, "coach", PRICE_COACH)
    c.answer()

# ============================================================
# 👑 АДМИН-ПАНЕЛЬ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '🧪 Тест AI')
def test_ai(message):
    """Тестирование AI"""
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🧪 Тестирую AI...")
        response = ask_ai("Ты — тестовый помощник.", "Напиши одно слово: 'ОК'", max_tokens=100)
        if response:
            bot.send_message(message.chat.id, f"✅ AI отвечает: {response}")
        else:
            bot.send_message(message.chat.id, "❌ AI не ответил.")

# ============================================================
# 📝 ПОСТЫ В КАНАЛ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '📝 Новый пост')
def new_post_menu(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📝 Что отправляем в канал?", 
                        reply_markup=post_type_menu())

@bot.message_handler(func=lambda m: m.text == '📝 Пост без картинки')
def post_without_image(message):
    if message.chat.id in ADMIN_IDS:
        sessions[message.chat.id] = {"action": "post_without_image"}
        bot.send_message(message.chat.id, "📝 Выбери тему:", reply_markup=theme_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def post_with_image(message):
    if message.chat.id in ADMIN_IDS:
        sessions[message.chat.id] = {"action": "post_with_image"}
        bot.send_message(message.chat.id, "📝 Выбери тему для поста с супер-картинкой:", 
                        reply_markup=theme_menu())

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
        c.execute("UPDATE stats SET images_generated = images_generated + 1")
        conn.commit()
        bot.send_message(chat_id, "✅ Супер-картинка отправлена!", reply_markup=admin_menu())
    else:
        bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())

# ============================================================
# 📊 СТАТИСТИКА
# ============================================================

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id in ADMIN_IDS:
        c.execute("""SELECT free_count, paid_test_count, coach_count, promo_used, 
                            users_count, posts_count, tests_created, images_generated, 
                            consultations_count, referrals_count, gifts_used, 
                            avg_test_score, total_revenue FROM stats""")
        row = c.fetchone()
        
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM gifts")
        gifts = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM checkins WHERE is_done = 0")
        checkins = c.fetchone()[0]
        
        revenue_rub = row[12] * 1.8 if row[12] else 0
        
        bot.send_message(
            message.chat.id,
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
            f"🎁 Подарков: {row[10]}\n"
            f"📊 Средний балл: {row[11]:.1f}%\n"
            f"💰 Доход (Stars): {row[12]}\n"
            f"💰 Доход (₽): ~{revenue_rub:.0f} руб.\n"
            f"⏳ Чек-инов: {checkins}",
            reply_markup=admin_menu()
        )

# ============================================================
# ⏰ РАСПИСАНИЕ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '⏰ Расписание')
def show_schedule(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(
            message.chat.id,
            "⏰ РАСПИСАНИЕ (Юрга UTC+7)\n\n"
            "📝 ПОСТЫ: 10:00, 16:00, 20:00\n"
            "🧠 ТЕСТ: 13:00\n"
            "🧠 ЧЕК-ИН: через 3 дня после сеанса",
            reply_markup=admin_menu()
        )

# ============================================================
# 📋 ЛОГИ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '📋 Логи')
def show_logs(message):
    if message.chat.id in ADMIN_IDS and os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            logs = ''.join(f.readlines()[-100:])
        bot.send_message(
            message.chat.id, 
            f"📋 ПОСЛЕДНИЕ 100 СТРОК:\n\n{logs[-4000:]}", 
            reply_markup=admin_menu()
        )
    else:
        bot.send_message(message.chat.id, "❌ Логов нет.", reply_markup=admin_menu())

# ============================================================
# 🖼 КАРТИНКИ В КАНАЛ
# ============================================================

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
        c.execute("UPDATE stats SET images_generated = images_generated + 1")
        conn.commit()
        bot.send_message(chat_id, "✅ Супер-картинка отправлена!", reply_markup=admin_menu())
    else:
        bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())

# ============================================================
# 🧠 ТЕСТЫ В КАНАЛ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def test_to_channel_start(message):
    if message.chat.id in ADMIN_IDS:
        sessions[message.chat.id] = {"action": "test_to_channel"}
        bot.send_message(message.chat.id, "🧠 Выбери тему для теста:", reply_markup=theme_menu())

# ============================================================
# 🎯 СЕАНС КОУЧИНГА
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎯 Сеанс коучинга')
def start_consultation(message):
    chat_id = message.chat.id
    start_consultation_logic(chat_id)

def start_consultation_logic(chat_id):
    """Начало консультации"""
    # Проверяем оплату
    c.execute("SELECT id FROM payments WHERE chat_id = ? AND (product = 'coach' OR product = 'coach_gift') AND status = 'completed'", (chat_id,))
    if not c.fetchone():
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    
    bot.send_message(
        chat_id,
        "🧠 ПЕРЕД СЕАНСОМ\n\n"
        "Как ты себя чувствуешь прямо сейчас?\n"
        "Это поможет мне подобрать правильные вопросы.",
        reply_markup=session_diagnostic_menu()
    )

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
    c.execute("SELECT id FROM payments WHERE chat_id = ? AND (product = 'coach' OR product = 'coach_gift') AND status = 'completed'", (chat_id,))
    if not c.fetchone():
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    
    diagnostic = consultations.get(chat_id, {}).get("diagnostic", "неизвестно")
    
    bot.send_message(
        chat_id,
        f"🎯 Начинаем сеанс.\nТвоё состояние: {diagnostic}\n\n"
        "Генерирую вопросы специально для тебя...\n⏱ Ожидание до 30 сек"
    )
    
    def generate():
        try:
            questions = generate_consultation_questions()
            if not questions:
                bot.send_message(chat_id, "❌ Не удалось сгенерировать вопросы.", 
                               reply_markup=get_main_menu(chat_id))
                if chat_id in consultations:
                    del consultations[chat_id]
                return
            
            # Сохраняем сессию
            c.execute("""INSERT INTO consultation_sessions 
                         (chat_id, questions, diagnostic) 
                         VALUES (?, ?, ?)""",
                      (chat_id, json.dumps(questions), diagnostic))
            conn.commit()
            session_id = c.lastrowid
            
            consultations[chat_id] = {
                "questions": questions,
                "answers": [],
                "current_q": 0,
                "session_id": session_id,
                "diagnostic": diagnostic
            }
            send_consultation_question(chat_id)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            bot.send_message(chat_id, f"❌ Ошибка: {str(e)}", 
                           reply_markup=get_main_menu(chat_id))
    
    threading.Thread(target=generate, daemon=True).start()

def send_consultation_question(chat_id):
    """Отправка вопроса консультации"""
    s = consultations.get(chat_id)
    if not s or s['current_q'] >= len(s['questions']):
        finish_consultation(chat_id)
        return
    
    q = s['questions'][s['current_q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    mk.add('⏹ Завершить сеанс')
    
    bot.send_message(
        chat_id,
        f"🧠 Вопрос {s['current_q']+1}/{len(s['questions'])}\n\n{q['question']}",
        reply_markup=mk
    )

@bot.message_handler(func=lambda m: m.text == '⏹ Завершить сеанс' and m.chat.id in consultations)
def stop_consultation(message):
    chat_id = message.chat.id
    if chat_id in consultations:
        s = consultations[chat_id]
        if len(s['answers']) >= 5:
            finish_consultation(chat_id)
        else:
            del consultations[chat_id]
            bot.send_message(chat_id, "⏹ Сеанс прерван. Жаль, что не дошли до конца.", 
                           reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text and m.chat.id in consultations and m.text != '⏹ Завершить сеанс')
def handle_consultation_answer(message):
    chat_id = message.chat.id
    s = consultations.get(chat_id)
    if not s:
        return
    
    s['answers'].append(message.text)
    s['current_q'] += 1
    send_consultation_question(chat_id)

def finish_consultation(chat_id):
    """Завершение консультации"""
    s = consultations.get(chat_id)
    if not s:
        return
    
    answers_text = '\n\n'.join([f"{i+1}. {ans}" for i, ans in enumerate(s['answers'])])
    
    bot.send_message(chat_id, "🧠 Анализирую твои ответы...\n⏱ Это займёт до 60 секунд")
    
    def generate():
        analysis = generate_consultation_analysis(answers_text, chat_id, s['session_id'])
        if analysis:
            try:
                bot.send_message(
                    chat_id, 
                    f"🔍 РАЗБОР ЛИЧНОСТИ\n\n{analysis}", 
                    reply_markup=get_main_menu(chat_id), 
                    parse_mode='Markdown'
                )
            except:
                bot.send_message(
                    chat_id, 
                    f"🔍 РАЗБОР ЛИЧНОСТИ\n\n{analysis}", 
                    reply_markup=get_main_menu(chat_id)
                )
            
            # Задания
            tasks = """📝 ЗАДАНИЯ НА НЕДЕЛЮ:

1. Каждое утро записывай 3 вещи, за которые ты благодарен(на)
2. Замечай свои эмоции и записывай их в дневник
3. Делай упражнение «Я выбираю...» вместо «Я должен...»

Через 3 дня я спрошу, как у тебя дела."""
            bot.send_message(chat_id, tasks)
        else:
            bot.send_message(chat_id, "❌ Не удалось получить анализ. Попробуй позже.", 
                           reply_markup=get_main_menu(chat_id))
        
        if chat_id in consultations:
            del consultations[chat_id]
    
    threading.Thread(target=generate, daemon=True).start()

# ============================================================
# 🎫 ПРОМОКОДЫ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🎫 Введите код (латиница, 3+ символов):")
        bot.register_next_step_handler(message, process_create_promo)

def process_create_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    if code == "ОТМЕНА" or len(code) < 3:
        bot.send_message(chat_id, "❌ Отменено или слишком короткий.", reply_markup=admin_menu())
        return
    try:
        c.execute("INSERT INTO promocodes (code, created_by) VALUES (?, ?)", (code, chat_id))
        conn.commit()
        bot.send_message(
            chat_id, 
            f"✅ Промокод создан!\n\n📌 Код: {code}\nДаёт 1 бесплатный тест из 20 вопросов.",
            reply_markup=admin_menu()
        )
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Уже существует.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(message.chat.id, "🎫 Введите промокод:", 
                    reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id))
        return
    if row[1] != 0:
        bot.send_message(chat_id, "❌ Уже использован.", reply_markup=get_main_menu(chat_id))
        return
    c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?",
             (chat_id, datetime.now().isoformat(), row[0]))
    conn.commit()
    c.execute("UPDATE stats SET promo_used = promo_used + 1")
    conn.commit()
    c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (chat_id,))
    conn.commit()
    bot.send_message(
        chat_id, 
        "🎉 Промокод активирован! Ты получил 1 бесплатный тест из 20 вопросов. Нажми «🎯 Пройти тест» и выбери платный.",
        reply_markup=get_main_menu(chat_id)
    )

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
        c.execute("INSERT INTO gifts (code, created_by, max_uses, expires_at) VALUES (?, ?, ?, ?)",
                 (code, chat_id, max_uses, expires_at))
        conn.commit()
        bot.send_message(
            chat_id,
            f"✅ ПОДАРОК СОЗДАН!\n\n🎁 Код: {code}\n📊 Сеансов: {max_uses}\n📅 Действует до: {expires_at[:10]}\nДаёт бесплатный коуч-сеанс.",
            reply_markup=admin_menu()
        )
        if chat_id in sessions:
            del sessions[chat_id]
    except:
        bot.send_message(message.chat.id, "❌ Введите число от 1 до 365.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎁 Активировать подарок')
def activate_gift_start(message):
    bot.send_message(message.chat.id, "🎁 Введите код подарка:", 
                    reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_gift_activation)

def process_gift_activation(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    c.execute("SELECT id, max_uses, used_count, expires_at FROM gifts WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id))
        return
    gift_id, max_uses, used_count, expires_at = row
    if expires_at and datetime.now(TIMEZONE).isoformat() > expires_at:
        bot.send_message(chat_id, "❌ Срок истёк.", reply_markup=get_main_menu(chat_id))
        return
    if used_count >= max_uses:
        bot.send_message(chat_id, "❌ Код использован.", reply_markup=get_main_menu(chat_id))
        return
    c.execute("UPDATE gifts SET used_count = used_count + 1 WHERE id = ?", (gift_id,))
    conn.commit()
    c.execute("UPDATE stats SET gifts_used = gifts_used + 1")
    conn.commit()
    c.execute("INSERT INTO payments (chat_id, amount, product, status) VALUES (?, 0, 'coach_gift', 'completed')", (chat_id,))
    conn.commit()
    bot.send_message(
        chat_id,
        "🎉 ПОДАРОК АКТИВИРОВАН!\n\nТы получил бесплатный коуч-сеанс.\nНажми кнопку ниже, чтобы начать.",
        reply_markup=telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("🎯 Начать коуч-сеанс", callback_data="start_coach")
        )
    )

@bot.callback_query_handler(func=lambda c: c.data == 'start_coach')
def start_coach_from_callback(c):
    chat_id = c.message.chat.id
    c.answer()
    c.execute("SELECT id FROM payments WHERE chat_id = ? AND (product = 'coach' OR product = 'coach_gift') AND status = 'completed'", (chat_id,))
    if not c.fetchone():
        send_invoice(chat_id, "coach", PRICE_COACH)
        return
    start_consultation_logic(chat_id)

# ============================================================
# 🔄 ОБЩИЙ ОБРАБОТЧИК ТЕМ ДЛЯ АДМИНА
# ============================================================

@bot.message_handler(func=lambda m: m.text in [t.title() for t in CHANNEL_THEMES] and m.chat.id in ADMIN_IDS)
def handle_theme_selection(message):
    try:
        chat_id = message.chat.id
        theme = message.text.lower()
        action = sessions.get(chat_id, {}).get("action")
        
        if action == "test_to_channel":
            bot.send_message(chat_id, f"⏳ Генерация теста...")
            questions = generate_test_questions(theme, 10)
            if not questions:
                bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())
                sessions[chat_id] = {}
                return
            
            # Сохраняем в БД
            c.execute("INSERT INTO daily_tests (topic, questions) VALUES (?, ?)",
                     (theme, json.dumps(questions)))
            conn.commit()
            test_id = c.lastrowid
            c.execute("UPDATE stats SET tests_created = tests_created + 1")
            conn.commit()
            
            bot_info = bot.get_me()
            test_text = f"🔮 ТЕСТ: «{theme.title()}» (10 вопросов)\n\n"
            for i, q in enumerate(questions[:5], 1):
                test_text += f"{i}. {q['question']}\n"
                for opt, txt in q['options'].items():
                    test_text += f"   {opt}) {txt}\n"
                test_text += "\n"
            test_text += f"... и ещё {len(questions)-5} вопросов\n\n🎯 Пройти полный тест: @{bot_info.username}?start=test_{test_id}"
            
            bot.send_message(CHANNEL_ID, test_text)
            bot.send_message(chat_id, "✅ Тест отправлен!", reply_markup=admin_menu())
            sessions[chat_id] = {}
            
        elif action == "post_without_image":
            post = generate_post(theme)
            if post:
                c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
                c.execute("UPDATE stats SET posts_count = posts_count + 1")
                conn.commit()
                bot.send_message(CHANNEL_ID, post)
                bot.send_message(chat_id, "✅ Пост отправлен!", reply_markup=admin_menu())
            else:
                bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())
            sessions[chat_id] = {}
            
        elif action == "post_with_image":
            post = generate_post(theme)
            if post:
                img = generate_post_image(theme)
                c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)",
                         (post, theme, img or ""))
                c.execute("UPDATE stats SET posts_count = posts_count + 1")
                if img:
                    c.execute("UPDATE stats SET images_generated = images_generated + 1")
                conn.commit()
                
                if img:
                    caption = post[:900] + "..." if len(post) > 900 else post
                    with open(img, 'rb') as photo:
                        bot.send_photo(CHANNEL_ID, photo, caption=caption)
                    os.remove(img)
                    if len(post) > 900:
                        bot.send_message(CHANNEL_ID, post)
                else:
                    bot.send_message(CHANNEL_ID, post)
                
                bot.send_message(chat_id, "✅ Пост с супер-картинкой отправлен!", 
                               reply_markup=admin_menu())
            else:
                bot.send_message(chat_id, "❌ Ошибка.", reply_markup=admin_menu())
            sessions[chat_id] = {}
        else:
            bot.send_message(chat_id, "❌ Сначала выбери действие в админке.", 
                           reply_markup=admin_menu())
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}", reply_markup=admin_menu())

# ============================================================
# 🚀 ЗАПУСК БОТА
# ============================================================

def start_bot():
    """Запуск бота"""
    try:
        logger.info("🤖 ЗАПУСК БОТА...")
        
        # Запуск планировщика
        scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler_thread.start()
        logger.info("✅ Планировщик запущен")
        
        # Удаление вебхука
        kill_409()
        
        # Запуск бота
        logger.info(f"✅ {BOT_NAME} v{BOT_VERSION} ГОТОВ К РАБОТЕ")
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(traceback.format_exc())
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    # Проверка ключей
    logger.info("🔐 ПРОВЕРКА КЛЮЧЕЙ:")
    logger.info(f"✓ BOT_TOKEN: {BOT_TOKEN[:10]}...")
    logger.info(f"✓ AGNES_API_KEY: {AGNES_API_KEY[:10]}...")
    logger.info(f"✓ OPENROUTER_API_KEY: {OPENROUTER_API_KEY[:10]}...")
    
    start_bot()
