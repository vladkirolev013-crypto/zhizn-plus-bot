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
# === НАСТРОЙКИ ===
# ============================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@zhizn_plus')
GIGA_CLIENT_ID = os.environ.get('GIGA_CLIENT_ID')
GIGA_CLIENT_SECRET = os.environ.get('GIGA_CLIENT_SECRET')

# === АДМИНЫ ===
ADMIN_IDS = [8746212340]

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен!")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# === GIGACHAT ===
# ============================================
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
            giga_token_cache["expires"] = time.time() + 3500
            logger.info("✅ Токен GigaChat получен")
            return token
        logger.error(f"❌ Ошибка токена: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка получения токена: {e}")
        return None

def ask_giga(system_prompt, user_prompt, max_tokens=2000):
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
        "temperature": 0.8,
        "max_tokens": max_tokens
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

def safe_ask_giga(system_prompt, user_prompt, chat_id=None):
    """Безопасный вызов GigaChat с уведомлением админа"""
    try:
        return ask_giga(system_prompt, user_prompt)
    except Exception as e:
        error_msg = f"❌ GigaChat не отвечает: {str(e)[:200]}"
        logger.error(error_msg)
        
        if chat_id:
            try:
                bot.send_message(chat_id, "❌ Сервис временно недоступен. Попробуйте позже.")
            except:
                pass
        
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, f"❗ ОШИБКА GigaChat:\n{error_msg}")
            except:
                pass
        
        return None

# ============================================
# === TELEGRAM БОТ ===
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# === БАЗА ДАННЫХ ===
# ============================================
DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ТОЛЬКО ОДНА ТАБЛИЦА
c.execute('''CREATE TABLE IF NOT EXISTS daily_tests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              topic TEXT, 
              questions TEXT, 
              created_at TEXT)''')
conn.commit()

# ============================================
# === ТЕМЫ ТЕСТОВ ===
# ============================================
TEST_TOPICS = {
    "психология": "🧠 Психологическое состояние",
    "отношения": "💕 Любовь и дружба",
    "карьера": "💼 Профессиональное развитие",
    "здоровье": "💪 Физическое и ментальное здоровье",
    "финансы": "💰 Отношение к деньгам",
    "личность": "🌟 Характер и самооценка"
}

# ============================================
# === ГЕНЕРАЦИЯ ТЕСТА ===
# ============================================
def generate_test_questions(topic, count=10, chat_id=None):
    """Генерирует вопросы через GigaChat"""
    system = """Ты — профессиональный психолог с 20-летним опытом.
    Ты составляешь глубокие психологические тесты.
    Вопросы должны заставлять задуматься, раскрывать личность.
    Каждый вопрос должен иметь 4 варианта ответа с баллами от 0 до 3."""
    
    user = f"""Составь {count} РАЗНЫХ, НЕ ПОВТОРЯЮЩИХСЯ вопросов на тему "{topic}".
    
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
    
    Верни ТОЛЬКО JSON, без лишнего текста."""
    
    response = safe_ask_giga(system, user, chat_id)
    if not response:
        return None
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start == -1 or end == -1:
            return None
        
        data = json.loads(response[start:end])
        questions = data.get('questions', [])
        
        if len(questions) < count:
            return None
        
        # Проверяем уникальность
        unique = []
        seen = set()
        for q in questions:
            q_text = q.get('question', '')
            if q_text and q_text not in seen:
                seen.add(q_text)
                unique.append(q)
        
        if len(unique) >= count:
            random.shuffle(unique)
            return unique[:count]
        
        return None
    except:
        return None

