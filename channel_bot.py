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
import traceback
import random
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from PIL import Image, ImageDraw, ImageFont

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# GIGACHAT — ТОЛЬКО ЗДЕСЬ, БЕЗ FALLBACK
# ============================================
giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
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
    if response.status_code != 200:
        return None
    token = response.json()['access_token']
    giga_token_cache["token"] = token
    giga_token_cache["expires"] = time.time() + 3500
    return token

def ask_giga(system, user, max_tokens=2500):
    token = get_giga_token()
    if not token:
        return None
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.95,
        "max_tokens": max_tokens
    }
    
    response = requests.post(
        'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=60
    )
    
    if response.status_code != 200:
        return None
    
    return response.json()['choices'][0]['message']['content']

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
conn.commit()

# ============================================
# ТЕМЫ
# ============================================
TEST_TOPICS = {
    "психология": "🧠 Психологическое состояние",
    "отношения": "💕 Любовь и дружба",
    "карьера": "💼 Профессиональное развитие",
    "здоровье": "💪 Здоровье",
    "финансы": "💰 Отношение к деньгам",
    "личность": "🌟 Личность"
}

# ============================================
# ГЕНЕРАЦИЯ — ТОЛЬКО GIGACHAT
# ============================================
def generate_test_questions(topic, count=10):
    system = "Ты — психолог. Составь вопросы для теста. Формат: JSON."
    user = f"Составь {count} вопросов на тему '{topic}'. Верни ТОЛЬКО JSON."
    response = ask_giga(system, user)
    if not response:
        return None
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        data = json.loads(response[start:end])
        return data.get('questions', [])[:count]
    except:
        return None

def generate_analysis(topic, answers, score, total, is_paid):
    min_len = 1400 if is_paid else 700
    system = "Ты — психолог и коуч. Дай глубокий анализ."
    user = f"Тема: {topic}. Ответы: {answers}. Баллы: {score} из {total}. Напиши анализ (минимум {min_len} знаков) с рекомендациями книг, упражнений, видео на русском языке."
    response = ask_giga(system, user)
    if not response:
        return None
    if len(response) < min_len * 0.7:
        return None
    return response

def generate_post(theme):
    system = "Ты — психолог. Напиши пост для Telegram."
    user = f"Тема: {theme}. Минимум 700 знаков."
    response = ask_giga(system, user)
    if not response:
        return None
    if len(response) < 700:
        return None
    return response

# ============================================
# КАРТИНКИ
# ============================================
def generate_result_image(score, total, topic):
    try:
        pct = int((score / total) * 100) if total > 0 else 0
        prompt = "sunset" if pct >= 70 else "nature" if pct >= 40 else "sunrise"
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=720&nologo=true"
        img = requests.get(url, timeout=30).content
        filename = f'/tmp/result_{int(time.time())}.jpg'
        with open(filename, 'wb') as f:
            f.write(img)
        return filename
    except:
        return None

def generate_certificate(name, topic, score, total):
    try:
        img = Image.new('RGB', (1200, 800), 'white')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        except:
            font = ImageFont.load_default()
        draw.text((600, 100), "СЕРТИФИКАТ", fill=(0,0,0), font=font, anchor="mt")
        draw.text((600, 200), f"{name}", fill=(0,0,0), font=font, anchor="mt")
        draw.text((600, 300), f"Тема: {topic}", fill=(0,0,0), font=font, anchor="mt")
        draw.text((600, 400), f"Результат: {score} из {total*3}", fill=(0,0,0), font=font, anchor="mt")
        filename = f'/tmp/cert_{int(time.time())}.png'
        img.save(filename)
        return filename
    except:
        return None

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
def main_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🎯 Тест', '📋 О тестах', '❤️ Канал')
    return mk

def test_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный', '💎 Платный')
    mk.add('🔙 Главная')
    return mk

# ============================================
# СОСТОЯНИЯ
# ============================================
sessions = {}

# ============================================
# КОМАНДЫ
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
                    q = json.loads(row[0])
                    sessions[message.chat.id] = {'topic': topic, 'questions': q, 'answers': [], 'q': 0, 'scores': []}
                    bot.send_message(message.chat.id, f"📌 Ежедневный тест: {topic}")
                    send_q(message.chat.id)
                    return
            except:
                pass
    bot.send_message(message.chat.id, "🌟 Жизнь+", reply_markup=main_menu())

