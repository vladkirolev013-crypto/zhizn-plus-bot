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
from datetime import datetime
from flask import Flask
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# НАСТРОЙКИ
# ============================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
ADMIN_IDS = [8746212340]

# ============================================
# 5 БЕСПЛАТНЫХ API (АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ)
# ============================================

AI_PROXIES = [
    {
        "name": "G4F",
        "url": "https://api.g4f.icu",
        "model": "gpt-4o-mini"
    },
    {
        "name": "Pawan",
        "url": "https://api.pawan.krd",
        "model": "gpt-3.5-turbo"
    },
    {
        "name": "SHN",
        "url": "https://chatgpt-api.shn.hk",
        "model": "gpt-3.5-turbo"
    },
    {
        "name": "REST",
        "url": "https://rest.ai",
        "model": "gpt-3.5-turbo"
    },
    {
        "name": "DeepAI",
        "url": "https://deepai.org",
        "model": "gpt-3.5-turbo"
    }
]

# ============================================
# ВЕРСИЯ
# ============================================

BOT_VERSION = "11.0.0"
BOT_NAME = "Жизнь+ AI"

DB_PATH = 'channel.db'
LOG_PATH = 'bot_logs.txt'

# ============================================
# ЛОГИРОВАНИЕ
# ============================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")

# ============================================
# УБИЙЦА 409
# ============================================

def super_kill_409():
    try:
        for i in range(15):
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                requests.post(url, json={"drop_pending_updates": True}, timeout=10)
                time.sleep(0.2)
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

# ============================================
# AI С АВТОМАТИЧЕСКИМ ПЕРЕКЛЮЧЕНИЕМ
# ============================================

def ask_ai(system, user, max_tokens=4000, retries=2):
    """Запрос к AI с автоматическим переключением между 5 API"""
    
    logger.info("="*80)
    logger.info("📤 ЗАПРОС К AI")
    logger.info(f"📝 Система: {system[:100]}...")
    logger.info(f"📝 Запрос: {user[:100]}...")
    
    if not user or len(user.strip()) == 0:
        user = "Сделай запрос."
    
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    
    # ПЕРЕБИРАЕМ ВСЕ ПРОКСИ
    for proxy in AI_PROXIES:
        for attempt in range(retries):
            try:
                logger.info(f"🔄 Прокси: {proxy['name']}, попытка {attempt+1}")
                
                payload = {
                    "model": proxy["model"],
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.95
                }
                
                start_time = time.time()
                
                response = requests.post(
                    f"{proxy['url']}/v1/chat/completions",
                    json=payload,
                    timeout=90,
                    verify=False
                )
                
                elapsed = time.time() - start_time
                logger.info(f"⏱ Ответ за {elapsed:.2f} сек")
                logger.info(f"📡 Статус: {response.status_code}")
                
                # Ждём 35 секунд (гарантия)
                if elapsed < 35:
                    wait_time = 35 - elapsed
                    logger.info(f"⏳ ОЖИДАНИЕ {wait_time:.1f} СЕКУНД")
                    time.sleep(wait_time)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if content and len(content) > 10:
                        logger.info(f"✅ ОТВЕТ ОТ {proxy['name']} ({len(content)} символов)")
                        return content
                    else:
                        logger.warning(f"⚠️ Пустой ответ от {proxy['name']}")
                else:
                    logger.warning(f"⚠️ Ошибка {proxy['name']}: {response.status_code}")
                
                time.sleep(1)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка {proxy['name']}: {e}")
                time.sleep(1)
        
        logger.info(f"⏳ {proxy['name']} не ответил, переключаюсь...")
    
    logger.error("❌ НИ ОДИН ИЗ 5 API НЕ ОТВЕТИЛ")
    return None

# ============================================
# ГЕНЕРАЦИЯ КАРТИНОК
# ============================================

