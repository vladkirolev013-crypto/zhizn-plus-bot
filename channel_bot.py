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
from flask import Flask, request
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://zhizn-plus-bot.onrender.com') + '/webhook'

GIGA_CLIENT_ID = "019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e"
GIGA_CLIENT_SECRET = "MDE5ZmM3YTItOGQ0Ni03MGNiLTkwMjgtZmNmYzVhMWQ0ZDBlOmY3NjZhOGZjLWUwNTItNGYwZC05NDQwLTUxNzJjNGYyOWE4NQ=="

ADMIN_IDS = [8746212340]

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен!")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# БАЗА ДАННЫХ
# ============================================
DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
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
conn.commit()

# ============================================
# GIGACHAT
# ============================================
giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
    try:
        headers = {
            'Authorization': f'Basic {GIGA_CLIENT_SECRET}',
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
            timeout=30,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"GigaChat ошибка: {response.status_code}")
            return None
        
        return response.json()['choices'][0]['message']['content']
        
    except Exception as e:
        logger.error(f"GigaChat ошибка: {e}")
        return None

def generate_image(prompt):
    try:
        token = get_giga_token()
        if not token:
            return None
        
        headers = {
            'Authorization': f'Bearer {token}',
            'RqUID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        }
        
        payload = {
            "model": "Kandinsky",
            "prompt": prompt,
            "num_images": 1,
            "width": 1024,
            "height": 768,
            "style": "photo-realistic"
        }
        
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/images/generations',
            headers=headers,
            json=payload,
            timeout=60,
            verify=False
        )
        
        if response.status_code != 200:
            logger.error(f"Ошибка генерации картинки: {response.status_code}")
            return None
        
        image_url = response.json()['data'][0]['url']
        img = requests.get(image_url, timeout=30).content
        filename = f'/tmp/image_{int(time.time())}.jpg'
        with open(filename, 'wb') as f:
            f.write(img)
        return filename
        
    except Exception as e:
        logger.error(f"Ошибка генерации картинки: {e}")
        return None

# ============================================
# TELEGRAM БОТ
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)

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
# ПРОМПТЫ
# ============================================
def generate_test_questions(topic, count=10):
    system = """Ты — клинический психолог. Составь глубокие вопросы без штампов.
    Вопросы должны создавать образы, чувства, воспоминания.
    Для платного теста — сложнее, с элементами коучинга.
    Вопросы НЕ повторяются."""
    
    user = f"""Составь {count} глубоких психологических вопросов на тему "{topic}" в формате JSON:
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
    
    response = ask_giga(system, user, max_tokens=3000)
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

def generate_analysis_free(topic, answers, score, total):
    system = """Ты — клинический психолог с 25-летним стажем.
    Говори коротко, но ёмко. Используй НЛП-язык.
    Без воды, без шаблонов.
    Объём: 700+ знаков. БЕЗ книг и упражнений."""
    
    user = f"""Тема: {topic}
Ответы: {answers}
Баллы: {score} из {total}
Проведи глубокий разбор личности. Дай 2 инсайта и 2 вопроса для размышления."""
    
    response = ask_giga(system, user, max_tokens=2000)
    if not response or len(response) < 500:
        return None
    return response

def generate_analysis_paid(topic, answers, score, total):
    system = """Ты — команда: клинический психолог и коуч мирового уровня.
    Психолог даёт 2 инсайта. Коуч даёт 3 конкретных шага на сегодня.
    ВСЁ НА РУССКОМ. Объём: 1400+ знаков."""
    
    user = f"""Тема: {topic}
