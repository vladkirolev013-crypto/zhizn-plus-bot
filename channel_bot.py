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
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8799965983:AAGGPCxN1XvrGnmy2INgEneFkLlKU7oRSe4')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID', '019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET', '7b92ff4b-a058-4d3e-a1a7-d8cba1a5d661')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === GIGACHAT ПРЯМЫЕ ЗАПРОСЫ (без библиотеки) ===
def get_giga_token():
    try:
        auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
        base64_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {base64_auth}',
            'RqUID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        }
        response = requests.post(
            'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
            headers=headers,
            json={"scope": "GIGACHAT_API_PERS"},
            timeout=15
        )
        if response.status_code == 200:
            return response.json()['access_token']
        logger.error(f"Ошибка токена: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Ошибка получения токена: {e}")
        return None

def ask_giga(system_prompt, user_prompt):
    token = get_giga_token()
    if not token:
        raise Exception("Не удалось получить токен GigaChat")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    response = requests.post(
        'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Ошибка GigaChat: {response.status_code}")

# === TELEGRAM BOT ===
bot = telebot.TeleBot(BOT_TOKEN)

# === БАЗА ДАННЫХ ===
DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS tests (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, type TEXT, questions_count INTEGER, category TEXT, price_stars INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, test_id INTEGER, question_text TEXT, option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT, score_a INTEGER DEFAULT 0, score_b INTEGER DEFAULT 1, score_c INTEGER DEFAULT 2, score_d INTEGER DEFAULT 3)''')
c.execute('''CREATE TABLE IF NOT EXISTS user_results (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, test_id INTEGER, answers TEXT, total_score INTEGER, ai_analysis TEXT, created_at TEXT)''')
conn.commit()
user_state = {}

# === ВЕБ-СЕРВЕР ДЛЯ RENDER ===
app = Flask(__name__)
@app.route('/')
def home():
    return "Бот жизнь+ работает!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# === ФУНКЦИИ ===
def generate_post(theme):
    logger.info(f"Генерирую пост: {theme}")
    system = "Ты — позитивный психолог. Пиши посты для Telegram."
    user = f"Пост на тему: {theme}. Длина 500-700 символов. 4-5 эмодзи. Заголовок, текст, совет, мотивация. Без markdown. Хештеги."
    text = ask_giga(system, user)
    logger.info(f"GigaChat ответил: {len(text)} символов")
    return text

def generate_image(theme):
    try:
        prompt = "sunrise motivational" if "утро" in theme.lower() else "people connection love" if "отношения" in theme.lower() else "success money growth"
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1080&nologo=true"
        img = requests.get(url, timeout=30).content
        filename = f'/tmp/temp_{int(datetime.now().timestamp())}.jpg'
        with open(filename, 'wb') as f:
            f.write(img)
        return filename
    except Exception as e:
        logger.error(f"Ошибка картинки: {e}")
        return None

def post_to_channel(theme):
    try:
        logger.info(f"Отправляю пост: {theme}")
        text = generate_post(theme)
        img_path = generate_image(theme)
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=text)
            os.remove(img_path)
        else:
            bot.send_message(CHANNEL_ID, text)
        logger.info("✅ Пост отправлен!")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False

# === ПЛАНИРОВЩИК ===
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: post_to_channel("утренняя мотивация"), 'cron', hour=8, minute=0)
scheduler.add_job(lambda: post_to_channel("психология отношений"), 'cron', hour=13, minute=0)
scheduler.add_job(lambda: post_to_channel("финансы и успех"), 'cron', hour=19, minute=0)
scheduler.start()

# === КОМАНДЫ ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add('Бесплатный тест (10 вопросов)', 'Платный тест (20 вопросов)', 'Список тестов')
    bot.send_message(message.chat.id, "Привет! Я бот канала жизнь+\n\nВыбери:", reply_markup=markup)

@bot.message_handler(commands=['post'])
def manual_post(message):
    bot.send_message(message.chat.id, "Запрашиваю пост...")
    if post_to_channel("утренняя мотивация"):
        bot.send_message(message.chat.id, "✅ Отправлено!")

@bot.message_handler(func=lambda m: m.text == 'Бесплатный тест (10 вопросов)')
def free_test(message):
    c.execute("SELECT id, title FROM tests WHERE type='free' LIMIT 1")
    test = c.fetchone()
    if not test:
        bot.send_message(message.chat.id, "Тесты еще не добавлены.")
        return
    user_state[message.chat.id] = {'test_id': test[0], 'title': test[1], 'answers': [], 'q_num': 0}
    send_question(message.chat.id)

@bot.message_handler(func=lambda m: m.text in ['Платный тест (20 вопросов)', 'Список тестов'])
def other(message):
    bot.send_message(message.chat.id, "В разработке!")

def send_question(chat_id):
    state = user_state.get(chat_id)
    if not state: return
    c.execute("SELECT question_text, option_a, option_b, option_c, option_d FROM questions WHERE test_id=? LIMIT 1 OFFSET ?", (state['test_id'], state['q_num']))
    q = c.fetchone()
    if not q:
        finish_test(chat_id); return
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(f'A) {q[1]}', f'B) {q[2]}', f'C) {q[3]}', f'D) {q[4]}')
    bot.send_message(chat_id, f"Тест: {state['title']}\n\nВопрос {state['q_num']+1}/10:\n\n{q[0]}", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text and m.text.startswith(('A) ', 'B) ', 'C) ', 'D) ')))
def handle_answer(message):
    state = user_state.get(message.chat.id)
    if not state: return
    letter = message.text[0]
    state['answers'].append(letter)
    state['q_num'] += 1
    c.execute("SELECT score_a, score_b, score_c, score_d FROM questions WHERE test_id=? LIMIT 1 OFFSET ?", (state['test_id'], state['q_num']-1))
    scores = c.fetchone()
    if scores:
        state.setdefault('total_score', 0)
        state['total_score'] += {'A': scores[0], 'B': scores[1], 'C': scores[2], 'D': scores[3]}.get(letter, 0)
    send_question(message.chat.id)

def finish_test(chat_id):
    state = user_state.get(chat_id)
    if not state: return
    c.execute("INSERT INTO user_results (user_id, test_id, answers, total_score, created_at) VALUES (?,?,?,?,?)",
              (chat_id, state['test_id'], json.dumps(state['answers']), state.get('total_score', 0), datetime.now().isoformat()))
    conn.commit()
    score = state.get('total_score', 0)
    result = "🎉 Отлично!" if score <= 10 else "😊 Нормально!" if score <= 20 else "💪 Отдохни!"
    bot.send_message(chat_id, f"Результат:\n\nБаллы: {score}/30\n\n{result}")
    del user_state[chat_id]

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("БОТ ЗАПУЩЕН!")
    logger.info("=" * 50)
    bot.polling(none_stop=True, interval=1, timeout=60)
