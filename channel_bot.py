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
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET')

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен в переменных окружения!")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === GIGACHAT С КЕШИРОВАНИЕМ ===
giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    """Получает токен GigaChat с кешированием"""
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
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
            token = response.json()['access_token']
            giga_token_cache["token"] = token
            giga_token_cache["expires"] = time.time() + 3500  # ~1 час
            logger.info("✅ Токен GigaChat получен")
            return token
        logger.error(f"❌ Ошибка токена: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка получения токена: {e}")
        return None

def ask_giga(system_prompt, user_prompt):
    """Запрос к GigaChat"""
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
        raise Exception(f"Ошибка GigaChat: {response.status_code} - {response.text}")

# === TELEGRAM БОТ ===
bot = telebot.TeleBot(BOT_TOKEN)

# === БАЗА ДАННЫХ ===
DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Создание таблиц
c.execute('''CREATE TABLE IF NOT EXISTS tests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              title TEXT, type TEXT, questions_count INTEGER, 
              category TEXT, price_stars INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS questions 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              test_id INTEGER, question_text TEXT, 
              option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT, 
              score_a INTEGER DEFAULT 0, score_b INTEGER DEFAULT 1, 
              score_c INTEGER DEFAULT 2, score_d INTEGER DEFAULT 3)''')

c.execute('''CREATE TABLE IF NOT EXISTS user_results 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              user_id INTEGER, test_id INTEGER, answers TEXT, 
              total_score INTEGER, ai_analysis TEXT, created_at TEXT)''')

