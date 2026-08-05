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

def kill_409():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        requests.post(url, json={"drop_pending_updates": True})
        for f in glob.glob('update-offset-*.json'):
            try:
                os.remove(f)
            except:
                pass
        return True
    except:
        return False

kill_409()
time.sleep(2)

# ============================================
# GIGACHAT С ОЖИДАНИЕМ
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
        start_time = time.time()
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=90,
            verify=False
        )
        
        elapsed = time.time() - start_time
        
        if elapsed < 30:
            wait_time = 30 - elapsed
            logger.info(f"⏳ Ожидание {wait_time:.1f} сек")
            time.sleep(wait_time)
        
        if response.status_code != 200:
            logger.error(f"Ошибка: {response.status_code}")
            return None
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

# ============================================
# ИДЕАЛЬНЫЕ ПРОМПТЫ - НЕ ПОВТОРЯЮТСЯ НИКОГДА
# ============================================

# 100+ ТЕМ ДЛЯ ПОСТОВ (каждый раз случайная)
POST_THEMES = [
    "внутренняя сила и ресурсность",
    "как перестать себя обесценивать",
    "искусство говорить НЕТ",
    "почему мы боимся перемен",
    "как полюбить свое тело",
    "энергия денег и изобилие",
    "как выйти из токсичных отношений",
    "сила благодарности каждый день",
    "как перестать ждать одобрения",
    "осознанное одиночество vs одиночество",
    "как прощать себя за ошибки",
    "эмоциональный интеллект в действии",
    "как превратить страх в топливо",
    "искусство быть уязвимым",
    "как найти свое призвание",
    "сила тишины и внутреннего покоя",
    "как выстроить личные границы",
    "психология денег: мышление богатого",
    "как пережить предательство",
    "искусство отпускать людей",
    "как стать лучшей версией себя",
    "сила привычек и ритуалов",
    "как управлять своими эмоциями",
    "почему мы выбираем не тех партнеров",
    "как исцелить внутреннего ребенка",
    "искусство быть счастливым здесь и сейчас",
    "как перестать сравнивать себя с другими",
    "сила рода и родовые сценарии",
    "как выйти из созависимости",
    "искусство принимать комплименты",
    "как полюбить свою работу",
    "сила дыхания и осознанности",
    "как пережить кризис среднего возраста",
    "искусство благодарности",
    "как найти опору внутри себя",
    "психология успеха и неудач",
    "как перестать быть жертвой",
    "сила женской энергии",
    "как выстроить здоровые отношения с едой",
    "искусство быть в потоке",
    "как преодолеть прокрастинацию",
    "сила утра и новые начинания",
    "как исцелить отношения с родителями",
    "искусство быть лидером своей жизни",
    "как перестать контролировать всё",
    "сила прощения себя и других",
    "как найти радость в простых вещах",
    "психология изобилия и достатка",
    "как выйти из зоны комфорта",
    "искусство слушать свое сердце",
    "как стать увереннее в себе",
    "сила юмора и легкости",
    "как пережить потерю близкого",
    "искусство быть в гармонии с собой",
    "как развить интуицию",
    "сила творчества и самовыражения",
    "как перестать тревожиться о будущем",
    "искусство настоящего момента",
    "как принять свою уникальность",
    "психология отношений с деньгами",
    "как выстроить доверие к себе",
    "сила тишины и уединения",
    "как пережить измену и предательство",
    "искусство быть щедрым к себе",
    "как найти внутренний стержень",
    "сила слова и намерения",
    "как исцелить сердечные раны",
    "искусство быть в контакте с телом",
    "как перестать быть удобным для всех",
    "сила рода и предков",
    "как выстроить здоровую самооценку",
    "психология успешных отношений",
    "как перестать обесценивать свои достижения",
    "искусство радоваться жизни",
    "как найти силу в слабости",
    "сила намерения и фокуса",
    "как пережить развод и расставание",
    "искусство быть в потоке денег",
    "как полюбить свои несовершенства",
    "сила благословения и благодарности",
    "как выстроить отношения с собой",
    "психология счастья и удовлетворенности",
    "как перестать бояться осуждения",
    "искусство быть честным с собой",
    "как найти призвание и миссию",
    "сила дисциплины и свободы",
    "как исцелить травмы прошлого",
    "искусство быть в гармонии с миром",
    "как перестать искать виноватых",
    "сила прощения и отпускания",
    "как выстроить здоровые отношения с деньгами",
    "психология самореализации",
    "как перестать играть роли",
    "искусство быть подлинным",
    "как найти внутреннюю опору",
    "сила каждого нового дня",
    "как пережить эмоциональное выгорание",
    "искусство быть в контакте с душой",
    "как выстроить отношения мечты",
    "сила благодарности как практика",
    "как перестать жить чужими ожиданиями",
    "искусство быть свободным",
    "как найти радость в процессе жизни"
]

