import telebot
import sqlite3
import requests
import os
import json
import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from gigachat import GigaChat
from gigachat.models import Messages, Message, Role

# === НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8799965983:AAGGPCxN1XvrGnmy2INgEneFkLlKU7oRSe4')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID', '019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET', '7b92ff4b-a058-4d3e-a1a7-d8cba1a5d661')

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === GIGACHAT КЛИЕНТ ===
giga = GigaChat(
    credentials=f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}",
    scope="GIGACHAT_API_PERS",
    verify_ssl_certs=True
)

# === TELEGRAM BOT ===
bot = telebot.TeleBot(BOT_TOKEN)

# === БАЗА ДАННЫХ ===
DB_PATH = '/app/data/channel.db'
os.makedirs('/app/data', exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    title TEXT, 
    type TEXT, 
    questions_count INTEGER, 
    category TEXT, 
    price_stars INTEGER DEFAULT 0
)''')

c.execute('''CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    test_id INTEGER, 
    question_text TEXT,
    option_a TEXT, 
    option_b TEXT, 
    option_c TEXT, 
    option_d TEXT,
    score_a INTEGER DEFAULT 0, 
    score_b INTEGER DEFAULT 1, 
    score_c INTEGER DEFAULT 2, 
    score_d INTEGER DEFAULT 3
)''')

c.execute('''CREATE TABLE IF NOT EXISTS user_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    test_id INTEGER, 
    answers TEXT, 
    total_score INTEGER, 
    ai_analysis TEXT, 
    created_at TEXT
)''')
conn.commit()

user_state = {}

# === ГЕНЕРАЦИЯ ПОСТА ЧЕРЕЗ GIGACHAT ===
def generate_post(theme):
    logger.info(f"Генерирую пост: {theme}")
    
    system = "Ты — позитивный психолог и лучший в мире коуч. Пиши тёплые, душевные посты для Telegram."
    user = f"Напиши вдохновляющий пост на тему: {theme}. Длина СТРОГО 500-700 символов. Добавь 4-5 эмодзи. Структура: яркий заголовок, текст (3-4 абзаца), практический совет, мотивирующее завершение. Без markdown-разметки. В конце 3-5 хештегов."
    
    response = giga.chat(Messages(messages=[
        Message(role=Role.SYSTEM, content=system),
        Message(role=Role.USER, content=user)
    ]))
    
    text = response.choices[0].message.content
    logger.info(f"GigaChat ответил: {len(text)} символов")
    return text

# === ГЕНЕРАЦИЯ КАРТИНКИ ===
def generate_image(theme):
    try:
        if "утро" in theme.lower():
            prompt = "sunrise motivational peaceful morning positive energy warm light"
        elif "отношения" in theme.lower():
            prompt = "people connection love warm relationship heart hands holding kindness"
        elif "финансы" in theme.lower():
            prompt = "success money growth business achievement gold coins upward trend"
        else:
            prompt = "positive motivation inspiration light hope dream achievement success"
        
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1080&nologo=true&model=flux"
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
    try:
        logger.info(f"Отправляю пост: {theme}")
        text = generate_post(theme)
        logger.info(f"Длина поста: {len(text)} символов")
        
        img_path = generate_image(theme)
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=text)
            os.remove(img_path)
            logger.info("Пост с картинкой отправлен!")
        else:
            bot.send_message(CHANNEL_ID, text)
            logger.info("Пост отправлен!")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False

# === ПЛАНИРОВЩИК АВТОПОСТИНГА ===
scheduler = BackgroundScheduler()

@scheduler.scheduled_job('cron', hour=8, minute=0)
def morning_post():
    post_to_channel("утренняя мотивация и позитивный настрой на день")

@scheduler.scheduled_job('cron', hour=13, minute=0)
def afternoon_post():
    post_to_channel("психология отношений и саморазвитие")

@scheduler.scheduled_job('cron', hour=19, minute=0)
def evening_post():
    post_to_channel("финансовая грамотность и успех в жизни")

# === КОМАНДА /START ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        telebot.types.KeyboardButton('Бесплатный тест (10 вопросов)'),
        telebot.types.KeyboardButton('Платный тест (20 вопросов)'),
        telebot.types.KeyboardButton('Список тестов')
    )
    bot.send_message(message.chat.id, 
        "Привет! Я бот канала жизнь+\n\n"
        "Тесты для самопознания:\n"
        "Бесплатные — быстрый разбор\n"
        "Платные — глубокий AI-анализ\n\n"
        "Выбери:", reply_markup=markup)

# === КОМАНДА /POST (ручной пост) ===
@bot.message_handler(commands=['post'])
def manual_post(message):
    bot.send_message(message.chat.id, "Запрашиваю пост у GigaChat...")
    if post_to_channel("утренняя мотивация"):
        bot.send_message(message.chat.id, "✅ Пост отправлен!")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка. Смотри логи.")

# === БЕСПЛАТНЫЙ ТЕСТ ===
@bot.message_handler(func=lambda m: m.text == 'Бесплатный тест (10 вопросов)')
def free_test(message):
    c.execute("SELECT id, title FROM tests WHERE type='free' LIMIT 1")
    test = c.fetchone()
    if not test:
        bot.send_message(message.chat.id, "Тесты еще не добавлены. Обратитесь к администратору.")
        return
    user_state[message.chat.id] = {'test_id': test[0], 'title': test[1], 'answers': [], 'q_num': 0}
    send_question(message.chat.id)

# === ПЛАТНЫЙ ТЕСТ И СПИСОК ===
@bot.message_handler(func=lambda m: m.text in ['Платный тест (20 вопросов)', 'Список тестов'])
def other(message):
    bot.send_message(message.chat.id, "В разработке! Пройди пока бесплатный тест 😉")

# === ОТПРАВКА ВОПРОСА ===
def send_question(chat_id):
    state = user_state.get(chat_id)
    if not state:
        return
    c.execute("SELECT question_text, option_a, option_b, option_c, option_d FROM questions WHERE test_id=? LIMIT 1 OFFSET ?", 
              (state['test_id'], state['q_num']))
    q = c.fetchone()
    if not q:
        finish_test(chat_id)
        return
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        telebot.types.KeyboardButton(f'A) {q[1]}'),
        telebot.types.KeyboardButton(f'B) {q[2]}'),
        telebot.types.KeyboardButton(f'C) {q[3]}'),
        telebot.types.KeyboardButton(f'D) {q[4]}')
    )
    bot.send_message(chat_id, 
        f"Тест: {state['title']}\n\n"
        f"Вопрос {state['q_num']+1}/10:\n\n"
        f"{q[0]}", reply_markup=markup)

# === ОБРАБОТКА ОТВЕТА ===
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
        state.setdefault('total_score', 0)
        state['total_score'] += score_map.get(letter, 0)
    send_question(message.chat.id)

# === ЗАВЕРШЕНИЕ ТЕСТА ===
def finish_test(chat_id):
    state = user_state.get(chat_id)
    if not state:
        return
    c.execute("INSERT INTO user_results (user_id, test_id, answers, total_score, created_at) VALUES (?,?,?,?,?)",
              (chat_id, state['test_id'], json.dumps(state['answers']), state.get('total_score', 0), datetime.now().isoformat()))
    conn.commit()
    
    score = state.get('total_score', 0)
    if score <= 10:
        result = "🎉 Отлично! У тебя низкий уровень стресса!"
    elif score <= 20:
        result = "😊 Нормально! Всё в порядке!"
    else:
        result = "💪 Стоит отдохнуть!"
    
    bot.send_message(chat_id, f"Твой результат:\n\nБаллы: {score}/30\n\n{result}")
    del user_state[chat_id]

# === ЗАПУСК ===
if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("БОТ КАНАЛА 'жизнь+' ЗАПУЩЕН НА RAILWAY!")
    logger.info("=" * 60)
    logger.info("AI: GigaChat (официальный клиент)")
    logger.info("Автопостинг: 8:00, 13:00, 19:00")
    logger.info("=" * 60)
    
    scheduler.start()
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            logger.error(f"Связь с Telegram прервалась: {e}")
            logger.info("Переподключение через 5 секунд...")
            time.sleep(5)
