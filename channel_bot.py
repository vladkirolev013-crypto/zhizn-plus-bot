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
ADMIN_IDS = [8746212340]

GIGA_CLIENT_ID = "019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e"
GIGA_CLIENT_SECRET = "MDE5ZmM3YTItOGQ0Ni03MGNiLTkwMjgtZmNmYzVhMWQ0ZDBlOjljMmUzNTI3LWI3NzAtNDU0NS1iMTFmLTBiZDljNDMxNWU1Mw=="

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# ЖЕСТКОЕ УБИЙСТВО 409 - ПЕРЕД ВСЕМ
# ============================================

def kill_409_forever():
    """Уничтожает ВСЕ следы вебхука и конфликтов"""
    try:
        # 1. Удаляем вебхук 5 раз для надежности
        for i in range(5):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            requests.post(url, json={"drop_pending_updates": True})
            time.sleep(0.5)
        
        # 2. Сбрасываем вебхук
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        requests.post(url, json={"url": "", "drop_pending_updates": True})
        
        # 3. Удаляем все возможные файлы
        for pattern in ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid']:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                    logger.info(f"Удален файл: {f}")
                except:
                    pass
        
        # 4. Проверяем статус
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url)
        logger.info(f"Вебхук статус: {response.json()}")
        
        time.sleep(3)
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        return False

# ВЫПОЛНЯЕМ УБИЙСТВО 409
kill_409_forever()

# ============================================
# GIGACHAT С ПРАВИЛЬНЫМ ОЖИДАНИЕМ
# ============================================

giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
    try:
        auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        logger.info("🔄 Получение токена...")
        response = requests.post(
            'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
            headers=headers,
            data='scope=GIGACHAT_API_PERS',
            timeout=30,
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
        logger.error(f"Ошибка: {e}")
        return None

def ask_giga(system, user, max_tokens=3000):
    """Запрос к GigaChat С ОЖИДАНИЕМ 30 СЕКУНД"""
    token = get_giga_token()
    if not token:
        logger.error("❌ Нет токена")
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
        logger.info("📤 Запрос к GigaChat...")
        start_time = time.time()
        
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=90,
            verify=False
        )
        
        elapsed = time.time() - start_time
        logger.info(f"⏱ Ответ за {elapsed:.1f} сек")
        
        # ГАРАНТИРОВАННОЕ ОЖИДАНИЕ 30 СЕКУНД
        if elapsed < 30:
            wait_time = 30 - elapsed
            logger.info(f"⏳ Ожидание {wait_time:.1f} сек (гарантия генерации)")
            time.sleep(wait_time)
        
        if response.status_code != 200:
            logger.error(f"Ошибка GigaChat: {response.status_code}")
            return None
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        logger.info("✅ Ответ получен")
        return content
        
    except requests.exceptions.Timeout:
        logger.error("❌ Таймаут 90 сек")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return None

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

# ============================================
# 100+ ТЕМ ДЛЯ ПОСТОВ
# ============================================

