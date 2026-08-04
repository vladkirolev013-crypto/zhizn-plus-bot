import telebot
import sqlite3
import requests
import os
import json
import time
import logging
import threading
import uuid
import base64
import random
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET')

ADMIN_IDS = [8746212340]

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен!")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# АНТИДОД 409
# ============================================
def kill_webhook():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        response = requests.post(url, json={"drop_pending_updates": True})
        logger.info(f"🧹 Удаление вебхука: {response.text}")
        return response.json().get('ok', False)
    except Exception as e:
        logger.error(f"❌ Ошибка удаления вебхука: {e}")
        return False

kill_webhook()
time.sleep(2)

# ============================================
# GIGACHAT
# ============================================
giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
    try:
        auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
        base64_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {base64_auth}',
            'RqUID': str(uuid.uuid4()),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(
            'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
            headers=headers,
            data='scope=GIGACHAT_API_PERS',
            timeout=15,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"Ошибка токена: {response.status_code}")
            return None
            
        token = response.json()['access_token']
        giga_token_cache["token"] = token
        giga_token_cache["expires"] = time.time() + 3500
        return token
        
    except Exception as e:
        logger.error(f"Ошибка токена: {e}")
        return None

def ask_giga(system, user, max_tokens=2500):
    token = get_giga_token()
    if not token:
        logger.error("❌ Токен не получен")
        return None
    
    headers = {
        'Authorization': f'Bearer {token}',
        'RqUID': str(uuid.uuid4()),
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.9,
        "max_tokens": max_tokens
    }
    
    try:
        logger.info("📤 Отправляю запрос в GigaChat...")
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60,
            verify=False
        )
        
        logger.info(f"✅ GigaChat ответил: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ Текст ошибки: {response.text[:500]}")
            return None
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        return content
        
    except requests.exceptions.Timeout:
        logger.error("❌ Таймаут GigaChat (60 секунд)")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка GigaChat: {e}")
        return None

def ask_giga_with_wait(system, user, max_tokens=2500):
    start_time = time.time()
    result = ask_giga(system, user, max_tokens)
    elapsed = time.time() - start_time
    
    if elapsed < 40:
        wait_time = 40 - elapsed
        logger.info(f"⏳ Ожидание {wait_time:.1f} секунд")
        time.sleep(wait_time)
    
    return result

