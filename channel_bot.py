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

# ОТКЛЮЧАЕМ SSL ПРЕДУПРЕЖДЕНИЯ
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
    
    try:
        # УВЕЛИЧИВАЕМ ТАЙМАУТ ДО 60 СЕКУНД
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"GigaChat ошибка: {response.status_code}")
            return None
        
        return response.json()['choices'][0]['message']['content']
        
    except requests.exceptions.Timeout:
        logger.error("GigaChat таймаут (60 секунд)")
        return None
    except Exception as e:
        logger.error(f"GigaChat ошибка: {e}")
        return None

# ============================================
# TELEGRAM БОТ
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

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
# ТЕМЫ ТЕСТОВ
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
# ГЕНЕРАТОРЫ (ВСЁ ЧЕРЕЗ GIGACHAT)
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
# МЕНЮ С КНОПКАМИ
# ============================================
def main_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🎯 Пройти тест', '📋 О тестах')
    mk.add('❤️ О канале')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Главное меню')
    return mk

# ============================================
# СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ
# ============================================
sessions = {}

# ============================================
# ОБРАБОТЧИК КОМАНД /start
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
    
    bot.send_message(
        message.chat.id,
        "🌟 Добро пожаловать в бота Жизнь+!\n\n"
        "Я помогу вам пройти психологические тесты и получить анализ от экспертов.\n\n"
        "👇 Нажмите кнопку «🎯 Пройти тест» чтобы начать!",
        reply_markup=main_menu()
    )

# ============================================
# ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ
# ============================================
@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    bot.send_message(
        message.chat.id,
        "🎯 Выберите тип теста:\n\n"
        "🧠 Бесплатный — 10 вопросов, анализ 700+ знаков\n"
        "💎 Платный — 20 вопросов, анализ 1400+ знаков\n\n"
        "👇 Выберите вариант:",
        reply_markup=test_type_menu()
    )

@bot.message_handler(func=lambda m: m.text == '📋 О тестах')
def about_tests(message):
    text = (
        "📋 О ТЕСТАХ ЖИЗНЬ+\n\n"
        "🧠 Бесплатный тест:\n"
        "• 10 вопросов\n"
        "• Анализ 700+ знаков\n"
        "• Рекомендации от психолога\n\n"
        "💎 Платный тест:\n"
        "• 20 вопросов\n"
        "• Анализ 1400+ знаков\n"
        "• Книги, упражнения, видео\n\n"
        "✅ Результаты НЕ сохраняются\n"
        "✅ Каждый раз новые вопросы"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton(
        "📢 Перейти в канал",
        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
    ))
    bot.send_message(
        message.chat.id,
        f"❤️ О КАНАЛЕ ЖИЗНЬ+\n\n"
        f"Канал о психологии и саморазвитии.\n\n"
        f"📌 Подписывайтесь: {CHANNEL_ID}",
        reply_markup=mk
    )

@bot.message_handler(func=lambda m: m.text == '🔙 Главное меню')
def back_to_main(message):
    bot.send_message(
        message.chat.id,
        "🌟 Главное меню",
        reply_markup=main_menu()
    )

# ============================================
# ОБРАБОТЧИКИ ВЫБОРА ТИПА ТЕСТА
# ============================================
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
            "💎 Платный тест — 50 ₽\n\n"
            "Оплата через Telegram Stars скоро будет доступна.\n"
            "А пока пройдите бесплатный тест.",
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
            "⏳ GigaChat генерирует тест...\n"
            "Это может занять до 40 секунд.\n"
            "Пожалуйста, подождите...",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, int(count))
        
        if not questions:
            bot.send_message(
                c.message.chat.id,
                "❌ Не удалось сгенерировать тест. Попробуйте позже."
            )
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
    bot.send_message(c.message.chat.id, "❌ Отменено", reply_markup=main_menu())

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
    bot.send_message(
        message.chat.id,
        "⏹ Тест прерван",
        reply_markup=main_menu()
    )

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
    
    bot.send_message(
        chat_id,
        f"📊 Тест завершен!\n\n"
        f"✅ Результат: {score} из {total}\n"
        f"⏳ GigaChat генерирует анализ...\n"
        f"Это займет до 40 секунд."
    )
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    
    if not analysis:
        bot.send_message(
            chat_id,
            "❌ Не удалось сгенерировать анализ. Попробуйте позже."
        )
        del sessions[chat_id]
        return
    
    bot.send_message(
        chat_id,
        f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}",
        reply_markup=main_menu()
    )
    
    del sessions[chat_id]
    bot.send_message(chat_id, "✨ Готово!", reply_markup=main_menu())

# ============================================
# ЕЖЕДНЕВНЫЙ ТЕСТ В КАНАЛ
# ============================================
def post_daily_test():
    topics = list(TEST_TOPICS.keys())
    random.shuffle(topics)
    
    for topic in topics:
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
            time.sleep(2)

# ============================================
# АДМИН-КОМАНДЫ
# ============================================
@bot.message_handler(commands=['daily'])
def cmd_daily(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Нет прав.")
        return
    
    bot.send_message(message.chat.id, "📤 Отправка ежедневных тестов...")
    post_daily_test()
    bot.send_message(message.chat.id, "✅ Готово!")

@bot.message_handler(commands=['post'])
def cmd_post(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Нет прав.")
        return
    
    bot.send_message(message.chat.id, "📤 Генерация поста...\n⏳ Это может занять до 40 секунд.")
    text = generate_post("мотивация")
    
    if not text:
        bot.send_message(message.chat.id, "❌ GigaChat не ответил. Пост НЕ отправлен.")
        return
    
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")

# ============================================
# ПЛАНИРОВЩИК
# ============================================
scheduler = BackgroundScheduler()

def schedule_morning():
    text = generate_post("утренняя мотивация")
    if text:
        bot.send_message(CHANNEL_ID, text)

def schedule_daily():
    post_daily_test()

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
    logger.info("🚀 БОТ ЗАПУЩЕН")
    logger.info("✅ Готов к работе!")
    bot.polling(none_stop=True)
