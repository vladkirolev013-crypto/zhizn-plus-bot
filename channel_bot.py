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
import glob
from datetime import datetime
from flask import Flask
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET')
ADMIN_IDS = [8746212340]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_409():
    try:
        for f in glob.glob('update-offset-*.json'):
            try:
                os.remove(f)
            except:
                pass
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        requests.post(url, json={"drop_pending_updates": True})
        return True
    except:
        return False

kill_409()
time.sleep(2)

giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
    try:
        auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
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
        
        data = response.json()
        token = data.get('access_token')
        
        if not token:
            return None
        
        giga_token_cache["token"] = token
        giga_token_cache["expires"] = time.time() + 3500
        logger.info("✅ Токен получен")
        return token
        
    except Exception as e:
        logger.error(f"Ошибка токена: {e}")
        return None

def ask_giga(system, user, max_tokens=2500):
    token = get_giga_token()
    if not token:
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
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"Ошибка GigaChat: {response.status_code}")
            return None
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        logger.error(f"Ошибка GigaChat: {e}")
        return None

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
              paid_count INTEGER DEFAULT 0,
              promo_used INTEGER DEFAULT 0)''')

c.execute("SELECT COUNT(*) FROM stats")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO stats (free_count, paid_count, promo_used) VALUES (0, 0, 0)")

c.execute('''CREATE TABLE IF NOT EXISTS user_sessions 
             (chat_id INTEGER PRIMARY KEY, 
              topic TEXT, 
              questions TEXT, 
              current_q INTEGER, 
              answers TEXT, 
              scores TEXT, 
              is_paid INTEGER, 
              result TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS promocodes 
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT UNIQUE,
              created_by INTEGER,
              created_at TEXT,
              used_by INTEGER DEFAULT 0,
              used_at TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS posts_history
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              content TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

conn.commit()

TEST_TOPICS = {
    "психология": "🧠 Психология",
    "отношения": "💕 Отношения",
    "карьера": "💼 Карьера",
    "здоровье": "💪 Здоровье",
    "финансы": "💰 Финансы",
    "личность": "🌟 Личность"
}

def generate_test_questions(topic, count=10):
    system = """Ты — профессиональный психолог. Составь вопросы для теста.
    Верни ТОЛЬКО JSON массив, без дополнительного текста."""
    
    user = f"""Составь {count} вопросов на тему "{topic}" в формате JSON:
    [
        {{
            "question": "текст вопроса?",
            "options": {{
                "A": "вариант 1",
                "B": "вариант 2",
                "C": "вариант 3",
                "D": "вариант 4"
            }}
        }}
    ]
    Верни ТОЛЬКО JSON."""
    
    response = ask_giga(system, user, 3000)
    if not response:
        return None
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start == -1 or end == -1:
            return None
        
        questions = json.loads(response[start:end])
        return questions[:count]
    except:
        return None

def generate_analysis(topic, answers, score, total, is_paid):
    if is_paid:
        system = """Ты — психолог и коуч. Дай полный разбор личности.
        Включи: портрет, инсайты, рекомендации, книги, упражнения."""
        
        user = f"""Тема: {topic}
Ответы: {answers}
Баллы: {score} из {total}
Сделай полный анализ."""
    else:
        system = """Ты — психолог. Дай честный анализ без пафоса."""
        user = f"""Тема: {topic}
Ответы: {answers}
Баллы: {score} из {total}
Сделай краткий анализ."""
    
    return ask_giga(system, user, 3000 if is_paid else 2000)

def generate_post():
    themes = ["психология", "отношения", "саморазвитие", "мотивация", "деньги"]
    theme = random.choice(themes)
    
    system = """Ты — автор канала о психологии. Пиши честно, без пафоса.
    Используй живой язык, как в разговоре с другом."""
    
    user = f"""Напиши пост на тему "{theme}" для Telegram.
    Длина: 500-800 знаков.
    Добавь практический совет.
    Закончи вопросом к читателю."""
    
    return ask_giga(system, user, 2000)

bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Бот работает!"

@app.route('/health')
def health():
    return {"status": "ok"}

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

threading.Thread(target=run_flask, daemon=True).start()

def get_main_menu(chat_id):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🚀 Старт', '🎯 Пройти тест')
    mk.add('🎫 Активировать промокод', '❤️ О канале')
    if chat_id in ADMIN_IDS:
        mk.add('👑 Админ-панель')
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('📤 Отправить пост', '🧠 Тест в канал')
    mk.add('📊 Статистика', '🎫 Создать промокод')
    mk.add('👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

sessions = {}

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    welcome = "🌟 Добро пожаловать в бота Жизнь+!\n\nНажми «🎯 Пройти тест» или «🎫 Активировать промокод»."
    bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = "Жизнь+ — это пространство, где каждый день начинается с новой силы."
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
    show_topics(message, 'paid', 20)

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
            bot.send_message(c.message.chat.id, "❌ Не удалось сгенерировать тест.")
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

def send_question(chat_id):
    s = sessions.get(chat_id)
    if not s:
        bot.send_message(chat_id, "❌ Активный тест не найден.")
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
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))

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
        f"⏳ GigaChat генерирует анализ..."
    )
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    
    if analysis:
        bot.send_message(
            chat_id,
            f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}",
            reply_markup=get_main_menu(chat_id)
        )
    else:
        bot.send_message(
            chat_id,
            f"❌ Не удалось сгенерировать анализ.",
            reply_markup=get_main_menu(chat_id)
        )
    
    del sessions[chat_id]

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "📤 Генерация поста...\n⏳ До 40 секунд.")
    text = generate_post()
    
    if not text:
        bot.send_message(message.chat.id, "❌ Не удалось сгенерировать пост.")
        return
    
    c.execute("INSERT INTO posts_history (content) VALUES (?)", (text,))
    conn.commit()
    
    try:
        bot.send_message(CHANNEL_ID, text)
        bot.send_message(message.chat.id, "✅ Пост отправлен в канал!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка отправки: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🧠 Генерация теста для канала...")
    
    topic = random.choice(list(TEST_TOPICS.keys()))
    questions = generate_test_questions(topic, 10)
    
    if not questions:
        bot.send_message(message.chat.id, "❌ Не удалось сгенерировать тест.")
        return
    
    c.execute("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?, ?, ?)",
              (topic, json.dumps(questions), datetime.now().isoformat()))
    conn.commit()
    test_id = c.lastrowid
    
    bot_info = bot.get_me()
    test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
    
    test_text = f"🧠 Ежедневный тест: «{topic.title()}»\n\n"
    test_text += f"Пройдите тест прямо сейчас!\n"
    test_text += f"🎯 {test_url}"
    
    bot.send_message(CHANNEL_ID, test_text)
    bot.send_message(message.chat.id, "✅ Тест отправлен в канал!", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    c.execute("SELECT free_count, paid_count, promo_used FROM stats")
    stats_row = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM daily_tests")
    tests_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM posts_history")
    posts_count = c.fetchone()[0]
    
    stats_text = f"📊 СТАТИСТИКА\n\n"
    stats_text += f"📝 Тестов в канале: {tests_count}\n"
    stats_text += f"📤 Постов отправлено: {posts_count}\n"
    stats_text += f"🧠 Бесплатных тестов: {stats_row[0] if stats_row else 0}\n"
    stats_text += f"💎 Платных тестов: {stats_row[1] if stats_row else 0}\n"
    stats_text += f"🎫 Активировано промокодов: {stats_row[2] if stats_row else 0}"
    
    bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🎫 Введите название промокода (латиницей, без пробелов):")
    bot.register_next_step_handler(message, process_create_promo)

def process_create_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    
    if code == "ОТМЕНА":
        bot.send_message(chat_id, "❌ Отменено.")
        return
    
    if not code or len(code) < 3:
        bot.send_message(chat_id, "❌ Минимум 3 символа.", reply_markup=admin_menu())
        return
    
    try:
        c.execute("INSERT INTO promocodes (code, created_by, created_at) VALUES (?, ?, ?)",
                  (code, chat_id, datetime.now().isoformat()))
        conn.commit()
        bot.send_message(
            chat_id,
            f"✅ Промокод создан!\n\n📌 Код: `{code}`",
            reply_markup=admin_menu()
        )
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Такой промокод уже существует.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(
        message.chat.id,
        "🎫 Введите промокод:",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    
    c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
    row = c.fetchone()
    
    if not row:
        bot.send_message(chat_id, "❌ Неверный промокод.", reply_markup=get_main_menu(chat_id))
        return
    
    promo_id, used_by = row
    
    if used_by != 0:
        bot.send_message(chat_id, "❌ Этот промокод уже был использован.", reply_markup=get_main_menu(chat_id))
        return
    
    c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
              (chat_id, datetime.now().isoformat(), promo_id))
    conn.commit()
    
    c.execute("UPDATE stats SET promo_used = promo_used + 1")
    conn.commit()
    
    bot.send_message(
        chat_id,
        "🎉 Промокод активирован!\n\nТеперь вы можете пройти 💎 Платный тест бесплатно!",
        reply_markup=get_main_menu(chat_id)
    )

def run_bot():
    logger.info("🤖 Запуск бота...")
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    run_bot()
