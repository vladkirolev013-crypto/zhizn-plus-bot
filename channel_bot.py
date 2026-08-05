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

# Agnes AI
AGNES_API_KEY = "sk-8nqC897jST7vx1brGMUTNLRsVGPXgP7Bcpuwmbl5quaCLN5c"
AGNES_API_URL = "https://apihub.agnes-ai.com/v1/images/generations"

TIMEZONE = ZoneInfo("Asia/Novokuznetsk")

BOT_VERSION = "11.0.0"
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

# ============================================================
# ЦЕНЫ В ЗВЁЗДАХ
# ============================================================

PRICE_TEST_20 = 50
PRICE_COACH = 100

# ============================================================
# AI-ПРОВАЙДЕРЫ
# ============================================================

AI_PROVIDERS = [
    {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openrouter/free",
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
# УБИЙЦА 409
# ============================================================

def super_kill_409():
    try:
        for i in range(30):
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                requests.post(url, json={"drop_pending_updates": True}, timeout=10)
                time.sleep(0.1)
            except:
                pass
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
        except:
            pass
        patterns = ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid']
        for pattern in patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                except:
                    pass
        logger.info("🔥 409 УНИЧТОЖЕН")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

for i in range(3):
    super_kill_409()
    time.sleep(2)

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
# ГЕНЕРАЦИЯ СУПЕР-КАРТИНОК (AGNES AI + ЕВРОПА)
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

def generate_test_image(topic):
    prompts = [
        f"psychological test illustration {topic}, brain, introspection, deep colors",
        f"abstract psychology art {topic}, meditation, self reflection, calm",
        f"mental health awareness {topic}, healing, balance, harmony"
    ]
    return generate_image(random.choice(prompts))

def generate_result_image(text, result):
    prompt = f"minimalist psychology illustration, {text}, {result}, inspirational, soft colors, self discovery"
    return generate_image(prompt)

# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def init_database():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
        bonus_tests INTEGER DEFAULT 0
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
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

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
        try:
            c.execute("""INSERT INTO consultation_history (chat_id, session_id, questions, answers, analysis) VALUES (?, ?, ?, ?, ?)""",
                      (chat_id, session_id, "", answers, response))
            conn.commit()
            c.execute("UPDATE stats SET consultations_count = consultations_count + 1")
            conn.commit()
            
            checkin_date = datetime.now() + timedelta(days=3)
            c.execute("""INSERT INTO checkins (chat_id, session_id, checkin_date) VALUES (?, ?, ?)""",
                      (chat_id, session_id, checkin_date.isoformat()))
            conn.commit()
            
        except:
            pass
        return response
    return None

# ============================================================
# РЕФЕРАЛЬНАЯ СИСТЕМА
# ============================================================

def generate_referral_code(chat_id):
    code = f"REF{chat_id}{random.randint(1000,9999)}"
    return code[:10]

def get_referral_link(chat_id):
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
    c.execute("SELECT chat_id FROM users WHERE referral_code = ?", (referral_code,))
    row = c.fetchone()
    if row:
        referrer_id = row[0]
        if referrer_id != new_user_id:
            c.execute("SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, new_user_id))
            if not c.fetchone():
                c.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, new_user_id))
                conn.commit()
                c.execute("UPDATE stats SET referrals_count = referrals_count + 1")
                conn.commit()
                
                c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (referrer_id,))
                conn.commit()
                
                try:
                    bot.send_message(referrer_id, 
                        "🎉 По твоей ссылке пришёл новый пользователь!\n"
                        "Ты получил БЕСПЛАТНЫЙ тест из 20 вопросов в подарок.\n"
                        "Нажми «🎯 Пройти тест» и выбери платный тест — он будет бесплатным!")
                except:
                    pass
                
                return True
    return False

# ============================================================
# ОПЛАТА ЧЕРЕЗ TELEGRAM STARS
# ============================================================