Ответы: {answers}
Баллы: {score} из {total}
Проведи полный разбор личности. Включи: портрет, 2 инсайта, шаги на неделю, книги, упражнения, видео."""
    
    response = ask_giga(system, user, max_tokens=3000)
    if not response or len(response) < 1000:
        return None
    return response

def generate_analysis(topic, answers, score, total, is_paid):
    if is_paid:
        return generate_analysis_paid(topic, answers, score, total)
    else:
        return generate_analysis_free(topic, answers, score, total)

def generate_post():
    themes = [
        "утренняя энергия", "внутренняя сила", "радость в простых вещах",
        "преодоление страхов", "любовь к себе", "благодарность",
        "мотивация", "осознанность", "отношения", "финансовое мышление"
    ]
    theme = random.choice(themes)
    
    system = """Ты — психолог, который пишет посты, от которых хочется действовать.
    Используй НЛП-язык. Без слащавости. Каждый пост уникальный."""
    
    user = f"""Напиши пост на тему "{theme}" для Telegram.
    Длина: 800–1000 знаков. Заголовок с эмодзи. Практический совет.
    Мотивирующая фраза. Хештеги."""
    
    response = ask_giga(system, user, max_tokens=2000)
    if not response or len(response) < 700:
        return None
    return response

# ============================================
# СЕССИИ
# ============================================
def load_session(chat_id):
    c.execute("SELECT topic, questions, current_q, answers, scores, is_paid, result FROM user_sessions WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    if row:
        return {
            'topic': row[0],
            'questions': json.loads(row[1]),
            'current_q': row[2],
            'answers': json.loads(row[3]) if row[3] else [],
            'scores': json.loads(row[4]) if row[4] else [],
            'is_paid': bool(row[5]),
            'result': row[6]
        }
    return None

def save_session(chat_id, session):
    c.execute("""INSERT OR REPLACE INTO user_sessions 
                 (chat_id, topic, questions, current_q, answers, scores, is_paid, result) 
                 VALUES (?,?,?,?,?,?,?,?)""",
              (chat_id, session['topic'], json.dumps(session['questions']), 
               session['current_q'], json.dumps(session['answers']), 
               json.dumps(session['scores']), int(session['is_paid']), 
               session.get('result', '')))
    conn.commit()

def delete_session(chat_id):
    c.execute("DELETE FROM user_sessions WHERE chat_id=?", (chat_id,))
    conn.commit()

# ============================================
# FLASK
# ============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот Жизнь+ работает!"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403

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
    mk.add('📤 Отправить пост', '🧠 Тест в канал')
    mk.add('🖼 Картинка в канал', '📊 Статистика')
    mk.add('🎫 Создать промокод', '👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

def get_result_menu(chat_id):
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    mk.add('📊 Получить анализ')
    mk.add('🎯 Пройти тест')
    mk.add('❤️ О канале')
    return mk

# ============================================
# ОБРАБОТЧИКИ
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    
    if ' ' in message.text:
        param = message.text.split(' ', 1)[1]
        if param.startswith('daily_'):
            try:
                _, topic, tid = param.split('_')
                c.execute("SELECT questions FROM daily_tests WHERE id=?", (tid,))
                row = c.fetchone()
                if row:
                    questions = json.loads(row[0])
                    session = {
                        'topic': topic,
                        'questions': questions,
                        'current_q': 0,
                        'answers': [],
                        'scores': [],
                        'is_paid': False
                    }
                    save_session(chat_id, session)
                    bot.send_message(chat_id, f"📌 Ежедневный тест: {topic}")
                    send_question(chat_id)
                    return
            except:
                pass
    
    welcome = "🌟 Добро пожаловать в бота Жизнь+!\n\nНажми «🎯 Пройти тест» или «🎫 Активировать промокод»."
    bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))

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
    chat_id = message.chat.id
    
    # Проверяем, есть ли у пользователя активный промокод
    session = load_session(chat_id)
    if session and session.get('is_paid'):
        show_topics(message, 'paid', 20)
        return
    
    if chat_id in ADMIN_IDS:
        show_topics(message, 'paid', 20)
    else:
        bot.send_message(
            chat_id,
            "💎 Платный тест — 50 ₽\n\n"
            "Если у вас есть промокод, активируйте его через кнопку «🎫 Активировать промокод».\n\n"
            "А пока пройдите бесплатный тест.",
            reply_markup=test_type_menu()
        )

# ============================================
# ПРОМОКОДЫ
# ============================================
@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(
        message.chat.id,
        "🎫 Введите промокод:\n\n"
        "Например: ZHIZN100"
    )
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    
    c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
    row = c.fetchone()
    
    if not row:
        bot.send_message(chat_id, "❌ Неверный промокод. Попробуйте ещё раз или проверьте правильность ввода.")
        return
    
    promo_id, used_by = row
    
    if used_by != 0:
        bot.send_message(chat_id, "❌ Этот промокод уже был использован.")
        return
    
    # Активируем промокод для пользователя
    c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
              (chat_id, datetime.now().isoformat(), promo_id))
    conn.commit()
    
    # Обновляем статистику
    c.execute("UPDATE stats SET promo_used = promo_used + 1")
    conn.commit()
    
    # Сохраняем в сессию, что пользователь может пройти платный тест
    session = load_session(chat_id) or {}
    session['is_paid'] = True
    session['promo_used'] = True
    save_session(chat_id, session)
    
    bot.send_message(
        chat_id,
        "🎉 Промокод активирован!\n\n"
        "Теперь вы можете пройти 💎 Платный тест (20 вопросов) БЕСПЛАТНО!\n\n"
        "Нажмите «🎯 Пройти тест» → «💎 Платный (20 вопросов)» и выберите тему."
    )

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "🎫 Введите название промокода (латиницей, без пробелов):\n\n"
        "Например: ZHIZN100\n"
        "Или нажмите «Отмена», чтобы отменить."
    )
    bot.register_next_step_handler(message, process_create_promo)

def process_create_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    
    if code == "ОТМЕНА":
        bot.send_message(chat_id, "❌ Создание промокода отменено.")
        return
    
    if not code or len(code) < 3:
        bot.send_message(chat_id, "❌ Промокод должен содержать минимум 3 символа.")
        return
    
    try:
        c.execute("INSERT INTO promocodes (code, created_by, created_at) VALUES (?, ?, ?)",
                  (code, chat_id, datetime.now().isoformat()))
        conn.commit()
        
        bot.send_message(
            chat_id,
            f"✅ Промокод создан!\n\n"
            f"📌 Код: `{code}`\n"
            f"👤 Создал: {chat_id}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Опубликуйте этот код в соцсетях!\n"
            f"Любой, кто введёт его в боте, получит бесплатный платный тест."
        )
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Такой промокод уже существует. Придумайте другой.")

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
        chat_id = c.message.chat.id
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        
        bot.edit_message_text(
            "⏳ Генерация теста...\nПодождите до 30 секунд.",
            chat_id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, int(count))
        if not questions:
            bot.send_message(chat_id, "❌ Не удалось сгенерировать тест. Попробуйте позже.")
            return
        
        session = {
            'topic': topic,
            'questions': questions,
            'current_q': 0,
            'answers': [],
            'scores': [],
            'is_paid': is_paid
        }
        save_session(chat_id, session)
        
        bot.delete_message(chat_id, c.message.message_id)
        send_question(chat_id)
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
    session = load_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Активный тест не найден. Начните новый через «🎯 Пройти тест».")
        return
    
    if session['current_q'] >= len(session['questions']):
        finish_test(chat_id)
        return
    
    q = session['questions'][session['current_q']]
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for opt, txt in q['options'].items():
        mk.add(f"{opt}) {txt}")
    mk.add('⏹ Прервать тест')
    
    bot.send_message(
        chat_id,
        f"📝 Вопрос {session['current_q']+1}/{len(session['questions'])}\n"
        f"📌 Тема: {session['topic'].title()}\n\n"
        f"{q['question']}",
        reply_markup=mk
    )

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    chat_id = message.chat.id
    delete_session(chat_id)
    bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text and m.text.upper().startswith(('A', 'B', 'C', 'D')))
def handle_answer(message):
    chat_id = message.chat.id
    session = load_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Активный тест не найден.")
        return
    
    if session['current_q'] >= len(session['questions']):
        finish_test(chat_id)
        return
    
    letter = message.text[0].upper()
    q = session['questions'][session['current_q']]
    
    session['answers'].append(letter)
    session['scores'].append(q['scores'][letter])
    session['current_q'] += 1
    save_session(chat_id, session)
    
    send_question(chat_id)

# ============================================
# ЗАВЕРШЕНИЕ ТЕСТА
# ============================================
def finish_test(chat_id):
    session = load_session(chat_id)
    if not session:
        return
    
    score = sum(session['scores'])
    total = len(session['questions']) * 3
    answers = ', '.join(session['answers'])
    is_paid = session.get('is_paid', False)
    
    basic_result = f"Тема: {session['topic']}\nРезультат: {score} из {total}\nОтветы: {answers}"
    session['result'] = basic_result
    save_session(chat_id, session)
    
    # Обновляем статистику
    if is_paid:
        c.execute("UPDATE stats SET paid_count = paid_count + 1")
    else:
        c.execute("UPDATE stats SET free_count = free_count + 1")
    conn.commit()
    
    bot.send_message(
        chat_id,
        f"📊 Тест завершен!\n\n"
        f"✅ Результат: {score} из {total}\n"
        f"⏳ GigaChat генерирует анализ...\nДо 30 секунд."
    )
    
    analysis = None
    for attempt in range(3):
        analysis = generate_analysis(session['topic'], answers, score, len(session['questions']), is_paid)
        if analysis:
            break
        time.sleep(2)
        bot.send_message(chat_id, f"🔄 Попытка {attempt + 2}/3...")
    
    if analysis:
        session['result'] = f"{basic_result}\n\n🔍 {analysis}"
        save_session(chat_id, session)
        bot.send_message(
            chat_id,
            f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}",
            reply_markup=get_main_menu(chat_id)
        )
    else:
        bot.send_message(
            chat_id,
            f"❌ GigaChat временно не отвечает.\n\n"
            f"✅ Ваш результат сохранён.\n\n"
            f"Нажмите «📊 Получить анализ» позже.",
            reply_markup=get_result_menu(chat_id)
        )
    
    delete_session(chat_id)

# ============================================
# ПОВТОРНЫЙ ЗАПРОС АНАЛИЗА
# ============================================
@bot.message_handler(func=lambda m: m.text == '📊 Получить анализ')
def retry_analysis(message):
    chat_id = message.chat.id
    session = load_session(chat_id)
    
    if not session or not session.get('result'):
        bot.send_message(chat_id, "❌ Нет сохранённых результатов.")
        return
    
    if '🔍' in session['result']:
        bot.send_message(chat_id, "✅ Анализ уже был сгенерирован.\n\n" + session['result'])
        return
    
    lines = session['result'].split('\n')
    topic = lines[0].replace('Тема: ', '')
    score_line = lines[1].replace('Результат: ', '')
    score = int(score_line.split(' из ')[0])
    total = int(score_line.split(' из ')[1].split(' ')[0])
    answers = lines[2].replace('Ответы: ', '')
    is_paid = session.get('is_paid', False)
    
    bot.send_message(chat_id, "⏳ Повторная генерация анализа...")
    
    analysis = generate_analysis(topic, answers, score, len(session['questions']), is_paid)
    
    if analysis:
        session['result'] = f"Тема: {topic}\nРезультат: {score} из {total}\nОтветы: {answers}\n\n🔍 {analysis}"
        save_session(chat_id, session)
        bot.send_message(
            chat_id,
            f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}",
            reply_markup=get_main_menu(chat_id)
        )
    else:
        bot.send_message(
            chat_id,
            "❌ GigaChat снова не отвечает. Попробуйте позже.",
            reply_markup=get_result_menu(chat_id)
        )

# ============================================
# АДМИН-КНОПКИ
# ============================================
@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "📤 Генерация поста...\n⏳ До 30 секунд.")
    text = generate_post()
    if not text:
        bot.send_message(message.chat.id, "❌ Не удалось сгенерировать пост.")
        return
    
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")

@bot.message_handler(func=lambda m: m.text == '🖼 Картинка в канал')
def admin_image(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🖼 Генерация картинки...\n⏳ До 30 секунд.")
    
    prompts = [
        "красивый закат над горами, вдохновение, счастье",
        "улыбающаяся девушка в поле цветов, солнечный свет, радость",
        "горное озеро на рассвете, спокойствие, гармония",
        "город на закате, новые возможности, оптимизм",
        "лес и луч солнца, пробуждение, новая жизнь"
    ]
    prompt = random.choice(prompts)
    
    img_path = generate_image(prompt)
    if img_path:
        with open(img_path, 'rb') as photo:
            bot.send_photo(CHANNEL_ID, photo)
        os.remove(img_path)
        bot.send_message(message.chat.id, "✅ Картинка отправлена в канал!")
    else:
        bot.send_message(message.chat.id, "❌ Не удалось сгенерировать картинку. Попробуйте позже.")

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
    
    c.execute("SELECT free_count, paid_count, promo_used FROM stats LIMIT 1")
    row = c.fetchone()
    
    if row:
        free_count, paid_count, promo_used = row
        text = (
            "📊 СТАТИСТИКА\n\n"
            f"🧠 Бесплатных тестов: {free_count}\n"
            f"💎 Платных тестов: {paid_count}\n"
            f"🎫 Промокодов активировано: {promo_used}\n\n"
            f"Всего: {free_count + paid_count + promo_used}"
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
    
    bot.send_message(message.chat.id, "📤 Генерация поста...\n⏳ До 30 секунд.")
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
    try:
        bot.delete_webhook()
        logger.info("✅ Старый вебхук удалён")
    except:
        pass
    time.sleep(2)
    
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"❌ Ошибка установки вебхука: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
