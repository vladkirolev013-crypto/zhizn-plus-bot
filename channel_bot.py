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
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET')

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен!")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === GIGACHAT С КЕШИРОВАНИЕМ ===
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
            giga_token_cache["expires"] = time.time() + 3500
            logger.info("✅ Токен GigaChat получен")
            return token
        logger.error(f"❌ Ошибка токена: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка получения токена: {e}")
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
        "temperature": 0.8,
        "max_tokens": 2000
    }
    
    response = requests.post(
        'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=60
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
              user_id INTEGER, test_id TEXT, answers TEXT, 
              total_score INTEGER, topic TEXT, ai_analysis TEXT, created_at TEXT)''')

conn.commit()

# === ТЕМЫ ТЕСТОВ ===
TEST_TOPICS = {
    "психология": "🧠 Психологическое состояние, эмоции, стресс, самооценка",
    "отношения": "💕 Любовь, дружба, семья, коммуникация", 
    "карьера": "💼 Профессиональное развитие, цели, успех",
    "здоровье": "💪 Физическое и ментальное здоровье, привычки",
    "финансы": "💰 Отношение к деньгам, финансовое мышление",
    "личность": "🌟 Характер, темперамент, личностные качества"
}

# === ГЕНЕРАЦИЯ ТЕСТА ЧЕРЕЗ GIGACHAT ===
def generate_test_questions(topic, count=10):
    """Генерирует уникальные вопросы для теста через GigaChat"""
    try:
        logger.info(f"Генерирую тест по теме: {topic}, {count} вопросов")
        
        system = """Ты — профессиональный психолог и коуч с 20-летним опытом. 
        Ты составляешь глубокие психологические тесты. 
        Вопросы должны быть небанальными, заставлять задуматься, раскрывать личность.
        Каждый вопрос должен иметь 4 варианта ответа с разными баллами (от 0 до 3)."""
        
        user = f"""Составь тест на тему "{topic}" из {count} вопросов.
        
        Требования:
        1. Вопросы должны быть глубокими и психологическими
        2. Каждый вопрос с 4 вариантами ответов (A, B, C, D)
        3. Для каждого варианта укажи баллы (0-3), где 0 - наименее здоровый ответ, 3 - наиболее здоровый
        4. Вопросы должны раскрывать разные аспекты темы
        
        Формат ответа (строго JSON):
        {{
            "questions": [
                {{
                    "question": "Текст вопроса?",
                    "options": {{
                        "A": "Вариант A",
                        "B": "Вариант B", 
                        "C": "Вариант C",
                        "D": "Вариант D"
                    }},
                    "scores": {{
                        "A": 0,
                        "B": 1,
                        "C": 2,
                        "D": 3
                    }}
                }}
            ]
        }}
        
        Верни только JSON, без лишнего текста."""
        
        response = ask_giga(system, user)
        
        # Извлекаем JSON из ответа
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end != -1:
            json_str = response[start:end]
            data = json.loads(json_str)
            return data.get('questions', [])
        else:
            raise Exception("Не удалось извлечь JSON из ответа")
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации теста: {e}")
        return get_fallback_questions(topic, count)

def get_fallback_questions(topic, count):
    """Запасные вопросы если GigaChat не работает"""
    fallback_questions = {
        "психология": [
            {
                "question": "Как часто вы испытываете стресс в повседневной жизни?",
                "options": {"A": "Постоянно", "B": "Часто", "C": "Иногда", "D": "Редко"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как вы обычно справляетесь с негативными эмоциями?",
                "options": {"A": "Подавляю", "B": "Игнорирую", "C": "Обсуждаю", "D": "Анализирую"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как вы оцениваете свою самооценку?",
                "options": {"A": "Низкая", "B": "Заниженная", "C": "Адекватная", "D": "Высокая"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как часто вы чувствуете тревогу без причины?",
                "options": {"A": "Постоянно", "B": "Часто", "C": "Иногда", "D": "Никогда"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как вы относитесь к своим ошибкам?",
                "options": {"A": "Самоедство", "B": "Избегание", "C": "Анализ", "D": "Принятие"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ],
        "отношения": [
            {
                "question": "Как вы реагируете на конфликт в отношениях?",
                "options": {"A": "Агрессивно", "B": "Ухожу от конфликта", "C": "Обсуждаю", "D": "Ищу компромисс"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как вы выражаете свои чувства партнеру?",
                "options": {"A": "Не выражаю", "B": "Редко", "C": "Открыто", "D": "Внимательно"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как вы справляетесь с недопониманием?",
                "options": {"A": "Ссора", "B": "Молчание", "C": "Объяснение", "D": "Диалог"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Доверяете ли вы своему партнеру?",
                "options": {"A": "Нет", "B": "Не полностью", "C": "В основном", "D": "Полностью"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как часто вы проводите время с близкими?",
                "options": {"A": "Редко", "B": "Иногда", "C": "Часто", "D": "Всегда"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ],
        "карьера": [
            {
                "question": "Как вы относитесь к своим профессиональным целям?",
                "options": {"A": "Нет целей", "B": "Неопределенно", "C": "Планирую", "D": "Активно иду"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            },
            {
                "question": "Как вы справляетесь с профессиональным выгоранием?",
                "options": {"A": "Игнорирую", "B": "Терплю", "C": "Отдыхаю", "D": "Меняю подход"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ],
        "здоровье": [
            {
                "question": "Как часто вы заботитесь о своем здоровье?",
                "options": {"A": "Никогда", "B": "Редко", "C": "Регулярно", "D": "Всегда"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ],
        "финансы": [
            {
                "question": "Как вы относитесь к деньгам?",
                "options": {"A": "Страх", "B": "Тревога", "C": "Уверенность", "D": "Спокойствие"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ],
        "личность": [
            {
                "question": "Как вы оцениваете свои личностные качества?",
                "options": {"A": "Критично", "B": "Сомневаюсь", "C": "Объективно", "D": "Позитивно"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]
    }
    
    default = fallback_questions.get(topic, fallback_questions["психология"])
    while len(default) < count:
        default.append(default[0].copy())
    return default[:count]

# === АНАЛИЗ РЕЗУЛЬТАТОВ ===
def analyze_results(topic, answers, scores, total_questions):
    """Генерирует глубокий анализ от психолога и коуча"""
    try:
        logger.info(f"Анализирую результаты теста по теме: {topic}")
        
        system = """Ты — команда из двух экспертов:
        1. Клинический психолог с 25-летним опытом, доктор наук
        2. Бизнес-коуч и коуч по личностному росту, автор бестселлеров
        
        Вы проводите глубокий анализ результатов психологического теста.
        Ваш анализ должен быть максимально полезным, глубоким и персонализированным.
        Пишите тепло, профессионально, с примерами и конкретикой."""
        
        user = f"""Проведи анализ результатов теста по теме "{topic}".
        
        Ответы пользователя (A, B, C, D):
        {answers}
        
        Общий балл: {scores} из {total_questions * 3}
        Процент: {int((scores / (total_questions * 3)) * 100)}%
        
        Напиши развернутый анализ (минимум 700 знаков для бесплатного и 1200 для платного):
        
        1. 🧠 Оценка от клинического психолога:
           - Глубокий анализ личности на основе ответов
           - Выявление сильных сторон и зон роста
           - Психологический портрет
           - Рекомендации по работе над собой
        
        2. 💼 Коучинговый разбор от эксперта:
           - Оценка потенциала и возможностей
           - Конкретные шаги для развития
           - Мотивационные техники
           - Практические упражнения
        
        3. 🌟 Интегральный вывод:
           - Общая картина состояния
           - 3 конкретных действия для улучшения
           - Мотивирующая поддержка
        
        Формат: используй эмодзи, переносы строк, структурируй текст.
        Пиши максимально полезно, конкретно и вдохновляюще."""
        
        response = ask_giga(system, user)
        
        if not response or len(response) < 100:
            raise Exception("Ответ слишком короткий")
            
        return response
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}")
        return get_fallback_analysis(topic, scores, total_questions)

def get_fallback_analysis(topic, scores, total_questions):
    """Запасной анализ если GigaChat не работает"""
    max_score = total_questions * 3
    percentage = int((scores / max_score) * 100)
    
    if percentage >= 70:
        status = "отличное психологическое состояние"
        recommendation = "рекомендуем поддерживать баланс и заниматься профилактикой"
        detail = "Вы демонстрируете высокий уровень психологического благополучия и осознанности."
    elif percentage >= 40:
        status = "удовлетворительное состояние с потенциалом для роста"
        recommendation = "рекомендуем работать над эмоциональным интеллектом и стрессоустойчивостью"
        detail = "У вас хороший фундамент, но есть зоны для развития."
    else:
        status = "требуется внимание к психологическому состоянию"
        recommendation = "рекомендуем обратиться к психологу и начать практиковать mindfulness"
        detail = "Важно уделить время себе и своему внутреннему состоянию."
    
    return f"""🔍 РЕЗУЛЬТАТЫ ТЕСТА
Тема: {topic.title()}

📊 ВАШ РЕЗУЛЬТАТ: {scores} из {max_score} баллов ({percentage}%)

🧠 АНАЛИЗ КЛИНИЧЕСКОГО ПСИХОЛОГА:
Ваше состояние характеризуется как {status}.
{detail}
{scores} баллов отражают ваш текущий уровень психологического благополучия.

💼 РЕКОМЕНДАЦИИ ОТ КОУЧА:
Для дальнейшего развития {recommendation}.
Рекомендуем практиковать осознанность и работать над своими целями.

🌟 ПРАКТИЧЕСКИЕ ШАГИ ДЛЯ УЛУЧШЕНИЯ:
1. Начните вести дневник эмоций (5 минут в день)
2. Практикуйте благодарность — записывайте 3 хороших события каждый день
3. Найдите время для саморефлексии и отдыха

💫 ЗАКЛЮЧЕНИЕ:
Ваш результат показывает, что у вас есть потенциал для роста. 
Каждый день — это возможность стать лучше. Доверяйте себе и своему пути!

#саморазвитие #психология #коучинг #жизньплюс"""

# === ВЕБ-СЕРВЕР ===
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

# === ПРОВЕРКА ПРАВ БОТА ===
def check_bot_in_channel():
    try:
        bot_id = bot.get_me().id
        member = bot.get_chat_member(CHANNEL_ID, bot_id)
        logger.info(f"Статус бота в канале: {member.status}")
        
        if member.status in ['administrator', 'creator']:
            logger.info("✅ Бот имеет права администратора")
            return True
        else:
            logger.error(f"❌ Бот не в канале! Статус: {member.status}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки прав: {e}")
        return False

# === ГЕНЕРАЦИЯ ПОСТА ===
def generate_post(theme):
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
        return f"""✨ {theme.title()}

Каждый день — это новая возможность стать лучше!

🌟 Помните:
• Вы сильнее, чем думаете
• Каждый шаг имеет значение
• Верьте в свои мечты

💫 Начните сегодня с маленького доброго дела!

#жизньплюс #мотивация #саморазвитие #позитив"""

def generate_image(theme):
    try:
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

def post_to_channel(theme):
    try:
        logger.info("=" * 50)
        logger.info(f"📝 ОТПРАВКА ПОСТА: {theme}")
        
        if not check_bot_in_channel():
            logger.error(f"❌ Бот не может постить в {CHANNEL_ID}")
            return False
        
        text = generate_post(theme)
        logger.info(f"Текст готов: {len(text)} символов")
        
        if len(text) > 4096:
            parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for i, part in enumerate(parts):
                bot.send_message(CHANNEL_ID, part)
        else:
            bot.send_message(CHANNEL_ID, text)
            logger.info("✅ Пост отправлен!")
        
        try:
            img_path = generate_image(theme)
            if img_path and os.path.exists(img_path):
                with open(img_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption="✨ Дополнительное вдохновение")
                    logger.info("✅ Картинка отправлена")
                os.remove(img_path)
        except Exception as e:
            logger.warning(f"Картинка не отправлена: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(traceback.format_exc())
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

# === СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ===
user_test_data = {}  # Хранит сгенерированные вопросы

# ============================================
# === ОСНОВНОЕ МЕНЮ С КНОПКАМИ ===
# ============================================

def get_main_keyboard():
    """Создает главную клавиатуру с кнопками"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton('🎯 Пройти тест'),
        telebot.types.KeyboardButton('📊 Мои результаты')
    )
    markup.add(
        telebot.types.KeyboardButton('📋 О тестах'),
        telebot.types.KeyboardButton('❤️ О канале')
    )
    return markup

def get_test_type_keyboard():
    """Клавиатура выбора типа теста"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton('🧠 Бесплатный тест'),
        telebot.types.KeyboardButton('💎 Платный тест')
    )
    markup.add(
        telebot.types.KeyboardButton('🔙 На главную')
    )
    return markup

# ============================================
# === КОМАНДЫ И ОБРАБОТЧИКИ ===
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    """Приветствие и главное меню"""
    welcome_text = (
        "🌟 Добро пожаловать в бота Жизнь+!\n\n"
        "Я создан командой лучших психологов и коучей.\n"
        "Здесь вы можете:\n"
        "✅ Пройти глубокие психологические тесты\n"
        "✅ Получить развернутый анализ от экспертов\n"
        "✅ Узнать больше о себе\n"
        "✅ Получить практические рекомендации\n\n"
        "👉 Нажмите кнопку «🎯 Пройти тест», чтобы начать!"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def show_test_selection(message):
    """Показывает выбор типа теста"""
    text = (
        "🎯 ВЫБЕРИТЕ ТИП ТЕСТА:\n\n"
        "🧠 Бесплатный тест (10 вопросов)\n"
        "• Глубокие психологические вопросы\n"
        "• Развернутый анализ (700+ знаков)\n"
        "• Рекомендации от психолога\n\n"
        "💎 Платный тест (20 вопросов)\n"
        "• Расширенная диагностика\n"
        "• Глубокий анализ (1200+ знаков)\n"
        "• Персональные рекомендации\n"
        "• План развития\n\n"
        "Выберите вариант ниже:"
    )
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=get_test_type_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный тест')
def start_free_test(message):
    """Начинает бесплатный тест с выбором темы"""
    show_topic_selection(message, "free", 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный тест')
def start_paid_test(message):
    """Начинает платный тест с выбором темы"""
    show_topic_selection(message, "paid", 20)

def show_topic_selection(message, test_type, count):
    """Показывает выбор темы для теста"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    for topic, description in TEST_TOPICS.items():
        # Берем только первую часть описания для кнопки
        short_desc = description.split(',')[0] if ',' in description else description
        markup.add(telebot.types.InlineKeyboardButton(
            f"{short_desc}", 
            callback_data=f"topic_{test_type}_{topic}_{count}"
        ))
    
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    bot.send_message(
        message.chat.id,
        f"🎯 Выберите тему теста:\n\n"
        f"Каждая тема содержит уникальные вопросы, созданные искусственным интеллектом.\n\n"
        f"📊 {count} вопросов + развернутый анализ от экспертов",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('topic_'))
def handle_topic_selection(call):
    """Обрабатывает выбор темы"""
    try:
        parts = call.data.split('_')
        test_type = parts[1]
        topic = parts[2]
        count = int(parts[3]) if len(parts) > 3 else 10
        
        # Отправляем уведомление
        bot.edit_message_text(
            f"🔄 Генерирую тест по теме «{topic.title()}»...\n"
            f"Это может занять несколько секунд.\n"
            f"Пожалуйста, подождите...",
            call.message.chat.id,
            call.message.message_id
        )
        
        # Генерируем вопросы
        questions = generate_test_questions(topic, count)
        
        if not questions or len(questions) < count:
            bot.send_message(
                call.message.chat.id,
                "❌ Не удалось сгенерировать тест. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Сохраняем тест
        test_id = f"temp_{int(time.time())}_{call.message.chat.id}"
        user_test_data[call.message.chat.id] = {
            'test_id': test_id,
            'topic': topic,
            'type': test_type,
            'questions': questions,
            'answers': [],
            'current_q': 0,
            'scores': [],
            'total_questions': len(questions)
        }
        
        # Отправляем первый вопрос
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_question(call.message.chat.id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка выбора темы: {e}")
        bot.send_message(
            call.message.chat.id,
            "❌ Произошла ошибка. Попробуйте снова.",
            reply_markup=get_main_keyboard()
        )

def send_question(chat_id):
    """Отправляет текущий вопрос"""
    state = user_test_data.get(chat_id)
    if not state:
        bot.send_message(
            chat_id,
            "❌ Активный тест не найден. Начните новый через кнопку «🎯 Пройти тест»",
            reply_markup=get_main_keyboard()
        )
        return
    
    questions = state['questions']
    current = state['current_q']
    
    if current >= len(questions):
        finish_test(chat_id)
        return
    
    q = questions[current]
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for option, text in q['options'].items():
        markup.add(f"{option}) {text}")
    
    # Кнопка для прерывания теста
    markup.add(telebot.types.KeyboardButton('⏹ Прервать тест'))
    
    bot.send_message(
        chat_id,
        f"📝 Вопрос {current+1}/{len(questions)}\n"
        f"📌 Тема: {state['topic'].title()}\n\n"
        f"{q['question']}",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def cancel_test(message):
    """Прерывает текущий тест"""
    chat_id = message.chat.id
    if chat_id in user_test_data:
        del user_test_data[chat_id]
        bot.send_message(
            chat_id,
            "⏹ Тест прерван.\n\n"
            "Вы можете начать новый в любое время через кнопку «🎯 Пройти тест»",
            reply_markup=get_main_keyboard()
        )
    else:
        bot.send_message(
            chat_id,
            "У вас нет активного теста.",
            reply_markup=get_main_keyboard()
        )

@bot.message_handler(func=lambda m: m.text and any(m.text.startswith(f"{x})") for x in 'ABCD'))
def handle_answer(message):
    """Обрабатывает ответ пользователя"""
    chat_id = message.chat.id
    state = user_test_data.get(chat_id)
    
    if not state:
        bot.send_message(
            chat_id,
            "❌ Активный тест не найден. Начните новый через кнопку «🎯 Пройти тест»",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверяем, что это ответ на текущий вопрос
    current_q = state['current_q']
    if current_q >= len(state['questions']):
        finish_test(chat_id)
        return
    
    # Сохраняем ответ
    letter = message.text[0]
    question = state['questions'][current_q]
    
    state['answers'].append(letter)
    state['scores'].append(question['scores'][letter])
    state['current_q'] += 1
    
    # Отправляем следующий вопрос или завершаем
    if state['current_q'] >= len(state['questions']):
        finish_test(chat_id)
    else:
        send_question(chat_id)

def finish_test(chat_id):
    """Завершает тест и отправляет результат"""
    state = user_test_data.get(chat_id)
    if not state:
        return
    
    # Рассчитываем результат
    total_score = sum(state['scores'])
    max_score = len(state['questions']) * 3
    answers_str = ', '.join(state['answers'])
    
    # Показываем промежуточный результат
    bot.send_message(
        chat_id,
        f"📊 Тест завершен!\n\n"
        f"✅ Вы ответили на {len(state['questions'])} вопросов\n"
        f"📊 Ваш результат: {total_score} из {max_score}\n\n"
        f"⏳ Генерирую подробный анализ от экспертов...\n"
        f"Это займет до 30 секунд. Пожалуйста, подождите!"
    )
    
    # Генерируем анализ
    try:
        analysis = analyze_results(
            state['topic'],
            answers_str,
            total_score,
            len(state['questions'])
        )
        
        # Сохраняем в базу
        c.execute("""INSERT INTO user_results 
                     (user_id, test_id, answers, total_score, topic, ai_analysis, created_at) 
                     VALUES (?,?,?,?,?,?,?)""",
                  (chat_id, state['test_id'], answers_str, total_score, 
                   state['topic'], analysis, datetime.now().isoformat()))
        conn.commit()
        
        # Отправляем результат
        message_text = f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}"
        
        # Разбиваем на части если длинный
        if len(message_text) > 4096:
            parts = [message_text[i:i+4096] for i in range(0, len(message_text), 4096)]
            for i, part in enumerate(parts):
                if i == 0:
                    bot.send_message(chat_id, part)
                else:
                    time.sleep(0.5)
                    bot.send_message(chat_id, part)
        else:
            bot.send_message(chat_id, message_text)
        
        # Отправляем финальную клавиатуру
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            telebot.types.KeyboardButton('🎯 Пройти тест'),
            telebot.types.KeyboardButton('📊 Мои результаты')
        )
        markup.add(
            telebot.types.KeyboardButton('📋 О тестах'),
            telebot.types.KeyboardButton('❤️ О канале')
        )
        
        bot.send_message(
            chat_id,
            "✨ Благодарим за прохождение теста!\n\n"
            "Что бы вы хотели сделать дальше?",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка завершения теста: {e}")
        bot.send_message(
            chat_id,
            "❌ Произошла ошибка при генерации анализа.\n"
            "Попробуйте пройти тест позже.",
            reply_markup=get_main_keyboard()
        )
    
    # Очищаем состояние
    if chat_id in user_test_data:
        del user_test_data[chat_id]

# ============================================
# === ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ===
# ============================================

@bot.message_handler(func=lambda m: m.text == '📊 Мои результаты')
def show_results(message):
    """Показывает историю результатов пользователя"""
    c.execute("""SELECT topic, total_score, created_at 
                 FROM user_results 
                 WHERE user_id = ? 
                 ORDER BY created_at DESC 
                 LIMIT 5""", (message.chat.id,))
    
    results = c.fetchall()
    
    if not results:
        bot.send_message(
            message.chat.id,
            "📭 У вас пока нет пройденных тестов.\n\n"
            "Пройдите первый тест через кнопку «🎯 Пройти тест»!",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = "📊 ВАША ИСТОРИЯ ТЕСТОВ:\n\n"
    for i, (topic, score, date) in enumerate(results, 1):
        text += f"{i}. 📌 {topic.title()}\n"
        text += f"   Баллы: {score}\n"
        text += f"   📅 {date[:10]}\n\n"
    
    text += "💡 Чтобы пройти новый тест, нажмите «🎯 Пройти тест»"
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '📋 О тестах')
def about_tests(message):
    """Информация о тестах"""
    text = (
        "📋 ЧТО ТАКОЕ ТЕСТЫ ЖИЗНЬ+?\n\n"
        "Это уникальные психологические тесты, созданные с помощью искусственного интеллекта на основе методик лучших психологов.\n\n"
        "🔹 Как это работает:\n"
        "1. Вы выбираете тему теста\n"
        "2. Отвечаете на вопросы (10 или 20)\n"
        "3. Получаете глубокий анализ от двух экспертов\n\n"
        "🔹 Кто анализирует результаты:\n"
        "🧠 Клинический психолог — оценивает ваше состояние\n"
        "💼 Коуч — дает практические рекомендации\n\n"
        "🔹 Темы тестов:\n"
        "• Психология — ваше эмоциональное состояние\n"
        "• Отношения — любовь, дружба, семья\n"
        "• Карьера — профессиональное развитие\n"
        "• Здоровье — физическое и ментальное\n"
        "• Финансы — отношение к деньгам\n"
        "• Личность — характер и самооценка\n\n"
        "🎯 Нажмите «🎯 Пройти тест», чтобы начать!"
    )
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    """Информация о канале"""
    text = (
        "❤️ О КАНАЛЕ ЖИЗНЬ+\n\n"
        "Это канал о психологии, саморазвитии и счастливой жизни.\n\n"
        "Здесь вы найдете:\n"
        "✅ Ежедневные посты от психологов\n"
        "✅ Практические советы для жизни\n"
        "✅ Глубокие психологические тесты\n"
        "✅ Мотивацию и вдохновение\n\n"
        "📌 Подписывайтесь, чтобы не пропустить новое!\n"
        f"{CHANNEL_ID}\n\n"
        "🌟 Помните: каждый день — это новая возможность стать лучше!"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "📢 Перейти в канал", 
        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
    ))
    markup.add(telebot.types.InlineKeyboardButton(
        "🎯 Пройти тест", 
        callback_data="go_to_test"
    ))
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == '🔙 На главную')
def back_to_main(message):
    """Возврат на главную"""
    start(message)

@bot.callback_query_handler(func=lambda call: call.data == 'go_to_test')
def callback_go_to_test(call):
    """Обработчик кнопки перехода к тесту"""
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_test_selection(call.message)

@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def callback_cancel(call):
    """Отмена выбора темы"""
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
        "❌ Выбор темы отменен.",
        reply_markup=get_main_keyboard()
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

# === ЗАПУСК БОТА ===
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА")
    logger.info("=" * 50)
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        exit(1)
    
    try:
        chat = bot.get_chat(CHANNEL_ID)
        logger.info(f"✅ Канал найден: {chat.title}")
    except Exception as e:
        logger.error(f"❌ Канал {CHANNEL_ID} не найден: {e}")
    
    check_bot_in_channel()
    
    logger.info("=" * 50)
    logger.info("✅ БОТ ГОТОВ К РАБОТЕ!")
    logger.info("=" * 50)
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
        logger.error(traceback.format_exc())