POST_THEMES = [
    "внутренняя сила и ресурсность", "как перестать себя обесценивать",
    "искусство говорить НЕТ", "почему мы боимся перемен",
    "как полюбить свое тело", "энергия денег и изобилие",
    "как выйти из токсичных отношений", "сила благодарности каждый день",
    "как перестать ждать одобрения", "осознанное одиночество",
    "как прощать себя за ошибки", "эмоциональный интеллект",
    "как превратить страх в топливо", "искусство быть уязвимым",
    "как найти свое призвание", "сила тишины и покоя",
    "как выстроить личные границы", "психология денег",
    "как пережить предательство", "искусство отпускать",
    "как стать лучшей версией себя", "сила привычек",
    "как управлять эмоциями", "почему мы выбираем не тех",
    "как исцелить внутреннего ребенка", "искусство быть счастливым",
    "как перестать сравнивать", "сила рода",
    "как выйти из созависимости", "искусство принимать",
    "как полюбить работу", "сила дыхания",
    "как пережить кризис", "искусство благодарности",
    "как найти опору", "психология успеха",
    "как перестать быть жертвой", "сила женской энергии",
    "как выстроить отношения с едой", "искусство быть в потоке",
    "как преодолеть прокрастинацию", "сила утра",
    "как исцелить отношения с родителями", "искусство быть лидером",
    "как перестать контролировать", "сила прощения",
    "как найти радость", "психология изобилия",
    "как выйти из зоны комфорта", "искусство слушать сердце",
    "как стать увереннее", "сила юмора",
    "как пережить потерю", "искусство быть в гармонии",
    "как развить интуицию", "сила творчества",
    "как перестать тревожиться", "искусство настоящего момента",
    "как принять уникальность", "психология отношений с деньгами",
    "как выстроить доверие к себе", "сила тишины",
    "как пережить измену", "искусство быть щедрым",
    "как найти внутренний стержень", "сила слова",
    "как исцелить сердечные раны", "искусство быть в контакте с телом",
    "как перестать быть удобным", "сила рода и предков"
]

TEST_TOPICS = {
    "психология": "🧠 Глубинная психология",
    "отношения": "💕 Трансформация отношений",
    "карьера": "💼 Самореализация",
    "здоровье": "💪 Психосоматика",
    "финансы": "💰 Денежное мышление",
    "личность": "🌟 Самость и архетипы"
}

# ============================================
# ИДЕАЛЬНЫЙ ПРОМПТ ДЛЯ ПОСТА
# ============================================

def generate_post():
    theme = random.choice(POST_THEMES)
    
    system = """ТЫ - МИРОВОЙ ЭКСПЕРТ В ПСИХОЛОГИИ И КОУЧИНГЕ.
    
    ТВОЙ СТИЛЬ:
    - Глубокий, мудрый, без пафоса
    - Используешь НЛП-язык
    - Каждый пост - терапевтический сеанс
    - Энергия текста заряжает и мотивирует
    
    СТРУКТУРА:
    1. ЗАХВАТЫВАЮЩИЙ ЗАГОЛОВОК (с эмодзи)
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ
    3. ОСНОВНАЯ ЧАСТЬ (инсайты)
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ
    5. ВОПРОС К ЧИТАТЕЛЮ
    6. МОТИВИРУЮЩИЙ ФИНАЛ
    7. ХЕШТЕГИ
    
    ДЛИНА: 800-1200 знаков"""
    
    user = f"""Напиши пост на тему: "{theme}"
    Сделай его уникальным и трансформирующим."""
    
    response = ask_giga(system, user, 3000)
    if response and len(response) > 500:
        return response
    return None

# ============================================
# ИДЕАЛЬНЫЙ ПРОМПТ ДЛЯ ТЕСТА (Б ВАРИАНТ)
# ============================================

def generate_test_questions(topic, count=10):
    if count == 10:
        system = """Ты — эксперт по клинической психологии.
        Создай СКРИНИНГОВЫЙ тест из 10 вопросов.
        Каждый вопрос должен задевать МАКСИМУМ сфер.
        Верни ТОЛЬКО JSON массив."""
        
        user = f"""Составь 10 вопросов для БЫСТРОЙ ДИАГНОСТИКИ по теме "{topic}".
        Каждый вопрос затрагивает 2-3 сферы жизни.
        Формат JSON:
        [
            {{
                "question": "вопрос?",
                "options": {{"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"}},
                "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}
            }}
        ]
        Верни ТОЛЬКО JSON."""
    else:
        system = """Ты — клинический психолог с 25-летним стажем.
        Проведи ПОЛНУЮ ДИАГНОСТИКУ личности.
        20 вопросов, которые проникают вглубь.
        Верни ТОЛЬКО JSON массив."""
        
        user = f"""Составь 20 ГЛУБИННЫХ вопросов для полного разбора по теме "{topic}".
        Вопросы должны выявлять КОРЕНЬ проблемы.
        Формат JSON:
        [
            {{
                "question": "глубокий вопрос?",
                "options": {{"A": "ответ 1", "B": "ответ 2", "C": "ответ 3", "D": "ответ 4"}},
                "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}
            }}
        ]
        Верни ТОЛЬКО JSON."""
    
    response = ask_giga(system, user, 4000)
    if not response:
        return None
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start == -1 or end == -1:
            return None
        
        questions = json.loads(response[start:end])
        for q in questions:
            if 'scores' not in q:
                q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        return questions[:count]
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