# ============================================
# ИДЕАЛЬНЫЙ ПРОМПТ ДЛЯ ПОСТА
# ============================================

def generate_post():
    """Генерирует УНИКАЛЬНЫЙ пост - НИКОГДА НЕ ПОВТОРЯЕТСЯ"""
    theme = random.choice(POST_THEMES)
    
    system = """ТЫ - МИРОВОЙ ЭКСПЕРТ В ПСИХОЛОГИИ И КОУЧИНГЕ, автор бестселлеров.
    
    ТВОЙ СТИЛЬ:
    - Глубокий, мудрый, без пафоса
    - Используешь НЛП-язык (предикаты, якоря, метамодель)
    - Каждый пост - терапевтический сеанс
    - Энергия текста заряжает и мотивирует
    - Высокий уровень осознанности и глубины
    - Ты говоришь с читателем как с равным
    - Используешь метафоры, истории, вопросы
    
    КАЖДЫЙ ПОСТ УНИКАЛЕН - ты создаешь шедевр здесь и сейчас
    НЕЛЬЗЯ использовать шаблоны, клише, общие фразы
    НЕЛЬЗЯ повторяться - каждый пост как откровение
    
    СТРУКТУРА ПОСТА:
    1. ЗАХВАТЫВАЮЩИЙ ЗАГОЛОВОК (с эмодзи)
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ (затрагивает струны души)
    3. ОСНОВНАЯ ЧАСТЬ (инсайты, открытия, прозрения)
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ (конкретное, выполнимое)
    5. ВОПРОС К ЧИТАТЕЛЮ (провокационный, пробуждающий)
    6. МОТИВИРУЮЩИЙ ФИНАЛ (крылья и энергия)
    7. ХЕШТЕГИ (#жизньплюс #саморазвитие)
    
    ДЛИНА: 800-1200 знаков (как живой разговор)
    
    ВАЖНО: 
    - Пиши от первого лица
    - Будь честным, даже если это неудобно
    - Дай читателю ощущение "ЭТО ПРО МЕНЯ"
    - Заряди энергией действия
    - Оставь послевкусие трансформации"""
    
    user = f"""Напиши глубокий, трансформирующий пост на тему: "{theme}"
    
    Ты уже затрагивал эту тему? Отлично! Напиши СОВЕРШЕННО ПО-НОВОМУ.
    
    Используй свой 25-летний опыт работы с людьми.
    Сделай этот пост откровением для каждого читателя.
    
    Время писать ШЕДЕВР!"""
    
    response = ask_giga(system, user, 3000)
    
    if response and len(response) > 500:
        return response
    
    # Если не получилось - пробуем еще раз с другой темой
    return None

# ============================================
# ИДЕАЛЬНЫЙ ПРОМПТ ДЛЯ ТЕСТА
# ============================================