# Добавляем тестовые вопросы если их нет
c.execute("SELECT COUNT(*) FROM tests")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO tests (title, type, questions_count, category) VALUES ('Психологический тест', 'free', 10, 'психология')")
    test_id = c.lastrowid
    questions = [
        ("Как вы обычно просыпаетесь?", "С радостью", "Нормально", "С трудом", "С раздражением", 3, 2, 1, 0),
        ("Что вы чувствуете утром?", "Энергию", "Спокойствие", "Усталость", "Тревогу", 3, 2, 1, 0),
        ("Какой у вас обычно завтрак?", "Полезный", "Быстрый", "Пропускаю", "Обильный", 3, 2, 1, 0),
        ("Как вы относитесь к планированию дня?", "Планирую всегда", "Иногда", "Редко", "Никогда", 3, 2, 1, 0),
        ("Ваше настроение утром?", "Отличное", "Хорошее", "Нейтральное", "Плохое", 3, 2, 1, 0),
        ("Занимаетесь ли вы зарядкой?", "Каждый день", "Пару раз в неделю", "Редко", "Никогда", 3, 2, 1, 0),
        ("Ваша утренняя рутина?", "Четкий распорядок", "Примерный план", "Как получится", "Хаос", 3, 2, 1, 0),
        ("Что вы делаете в первую очередь?", "Медитация", "Душ", "Кофе", "Телефон", 3, 2, 1, 0),
        ("Как вы настраиваетесь на день?", "Позитивные аффирмации", "План действий", "Просмотр новостей", "Никак", 3, 2, 1, 0),
        ("Ваше отношение к утру?", "Люблю", "Нормально", "Терплю", "Ненавижу", 3, 2, 1, 0)
    ]
    for q in questions:
        c.execute("""INSERT INTO questions 
                     (test_id, question_text, option_a, option_b, option_c, option_d, 
                      score_a, score_b, score_c, score_d) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                  (test_id,) + q)
    conn.commit()
    logger.info("✅ Добавлены тестовые вопросы")

conn.commit()
user_state = {}

# === ВЕБ-СЕРВЕР ДЛЯ RENDER ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот жизнь+ работает!"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# === ПРОВЕРКА ПРАВ БОТА В КАНАЛЕ ===
def check_bot_in_channel():
    """Проверяет, может ли бот отправлять сообщения в канал"""
    try:
        bot_id = bot.get_me().id
        member = bot.get_chat_member(CHANNEL_ID, bot_id)
        logger.info(f"Статус бота в канале: {member.status}")
        
        if member.status in ['administrator', 'creator']:
            logger.info("✅ Бот имеет права администратора")
            return True
        elif member.status == 'member':
            logger.warning("⚠️ Бот просто участник, не может постить")
            return False
        else:
            logger.error(f"❌ Бот не в канале! Статус: {member.status}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки прав: {e}")
        logger.error("Убедитесь, что:")
        logger.error(f"1. Бот добавлен в канал {CHANNEL_ID}")
        logger.error("2. Бот имеет права на отправку сообщений")
        logger.error("3. CHANNEL_ID указан правильно")
        return False

# === ГЕНЕРАЦИЯ ПОСТА С ЗАПАСНЫМ ВАРИАНТОМ ===
def generate_post(theme):
    """Генерирует пост с fallback при ошибке"""
    try:
        logger.info(f"Генерирую пост на тему: {theme}")
        
        system = """Ты — позитивный психолог и мотивационный спикер. Пиши вдохновляющие посты для Telegram-канала о жизни и саморазвитии."""
        user = f"""Напиши пост для Telegram на тему: {theme}.
        Требования:
        - Заголовок с эмодзи
        - Основной текст (400-600 символов)
        - Практический совет или упражнение
        - Мотивационная фраза в конце
        - 3-5 хештегов
        - Без Markdown разметки
        - Только текст"""
        
        text = ask_giga(system, user)
        
        if not text or len(text) < 50:
            raise Exception("GigaChat вернул пустой или короткий ответ")
            
        logger.info(f"✅ Пост сгенерирован: {len(text)} символов")
        return text
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        # Запасной текст
        return f"""✨ {theme.title()}

Каждый день — это новая возможность стать лучше!

🌟 Помните:
• Вы сильнее, чем думаете
• Каждый шаг имеет значение
• Верьте в свои мечты

💫 Начните сегодня с маленького доброго дела!

#жизньплюс #мотивация #саморазвитие #позитив"""

# === ГЕНЕРАЦИЯ КАРТИНКИ ===
def generate_image(theme):
    try:
        # Определяем промпт по теме
        theme_lower = theme.lower()
        if "утро" in theme_lower or "мотивация" in theme_lower:
            prompt = "sunrise motivational landscape beautiful"
        elif "отношения" in theme_lower or "любов" in theme_lower:
            prompt = "couple love relationship happiness"
        elif "финанс" in theme_lower or "успех" in theme_lower:
            prompt = "success wealth money growth"
        else:
            prompt = "motivation inspiration positivity"
            
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1080&height=720&nologo=true"
        img = requests.get(url, timeout=30).content
        filename = f'/tmp/temp_{int(datetime.now().timestamp())}.jpg'
        with open(filename, 'wb') as f:
            f.write(img)
        return filename
    except Exception as e:
        logger.error(f"Ошибка картинки: {e}")
        return None

# === ОТПРАВКА ПОСТА В КАНАЛ ===
def post_to_channel(theme):
    """Отправляет пост в канал с подробным логированием"""
    try:
        logger.info("=" * 50)
        logger.info(f"📝 ОТПРАВКА ПОСТА: {theme}")
        logger.info("=" * 50)
        
        # 1. Проверка прав
        if not check_bot_in_channel():
            error_msg = f"❌ Бот не может постить в {CHANNEL_ID}"
            logger.error(error_msg)
            return False
        
        # 2. Генерация текста
        text = generate_post(theme)
        logger.info(f"Текст готов: {len(text)} символов")
        
        # 3. Отправка
        logger.info(f"Отправляю в {CHANNEL_ID}...")
        
        # Разбиваем если текст длинный
        if len(text) > 4096:
            parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for i, part in enumerate(parts):
                bot.send_message(CHANNEL_ID, part)
                logger.info(f"Часть {i+1}/{len(parts)} отправлена")
        else:
            bot.send_message(CHANNEL_ID, text)
            logger.info("✅ Пост отправлен!")
        
        # 4. Отправка картинки
        try:
            img_path = generate_image(theme)
            if img_path and os.path.exists(img_path):
                with open(img_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption="✨ Дополнительное вдохновение")
                    logger.info("✅ Картинка отправлена")
                os.remove(img_path)
        except Exception as e:
            logger.warning(f"Картинка не отправлена: {e}")
        
        logger.info("=" * 50)
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(traceback.format_exc())
        logger.info("=" * 50)
        return False

# === ПЛАНИРОВЩИК ===
scheduler = BackgroundScheduler()

def post_morning():
    post_to_channel("утренняя мотивация")

def post_relationship():
    post_to_channel("психология отношений")

def post_success():
    post_to_channel("финансы и успех")

scheduler.add_job(post_morning, 'cron', hour=8, minute=0)
scheduler.add_job(post_relationship, 'cron', hour=13, minute=0)
scheduler.add_job(post_success, 'cron', hour=19, minute=0)
scheduler.start()
logger.info("✅ Планировщик запущен")

# === КОМАНДЫ БОТА ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add('Бесплатный тест (10 вопросов)', 'Платный тест (20 вопросов)', 'Список тестов')
    bot.send_message(
        message.chat.id, 
        "Привет! Я бот канала жизнь+\n\nВыбери:", 
        reply_markup=markup
    )

@bot.message_handler(commands=['post'])
def manual_post(message):
    bot.send_message(message.chat.id, "📤 Запрашиваю пост...")
    if post_to_channel("утренняя мотивация"):
        bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка отправки. Проверьте логи.")

@bot.message_handler(commands=['testpost'])
def test_post(message):
    """Тестовая отправка для диагностики"""
    msg = bot.send_message(message.chat.id, "🔍 Проверяю настройки...")
    
    # Проверка 1: Бот в канале
    try:
        bot_info = bot.get_chat_member(CHANNEL_ID, bot.get_me().id)
        status = bot_info.status
        can_post = getattr(bot_info, 'can_post_messages', 'неизвестно')
        bot.edit_message_text(
            f"✅ Бот в канале: {CHANNEL_ID}\n"
            f"Статус: {status}\n"
            f"Может постить: {can_post}",
            message.chat.id, msg.message_id
        )
    except Exception as e:
        bot.edit_message_text(
            f"❌ Бот НЕ в канале!\n"
            f"Ошибка: {e}\n\n"
            f"Добавьте бота в канал {CHANNEL_ID}",
            message.chat.id, msg.message_id
        )
        return
    
    # Проверка 2: Отправка тестового сообщения
    try:
        bot.send_message(CHANNEL_ID, "🧪 Тестовое сообщение от бота")
        bot.edit_message_text(
            "✅ Тестовое сообщение отправлено!\n"
            "Проверьте канал.",
            message.chat.id, msg.message_id
        )
    except Exception as e:
        bot.edit_message_text(
            f"❌ Не могу отправить сообщение!\n"
            f"Ошибка: {e}",
            message.chat.id, msg.message_id
        )

@bot.message_handler(func=lambda m: m.text == 'Бесплатный тест (10 вопросов)')
def free_test(message):
    c.execute("SELECT id, title FROM tests WHERE type='free' LIMIT 1")
    test = c.fetchone()
    if not test:
        bot.send_message(message.chat.id, "Тесты еще не добавлены.")
        return
    user_state[message.chat.id] = {
        'test_id': test[0], 
        'title': test[1], 
        'answers': [], 
        'q_num': 0,
        'total_score': 0
    }
    send_question(message.chat.id)

@bot.message_handler(func=lambda m: m.text in ['Платный тест (20 вопросов)', 'Список тестов'])
def other(message):
    bot.send_message(message.chat.id, "В разработке!")

def send_question(chat_id):
    state = user_state.get(chat_id)
    if not state:
        return
    
    c.execute("""SELECT question_text, option_a, option_b, option_c, option_d 
                 FROM questions WHERE test_id=? LIMIT 1 OFFSET ?""", 
              (state['test_id'], state['q_num']))
    q = c.fetchone()
    
    if not q:
        finish_test(chat_id)
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(f'A) {q[1]}', f'B) {q[2]}')
    markup.add(f'C) {q[3]}', f'D) {q[4]}')
    
    bot.send_message(
        chat_id, 
        f"📝 Тест: {state['title']}\n\n"
        f"Вопрос {state['q_num']+1}/10:\n\n"
        f"{q[0]}", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith(('A) ', 'B) ', 'C) ', 'D) ')))
def handle_answer(message):
    state = user_state.get(message.chat.id)
    if not state:
        return
    
    letter = message.text[0]
    state['answers'].append(letter)
    state['q_num'] += 1
    
    c.execute("SELECT score_a, score_b, score_c, score_d FROM questions WHERE test_id=? LIMIT 1 OFFSET ?", 
              (state['test_id'], state['q_num']-1))
    scores = c.fetchone()
    
    if scores:
        score_map = {'A': scores[0], 'B': scores[1], 'C': scores[2], 'D': scores[3]}
        state['total_score'] += score_map.get(letter, 0)
    
    send_question(message.chat.id)

def finish_test(chat_id):
    state = user_state.get(chat_id)
    if not state:
        return
    
    c.execute("""INSERT INTO user_results 
                 (user_id, test_id, answers, total_score, created_at) 
                 VALUES (?,?,?,?,?)""",
              (chat_id, state['test_id'], json.dumps(state['answers']), 
               state.get('total_score', 0), datetime.now().isoformat()))
    conn.commit()
    
    score = state.get('total_score', 0)
    if score <= 10:
        result = "🎉 Отлично! Вы очень позитивный человек!"
    elif score <= 20:
        result = "😊 Хорошо! У вас здоровый подход к жизни!"
    else:
        result = "💪 Вам стоит немного отдохнуть и расслабиться!"
    
    bot.send_message(
        chat_id, 
        f"📊 Результат:\n\n"
        f"Баллы: {score}/30\n\n"
        f"{result}"
    )
    del user_state[chat_id]

# === ЗАПУСК БОТА ===
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА")
    logger.info("=" * 50)
    
    # Проверка токена
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        exit(1)
    else:
        logger.info("✅ BOT_TOKEN найден")
    
    # Проверка канала
    try:
        chat = bot.get_chat(CHANNEL_ID)
        logger.info(f"✅ Канал найден: {chat.title}")
    except Exception as e:
        logger.error(f"❌ Канал {CHANNEL_ID} не найден: {e}")
        logger.error("Проверьте CHANNEL_ID и добавьте бота в канал")
    
    # Проверка прав
    check_bot_in_channel()
    
    logger.info("=" * 50)
    logger.info("✅ БОТ ГОТОВ К РАБОТЕ!")
    logger.info("=" * 50)
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
        logger.error(traceback.format_exc())