def generate_image(prompt):
    try:
        clean_prompt = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "")
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=768&nologo=true&seed={random.randint(1,999999)}"
        
        logger.info("🖼 Генерация картинки...")
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200 and len(response.content) > 1000:
            filename = f"/tmp/image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"✅ Картинка создана")
            return filename
        
        return None
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

def generate_post_image(theme):
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational, peaceful",
        f"beautiful landscape {theme}, sunrise, hope, positive energy",
        f"minimalist illustration {theme}, soft pastel, calm, self discovery"
    ]
    return generate_image(random.choice(prompts))

def generate_test_image(topic):
    prompts = [
        f"psychological test illustration {topic}, brain, mind, introspection",
        f"abstract psychology art {topic}, meditation, self reflection, calm",
        f"mental health awareness {topic}, healing, balance, harmony"
    ]
    return generate_image(random.choice(prompts))

# ============================================
# БАЗА ДАННЫХ
# ============================================

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
        last_activity TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        free_count INTEGER DEFAULT 0,
        paid_count INTEGER DEFAULT 0,
        promo_used INTEGER DEFAULT 0,
        users_count INTEGER DEFAULT 0,
        posts_count INTEGER DEFAULT 0,
        tests_created INTEGER DEFAULT 0,
        images_generated INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO stats (free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated) VALUES (0, 0, 0, 0, 0, 0, 0)")
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions (
        chat_id INTEGER PRIMARY KEY,
        topic TEXT,
        questions TEXT,
        current_q INTEGER DEFAULT 0,
        answers TEXT,
        scores TEXT,
        is_paid INTEGER DEFAULT 0,
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
        image_path TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS used_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    logger.info("✅ БАЗА ДАННЫХ ИНИЦИАЛИЗИРОВАНА")

init_database()

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ============================================
# ТЕМЫ
# ============================================

POST_THEMES = [
    "внутренняя сила", "самооценка", "отношения", "деньги", "карьера",
    "эмоции", "страхи", "границы", "любовь к себе", "благодарность",
    "мотивация", "осознанность", "прощение", "энергия", "выбор"
]

TEST_TOPICS = {
    "психология": "🧠 Психология",
    "отношения": "💕 Отношения",
    "карьера": "💼 Карьера",
    "здоровье": "💪 Здоровье",
    "финансы": "💰 Финансы",
    "личность": "🌟 Личность"
}

def get_unique_theme():
    try:
        c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 30")
        used = [row[0] for row in c.fetchall()]
        available = [t for t in POST_THEMES if t not in used]
        if available:
            theme = random.choice(available)
        else:
            c.execute("DELETE FROM used_topics")
            conn.commit()
            theme = random.choice(POST_THEMES)
        c.execute("INSERT INTO used_topics (topic) VALUES (?) ON CONFLICT(topic) DO UPDATE SET used_at = CURRENT_TIMESTAMP", (theme,))
        conn.commit()
        return theme
    except:
        return random.choice(POST_THEMES)

# ============================================
# ГЕНЕРАТОР ПОСТА
# ============================================

def generate_post():
    theme = get_unique_theme()
    system = """Ты — автор канала о психологии. Напиши пост на тему.
    Минимум 800 символов. Пиши глубоко, честно, без пафоса."""
    user = f"Тема: {theme}. Пост 800+ символов."
    response = ask_ai(system, user, 4000)
    if response and len(response) >= 800:
        return response, theme
    return None, theme

# ============================================
# ГЕНЕРАТОР ТЕСТА
# ============================================

def generate_test_questions(topic, count=10):
    system = f"""Составь {count} вопросов для теста на тему "{topic}".
    Верни ТОЛЬКО JSON.
    Формат: [{{"question": "текст?", "options": {{"A": "вар1", "B": "вар2", "C": "вар3", "D": "вар4"}}, "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}}}]"""
    
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
    except:
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    if is_paid:
        system = """Ты — клинический психолог. Сделай полный разбор личности.
        Портрет, инсайты, корень проблемы, план на неделю."""
        user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
    else:
        system = """Ты — психолог. Дай краткий анализ. Назови главную проблему, дай 1 инсайт."""
        user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
    
    return ask_ai(system, user, 4000 if is_paid else 2500)

# ============================================
# TELEGRAM БОТ
# ============================================

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

# ============================================
# МЕНЮ
# ============================================

def get_main_menu(chat_id):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🚀 Старт', '🎯 Пройти тест')
    mk.add('🎫 Активировать промокод', '❤️ О канале')
    if chat_id in ADMIN_IDS:
        mk.add('👑 Админ-панель')
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('📤 Отправить пост', '🖼 Пост с картинкой')
    mk.add('🧠 Тест в канал', '📊 Статистика')
    mk.add('🎫 Создать промокод', '📋 Логи')
    mk.add('👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

sessions = {}

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        c.execute("INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                  (chat_id, username, first_name, last_name))
        conn.commit()
        c.execute("UPDATE stats SET users_count = (SELECT COUNT(*) FROM users)")
        conn.commit()
    except:
        pass

# ============================================
# КНОПКА ЛОГОВ
# ============================================

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

# ============================================
# ОБРАБОТЧИКИ
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    try:
        chat_id = message.chat.id
        user = message.from_user
        save_user(chat_id, user.username, user.first_name, user.last_name)
        bot.send_message(chat_id, "🌟 Добро пожаловать!", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    try:
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Перейти в канал", url="https://t.me/zhizn_plus"))
        bot.send_message(message.chat.id, "💫 ЖИЗНЬ+", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    try:
        bot.send_message(message.chat.id, "🎯 Выбери тест:", reply_markup=test_type_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🔙 Назад')
def back_to_main(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный (10 вопросов)')
def free_test(message):
    show_topics(message, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов)')
def paid_test(message):
    show_topics(message, 'paid', 20)

def show_topics(message, test_type, count):
    try:
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for topic, emoji in TEST_TOPICS.items():
            mk.add(telebot.types.InlineKeyboardButton(emoji, callback_data=f"{test_type}_{topic}_{count}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
        bot.send_message(message.chat.id, f"🔮 Выбери тему:", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        bot.edit_message_text("⏳ Генерация теста...\n⏱ Ожидание до 35 сек", chat_id, c.message.message_id)
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
            c.execute("UPDATE stats SET paid_count = paid_count + 1")
        else:
            c.execute("UPDATE stats SET free_count = free_count + 1")
        conn.commit()
        
        bot.send_message(chat_id, f"📊 Тест завершен!\nРезультат: {score} из {total}\n⏳ Анализирую...\n⏱ Ожидание до 35 сек")
        analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
        
        if analysis:
            bot.send_message(chat_id, f"🔍 АНАЛИЗ\n\n{analysis}", reply_markup=get_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ AI не ответил. Попробуй позже.", reply_markup=get_main_menu(chat_id))
        
        if chat_id in sessions:
            del sessions[chat_id]
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

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

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        bot.send_message(message.chat.id, "⏳ Генерация поста...\n⏱ Ожидание до 35 сек")
        post, theme = generate_post()
        
        if not post:
            bot.send_message(message.chat.id, "❌ AI не ответил. Проверь логи.", reply_markup=admin_menu())
            return
        
        try:
            c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
            conn.commit()
            c.execute("UPDATE stats SET posts_count = posts_count + 1")
            conn.commit()
        except:
            pass
        
        try:
            bot.send_message(CHANNEL_ID, post)
            bot.send_message(message.chat.id, "✅ Пост отправлен!", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def admin_post_with_image(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        bot.send_message(message.chat.id, "⏳ Генерация поста и картинки...\n⏱ Ожидание до 60 сек")
        post, theme = generate_post()
        
        if not post:
            bot.send_message(message.chat.id, "❌ AI не ответил. Проверь логи.", reply_markup=admin_menu())
            return
        
        image_path = generate_post_image(theme)
        
        try:
            c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", 
                      (post, theme, image_path if image_path else ""))
            conn.commit()
            c.execute("UPDATE stats SET posts_count = posts_count + 1")
            if image_path:
                c.execute("UPDATE stats SET images_generated = images_generated + 1")
            conn.commit()
        except:
            pass
        
        try:
            if image_path:
                with open(image_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption=post)
                os.remove(image_path)
            else:
                bot.send_message(CHANNEL_ID, post)
            bot.send_message(message.chat.id, "✅ Пост с картинкой отправлен!", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        bot.send_message(message.chat.id, "⏳ Генерация теста...\n⏱ Ожидание до 35 сек")
        
        topic = random.choice(list(TEST_TOPICS.keys()))
        questions = generate_test_questions(topic, 10)
        
        if not questions:
            bot.send_message(message.chat.id, "❌ AI не ответил. Проверь логи.", reply_markup=admin_menu())
            return
        
        image_path = generate_test_image(topic)
        
        try:
            c.execute("INSERT INTO daily_tests (topic, questions, created_at, is_paid, image_path) VALUES (?, ?, ?, ?, ?)",
                      (topic, json.dumps(questions), datetime.now().isoformat(), 0, image_path if image_path else ""))
            conn.commit()
            test_id = c.lastrowid
            c.execute("UPDATE stats SET tests_created = tests_created + 1")
            if image_path:
                c.execute("UPDATE stats SET images_generated = images_generated + 1")
            conn.commit()
        except:
            test_id = int(time.time())
        
        bot_info = bot.get_me()
        test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
        test_text = f"🔮 Тест: «{topic.title()}»\n\nПройти: {test_url}"
        
        try:
            if image_path:
                with open(image_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption=test_text)
                os.remove(image_path)
            else:
                bot.send_message(CHANNEL_ID, test_text)
            bot.send_message(message.chat.id, "✅ Тест отправлен!", reply_markup=admin_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated FROM stats")
        stats_row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        stats_text = f"📊 Статистика\n\n👥 Пользователей: {users_count}\n🧠 Бесплатных: {stats_row[0] if stats_row else 0}\n💎 Платных: {stats_row[1] if stats_row else 0}\n🎫 Промокодов: {stats_row[2] if stats_row else 0}\n📤 Постов: {stats_row[4] if stats_row else 0}\n🖼 Картинок: {stats_row[6] if stats_row else 0}"
        bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

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
            bot.send_message(chat_id, f"✅ Промокод: `{code}`", reply_markup=admin_menu())
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
        c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", (chat_id, datetime.now().isoformat(), promo_id))
        conn.commit()
        c.execute("UPDATE stats SET promo_used = promo_used + 1")
        conn.commit()
        bot.send_message(chat_id, "🎉 Промокод активирован!", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info(f"🤖 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")
    logger.info(f"📊 Канал: {CHANNEL_ID}")
    logger.info(f"👑 Админы: {ADMIN_IDS}")
    
    try:
        super_kill_409()
        time.sleep(2)
        
        bot.remove_webhook()
        logger.info("✅ Вебхук удален")
        
        bot.polling(
            none_stop=True,
            interval=0,
            timeout=20,
            allowed_updates=['message', 'callback_query']
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
        
        if "409" in str(e):
            logger.info("🔄 Обнаружена 409, жесткий перезапуск...")
            super_kill_409()
            time.sleep(3)
            run_bot()
        else:
            time.sleep(5)
            run_bot()

if __name__ == "__main__":
    logger.info("🚀 ПОДГОТОВКА К ЗАПУСКУ...")
    for i in range(3):
        logger.info(f"🔄 Предстартовый проход #{i+1}/3")
        super_kill_409()
        time.sleep(2)
    
    logger.info("🚀 СТАРТ БОТА...")
    run_bot()