def generate_test_questions(topic, count=10):
    """Генерирует УНИКАЛЬНЫЙ тест - как у лучших психологов"""
    
    system = """ТЫ - КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ, автор методик.
    
    ТВОИ ТЕСТЫ:
    - Глубокие и проникающие в суть
    - Используют проективные техники
    - Затрагивают подсознание
    - Каждый вопрос - мини-исследование личности
    - Никаких банальных "как у вас дела?"
    - Вопросы заставляют задуматься и удивиться себе
    
    КАЖДЫЙ ТЕСТ УНИКАЛЕН:
    - Нет двух одинаковых тестов
    - Вопросы всегда новые и неожиданные
    - Ты создаешь тест здесь и сейчас
    - Используешь свой клинический опыт
    
    ФОРМАТ ОТВЕТА:
    Верни ТОЛЬКО JSON массив вопросов.
    
    КАЖДЫЙ ВОПРОС:
    - Формулировка: глубокая, психологичная
    - Варианты A, B, C, D: разные грани личности
    - Нет правильных/неправильных ответов
    - Есть градация от 0 до 3 баллов
    
    ТЕМЫ ВОПРОСОВ (варируй случайно):
    - Детские травмы и их влияние
    - Сценарии поведения в отношениях
    - Отношение к деньгам и успеху
    - Самооценка и самоценность
    - Страхи и их корни
    - Желания и истинные потребности
    - Границы и их нарушение
    - Тени и проекции
    - Ресурсные состояния
    - Жизненные сценарии
    - Привязанность и сепарация
    - Эмоциональный интеллект
    - Копинг-стратегии
    - Ценности и приоритеты
    - Саботаж и самосаботаж"""
    
    user = f"""Составь {count} ГЛУБОКИХ психологических вопросов на тему "{topic}".
    
    ТРЕБОВАНИЯ:
    - Вопросы должны ПРОНИКАТЬ вглубь личности
    - Заставлять задуматься и удивиться
    - Открывать то, что человек не замечал в себе
    - Использовать проективные формулировки
    - Быть как мини-сеанс психотерапии
    
    Верни ТОЛЬКО JSON:
    [
        {{
            "question": "глубокий вопрос?",
            "options": {{
                "A": "вариант 1",
                "B": "вариант 2",
                "C": "вариант 3",
                "D": "вариант 4"
            }}
        }}
    ]
    
    Сделай каждый вопрос - маленьким откровением.
    Время создавать ШЕДЕВР!"""
    
    response = ask_giga(system, user, 4000)
    
    if not response:
        return None
    
    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start == -1 or end == -1:
            return None
        
        questions = json.loads(response[start:end])
        
        # Добавляем баллы
        for q in questions:
            if 'scores' not in q:
                q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        
        return questions[:count]
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        return None

# ============================================
# ИДЕАЛЬНЫЙ ПРОМПТ ДЛЯ АНАЛИЗА
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    """Генерация анализа - как у лучших психологов"""
    
    if is_paid:
        system = """ТЫ - КОМАНДА МИРОВОГО УРОВНЯ:
        1. КЛИНИЧЕСКИЙ ПСИХОЛОГ с 25-летним стажем
        2. МЕЖДУНАРОДНЫЙ КОУЧ с тысячами часов практики
        3. АВТОР БЕСТСЕЛЛЕРОВ по личностному росту
        
        ТВОЙ АНАЛИЗ:
        - Глубокий, проникающий в суть личности
        - Трансформирующий, меняющий мышление
        - Прямой, честный, без сахара
        - Дает инсайты и ясность
        - Заряжает энергией и мотивацией
        
        СТРУКТУРА:
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ личности
        2. 3 ГЛУБИННЫХ ИНСАЙТА (что важно осознать)
        3. 3 КОНКРЕТНЫХ ШАГА НА НЕДЕЛЮ
        4. РЕКОМЕНДАЦИИ КНИГ (по теме)
        5. УПРАЖНЕНИЯ для практики
        6. ВИДЕО (известных спикеров)
        7. МОТИВИРУЮЩЕЕ ЗАКЛЮЧЕНИЕ
        
        ЯЗЫК: русский, живой, честный
        ОБЪЕМ: 1500+ знаков
        СТИЛЬ: как личный сеанс терапии"""
    else:
        system = """ТЫ - КЛИНИЧЕСКИЙ ПСИХОЛОГ-ПРАКТИК.
        
        ДАЙ КРАТКИЙ, НО ГЛУБОКИЙ АНАЛИЗ:
        - Без воды и общих фраз
        - 2 ключевых инсайта
        - 2 вопроса для размышления
        - Честно, прямо, без пафоса
        
        Это как 15-минутная консультация.
        Объем: 800+ знаков."""
    
    user = f"""Проведи анализ личности по результатам теста.
    
    ТЕМА: {topic}
    ОТВЕТЫ: {answers}
    БАЛЛЫ: {score} из {total}
    
    Сделай анализ глубже, чем все предыдущие.
    Открой человеку то, что он не видел в себе.
    Дай ТРАНСФОРМИРУЮЩУЮ обратную связь.
    
    Твой опыт и мудрость нужны здесь и сейчас."""
    
    response = ask_giga(system, user, 4000 if is_paid else 2500)
    
    if response:
        return response
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
# ТЕМЫ ТЕСТОВ
# ============================================