# ============================================
# === ГЕНЕРАЦИЯ АНАЛИЗА ===
# ============================================
def generate_analysis(topic, answers_str, total_score, total_questions, is_paid=False, chat_id=None):
    """Генерирует анализ через GigaChat"""
    max_score = total_questions * 3
    if max_score == 0:
        return None
    
    percentage = int((total_score / max_score) * 100)
    
    if percentage >= 70:
        level = "высокий"
        rec_count = 4
    elif percentage >= 40:
        level = "средний"
        rec_count = 5
    else:
        level = "начальный"
        rec_count = 6
    
    min_length = 1400 if is_paid else 700
    
    system = """Ты — команда из двух экспертов:
    1. Клинический психолог с 25-летним опытом
    2. Коуч по личностному росту
    
    Проводи глубокий анализ результатов теста.
    ВСЕ РЕКОМЕНДАЦИИ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
    Пиши тепло, профессионально, с примерами."""
    
    user = f"""Проведи анализ теста по теме "{topic}".
    
    Ответы: {answers_str}
    Баллы: {total_score} из {max_score} ({percentage}%)
    Уровень: {level}
    
    Напиши анализ МИНИМУМ на {min_length} знаков:
    
    1. 🧠 Оценка клинического психолога:
       - Психологический портрет
       - Сильные стороны и зоны роста
       - Рекомендации
    
    2. 💼 Коучинговый разбор:
       - Оценка потенциала
       - Шаги для развития
       - Мотивационные техники
    
    3. 📚 ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ ОТ ЭКСПЕРТОВ:
       Подбери {rec_count} КНИГ на русском языке
       Подбери {rec_count} УПРАЖНЕНИЙ на русском языке
       Подбери {rec_count} ВИДЕО на русском языке
    
    ВСЁ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ!"""
    
    response = safe_ask_giga(system, user, chat_id)
    if not response:
        return None
    
    if len(response) < min_length:
        response += f"\n\n💫 Дополнительные рекомендации:\n"
        if percentage >= 70:
            response += "Вы на правильном пути! Продолжайте развиваться."
        elif percentage >= 40:
            response += "У вас хороший фундамент. Сфокусируйтесь на росте."
        else:
            response += "Начните с малого. Каждый шаг важен."
    
    return response

# ============================================
# === ГЕНЕРАЦИЯ ПОСТА ===
# ============================================
def generate_post(theme, chat_id=None):
    """Генерирует пост через GigaChat (1000+ знаков)"""
    system = """Ты — позитивный психолог и мотивационный спикер.
    Пиши глубокие, вдохновляющие посты для Telegram-канала.
    Используй эмодзи, структурируй текст."""
    
    user = f"""Напиши РАЗВЕРНУТЫЙ пост для Telegram на тему "{theme}".
    
    Требования:
    1. Яркий заголовок с эмодзи
    2. Основная часть (500-600 символов) — раскрой тему психологически
    3. Практический совет (100-150 символов)
    4. Вдохновляющая история или притча
    5. Вывод (2-3 предложения)
    6. Мотивационная цитата
    7. 5-7 хештегов
    
    ОБЩАЯ ДЛИНА: 1000-1300 знаков"""
    
    response = safe_ask_giga(system, user, chat_id)
    if not response:
        return None
    
    if len(response) < 800:
        response += f"\n\n💫 Помните: каждый день — это новая возможность стать лучше!"
    
    return response

# ============================================
# === ГЕНЕРАЦИЯ КАРТИНКИ ===
# ============================================
def generate_result_image(score, total, topic):
    """Генерирует картинку результата"""
    try:
        if total == 0:
            return None
        
        percentage = int((score / total) * 100)
        
        if percentage >= 70:
            prompt = "beautiful sunset motivational success happiness celebration"
        elif percentage >= 40:
            prompt = "peaceful nature landscape meditation growth"
        else:
            prompt = "motivational sunrise new beginning hope"
        
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1080&height=720&nologo=true"
        img = requests.get(url, timeout=30).content
        filename = f'/tmp/result_{int(time.time())}.jpg'
        with open(filename, 'wb') as f:
            f.write(img)
        return filename
    except Exception as e:
        logger.error(f"Ошибка картинки: {e}")
        return None