# ============================================
# КНОПКИ
# ============================================
@bot.message_handler(func=lambda m: m.text == '🎯 Тест')
def choose_test(m):
    bot.send_message(m.chat.id, "Выберите тип:", reply_markup=test_menu())

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный')
def free_test(m):
    show_topics(m, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный')
def paid_test(m):
    if m.chat.id in ADMIN_IDS:
        show_topics(m, 'free', 20)
    else:
        bot.send_message(m.chat.id, "💎 50 ₽ (скоро оплата через Stars)\nПока пройдите бесплатный.")

@bot.message_handler(func=lambda m: m.text == '📋 О тестах')
def about(m):
    bot.send_message(m.chat.id, "🧠 Бесплатный: 10 вопросов\n💎 Платный: 20 вопросов\nРезультаты не хранятся.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == '❤️ Канал')
def channel(m):
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("📢 Перейти", url=f"https://t.me/{CHANNEL_ID.replace('@','')}"))
    bot.send_message(m.chat.id, f"📌 {CHANNEL_ID}", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '🔙 Главная')
def back(m):
    bot.send_message(m.chat.id, "Главное меню", reply_markup=main_menu())

# ============================================
# ВЫБОР ТЕМЫ
# ============================================
def show_topics(m, ttype, count):
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    for t, desc in TEST_TOPICS.items():
        mk.add(telebot.types.InlineKeyboardButton(desc, callback_data=f"{ttype}_{t}_{count}"))
    mk.add(telebot.types.InlineKeyboardButton("❌", callback_data="cancel"))
    bot.send_message(m.chat.id, "Выберите тему:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_cb(c):
    try:
        ttype, topic, count = c.data.split('_')
        bot.edit_message_text("⏳ Генерация...", c.message.chat.id, c.message.message_id)
        
        q = generate_test_questions(topic, int(count))
        if not q:
            bot.send_message(c.message.chat.id, "❌ GigaChat не ответил")
            return
        
        sessions[c.message.chat.id] = {'topic': topic, 'questions': q, 'answers': [], 'q': 0, 'scores': [], 'paid': ttype == 'paid'}
        bot.delete_message(c.message.chat.id, c.message.message_id)
        send_q(c.message.chat.id)
    except Exception as e:
        bot.send_message(c.message.chat.id, f"❌ {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_cb(c):
    bot.delete_message(c.message.chat.id, c.message.message_id)
    bot.send_message(c.message.chat.id, "Отменено", reply_markup=main_menu())

# ============================================
# ПРОХОЖДЕНИЕ ТЕСТА
# ============================================
def send_q(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    if s['q'] >= len(s['questions']):
        finish(chat_id)
        return
    
    q = s['questions'][s['q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for opt, txt in q['options'].items():
        mk.add(f"{opt}) {txt}")
    mk.add("⏹ Стоп")
    bot.send_message(chat_id, f"📝 {s['q']+1}/{len(s['questions'])}\n📌 {s['topic']}\n\n{q['question']}", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '⏹ Стоп')
def stop(m):
    if m.chat.id in sessions:
        del sessions[m.chat.id]
    bot.send_message(m.chat.id, "⏹ Тест остановлен", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text and m.text[0] in 'ABCD')
def answer(m):
    s = sessions.get(m.chat.id)
    if not s:
        return
    if s['q'] >= len(s['questions']):
        return
    
    letter = m.text[0]
    q = s['questions'][s['q']]
    s['answers'].append(letter)
    s['scores'].append(q['scores'][letter])
    s['q'] += 1
    send_q(m.chat.id)

# ============================================
# ЗАВЕРШЕНИЕ
# ============================================
def finish(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    
    score = sum(s['scores'])
    total = len(s['questions']) * 3
    answers = ', '.join(s['answers'])
    is_paid = s.get('paid', False)
    
    bot.send_message(chat_id, f"📊 Результат: {score} из {total}\n⏳ Анализ...")
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    if not analysis:
        bot.send_message(chat_id, "❌ GigaChat не ответил")
        del sessions[chat_id]
        return
    
    cert = generate_certificate("Пользователь", s['topic'], score, len(s['questions']))
    if cert:
        with open(cert, 'rb') as f:
            bot.send_document(chat_id, f, caption="🏆 Сертификат")
        os.remove(cert)
    
    img = generate_result_image(score, len(s['questions'])*3, s['topic'])
    if img:
        with open(img, 'rb') as f:
            bot.send_photo(chat_id, f, caption=f"🌟 {score}/{len(s['questions'])*3}")
        os.remove(img)
    
    bot.send_message(chat_id, f"🔍 {analysis}")
    del sessions[chat_id]
    bot.send_message(chat_id, "✨ Готово!", reply_markup=main_menu())

# ============================================
# ЕЖЕДНЕВНЫЙ ТЕСТ
# ============================================
def post_daily():
    topics = list(TEST_TOPICS.keys())
    random.shuffle(topics)
    for t in topics:
        q = generate_test_questions(t, 10)
        if q:
            c.execute("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?,?,?)",
                      (t, json.dumps(q), datetime.now().isoformat()))
            conn.commit()
            tid = c.lastrowid
            mk = telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("🎯 Пройти", url=f"https://t.me/{bot.get_me().username}?start=daily_{t}_{tid}"))
            bot.send_message(CHANNEL_ID, f"🧠 ЕЖЕДНЕВНЫЙ ТЕСТ\n📌 {t}\n10 вопросов", reply_markup=mk)
            time.sleep(2)

# ============================================
# АДМИН-КОМАНДЫ
# ============================================
@bot.message_handler(commands=['daily'])
def cmd_daily(m):
    if m.chat.id in ADMIN_IDS:
        bot.send_message(m.chat.id, "📤 Отправка...")
        post_daily()
        bot.send_message(m.chat.id, "✅ Готово!")

@bot.message_handler(commands=['post'])
def cmd_post(m):
    if m.chat.id in ADMIN_IDS:
        bot.send_message(m.chat.id, "📤 Генерация поста...")
        text = generate_post("мотивация")
        if not text:
            bot.send_message(m.chat.id, "❌ GigaChat не ответил. Пост НЕ отправлен.")
            return
        bot.send_message(CHANNEL_ID, text)
        bot.send_message(m.chat.id, "✅ Отправлено!")

# ============================================
# ПЛАНИРОВЩИК
# ============================================
scheduler = BackgroundScheduler()

def schedule_morning():
    text = generate_post("утренняя мотивация")
    if text:
        bot.send_message(CHANNEL_ID, text)

def schedule_daily():
    post_daily()

def schedule_evening():
    text = generate_post("вечерняя мотивация")
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
    print("🚀 БОТ ЗАПУЩЕН")
    bot.polling(none_stop=True)