# ============================================
# ИДЕАЛЬНЫЙ ПРОМПТ ДЛЯ АНАЛИЗА (Б ВАРИАНТ)
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    if not is_paid:
        system = """Ты — опытный психолог-диагност.
        По результатам 10 вопросов определи ГЛАВНУЮ проблему человека.
        
        СТРУКТУРА:
        1. ТОП-1 проблема
        2. 1 МОЩНЫЙ ИНСАЙТ
        3. 1 ВОПРОС ДЛЯ РАЗМЫШЛЕНИЯ
        4. 1 КОНКРЕТНЫЙ ШАГ
        
        Объем: 600-800 знаков."""
        
        user = f"""ТЕМА: {topic}
ОТВЕТЫ: {answers}
БАЛЛЫ: {score} из {total}
Определи главную проблему и дай ценный ответ."""
    else:
        system = """ТЫ - МЕЖДУНАРОДНАЯ КОМАНДА ЭКСПЕРТОВ:
        1. Клинический психолог
        2. Коуч
        3. НЛП-терапевт
        
        СТРУКТУРА:
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
        2. 2-3 ГЛУБИННЫХ ИНСАЙТА
        3. КОРЕНЬ ПРОБЛЕМЫ
        4. ПЛАН НА НЕДЕЛЮ (3 шага)
        5. РЕКОМЕНДАЦИИ КНИГ (2 книги)
        6. УПРАЖНЕНИЕ
        7. ВИДЕО
        
        Объем: 1500+ знаков."""
        
        user = f"""ТЕМА: {topic}
ОТВЕТЫ: {answers}
БАЛЛЫ: {score} из {total}
Проведи полный разбор личности."""
    
    response = ask_giga(system, user, 4000 if is_paid else 2500)
    if response:
        return response
    return None

# ============================================
# TELEGRAM БОТ
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# ВЕБ-СЕРВЕР
# ============================================

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
    welcome = """🌟 ДОБРО ПОЖАЛОВАТЬ!

Я — твой проводник в мир осознанности.

Нажми «🎯 Пройти тест» — начни исследование себя."""
    bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = """💫 ЖИЗНЬ+ — пространство трансформаций.

Подпишись, чтобы не пропустить магию каждого дня."""
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
        "🎯 ВЫБЕРИ ГЛУБИНУ:\n\n"
        "🧠 БЕСПЛАТНЫЙ — 10 вопросов (диагностика)\n"
        "💎 ПЛАТНЫЙ — 20 вопросов (полный разбор)",
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
        f"🔮 ВЫБЕРИ СФЕРУ:\n\nВопросов: {count}",
        reply_markup=mk
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n⏱ До 30 секунд",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, int(count))
        
        if not questions:
            bot.send_message(c.message.chat.id, "❌ Ошибка. Попробуй позже.")
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
    c.answer()