def send_invoice(chat_id, product, amount):
    if product == "test_20":
        title = "🧠 Тест из 20 вопросов"
        desc = "Полный психологический разбор личности. Результат через 30 секунд."
    elif product == "coach":
        title = "🎯 Коуч-сеанс"
        desc = "25 вопросов + полный разбор + план действий + задания на неделю."
    else:
        return
    
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
        
        c.execute("""INSERT INTO payments (chat_id, amount, product, status) VALUES (?, ?, ?, ?)""",
                  (chat_id, payment.total_amount, product, "completed"))
        conn.commit()
        
        if product == "test_20":
            c.execute("UPDATE stats SET paid_test_count = paid_test_count + 1")
            conn.commit()
            bot.send_message(chat_id, "✅ Оплата прошла успешно!\n\nТы можешь пройти полный тест из 20 вопросов.\nНажми «🎯 Пройти тест» и выбери «💎 Платный».")
            
        elif product == "coach":
            c.execute("UPDATE stats SET coach_count = coach_count + 1")
            conn.commit()
            bot.send_message(chat_id, "✅ Оплата прошла успешно!\n\nТы можешь пройти коуч-сеанс.\nНажми «👑 Админ-панель» → «🎯 Сеанс коучинга».")
            
    except Exception as e:
        logger.error(f"Ошибка обработки оплаты: {e}")

# ============================================================
# ПЛАНИРОВЩИК
# ============================================================

def get_schedule():
    now = datetime.now(TIMEZONE)
    tasks = []
    schedule_posts = [10, 16, 20]
    for hour in schedule_posts:
        if now.hour == hour and now.minute == 0:
            c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 10")
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
    if now.hour == 13 and now.minute == 0:
        topic = random.choice(CHANNEL_THEMES)
        tasks.append({"type": "test", "topic": topic, "count": 10, "is_paid": False})
    
    if now.minute == 0:
        c.execute("""SELECT chat_id, session_id FROM checkins 
                     WHERE is_done = 0 AND checkin_date <= ?""", 
                  (now.isoformat(),))
        checkins = c.fetchall()
        for chat_id, session_id in checkins:
            tasks.append({"type": "checkin", "chat_id": chat_id, "session_id": session_id})
            c.execute("UPDATE checkins SET is_done = 1 WHERE chat_id = ? AND session_id = ?", (chat_id, session_id))
            conn.commit()
    
    return tasks

def scheduler_loop():
    while True:
        try:
            tasks = get_schedule()
            for task in tasks:
                if task["type"] == "post":
                    post = generate_post(task["topic"])
                    if post:
                        img = generate_post_image(task["topic"])
                        if img:
                            with open(img, 'rb') as photo:
                                bot.send_photo(CHANNEL_ID, photo, caption=post)
                            os.remove(img)
                        else:
                            bot.send_message(CHANNEL_ID, post)
                elif task["type"] == "test":
                    questions = generate_test_questions(task["topic"], 10)
                    if questions:
                        bot_info = bot.get_me()
                        test_text = f"🔮 ТЕСТ ДНЯ: «{task['topic'].title()}» (10 вопросов)\n\n"
                        for i, q in enumerate(questions[:3], 1):
                            test_text += f"{i}. {q['question']}\n"
                        test_text += f"\n🎯 Пройти полный тест в боте: @{bot_info.username}?start=test_daily"
                        bot.send_message(CHANNEL_ID, test_text)
                elif task["type"] == "checkin":
                    try:
                        bot.send_message(
                            task["chat_id"],
                            "🧠 Привет! Прошло 3 дня после нашего сеанса.\n\n"
                            "Как ты себя чувствуешь?\n"
                            "Что изменилось?\n"
                            "Есть ли что-то, что я могу сделать для тебя?\n\n"
                            "Напиши мне — я здесь."
                        )
                    except:
                        pass
            time.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
            time.sleep(60)