TEST_TOPICS = {
    "психология": "🧠 Глубинная психология",
    "отношения": "💕 Трансформация отношений",
    "карьера": "💼 Самореализация",
    "здоровье": "💪 Психосоматика",
    "финансы": "💰 Денежное мышление",
    "личность": "🌟 Самость и архетипы"
}

# ============================================
# TELEGRAM БОТ
# ============================================

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
    welcome = """🌟 ДОБРО ПОЖАЛОВАТЬ В ПРОСТРАНСТВО ТРАНСФОРМАЦИИ!

Я — твой проводник в мире осознанности и глубины.

Здесь ты:
• Откроешь в себе то, что скрыто
• Получишь ответы, которых искал
• Начнешь видеть свою уникальность

Нажми «🎯 Пройти тест» — и начни исследование себя.
«🎫 Активировать промокод» — если у тебя есть доступ к глубине."""

    bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = """💫 ЖИЗНЬ+ — пространство, где происходят трансформации.

Мы не даем готовых ответов.
Мы создаем пространство для твоих ОТКРЫТИЙ.

Здесь ты встретишь:
• Глубину, которая меняет
• Мудрость, которая освобождает
• Энергию, которая вдохновляет

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
        "🎯 ВЫБЕРИ ГЛУБИНУ ПОГРУЖЕНИЯ:\n\n"
        "🧠 БЕСПЛАТНЫЙ — 10 вопросов (поверхностное сканирование)\n"
        "💎 ПЛАТНЫЙ — 20 вопросов (полная диагностика личности)",
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
        f"🔮 ВЫБЕРИ СФЕРУ ИССЛЕДОВАНИЯ:\n\n"
        f"Количество вопросов: {count}\n"
        f"Время на тест: ~{count * 3} минут",
        reply_markup=mk
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n\n"
            "Создаю уникальные вопросы специально для тебя.\n"
            "Это займет до 30 секунд — дыши глубоко.",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, int(count))
        
        if not questions:
            bot.send_message(
                c.message.chat.id,
                "❌ Не удалось сгенерировать тест.\n"
                "Возможно, вселенная готовит для тебя что-то другое.\n"
                "Попробуй еще раз через минуту."
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
    bot.send_message(
        c.message.chat.id,
        "❌ Отменено. Возвращаюсь в точку опоры.",
        reply_markup=get_main_menu(c.message.chat.id)
    )
    c.answer()

def send_question(chat_id):
    s = sessions.get(chat_id)
    if not s:
        bot.send_message(chat_id, "❌ Сессия не найдена. Начни заново.")
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

Выбери вариант ответа, который откликается больше всего:"""
    
    bot.send_message(chat_id, message, reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    bot.send_message(
        chat_id,
        "⏹ Тест прерван.\n"
        "Ты всегда можешь вернуться, когда будешь готов.",
        reply_markup=get_main_menu(chat_id)
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
        f"⏳ Анализирую глубину твоей личности...\n"
        f"Это займет до 30 секунд — прислушайся к себе."
    )
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    
    if analysis:
        if is_paid:
            result = f"🔮 ГЛУБИННЫЙ АНАЛИЗ ЛИЧНОСТИ\n\n{analysis}"
        else:
            result = f"🔍 ИНСАЙТЫ И ОТКРЫТИЯ\n\n{analysis}"
        
        bot.send_message(chat_id, result, reply_markup=get_main_menu(chat_id))
    else:
        bot.send_message(
            chat_id,
            "❌ Не удалось сгенерировать анализ.\n"
            "Но твои ответы уже начали процесс трансформации.\n"
            "Попробуй еще раз позже.",
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
    bot.send_message(
        message.chat.id,
        "👑 АДМИН-ПАНЕЛЬ\n\n"
        "Управляй контентом и трансформацией.",
        reply_markup=admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "🌀 ГЕНЕРАЦИЯ ИДЕАЛЬНОГО ПОСТА...\n\n"
        "Создаю уникальный контент с максимальной глубиной.\n"
        "Это займет до 30 секунд — создается магия."
    )
    
    text = generate_post()
    
    if not text:
        bot.send_message(
            message.chat.id,
            "❌ Не удалось создать пост.\n"
            "Вселенная готовит что-то особенное, попробуй позже."
        )
        return
    
    c.execute("INSERT INTO posts_history (content) VALUES (?)", (text,))
    conn.commit()
    
    try:
        bot.send_message(CHANNEL_ID, text)
        bot.send_message(
            message.chat.id,
            "✅ ПОСТ ОТПРАВЛЕН В КАНАЛ!\n\n"
            "Еще одна трансформация началась.",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка отправки: {e}",
            reply_markup=admin_menu()
        )

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "🌀 ГЕНЕРАЦИЯ ТЕСТА ДЛЯ КАНАЛА...\n"
        "Создаю глубину для всех подписчиков."
    )
    
    topic = random.choice(list(TEST_TOPICS.keys()))
    questions = generate_test_questions(topic, 10)
    
    if not questions:
        bot.send_message(message.chat.id, "❌ Не удалось создать тест.")
        return
    
    c.execute("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?, ?, ?)",
              (topic, json.dumps(questions), datetime.now().isoformat()))
    conn.commit()
    test_id = c.lastrowid
    
    bot_info = bot.get_me()
    test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
    
    test_text = f"""🔮 ЕЖЕДНЕВНЫЙ ТЕСТ: «{topic.title()}»

Пройди исследование себя прямо сейчас.
Узнай то, что скрыто от тебя.

🎯 {test_url}

#жизньплюс #тест #психология"""
    
    bot.send_message(CHANNEL_ID, test_text)
    bot.send_message(
        message.chat.id,
        "✅ Тест отправлен в канал!",
        reply_markup=admin_menu()
    )

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
    
    stats_text = f"""📊 СТАТИСТИКА ТРАНСФОРМАЦИЙ

📝 Тестов в канале: {tests_count}
📤 Постов создано: {posts_count}
🧠 Бесплатных тестов: {stats_row[0] if stats_row else 0}
💎 Платных тестов: {stats_row[1] if stats_row else 0}
🎫 Промокодов активировано: {stats_row[2] if stats_row else 0}

Каждая цифра — чья-то трансформация."""
    
    bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "🎫 СОЗДАНИЕ ПРОМОКОДА\n\n"
        "Введи уникальный код (латиница, без пробелов):"
    )
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
            f"✅ ПРОМОКОД СОЗДАН!\n\n"
            f"📌 Код: `{code}`\n"
            f"Дай доступ к глубине кому-то особенному.",
            reply_markup=admin_menu()
        )
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Такой код уже существует.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    bot.send_message(
        message.chat.id,
        "🎫 ВВЕДИ ПРОМОКОД:\n\n"
        "Код, который открывает глубину.",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
    chat_id = message.chat.id
    code = message.text.strip().upper()
    
    c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
    row = c.fetchone()
    
    if not row:
        bot.send_message(
            chat_id,
            "❌ Неверный код.\n"
            "Возможно, это знак — продолжай путь.",
            reply_markup=get_main_menu(chat_id)
        )
        return
    
    promo_id, used_by = row
    
    if used_by != 0:
        bot.send_message(
            chat_id,
            "❌ Этот код уже использован.\n"
            "Время создавать свою магию.",
            reply_markup=get_main_menu(chat_id)
        )
        return
    
    c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
              (chat_id, datetime.now().isoformat(), promo_id))
    conn.commit()
    
    c.execute("UPDATE stats SET promo_used = promo_used + 1")
    conn.commit()
    
    bot.send_message(
        chat_id,
        "🎉 ПРОМОКОД АКТИВИРОВАН!\n\n"
        "Теперь тебе открыт доступ к 💎 Платному тесту.\n"
        "Готов к глубине?",
        reply_markup=get_main_menu(chat_id)
    )

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info("🤖 Запуск трансформационного бота...")
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    run_bot()