# ============================================
# TELEGRAM БОТ
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# БАЗА ДАННЫХ
# ============================================
DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS daily_tests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              topic TEXT, 
              questions TEXT, 
              created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS stats 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              free_count INTEGER DEFAULT 0, 
              paid_count INTEGER DEFAULT 0)''')
c.execute("SELECT COUNT(*) FROM stats")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO stats (free_count, paid_count) VALUES (0, 0)")
conn.commit()

# ============================================
# ТЕМЫ
# ============================================
TEST_TOPICS = {
    "психология": "🧠 Психология",
    "отношения": "💕 Отношения",
    "карьера": "💼 Карьера",
    "здоровье": "💪 Здоровье",
    "финансы": "💰 Финансы",
    "личность": "🌟 Личность"
}

# ============================================
# ГЕНЕРАТОР ТЕСТОВ
# ============================================
def generate_test_questions(topic, count=10):
    system = """Ты — профессиональный психолог с 25-летним стажем.
    Вопросы должны быть глубокими, небанальными, без штампов."""
    
    user = f"""Составь {count} глубоких вопросов на тему "{topic}" в формате JSON:
    [
        {{
            "question": "текст вопроса?",
            "options": {{
                "A": "вариант 1",
                "B": "вариант 2",
                "C": "вариант 3",
                "D": "вариант 4"
            }},
            "scores": {{
                "A": 0,
                "B": 1,
                "C": 2,
                "D": 3
            }}
        }}
    ]
    Верни ТОЛЬКО JSON."""
    
    response = ask_giga_with_wait(system, user, max_tokens=3000)
    if not response:
        return None
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start == -1 or end == -1:
            return None
        
        data = json.loads(response[start:end])
        if isinstance(data, dict) and 'questions' in data:
            data = data['questions']
        
        parsed = []
        for q in data:
            if 'question' in q and 'options' in q:
                if 'scores' not in q:
                    q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                parsed.append(q)
        
        return parsed[:count] if parsed else None
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА
# ============================================
def generate_analysis(topic, answers, score, total, is_paid):
    min_len = 1400 if is_paid else 700
    
    if is_paid:
        system = """Ты — команда: клинический психолог (25 лет) и коуч мирового уровня.
        Дай глубокий разбор личности и мощные рекомендации."""
        user = f"""Тема: {topic}. Ответы: {answers}. Баллы: {score} из {total}.
        Проведи разбор личности. Включи:
        - Глубокий психологический портрет
        - 2 инсайта
        - Книги, упражнения, видео (на русском)
        - Вызов от коуча
        """
    else:
        system = """Ты — лучший клинический психолог. Проведи глубокий разбор личности.
        Без воды, без штампов. Дай 2 инсайта и 2 вопроса для размышления."""
        user = f"""Тема: {topic}. Ответы: {answers}. Баллы: {score} из {total}.
        Проведи глубокий разбор личности. БЕЗ книг и упражнений."""
    
    response = ask_giga_with_wait(system, user, max_tokens=3000 if is_paid else 2000)
    if not response or len(response) < min_len * 0.7:
        return None
    return response

# ============================================
# ГЕНЕРАТОР ПОСТА
# ============================================
def generate_post():
    themes = [
        "утренняя энергия", "внутренняя сила", "радость в простых вещах",
        "преодоление страхов", "любовь к себе", "благодарность",
        "мотивация", "осознанность", "отношения", "финансовое мышление"
    ]
    theme = random.choice(themes)
    
    system = """Ты — психолог и коуч. Напиши пост для Telegram, который даёт энергию,
    использует мягкое НЛП, не повторяется."""
    
    user = f"""Напиши пост на тему "{theme}" для Telegram.
    Длина: 800–1000 знаков. Заголовок с эмодзи. Практический совет.
    Мотивирующая фраза. Хештеги."""
    
    response = ask_giga_with_wait(system, user, max_tokens=2000)
    if not response or len(response) < 700:
        return None
    return response

# ============================================
# ВЕБ-СЕРВЕР
# ============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

@app.route('/health')
def health():
    return {"status": "ok"}

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ============================================
# МЕНЮ
# ============================================
def get_main_menu(chat_id):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🚀 Старт', '🎯 Пройти тест')
    mk.add('❤️ О канале')
    if chat_id in ADMIN_IDS:
        mk.add('👑 Админ-панель')
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('📤 Отправить пост', '🧠 Тест в канал')
    mk.add('📊 Статистика')
    mk.add('👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

# ============================================
# СОСТОЯНИЯ
# ============================================
sessions = {}

# ============================================
# ОБРАБОТЧИКИ
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    if ' ' in message.text:
        param = message.text.split(' ', 1)[1]
        if param.startswith('daily_'):
            try:
                _, topic, tid = param.split('_')
                c.execute("SELECT questions FROM daily_tests WHERE id=?", (tid,))
                row = c.fetchone()
                if row:
                    questions = json.loads(row[0])
                    sessions[message.chat.id] = {
                        'topic': topic,
                        'questions': questions,
                        'answers': [],
                        'q': 0,
                        'scores': [],
                        'is_paid': False
                    }
                    bot.send_message(message.chat.id, f"📌 Ежедневный тест: {topic}")
                    send_question(message.chat.id)
                    return
            except:
                pass
    
    welcome = "🌟 Добро пожаловать в бота Жизнь+!\n\nНажми «🎯 Пройти тест» или «❤️ О канале»."
    bot.send_message(message.chat.id, welcome, reply_markup=get_main_menu(message.chat.id))

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel_button(message):
    if message.chat.id not in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = (
        "Жизнь+ — это не просто канал. Это пространство, где каждый день начинается с новой силы. "
        "Здесь ты находишь ответы, которых не ждал, и чувствуешь, как внутри просыпается энергия, "
        "которую ты давно искал. Мы говорим о том, что действительно важно — о внутренней опоре, "
        "о легкости в теле и ясности в голове. Подпишись, чтобы напоминать себе: ты уже на верном пути. "
        "А бот Жизнь+ поможет тебе заглянуть в себя глубже и увидеть то, что всегда было с тобой."
    )
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton(
        "📢 Перейти в канал",
        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
    ))
    bot.send_message(message.chat.id, text, reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    bot.send_message(
        message.chat.id,
        "🎯 Выберите тип теста:\n\n🧠 Бесплатный — 10 вопросов\n💎 Платный — 20 вопросов",
        reply_markup=test_type_menu()
    )

@bot.message_handler(func=lambda m: m.text == '🔙 Назад')
def back_to_main_from_test(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный (10 вопросов)')
def free_test(message):
    show_topics(message, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов)')
def paid_test(message):
    if message.chat.id in ADMIN_IDS:
        show_topics(message, 'paid', 20)
    else:
        bot.send_message(
            message.chat.id,
            "💎 Платный тест — 50 ₽\n\nА пока пройдите бесплатный.",
            reply_markup=test_type_menu()
        )

# ============================================
# ВЫБОР ТЕМЫ
# ============================================
def show_topics(message, test_type, count):
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    for topic, emoji in TEST_TOPICS.items():
        mk.add(telebot.types.InlineKeyboardButton(
            emoji,
            callback_data=f"{test_type}_{topic}_{count}"
        ))
    mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    bot.send_message(
        message.chat.id,
        f"🎯 Выберите тему:\n\n{count} вопросов",
        reply_markup=mk
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        
        bot.edit_message_text(
            "⏳ Генерация теста...\nПодождите до 40 секунд.",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, int(count))
        if not questions:
            bot.send_message(c.message.chat.id, "❌ Не удалось сгенерировать тест. Попробуйте позже.")
            return
        
        sessions[c.message.chat.id] = {
            'topic': topic,
            'questions': questions,
            'answers': [],
            'q': 0,
            'scores': [],
            'is_paid': is_paid
        }
        bot.delete_message(c.message.chat.id, c.message.message_id)
        send_question(c.message.chat.id)
    except Exception as e:
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    bot.delete_message(c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "❌ Отменено", reply_markup=get_main_menu(c.message.chat.id))

# ============================================
# ПРОХОЖДЕНИЕ ТЕСТА
# ============================================
def send_question(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    
    if s['q'] >= len(s['questions']):
        finish_test(chat_id)
        return
    
    q = s['questions'][s['q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for opt, txt in q['options'].items():
        mk.add(f"{opt}) {txt}")
    mk.add('⏹ Прервать тест')
    
    bot.send_message(
        chat_id,
        f"📝 Вопрос {s['q']+1}/{len(s['questions'])}\n"
        f"📌 Тема: {s['topic'].title()}\n\n"
        f"{q['question']}",
        reply_markup=mk
    )

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    if message.chat.id in sessions:
        del sessions[message.chat.id]
    bot.send_message(message.chat.id, "⏹ Тест прерван", reply_markup=get_main_menu(message.chat.id))

@bot.message_handler(func=lambda m: m.text and m.text[0] in 'ABCD')
def handle_answer(message):
    s = sessions.get(message.chat.id)
    if not s:
        return
    if s['q'] >= len(s['questions']):
        return
    
    letter = message.text[0]
    q = s['questions'][s['q']]
    s['answers'].append(letter)
    s['scores'].append(q['scores'][letter])
    s['q'] += 1
    send_question(message.chat.id)

# ============================================
# ЗАВЕРШЕНИЕ ТЕСТА
# ============================================
def finish_test(chat_id):
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
    
    bot.send_message(
        chat_id,
        f"📊 Тест завершен!\n\n"
        f"✅ Результат: {score} из {total}\n"
        f"⏳ Генерация анализа...\nДо 40 секунд."
    )
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    if not analysis:
        bot.send_message(chat_id, "❌ Не удалось сгенерировать анализ. Попробуйте позже.")
        del sessions[chat_id]
        return
    
    bot.send_message(
        chat_id,
        f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}",
        reply_markup=get_main_menu(chat_id)
    )
    
    del sessions[chat_id]
    bot.send_message(chat_id, "✨ Готово!", reply_markup=get_main_menu(chat_id))

# ============================================
# АДМИН-КНОПКИ
# ============================================
@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "📤 Генерация поста...\n⏳ До 40 секунд.")
    text = generate_post()
    if not text:
        bot.send_message(message.chat.id, "❌ Не удалось сгенерировать пост.")
        return
    
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    for topic, emoji in TEST_TOPICS.items():
        mk.add(telebot.types.InlineKeyboardButton(
            emoji,
            callback_data=f"admin_test_{topic}"
        ))
    mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel"))
    
    bot.send_message(
        message.chat.id,
        "🎯 Выберите тему для теста в канал:",
        reply_markup=mk
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith('admin_test_'))
def admin_test_topic_callback(c):
    try:
        topic = c.data.replace('admin_test_', '')
        bot.edit_message_text(
            f"⏳ Генерация теста по теме {topic}...",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, 10)
        if not questions:
            bot.send_message(c.message.chat.id, "❌ Не удалось сгенерировать тест.")
            return
        
        conn.execute(
            "INSERT INTO daily_tests (topic, questions, created_at) VALUES (?,?,?)",
            (topic, json.dumps(questions), datetime.now().isoformat())
        )
        conn.commit()
        test_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton(
            "🎯 Пройти тест",
            url=f"https://t.me/{bot.get_me().username}?start=daily_{topic}_{test_id}"
        ))
        
        bot.send_message(
            CHANNEL_ID,
            f"🧠 ТЕСТ ПО ТЕМЕ: {topic.upper()}\n\n📊 10 вопросов\n\nПроверьте себя прямо сейчас!",
            reply_markup=mk
        )
        bot.edit_message_text(
            f"✅ Тест по теме {topic} отправлен в канал!",
            c.message.chat.id,
            c.message.message_id
        )
    except Exception as e:
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == 'admin_cancel')
def admin_cancel(c):
    bot.delete_message(c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "❌ Отменено", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    c.execute("SELECT free_count, paid_count FROM stats LIMIT 1")
    row = c.fetchone()
    
    if row:
        free_count, paid_count = row
        text = (
            "📊 СТАТИСТИКА\n\n"
            f"🧠 Бесплатных: {free_count}\n"
            f"💎 Платных: {paid_count}\n\n"
            f"Всего: {free_count + paid_count}"
        )
    else:
        text = "📊 Статистика пуста."
    
    bot.send_message(message.chat.id, text)

# ============================================
# ЕЖЕДНЕВНЫЙ ТЕСТ
# ============================================
def post_daily_test():
    topics = list(TEST_TOPICS.keys())
    random.shuffle(topics)
    topic = topics[0]
    
    questions = generate_test_questions(topic, 10)
    if questions:
        c.execute(
            "INSERT INTO daily_tests (topic, questions, created_at) VALUES (?,?,?)",
            (topic, json.dumps(questions), datetime.now().isoformat())
        )
        conn.commit()
        test_id = c.lastrowid
        
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton(
            "🎯 Пройти тест",
            url=f"https://t.me/{bot.get_me().username}?start=daily_{topic}_{test_id}"
        ))
        
        bot.send_message(
            CHANNEL_ID,
            f"🧠 ЕЖЕДНЕВНЫЙ ТЕСТ ДНЯ!\n\n"
            f"📌 Тема: {topic.title()}\n"
            f"📊 Вопросов: 10\n\n"
            f"Проверьте себя прямо сейчас!",
            reply_markup=mk
        )

# ============================================
# АДМИН-КОМАНДЫ
# ============================================
@bot.message_handler(commands=['daily'])
def cmd_daily(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "📤 Отправка ежедневного теста...")
    post_daily_test()
    bot.send_message(message.chat.id, "✅ Готово!")

@bot.message_handler(commands=['post'])
def cmd_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "📤 Генерация поста...\n⏳ До 40 секунд.")
    text = generate_post()
    if not text:
        bot.send_message(message.chat.id, "❌ Не удалось сгенерировать пост.")
        return
    
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")

# ============================================
# ПЛАНИРОВЩИК
# ============================================
scheduler = BackgroundScheduler()

def schedule_morning():
    text = generate_post()
    if text:
        bot.send_message(CHANNEL_ID, text)

def schedule_daily():
    post_daily_test()

def schedule_evening():
    text = generate_post()
    if text:
        bot.send_message(CHANNEL_ID, text)

scheduler.add_job(schedule_morning, 'cron', hour=8, minute=0)
scheduler.add_job(schedule_daily, 'cron', hour=10, minute=0)
scheduler.add_job(schedule_evening, 'cron', hour=19, minute=0)
scheduler.start()

# ============================================
# ЗАПУСК
# ============================================
if __name__ == '__main__':
    logger.info("🚀 БОТ ЗАПУЩЕН")
    logger.info("✅ Готов к работе!")
    bot.polling(none_stop=True)