# ============================================
# === ГЕНЕРАЦИЯ СЕРТИФИКАТА ===
# ============================================
def generate_certificate(user_name, topic, score, total_questions):
    """Генерирует сертификат"""
    try:
        img = Image.new('RGB', (1200, 800), color='white')
        draw = ImageDraw.Draw(img)
        
        # Пытаемся загрузить шрифт
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        except:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
        
        backgrounds = {
            "психология": (200, 230, 255),
            "отношения": (255, 200, 220),
            "карьера": (200, 255, 220),
            "здоровье": (220, 255, 200),
            "финансы": (255, 220, 200),
            "личность": (230, 200, 255)
        }
        
        bg_color = backgrounds.get(topic, (200, 230, 255))
        
        # Градиент
        for i in range(800):
            r = int(bg_color[0] * (1 - i/1600) + 255 * (i/1600))
            g = int(bg_color[1] * (1 - i/1600) + 215 * (i/1600))
            b = int(bg_color[2] * (1 - i/1600) + 200 * (i/1600))
            draw.line([(0, i), (1200, i)], fill=(r, g, b), width=1)
        
        # Рамка
        draw.rectangle([(20, 20), (1180, 780)], outline=(100, 100, 100), width=3)
        
        # Текст
        draw.text((600, 80), "СЕРТИФИКАТ О ПРОХОЖДЕНИИ", fill=(50, 50, 150), font=font_title, anchor="mt")
        draw.text((600, 200), f"🌟 {user_name} 🌟", fill=(50, 50, 150), font=font_title, anchor="mt")
        draw.text((600, 280), "успешно прошел(ла) тест", fill=(80, 80, 80), font=font_text, anchor="mt")
        draw.text((600, 350), f"📌 {topic.upper()}", fill=(100, 50, 150), font=font_title, anchor="mt")
        
        max_score = total_questions * 3
        draw.text((600, 430), f"Результат: {score} из {max_score} баллов", fill=(50, 50, 50), font=font_text, anchor="mt")
        
        if max_score > 0:
            percentage = int((score / max_score) * 100)
            if percentage >= 70:
                emoji = "🌟"
                status = "Отличный результат!"
            elif percentage >= 40:
                emoji = "💫"
                status = "Хороший результат!"
            else:
                emoji = "🌱"
                status = "Есть к чему стремиться!"
            
            draw.text((600, 490), f"{emoji} {status}", fill=(50, 50, 150), font=font_title, anchor="mt")
        
        draw.text((600, 580), f"📅 {datetime.now().strftime('%d.%m.%Y')}", fill=(100, 100, 100), font=font_text, anchor="mt")
        draw.text((600, 670), "Жизнь+ | Психология и саморазвитие", fill=(80, 80, 80), font=font_text, anchor="mt")
        
        filename = f'/tmp/certificate_{int(time.time())}.png'
        img.save(filename)
        return filename
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации сертификата: {e}")
        return None

# ============================================
# === УДАЛЕНИЕ СТАРЫХ ТЕСТОВ ===
# ============================================
def cleanup_old_daily_tests():
    """Удаляет тесты старше 24 часов"""
    try:
        cutoff = (datetime.now() - timedelta(days=1)).isoformat()
        c.execute("DELETE FROM daily_tests WHERE created_at < ?", (cutoff,))
        conn.commit()
        logger.info("🧹 Старые ежедневные тесты удалены")
    except Exception as e:
        logger.error(f"Ошибка очистки: {e}")

# ============================================
# === ВЕБ-СЕРВЕР ===
# ============================================
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

# ============================================
# === ПРОВЕРКА ПРАВ ===
# ============================================
def check_bot_in_channel():
    try:
        bot_id = bot.get_me().id
        member = bot.get_chat_member(CHANNEL_ID, bot_id)
        logger.info(f"Статус бота в канале: {member.status}")
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"❌ Ошибка проверки прав: {e}")
        return False

# ============================================
# === ОТПРАВКА ПОСТА ===
# ============================================
def post_to_channel(theme):
    try:
        logger.info(f"📝 ОТПРАВКА ПОСТА: {theme}")
        
        if not check_bot_in_channel():
            logger.error(f"❌ Бот не может постить в {CHANNEL_ID}")
            return False
        
        text = generate_post(theme, ADMIN_IDS[0])
        if not text:
            bot.send_message(ADMIN_IDS[0], f"❌ Не удалось сгенерировать пост на тему: {theme}")
            return False
        
        logger.info(f"Текст готов: {len(text)} символов")
        
        if len(text) > 4096:
            parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for part in parts:
                bot.send_message(CHANNEL_ID, part)
                time.sleep(1)
        else:
            bot.send_message(CHANNEL_ID, text)
        
        logger.info("✅ Пост отправлен!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False

# ============================================
# === ЕЖЕДНЕВНЫЕ ТЕСТЫ ===
# ============================================
def post_daily_test():
    try:
        logger.info("📤 Начинаю отправку ежедневных тестов")
        topics = list(TEST_TOPICS.keys())
        random.shuffle(topics)
        
        sent_count = 0
        for topic in topics:
            try:
                logger.info(f"🔄 Генерирую тест для: {topic}")
                questions = generate_test_questions(topic, 10, ADMIN_IDS[0])
                
                if not questions:
                    bot.send_message(ADMIN_IDS[0], f"❌ Не удалось сгенерировать тест: {topic}")
                    continue
                
                questions_json = json.dumps(questions)
                c.execute("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?,?,?)",
                          (topic, questions_json, datetime.now().isoformat()))
                conn.commit()
                
                test_id = c.lastrowid
                logger.info(f"✅ Тест сохранен, ID: {test_id}")
                
                bot_username = bot.get_me().username
                post_text = (
                    f"🧠 **ЕЖЕДНЕВНЫЙ ТЕСТ ДНЯ!**\n\n"
                    f"📌 Тема: **{topic.title()}**\n"
                    f"📊 Вопросов: 10\n\n"
                    f"Проверьте себя прямо сейчас!\n"
                    f"Нажмите кнопку ниже 👇"
                )
                
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton(
                    "🎯 Пройти тест",
                    url=f"https://t.me/{bot_username}?start=daily_{topic}_{test_id}"
                ))
                
                bot.send_message(CHANNEL_ID, post_text, reply_markup=markup, parse_mode='Markdown')
                
                sent_count += 1
                logger.info(f"✅ Тест отправлен: {topic}")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Ошибка по теме {topic}: {e}")
                continue
        
        # Удаляем старые тесты
        cleanup_old_daily_tests()
        
        logger.info(f"📊 Отправлено {sent_count} тестов")
        return sent_count > 0
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return False