# ============================================================
# TELEGRAM БОТ
# ============================================================

bot = telebot.TeleBot(BOT_TOKEN)

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
    try:
        c.execute("""INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name, referral_code) 
                     VALUES (?, ?, ?, ?, ?)""",
                  (chat_id, username, first_name, last_name, generate_referral_code(chat_id)))
        conn.commit()
        c.execute("UPDATE stats SET users_count = (SELECT COUNT(*) FROM users)")
        conn.commit()
    except:
        pass

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
                referral_code = param.replace('ref_', '')
                process_referral(referral_code, chat_id)
        
        bot.send_message(chat_id, "🌟 Добро пожаловать в Жизнь+!", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

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
        bot.send_message(chat_id, "✅ Поделился! Спасибо, что помогаешь другим найти себя.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    try:
        text = """🧠 **ЖИЗНЬ+** — канал о том, что внутри.

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
        bot.send_message(message.chat.id, text, reply_markup=mk, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
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

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        bot.edit_message_text("⏳ Генерация теста...\n⏱ Ожидание до 30 сек", chat_id, c.message.message_id)
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
        bot.delete_message(chat_id, c.message.message_id)
        send_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        try:
            bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")
        except:
            pass
    c.answer()

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

@bot.message_handler(func=lambda m: m.text and m.text[0] in 'ABCD')
def handle_answer(message):
    try:
        chat_id = message.chat.id
        s = sessions.get(chat_id)
        if not s or s['q'] >= len(s['questions']):
            return
        letter = message.text[0]
        q = s['questions'][s['q']]
        s['answers'].append(letter)
        s['scores'].append(q['scores'][letter])
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
        
        if is_paid:
            c.execute("UPDATE stats SET paid_test_count = paid_test_count + 1")
        else:
            c.execute("UPDATE stats SET free_count = free_count + 1")
        conn.commit()
        
        bot.send_message(chat_id, f"📊 Тест завершен!\nРезультат: {score} из {total}\n⏳ Анализирую...\n⏱ Ожидание до 30 сек")
        analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
        
        if analysis:
            bot.send_message(chat_id, f"🔍 АНАЛИЗ\n\n{analysis}", reply_markup=get_main_menu(chat_id))
            
            if is_paid:
                mk = telebot.types.InlineKeyboardMarkup()
                mk.add(telebot.types.InlineKeyboardButton("🎯 Коуч-сеанс за 100 Stars", callback_data="buy_coach"))
                bot.send_message(chat_id, "🎯 Хочешь разобраться глубже? Пройди коуч-сеанс — 25 вопросов + план действий.", reply_markup=mk)
        else:
            bot.send_message(chat_id, "❌ AI не ответил. Попробуй позже.", reply_markup=get_main_menu(chat_id))
        if chat_id in sessions:
            del sessions[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data == 'buy_coach')
def buy_coach(c):
    try:
        chat_id = c.message.chat.id
        send_invoice(chat_id, "coach", PRICE_COACH)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    c.answer()

# ============================================================
# АДМИН-ПАНЕЛЬ
# ============================================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

# -------------------- НОВЫЙ ПОСТ --------------------

@bot.message_handler(func=lambda m: m.text == '📝 Новый пост')
def new_post_menu(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "📝 Что отправляем в канал?", reply_markup=post_type_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '📝 Пост без картинки')
def post_without_image(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        sessions[message.chat.id] = {"action": "post_without_image"}
        bot.send_message(message.chat.id, "📝 Выбери тему для поста:", reply_markup=theme_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def post_with_image(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        sessions[message.chat.id] = {"action": "post_with_image"}
        bot.send_message(message.chat.id, "📝 Выбери тему для поста с супер-картинкой:", reply_markup=theme_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🖼 Только картинка')
def only_image(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "📝 Введи описание для супер-картинки:")
        bot.register_next_step_handler(message, process_only_image)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_only_image(message):
    try:
        chat_id = message.chat.id
        prompt = message.text
        bot.send_message(chat_id, "🖼 Генерация супер-картинки...\n⏱ Ожидание до 30 сек")
        image_path = generate_image(prompt)
        if image_path:
            with open(image_path, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=f"🖼 {prompt}")
            os.remove(image_path)
            c.execute("UPDATE stats SET images_generated = images_generated + 1")
            conn.commit()
            bot.send_message(chat_id, "✅ Супер-картинка отправлена в канал!", reply_markup=admin_menu())
        else:
            bot.send_message(chat_id, "❌ Не удалось создать картинку.", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- СТАТИСТИКА --------------------

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        c.execute("SELECT free_count, paid_test_count, coach_count, promo_used, users_count, posts_count, tests_created, images_generated, consultations_count, referrals_count, gifts_used FROM stats")
        stats_row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM gifts")
        gifts_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM checkins WHERE is_done = 0")
        pending_checkins = c.fetchone()[0]
        
        stats_text = f"""📊 СТАТИСТИКА

👥 Пользователей: {users_count}
🧠 Бесплатных тестов: {stats_row[0] if stats_row else 0}
💎 Платных тестов: {stats_row[1] if stats_row else 0}
🎯 Коуч-сеансов: {stats_row[2] if stats_row else 0}
🎫 Промокодов: {stats_row[3] if stats_row else 0}
📤 Постов: {stats_row[4] if stats_row else 0}
🧠 Тестов создано: {stats_row[5] if stats_row else 0}
🖼 Супер-картинок: {stats_row[6] if stats_row else 0}
🎯 Консультаций: {stats_row[7] if stats_row else 0}
👥 Рефералов: {stats_row[8] if stats_row else 0}
🎁 Подарков активировано: {stats_row[9] if stats_row else 0}
🎁 Подарков создано: {gifts_count}
⏳ Чек-инов: {pending_checkins}"""
        bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- РАСПИСАНИЕ --------------------

@bot.message_handler(func=lambda m: m.text == '⏰ Расписание')
def show_schedule(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        schedule_text = """⏰ РАСПИСАНИЕ (Юрга UTC+7)

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
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- ЛОГИ --------------------

@bot.message_handler(func=lambda m: m.text == '📋 Логи')
def show_logs(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-50:] if len(lines) > 50 else lines
                logs = ''.join(last_lines)
                if len(logs) > 4000:
                    logs = logs[-4000:]
                bot.send_message(chat_id, f"📋 ПОСЛЕДНИЕ 50 СТРОК ЛОГОВ:\n\n```\n{logs}\n```", parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "❌ Файл логов не найден.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {e}")

# -------------------- КАРТИНКИ В КАНАЛ --------------------

@bot.message_handler(func=lambda m: m.text == '🖼 Картинка в канал')
def image_to_channel(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "📝 Введи описание для супер-картинки:")
        bot.register_next_step_handler(message, process_image_only_standalone)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_image_only_standalone(message):
    try:
        chat_id = message.chat.id
        prompt = message.text
        bot.send_message(chat_id, "🖼 Генерация супер-картинки...\n⏱ Ожидание до 30 сек")
        image_path = generate_image(prompt)
        if image_path:
            with open(image_path, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=f"🖼 {prompt}")
            os.remove(image_path)
            c.execute("UPDATE stats SET images_generated = images_generated + 1")
            conn.commit()
            bot.send_message(chat_id, "✅ Супер-картинка отправлена в канал!", reply_markup=admin_menu())
        else:
            bot.send_message(chat_id, "❌ Не удалось создать картинку.", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- ТЕСТЫ В КАНАЛ --------------------

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def test_to_channel_start(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        sessions[message.chat.id] = {"action": "test_to_channel"}
        bot.send_message(message.chat.id, "🧠 Выбери тему для теста:", reply_markup=theme_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- КОУЧ-СЕАНС --------------------

@bot.message_handler(func=lambda m: m.text == '🎯 Сеанс коучинга')
def start_consultation(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        
        # Проверяем, оплачен ли сеанс или есть подарок
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
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text in ['😔 Подавленность', '😰 Тревога', '😡 Раздражение', '😌 Спокойствие', '😊 Радость'])
def handle_diagnostic(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
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

@bot.message_handler(func=lambda m: m.text == '❌ Отмена' and m.chat.id in ADMIN_IDS)
def cancel_consultation(message):
    try:
        chat_id = message.chat.id
        bot.send_message(chat_id, "❌ Сеанс отменён.", reply_markup=admin_menu())
        if chat_id in consultations:
            del consultations[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '✅ Начать' and m.chat.id in ADMIN_IDS)
def confirm_consultation(message):
    try:
        chat_id = message.chat.id
        
        diagnostic = consultations.get(chat_id, {}).get("diagnostic", "неизвестно")
        
        bot.send_message(
            chat_id,
            f"🎯 Начинаем сеанс.\nТвоё состояние: {diagnostic}\n\n"
            "Генерирую вопросы специально для тебя...\n⏱ Ожидание до 30 сек",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        
        questions = generate_consultation_questions()
        if not questions:
            bot.send_message(chat_id, "❌ Не удалось сгенерировать вопросы.", reply_markup=admin_menu())
            if chat_id in consultations:
                del consultations[chat_id]
            return
        
        c.execute("""INSERT INTO consultation_sessions (chat_id, questions, current_q, is_active, is_paid) VALUES (?, ?, ?, ?, ?)""",
                  (chat_id, json.dumps(questions), 0, 1, 1))
        conn.commit()
        session_id = c.lastrowid
        
        consultations[chat_id] = {
            "session_id": session_id,
            "questions": questions,
            "answers": [],
            "q": 0,
            "diagnostic": diagnostic
        }
        
        send_consultation_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def send_consultation_question(chat_id):
    try:
        s = consultations.get(chat_id)
        if not s:
            bot.send_message(chat_id, "❌ Сессия не найдена.", reply_markup=admin_menu())
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
            bot.send_message(chat_id, "❌ Нет активного сеанса.", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def finish_consultation(chat_id):
    try:
        s = consultations.get(chat_id)
        if not s:
            bot.send_message(chat_id, "❌ Сессия не найдена.", reply_markup=admin_menu())
            return
        
        c.execute("UPDATE consultation_sessions SET is_active = 0 WHERE id = ?", (s['session_id'],))
        conn.commit()
        
        if len(s['answers']) == 0:
            bot.send_message(chat_id, "❌ Сеанс прерван.", reply_markup=admin_menu())
            if chat_id in consultations:
                del consultations[chat_id]
            return
        
        bot.send_message(chat_id, "📊 Обрабатываю ответы...\n⏱ Это займёт 1–2 минуты.", reply_markup=admin_menu())
        
        def background_analysis():
            try:
                answers_text = "\n".join([f"{i+1}. {a}" for i, a in enumerate(s['answers'])])
                analysis = generate_consultation_analysis(answers_text, chat_id, s['session_id'])
                
                tasks = [
                    "🟢 Задание 1: Напиши 3 вещи, за которые ты благодарен сегодня",
                    "🟢 Задание 2: Скажи себе в зеркале: 'Я справлюсь'",
                    "🟢 Задание 3: 5 минут тишины без телефона"
                ]
                tasks_text = "\n\n📋 **ТВОИ ЗАДАНИЯ НА СЕГОДНЯ:**\n" + "\n".join(tasks)
                
                mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                mk.add('📤 Поделиться', '🚀 Старт')
                
                if analysis:
                    bot.send_message(
                        chat_id,
                        f"🔮 ПОЛНЫЙ РАЗБОР\n\n{analysis}\n\n{tasks_text}",
                        reply_markup=mk,
                        parse_mode='Markdown'
                    )
                else:
                    bot.send_message(
                        chat_id,
                        f"❌ Не удалось сгенерировать анализ.\n\n{tasks_text}",
                        reply_markup=mk,
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Ошибка фонового анализа: {e}")
                bot.send_message(chat_id, "❌ Ошибка при анализе.", reply_markup=admin_menu())
        
        threading.Thread(target=background_analysis, daemon=True).start()
        
        if chat_id in consultations:
            del consultations[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text and m.text not in ['✅ Начать', '❌ Отмена', '⏹ Завершить сеанс', '👑 Админ-панель', '👑 Главное меню'] and m.text not in [t.title() for t in CHANNEL_THEMES] and m.text not in ['😔 Подавленность', '😰 Тревога', '😡 Раздражение', '😌 Спокойствие', '😊 Радость'])
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
        c.execute("UPDATE consultation_sessions SET current_q = ?, answers = ? WHERE id = ?",
                  (s['q'], json.dumps(s['answers']), s['session_id']))
        conn.commit()
        send_consultation_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# -------------------- ОБЩИЙ ОБРАБОТЧИК --------------------

@bot.message_handler(func=lambda m: m.text in [t.title() for t in CHANNEL_THEMES] and m.chat.id in ADMIN_IDS)
def handle_theme_selection(message):
    try:
        chat_id = message.chat.id
        theme = message.text.lower()
        action = sessions.get(chat_id, {}).get("action")
        
        if action == "test_to_channel":
            # === ТЕСТ ===
            bot.send_message(chat_id, f"⏳ Генерация теста на тему '{theme}'...\n⏱ Ожидание до 30 сек")
            questions = generate_test_questions(theme, 10)
            if not questions:
                bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=admin_menu())
                sessions[chat_id] = {}
                return
            
            try:
                c.execute("""INSERT INTO daily_tests (topic, questions, created_at, is_paid) 
                             VALUES (?, ?, ?, ?)""",
                          (theme, json.dumps(questions), datetime.now().isoformat(), 0))
                conn.commit()
            except:
                pass
            
            test_text = f"🔮 ТЕСТ: «{theme.title()}» (10 вопросов)\n\n"
            for i, q in enumerate(questions[:5], 1):
                test_text += f"{i}. {q['question']}\n"
                for opt, txt in q['options'].items():
                    test_text += f"   {opt}) {txt}\n"
                test_text += "\n"
            test_text += f"... и ещё {len(questions)-5} вопросов\n\n"
            test_text += f"🎯 Пройди полный тест в боте: @{bot.get_me().username}?start=test_daily"
            
            try:
                bot.send_message(CHANNEL_ID, test_text)
                bot.send_message(chat_id, "✅ Тест отправлен в канал!", reply_markup=admin_menu())
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
            
            sessions[chat_id] = {}
            
        elif action == "post_without_image":
            # === ПОСТ БЕЗ КАРТИНКИ ===
            bot.send_message(chat_id, f"⏳ Генерация поста на тему '{theme}'...\n⏱ Ожидание до 30 сек")
            post = generate_post(theme)
            if not post:
                bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=admin_menu())
                sessions[chat_id] = {}
                return
            
            try:
                c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
                conn.commit()
                c.execute("UPDATE stats SET posts_count = posts_count + 1")
                conn.commit()
            except:
                pass
            
            bot.send_message(CHANNEL_ID, post)
            bot.send_message(chat_id, "✅ Пост отправлен в канал!", reply_markup=admin_menu())
            sessions[chat_id] = {}
            
        elif action == "post_with_image":
            # === ПОСТ С СУПЕР-КАРТИНКОЙ ===
            bot.send_message(chat_id, f"⏳ Генерация поста на тему '{theme}'...\n⏱ Ожидание до 30 сек")
            post = generate_post(theme)
            if not post:
                bot.send_message(chat_id, "❌ AI не ответил.", reply_markup=admin_menu())
                sessions[chat_id] = {}
                return
            
            bot.send_message(chat_id, "🖼 Генерация супер-картинки к посту...")
            image_path = generate_post_image(theme)
            
            try:
                c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", (post, theme, image_path if image_path else ""))
                conn.commit()
                c.execute("UPDATE stats SET posts_count = posts_count + 1")
                if image_path:
                    c.execute("UPDATE stats SET images_generated = images_generated + 1")
                conn.commit()
            except:
                pass
            
            try:
                if image_path:
                    caption = post[:900] + "..." if len(post) > 900 else post
                    with open(image_path, 'rb') as photo:
                        bot.send_photo(CHANNEL_ID, photo, caption=caption)
                    os.remove(image_path)
                    bot.send_message(CHANNEL_ID, post)
                else:
                    bot.send_message(CHANNEL_ID, post)
                bot.send_message(chat_id, "✅ Пост с супер-картинкой отправлен в канал!", reply_markup=admin_menu())
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
            
            sessions[chat_id] = {}
            
        else:
            bot.send_message(chat_id, "❌ Сначала выбери действие в админке", reply_markup=admin_menu())
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}", reply_markup=admin_menu())

# ============================================================
# ПРОМОКОДЫ (БЕСПЛАТНЫЙ ТЕСТ 20 ВОПРОСОВ)
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "🎫 Введите код (латиница, 3+ символов):")
        bot.register_next_step_handler(message, process_create_promo)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_create_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        if code == "ОТМЕНА":
            bot.send_message(chat_id, "❌ Отменено")
            return
        if not code or len(code) < 3:
            bot.send_message(chat_id, "❌ Минимум 3 символа", reply_markup=admin_menu())
            return
        try:
            c.execute("INSERT INTO promocodes (code, created_by, created_at) VALUES (?, ?, ?)",
                      (code, chat_id, datetime.now().isoformat()))
            conn.commit()
            bot.send_message(chat_id, f"✅ Промокод создан!\n\n📌 Код: `{code}`\nДаёт 1 бесплатный тест из 20 вопросов.", parse_mode='Markdown', reply_markup=admin_menu())
        except sqlite3.IntegrityError:
            bot.send_message(chat_id, "❌ Уже существует", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    try:
        bot.send_message(message.chat.id, "🎫 Введите промокод:", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, process_promo)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
        row = c.fetchone()
        if not row:
            bot.send_message(chat_id, "❌ Неверный код", reply_markup=get_main_menu(chat_id))
            return
        promo_id, used_by = row
        if used_by != 0:
            bot.send_message(chat_id, "❌ Уже использован", reply_markup=get_main_menu(chat_id))
            return
        c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
                  (chat_id, datetime.now().isoformat(), promo_id))
        conn.commit()
        c.execute("UPDATE stats SET promo_used = promo_used + 1")
        conn.commit()
        c.execute("UPDATE users SET bonus_tests = bonus_tests + 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        bot.send_message(chat_id, "🎉 Промокод активирован! Ты получил 1 бесплатный тест из 20 вопросов. Нажми «🎯 Пройти тест» и выбери платный.", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================================
# ПОДАРКИ (БЕСПЛАТНЫЙ КОУЧ-СЕАНС)
# ============================================================

@bot.message_handler(func=lambda m: m.text == '🎁 Создать подарок')
def create_gift(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "🎁 Введите количество сеансов (1-10):")
        bot.register_next_step_handler(message, process_gift_max_uses)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_gift_max_uses(message):
    try:
        chat_id = message.chat.id
        try:
            max_uses = int(message.text.strip())
            if max_uses < 1 or max_uses > 10:
                raise ValueError
        except:
            bot.send_message(chat_id, "❌ Введите число от 1 до 10.", reply_markup=admin_menu())
            return
        if chat_id not in sessions:
            sessions[chat_id] = {}
        sessions[chat_id]['gift_max_uses'] = max_uses
        bot.send_message(chat_id, "📅 Введите срок действия (дней):")
        bot.register_next_step_handler(message, process_gift_expires)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_gift_expires(message):
    try:
        chat_id = message.chat.id
        try:
            days = int(message.text.strip())
            if days < 1 or days > 365:
                raise ValueError
        except:
            bot.send_message(chat_id, "❌ Введите число от 1 до 365.", reply_markup=admin_menu())
            return
        max_uses = sessions.get(chat_id, {}).get('gift_max_uses', 1)
        code = "GIFT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()
        c.execute("""INSERT INTO gifts (code, created_by, max_uses, expires_at) VALUES (?, ?, ?, ?)""",
                  (code, chat_id, max_uses, expires_at))
        conn.commit()
        bot.send_message(
            chat_id,
            f"✅ ПОДАРОК СОЗДАН!\n\n🎁 Код: `{code}`\n📊 Сеансов: {max_uses}\n📅 Действует до: {expires_at[:10]}\nДаёт бесплатный коуч-сеанс.",
            parse_mode='Markdown',
            reply_markup=admin_menu()
        )
        if chat_id in sessions:
            del sessions[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎁 Активировать подарок')
def activate_gift_start(message):
    try:
        chat_id = message.chat.id
        bot.send_message(
            chat_id,
            "🎁 Введите код подарка:",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(message, process_gift_activation)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_gift_activation(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        c.execute("SELECT id, max_uses, used_count, expires_at FROM gifts WHERE code = ?", (code,))
        row = c.fetchone()
        if not row:
            bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id))
            return
        gift_id, max_uses, used_count, expires_at = row
        if expires_at and datetime.now().isoformat() > expires_at:
            bot.send_message(chat_id, "❌ Срок истёк.", reply_markup=get_main_menu(chat_id))
            return
        if used_count >= max_uses:
            bot.send_message(chat_id, "❌ Код использован.", reply_markup=get_main_menu(chat_id))
            return
        c.execute("UPDATE gifts SET used_count = used_count + 1 WHERE id = ?", (gift_id,))
        conn.commit()
        c.execute("UPDATE stats SET gifts_used = gifts_used + 1")
        conn.commit()
        # Записываем пользователю бонусный коуч-сеанс
        c.execute("INSERT INTO payments (chat_id, amount, product, status) VALUES (?, 0, 'coach_gift', 'completed')", (chat_id,))
        conn.commit()
        bot.send_message(chat_id, "🎉 ПОДАРОК АКТИВИРОВАН!\n\nТы получил бесплатный коуч-сеанс.\nНажми «👑 Админ-панель» → «🎯 Сеанс коучинга»", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, "❌ Ошибка при активации.", reply_markup=get_main_menu(chat_id))

# ============================================================
# ЗАПУСК БОТА
# ============================================================

def run_bot():
    logger.info(f"🤖 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")
    try:
        super_kill_409()
        time.sleep(2)
        bot.remove_webhook()
        logger.info("✅ Вебхук удален")
        bot.polling(none_stop=True, interval=0, timeout=20, allowed_updates=['message', 'callback_query'])
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        if "409" in str(e):
            logger.info("🔄 Обнаружена 409, жесткий перезапуск...")
            super_kill_409()
            time.sleep(3)
            run_bot()
        else:
            time.sleep(5)
            run_bot()

threading.Thread(target=scheduler_loop, daemon=True).start()
logger.info("✅ Планировщик запущен")

if __name__ == "__main__":
    logger.info("🚀 ПОДГОТОВКА К ЗАПУСКУ...")
    for i in range(3):
        logger.info(f"🔄 Предстартовый проход #{i+1}/3")
        super_kill_409()
        time.sleep(2)
    logger.info("🚀 СТАРТ БОТА...")
    run_bot()