def send_question(chat_id):
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
    
    total = len(s['questions'])
    current = s['q'] + 1
    
    message = f"""🔮 ВОПРОС {current} ИЗ {total}

📌 СФЕРА: {s['topic'].title()}

{q['question']}

Выбери вариант ответа:"""
    
    bot.send_message(chat_id, message, reply_markup=mk)

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
        f"📊 ТЕСТ ЗАВЕРШЕН!\n\n"
        f"✅ Результат: {score} из {total}\n"
        f"⏳ Анализирую... До 30 секунд"
    )
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    
    if analysis:
        if is_paid:
            result = f"🔮 ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ\n\n{analysis}"
        else:
            result = f"🔍 ДИАГНОСТИКА\n\n{analysis}"
        
        bot.send_message(chat_id, result, reply_markup=get_main_menu(chat_id))
    else:
        bot.send_message(
            chat_id,
            "❌ Не удалось сгенерировать анализ.\nПопробуй позже.",
            reply_markup=get_main_menu(chat_id)
        )
    
    del sessions[chat_id]

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    if message.chat.id not in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "👑 АДМИН-ПАНЕЛЬ", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🌀 ГЕНЕРАЦИЯ ПОСТА...\n⏱ До 30 секунд")
    text = generate_post()
    
    if not text:
        bot.send_message(message.chat.id, "❌ Ошибка")
        return
    
    c.execute("INSERT INTO posts_history (content) VALUES (?)", (text,))
    conn.commit()
    
    try:
        bot.send_message(CHANNEL_ID, text)
        bot.send_message(message.chat.id, "✅ ПОСТ ОТПРАВЛЕН!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🌀 ГЕНЕРАЦИЯ ТЕСТА...")
    
    topic = random.choice(list(TEST_TOPICS.keys()))
    questions = generate_test_questions(topic, 10)
    
    if not questions:
        bot.send_message(message.chat.id, "❌ Ошибка")
        return
    
    c.execute("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?, ?, ?)",
              (topic, json.dumps(questions), datetime.now().isoformat()))
    conn.commit()
    test_id = c.lastrowid
    
    bot_info = bot.get_me()
    test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
    
    test_text = f"""🔮 ТЕСТ: «{topic.title()}»

🎯 {test_url}

#жизньплюс #тест"""
    
    bot.send_message(CHANNEL_ID, test_text)
    bot.send_message(message.chat.id, "✅ ТЕСТ ОТПРАВЛЕН!", reply_markup=admin_menu())

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
    
    stats_text = f"""📊 СТАТИСТИКА

📝 Тестов: {tests_count}
📤 Постов: {posts_count}
🧠 Бесплатных: {stats_row[0] if stats_row else 0}
💎 Платных: {stats_row[1] if stats_row else 0}
🎫 Промокодов: {stats_row[2] if stats_row else 0}"""
    
    bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🎫 ВВЕДИ КОД:")
    bot.register_next_step_handler(message, process_create_promo)

def process_create_promo(message):
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
        bot.send_message(
            chat_id,
            f"✅ ПРОМОКОД: `{code}`",
            reply_markup=admin_menu()
        )
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ УЖЕ СУЩЕСТВУЕТ", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(
        message.chat.id,
        "🎫 ВВЕДИ ПРОМОКОД:",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    
    c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
    row = c.fetchone()
    
    if not row:
        bot.send_message(chat_id, "❌ НЕВЕРНЫЙ КОД", reply_markup=get_main_menu(chat_id))
        return
    
    promo_id, used_by = row
    
    if used_by != 0:
        bot.send_message(chat_id, "❌ УЖЕ ИСПОЛЬЗОВАН", reply_markup=get_main_menu(chat_id))
        return
    
    c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
              (chat_id, datetime.now().isoformat(), promo_id))
    conn.commit()
    
    c.execute("UPDATE stats SET promo_used = promo_used + 1")
    conn.commit()
    
    bot.send_message(
        chat_id,
        "🎉 ПРОМОКОД АКТИВИРОВАН!\n\nТеперь доступен платный тест!",
        reply_markup=get_main_menu(chat_id)
    )

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info("🤖 ЗАПУСК БОТА...")
    try:
        # ЕЩЕ РАЗ УДАЛЯЕМ ВЕБХУК
        kill_409_forever()
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    run_bot()