# ============================================
# === МЕНЮ ===
# ============================================
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton('🎯 Пройти тест'),
        telebot.types.KeyboardButton('📋 О тестах')
    )
    markup.add(
        telebot.types.KeyboardButton('❤️ О канале')
    )
    return markup

def get_test_type_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton('🧠 Бесплатный тест (10)'),
        telebot.types.KeyboardButton('💎 Платный тест (20) — 50 ₽')
    )
    markup.add(
        telebot.types.KeyboardButton('🔙 На главную')
    )
    return markup

# ============================================
# === СОСТОЯНИЯ ===
# ============================================
user_test_data = {}

# ============================================
# === КОМАНДЫ БОТА ===
# ============================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    
    if message.text and ' ' in message.text:
        param = message.text.split(' ', 1)[1]
        
        if param.startswith('daily_'):
            try:
                parts = param.split('_')
                if len(parts) >= 3:
                    topic = parts[1]
                    test_id = int(parts[2])
                    
                    c.execute("SELECT questions FROM daily_tests WHERE id = ?", (test_id,))
                    row = c.fetchone()
                    
                    if row:
                        questions = json.loads(row[0])
                        
                        bot.send_message(chat_id, f"🧠 Вы перешли по ежедневному тесту!\n📌 Тема: {topic.title()}")
                        
                        user_test_data[chat_id] = {
                            'topic': topic,
                            'questions': questions,
                            'answers': [],
                            'current_q': 0,
                            'scores': [],
                            'is_paid': False,
                            'is_daily': True
                        }
                        
                        send_question(chat_id)
                        return
            except Exception as e:
                logger.error(f"Ошибка: {e}")
    
    start_menu(message)

def start_menu(message):
    welcome_text = (
        "🌟 Добро пожаловать в бота Жизнь+!\n\n"
        "Я создан командой лучших психологов и коучей.\n"
        "Здесь вы можете пройти глубокие психологические тесты.\n\n"
        "👉 Нажмите кнопку «🎯 Пройти тест»!"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())

# ============================================
# === ОБРАБОТЧИКИ КНОПОК ===
# ============================================
@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def show_test_selection(message):
    text = (
        "🎯 ВЫБЕРИТЕ ТИП ТЕСТА:\n\n"
        "🧠 Бесплатный (10 вопросов)\n"
        "• Анализ 700+ знаков\n"
        "• Рекомендации от экспертов\n\n"
        "💎 Платный (20 вопросов) — 50 ₽\n"
        "• Анализ 1400+ знаков\n"
        "• Книги, упражнения, видео\n\n"
        "Выберите вариант:"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=get_test_type_keyboard())

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный тест (10)')
def start_free_test(message):
    show_topic_selection(message, "free", 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный тест (20) — 50 ₽')
def start_paid_test(message):
    chat_id = message.chat.id
    
    if chat_id in ADMIN_IDS:
        bot.send_message(chat_id, "👑 Платный тест доступен БЕСПЛАТНО для модератора.")
        show_topic_selection(message, "paid_free", 20)
    else:
        bot.send_message(chat_id, "💎 Платный тест — 50 ₽\n\nОплата через Telegram Stars скоро будет доступна.\nА пока пройдите бесплатный тест.")
        show_topic_selection(message, "free", 10)

@bot.message_handler(func=lambda m: m.text == '📋 О тестах')
def about_tests(message):
    text = (
        "📋 О ТЕСТАХ ЖИЗНЬ+\n\n"
        "Каждый тест уникален — вопросы генерируются ИИ.\n"
        "Анализ проводят виртуальные психолог и коуч.\n\n"
        "🔹 Бесплатный: 10 вопросов, анализ 700+ знаков\n"
        "🔹 Платный: 20 вопросов, анализ 1400+ знаков\n\n"
        "🔹 Темы:\n"
        "• Психология\n"
        "• Отношения\n"
        "• Карьера\n"
        "• Здоровье\n"
        "• Финансы\n"
        "• Личность\n\n"
        "Результаты НЕ сохраняются."
    )
    
    bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = (
        "❤️ О КАНАЛЕ ЖИЗНЬ+\n\n"
        "Канал о психологии и саморазвитии.\n\n"
        f"📌 Подписывайтесь: {CHANNEL_ID}\n\n"
        "🌟 Каждый день — новая возможность стать лучше!"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "📢 Перейти в канал",
        url=f"https://t.me/{CHANNEL_ID.replace('@', '')}"
    ))
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '🔙 На главную')
def back_to_main(message):
    start_menu(message)

# ============================================
# === ВЫБОР ТЕМЫ ===
# ============================================
def show_topic_selection(message, test_type, count):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    for topic, description in TEST_TOPICS.items():
        markup.add(telebot.types.InlineKeyboardButton(
            description, 
            callback_data=f"topic_{test_type}_{topic}_{count}"
        ))
    
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    bot.send_message(
        message.chat.id,
        f"🎯 Выберите тему:\n\n{count} вопросов + анализ от экспертов",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('topic_'))
def handle_topic_selection(call):
    try:
        parts = call.data.split('_')
        test_type = parts[1]
        topic = parts[2]
        count = int(parts[3])
        
        is_paid = test_type in ['paid', 'paid_free']
        
        bot.edit_message_text(
            f"🔄 GigaChat генерирует тест...\nПодождите несколько секунд.",
            call.message.chat.id,
            call.message.message_id
        )
        
        questions = generate_test_questions(topic, count, call.message.chat.id)
        
        if not questions:
            bot.send_message(call.message.chat.id, "❌ Не удалось сгенерировать тест. Попробуйте позже.")
            return
        
        user_test_data[call.message.chat.id] = {
            'topic': topic,
            'questions': questions,
            'answers': [],
            'current_q': 0,
            'scores': [],
            'total_questions': len(questions),
            'is_paid': is_paid,
            'is_daily': False
        }
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_question(call.message.chat.id)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(call.message.chat.id, f"❌ Ошибка: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def callback_cancel(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Отменено.", reply_markup=get_main_keyboard())

# ============================================
# === ПРОХОЖДЕНИЕ ТЕСТА ===
# ============================================
def send_question(chat_id):
    state = user_test_data.get(chat_id)
    if not state:
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
    chat_id = message.chat.id
    if chat_id in user_test_data:
        del user_test_data[chat_id]
        bot.send_message(chat_id, "⏹ Тест прерван.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text and any(m.text.startswith(f"{x})") for x in 'ABCD'))
def handle_answer(message):
    chat_id = message.chat.id
    state = user_test_data.get(chat_id)
    
    if not state:
        return
    
    current_q = state['current_q']
    if current_q >= len(state['questions']):
        return
    
    letter = message.text[0]
    question = state['questions'][current_q]
    
    state['answers'].append(letter)
    state['scores'].append(question['scores'][letter])
    state['current_q'] += 1
    
    if state['current_q'] >= len(state['questions']):
        finish_test(chat_id)
    else:
        send_question(chat_id)

# ============================================
# === ЗАВЕРШЕНИЕ ТЕСТА ===
# ============================================
def finish_test(chat_id):
    state = user_test_data.get(chat_id)
    if not state:
        return
    
    # Проверяем, что есть ответы
    if not state.get('scores'):
        bot.send_message(chat_id, "❌ Нет ответов для анализа.")
        del user_test_data[chat_id]
        return
    
    total_score = sum(state['scores'])
    max_score = len(state['questions']) * 3
    answers_str = ', '.join(state['answers'])
    is_paid = state.get('is_paid', False)
    
    if max_score == 0:
        bot.send_message(chat_id, "❌ Ошибка: нет вопросов.")
        del user_test_data[chat_id]
        return
    
    bot.send_message(
        chat_id,
        f"📊 Тест завершен!\n\n"
        f"✅ Ответов: {len(state['questions'])}\n"
        f"📊 Результат: {total_score} из {max_score}\n\n"
        f"⏳ GigaChat генерирует анализ...\nПодождите до 30 секунд."
    )
    
    try:
        analysis = generate_analysis(
            state['topic'],
            answers_str,
            total_score,
            len(state['questions']),
            is_paid,
            chat_id
        )
        
        if not analysis:
            bot.send_message(chat_id, "❌ Не удалось сгенерировать анализ. Попробуйте позже.")
            del user_test_data[chat_id]
            return
        
        # Сертификат
        try:
            user_name = bot.get_chat(chat_id).first_name or "Пользователь"
            cert_path = generate_certificate(user_name, state['topic'], total_score, len(state['questions']))
            
            if cert_path:
                with open(cert_path, 'rb') as cert:
                    bot.send_document(chat_id, cert, caption="🏆 Ваш сертификат!")
                os.remove(cert_path)
        except Exception as e:
            logger.error(f"Ошибка сертификата: {e}")
        
        # Картинка результата
        try:
            img_path = generate_result_image(total_score, max_score, state['topic'])
            if img_path:
                with open(img_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption=f"🌟 Ваш результат: {total_score} из {max_score}")
                os.remove(img_path)
        except Exception as e:
            logger.error(f"Ошибка картинки: {e}")
        
        # Текст результата
        result_text = f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}"
        
        if len(result_text) > 4096:
            parts = [result_text[i:i+4096] for i in range(0, len(result_text), 4096)]
            for part in parts:
                bot.send_message(chat_id, part)
        else:
            bot.send_message(chat_id, result_text)
        
        # НЕ СОХРАНЯЕМ РЕЗУЛЬТАТЫ В БАЗУ
        
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            telebot.types.KeyboardButton('🎯 Пройти тест'),
            telebot.types.KeyboardButton('📋 О тестах')
        )
        markup.add(
            telebot.types.KeyboardButton('❤️ О канале')
        )
        
        bot.send_message(chat_id, "✨ Что дальше?", reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)[:100]}")
    
    if chat_id in user_test_data:
        del user_test_data[chat_id]

# ============================================
# === АДМИН-КОМАНДЫ ===
# ============================================
@bot.message_handler(commands=['daily'])
def manual_daily_test(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Нет прав.")
        return
    
    bot.send_message(message.chat.id, "📤 Отправляю ежедневные тесты...")
    if post_daily_test():
        bot.send_message(message.chat.id, "✅ Тесты отправлены в канал!")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка. Проверьте логи.")

@bot.message_handler(commands=['post'])
def manual_post(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Нет прав.")
        return
    
    bot.send_message(message.chat.id, "📤 Запрашиваю пост...")
    if post_to_channel("утренняя мотивация"):
        bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка.")

@bot.message_handler(commands=['testpost'])
def test_post(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Нет прав.")
        return
    
    msg = bot.send_message(message.chat.id, "🔍 Проверка...")
    
    try:
        bot_info = bot.get_chat_member(CHANNEL_ID, bot.get_me().id)
        bot.edit_message_text(
            f"✅ Бот в канале\nСтатус: {bot_info.status}",
            message.chat.id, msg.message_id
        )
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", message.chat.id, msg.message_id)

# ============================================
# === ПЛАНИРОВЩИК ===
# ============================================
scheduler = BackgroundScheduler()

def schedule_morning():
    post_to_channel("утренняя мотивация")

def schedule_daily_test():
    post_daily_test()

def schedule_evening():
    post_to_channel("финансы и успех")

scheduler.add_job(schedule_morning, 'cron', hour=8, minute=0)
scheduler.add_job(schedule_daily_test, 'cron', hour=10, minute=0)
scheduler.add_job(schedule_evening, 'cron', hour=19, minute=0)
scheduler.start()
logger.info("✅ Планировщик запущен")

# ============================================
# === ЗАПУСК ===
# ============================================
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
    
    # Очищаем старые тесты при старте
    cleanup_old_daily_tests()
    
    logger.info("=" * 50)
    logger.info("✅ БОТ ГОТОВ К РАБОТЕ!")
    logger.info("=" * 50)
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
        logger.error(traceback.format_exc())
