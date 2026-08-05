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
import sys
import traceback
from datetime import datetime
from flask import Flask
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# НАСТРОЙКИ
# ============================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
ADMIN_IDS = [8746212340]

# ⚠️ ВНИМАНИЕ: Твой CLIENT_SECRET УЖЕ В BASE64!
GIGA_CLIENT_ID = "019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e"
GIGA_CLIENT_SECRET = "MDE5ZmM3YTItOGQ0Ni03MGNiLTkwMjgtZmNmYzVhMWQ0ZDBlOjljMmUzNTI3LWI3NzAtNDU0NS1iMTFmLTBiZDljNDMxNWU1Mw=="

# ============================================
# МАКСИМАЛЬНОЕ ЛОГИРОВАНИЕ
# ============================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info("🚀 ЗАПУСК БОТА С ОБРАБОТКОЙ ОШИБОК")

# ============================================
# УБИЙЦА 409 (С ОБРАБОТКОЙ ОШИБОК)
# ============================================

def kill_409():
    try:
        logger.info("🔥 НАЧАЛО УНИЧТОЖЕНИЯ 409")
        
        # 1. Удаляем вебхук
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            response = requests.post(url, json={"drop_pending_updates": True}, timeout=10)
            logger.info(f"📡 deleteWebhook: {response.status_code}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка deleteWebhook: {e}")
        
        # 2. Удаляем offset файлы
        try:
            for f in glob.glob('update-offset-*.json'):
                try:
                    os.remove(f)
                    logger.info(f"🗑️ Удален файл: {f}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось удалить {f}: {e}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка при удалении файлов: {e}")
        
        # 3. Проверяем статус
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
            response = requests.get(url, timeout=10)
            logger.info(f"📡 Статус вебхука: {response.json()}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка проверки вебхука: {e}")
        
        logger.info("✅ 409 УНИЧТОЖЕН")
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА В kill_409: {e}")
        logger.error(traceback.format_exc())
        return False

# ВЫПОЛНЯЕМ
for i in range(3):
    logger.info(f"🔄 Проход уничтожения 409 #{i+1}")
    kill_409()
    time.sleep(2)

# ============================================
# GIGACHAT (С ПОЛНОЙ ОБРАБОТКОЙ ОШИБОК)
# ============================================

giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    """Получение токена с обработкой ошибок"""
    
    logger.info("🔑 НАЧАЛО ПОЛУЧЕНИЯ ТОКЕНА")
    
    try:
        # Проверяем кэш
        if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
            logger.info("✅ Токен из кэша")
            return giga_token_cache["token"]
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при проверке кэша: {e}")
    
    # Пробуем получить токен
    for attempt in range(1, 4):
        try:
            logger.info(f"🔄 Попытка {attempt}/3...")
            
            # ⚠️ ВАЖНО: Используем GIGA_CLIENT_SECRET как есть
            auth_b64 = GIGA_CLIENT_SECRET
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logger.info("📤 Отправка запроса к GigaChat Auth...")
            
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data='scope=GIGACHAT_API_PERS',
                timeout=30,
                verify=False
            )
            
            logger.info(f"📡 Статус: {response.status_code}")
            
            # Проверяем статус
            if response.status_code == 200:
                try:
                    data = response.json()
                    token = data.get('access_token')
                    
                    if token:
                        giga_token_cache["token"] = token
                        giga_token_cache["expires"] = time.time() + 3500
                        logger.info("✅ ТОКЕН ПОЛУЧЕН!")
                        return token
                    else:
                        logger.error("❌ Токен не найден в ответе")
                        logger.debug(f"📄 Ответ: {data}")
                except json.JSONDecodeError as je:
                    logger.error(f"❌ Ошибка парсинга JSON: {je}")
                    logger.debug(f"📄 Текст: {response.text[:300]}")
            else:
                logger.error(f"❌ Ошибка HTTP {response.status_code}")
                logger.debug(f"📄 Текст: {response.text[:300]}")
                
                # Если 400 - проверяем ключи
                if response.status_code == 400:
                    logger.error("❌ ВОЗМОЖНО НЕВЕРНЫЙ CLIENT_SECRET!")
                    logger.error("📄 Проверь, что CLIENT_SECRET правильный")
            
            time.sleep(2)
            
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ при получении токена")
            time.sleep(3)
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {ce}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")
            logger.error(traceback.format_exc())
            time.sleep(3)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ТОКЕН ПОСЛЕ 3 ПОПЫТОК")
    return None

def ask_giga(system, user, max_tokens=3000, retries=3):
    """Запрос к GigaChat с обработкой ошибок и повторными попытками"""
    
    logger.info("="*60)
    logger.info("📤 ЗАПРОС К GIGACHAT")
    logger.info(f"📝 Система: {system[:100]}...")
    logger.info(f"📝 Запрос: {user[:100]}...")
    
    # Проверяем входные данные
    if not system or not isinstance(system, str):
        logger.error("❌ Системный промпт пустой или не строка")
        return None
    
    # Получаем токен
    token = get_giga_token()
    if not token:
        logger.error("❌ НЕТ ТОКЕНА")
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
        "temperature": 0.9,
        "max_tokens": max_tokens
    }
    
    # Повторные попытки
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"🔄 Попытка {attempt}/{retries}...")
            
            start_time = time.time()
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=60,
                verify=False
            )
            
            elapsed = time.time() - start_time
            logger.info(f"⏱ Ответ за {elapsed:.2f} сек")
            logger.info(f"📡 Статус: {response.status_code}")
            
            # Гарантированное ожидание
            if elapsed < 30:
                wait_time = 30 - elapsed
                logger.info(f"⏳ Ожидание {wait_time:.1f} сек")
                time.sleep(wait_time)
            
            # Обработка ответа
            if response.status_code == 200:
                try:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    if content and len(content) > 10:
                        logger.info(f"✅ ОТВЕТ ПОЛУЧЕН ({len(content)} символов)")
                        return content
                    else:
                        logger.error(f"❌ ПУСТОЙ ОТВЕТ (длина: {len(content)})")
                        if attempt < retries:
                            logger.info(f"🔄 Повторная попытка через 2 сек...")
                            time.sleep(2)
                            continue
                        else:
                            return None
                            
                except json.JSONDecodeError as je:
                    logger.error(f"❌ ОШИБКА ПАРСИНГА JSON: {je}")
                    logger.debug(f"📄 Текст: {response.text[:300]}")
                    if attempt < retries:
                        time.sleep(2)
                        continue
                    else:
                        return None
            else:
                logger.error(f"❌ ОШИБКА HTTP {response.status_code}")
                logger.debug(f"📄 Текст: {response.text[:300]}")
                
                # Если 401 - токен умер
                if response.status_code == 401:
                    logger.warning("⚠️ ТОКЕН УМЕР, СБРАСЫВАЕМ КЭШ")
                    giga_token_cache["token"] = None
                    giga_token_cache["expires"] = 0
                    time.sleep(2)
                    continue
                
                if attempt < retries:
                    time.sleep(2)
                    continue
                else:
                    return None
                
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ (60 сек)")
            if attempt < retries:
                time.sleep(3)
                continue
            else:
                return None
                
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {ce}")
            if attempt < retries:
                time.sleep(5)
                continue
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")
            logger.error(traceback.format_exc())
            if attempt < retries:
                time.sleep(3)
                continue
            else:
                return None
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ОТВЕТ ПОСЛЕ ВСЕХ ПОПЫТОК")
    return None

# ============================================
# БАЗА ДАННЫХ (С ОБРАБОТКОЙ ОШИБОК)
# ============================================

def init_db():
    try:
        DB_PATH = 'channel.db'
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Создаем таблицы
        c.execute('''CREATE TABLE IF NOT EXISTS daily_tests 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      topic TEXT, 
                      questions TEXT, 
                      created_at TEXT,
                      is_paid INTEGER DEFAULT 0)''')
        
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
                      is_paid INTEGER)''')
        
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
                      topic TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (chat_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных готова")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        logger.error(traceback.format_exc())
        return False

init_db()

# Подключаемся к базе
try:
    conn = sqlite3.connect('channel.db', check_same_thread=False)
    c = conn.cursor()
    logger.info("✅ Подключение к базе данных установлено")
except Exception as e:
    logger.error(f"❌ Ошибка подключения к базе: {e}")
    sys.exit(1)

# ============================================
# ТЕМЫ
# ============================================

POST_THEMES = [
    "внутренняя сила", "самооценка", "отношения", "деньги", "карьера",
    "эмоции", "страхи", "границы", "любовь к себе", "благодарность"
]

TEST_TOPICS = {
    "психология": "🧠 Психология",
    "отношения": "💕 Отношения",
    "карьера": "💼 Карьера",
    "здоровье": "💪 Здоровье",
    "финансы": "💰 Финансы",
    "личность": "🌟 Личность"
}

# ============================================
# ГЕНЕРАТОР ПОСТА (С ОБРАБОТКОЙ ОШИБОК)
# ============================================

def generate_post():
    try:
        theme = random.choice(POST_THEMES)
        logger.info(f"📝 Тема: {theme}")
        
        system = """Ты — автор канала о психологии. Напиши пост на тему.
        Минимум 800 символов. Пиши глубоко, честно, без пафоса.
        Не используй шаблоны. Добавь вопрос в конце."""
        
        user = f"Тема: {theme}. Пост 800+ символов."
        
        response = ask_giga(system, user, 4000)
        
        if response and len(response) > 600:
            logger.info(f"✅ Пост создан ({len(response)} символов)")
            return response, theme
        else:
            logger.error("❌ Пост не создан")
            return None, theme
            
    except Exception as e:
        logger.error(f"❌ Ошибка в generate_post: {e}")
        logger.error(traceback.format_exc())
        return None, None

# ============================================
# ГЕНЕРАТОР ТЕСТА (С ОБРАБОТКОЙ ОШИБОК)
# ============================================

def generate_test_questions(topic, count=10):
    try:
        logger.info(f"🧠 Тест: {topic}, {count} вопросов")
        
        system = f"""Составь {count} вопросов для теста на тему "{topic}".
        Верни ТОЛЬКО JSON.
        Формат: [{{"question": "текст?", "options": {{"A": "вар1", "B": "вар2", "C": "вар3", "D": "вар4"}}, "scores": {{"A": 0, "B": 1, "C": 2, "D": 3}}}}]
        НЕ ДОБАВЛЯЙ НИЧЕГО КРОМЕ JSON."""
        
        response = ask_giga(system, "", 4000)
        
        if not response:
            logger.error("❌ GigaChat не ответил")
            return None
        
        # Ищем JSON
        start = response.find('[')
        end = response.rfind(']') + 1
        
        if start == -1 or end == -1:
            logger.error("❌ JSON не найден")
            logger.debug(f"📄 Ответ: {response[:300]}")
            return None
        
        json_str = response[start:end]
        
        try:
            questions = json.loads(json_str)
            
            if not questions or len(questions) == 0:
                logger.error("❌ Пустой массив")
                return None
            
            # Добавляем баллы
            for q in questions:
                if 'scores' not in q:
                    q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                if 'options' not in q:
                    q['options'] = {'A': 'Да', 'B': 'Скорее да', 'C': 'Скорее нет', 'D': 'Нет'}
            
            logger.info(f"✅ Тест создан ({len(questions)} вопросов)")
            return questions[:count]
            
        except json.JSONDecodeError as je:
            logger.error(f"❌ Ошибка JSON: {je}")
            logger.debug(f"📄 Строка: {json_str[:300]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка в generate_test_questions: {e}")
        logger.error(traceback.format_exc())
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА (С ОБРАБОТКОЙ ОШИБОК)
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    try:
        if is_paid:
            system = """Ты — клинический психолог. Сделай полный разбор личности.
            Портрет, инсайты, корень проблемы, план на неделю."""
            user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
        else:
            system = """Ты — психолог. Дай краткий анализ. Назови главную проблему, дай 1 инсайт."""
            user = f"Тема: {topic}\nОтветы: {answers}\nБаллы: {score} из {total}"
        
        return ask_giga(system, user, 4000 if is_paid else 2500)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в generate_analysis: {e}")
        logger.error(traceback.format_exc())
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
    return "✅ БОТ РАБОТАЕТ!"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

def run_flask():
    try:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

threading.Thread(target=run_flask, daemon=True).start()
logger.info("✅ Веб-сервер запущен")

# ============================================
# МЕНЮ
# ============================================

def get_main_menu(chat_id):
    try:
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        mk.add('🚀 Старт', '🎯 Пройти тест')
        mk.add('🎫 Активировать промокод', '❤️ О канале')
        if chat_id in ADMIN_IDS:
            mk.add('👑 Админ-панель')
        return mk
    except Exception as e:
        logger.error(f"❌ Ошибка меню: {e}")
        return None

def admin_menu():
    try:
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        mk.add('📤 Отправить пост', '🖼 Пост с картинкой')
        mk.add('🧠 Тест в канал', '📊 Статистика')
        mk.add('🎫 Создать промокод', '👑 Главное меню')
        return mk
    except Exception as e:
        logger.error(f"❌ Ошибка админ-меню: {e}")
        return None

def test_type_menu():
    try:
        mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        mk.add('🧠 Бесплатный (10 вопросов)')
        mk.add('💎 Платный (20 вопросов)')
        mk.add('🔙 Назад')
        return mk
    except Exception as e:
        logger.error(f"❌ Ошибка меню тестов: {e}")
        return None

# ============================================
# ХРАНИЛИЩЕ СЕССИЙ
# ============================================

sessions = {}

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        c.execute("""INSERT OR IGNORE INTO users 
                     (chat_id, username, first_name, last_name) 
                     VALUES (?, ?, ?, ?)""",
                  (chat_id, username, first_name, last_name))
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения пользователя: {e}")

# ============================================
# ОБРАБОТЧИКИ
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    try:
        chat_id = message.chat.id
        user = message.from_user
        
        save_user(chat_id, user.username, user.first_name, user.last_name)
        
        welcome = "🌟 Добро пожаловать!\n\nНажми «🎯 Пройти тест» или «🎫 Активировать промокод»."
        bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))
        
    except Exception as e:
        logger.error(f"❌ Ошибка в start: {e}")
        logger.error(traceback.format_exc())
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    try:
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Перейти в канал", url="https://t.me/zhizn_plus"))
        bot.send_message(message.chat.id, "💫 ЖИЗНЬ+ — канал о психологии и саморазвитии.", reply_markup=mk)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    try:
        bot.send_message(message.chat.id, "🎯 Выбери тест:", reply_markup=test_type_menu())
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🔙 Назад')
def back_to_main(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный (10 вопросов)')
def free_test(message):
    show_topics(message, 'free', 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный (20 вопросов)')
def paid_test(message):
    show_topics(message, 'paid', 20)

def show_topics(message, test_type, count):
    try:
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for topic, emoji in TEST_TOPICS.items():
            mk.add(telebot.types.InlineKeyboardButton(emoji, callback_data=f"{test_type}_{topic}_{count}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
        bot.send_message(message.chat.id, f"🔮 Выбери тему:", reply_markup=mk)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        bot.edit_message_text("⏳ Генерация теста...", chat_id, c.message.message_id)
        
        questions = generate_test_questions(topic, count)
        
        if not questions:
            bot.send_message(chat_id, "❌ GigaChat не ответил. Попробуй позже.")
            return
        
        sessions[chat_id] = {
            'topic': topic,
            'questions': questions,
            'answers': [],
            'q': 0,
            'scores': [],
            'is_paid': is_paid
        }
        
        bot.delete_message(chat_id, c.message.message_id)
        send_question(chat_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в topic_callback: {e}")
        logger.error(traceback.format_exc())
        try:
            bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")
        except:
            pass
    c.answer()

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, "❌ Отменено", reply_markup=get_main_menu(c.message.chat.id))
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    c.answer()

def send_question(chat_id):
    try:
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
        
        message = f"🔮 ВОПРОС {current} ИЗ {total}\n\n📌 {s['topic'].title()}\n\n{q['question']}"
        bot.send_message(chat_id, message, reply_markup=mk)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в send_question: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    try:
        chat_id = message.chat.id
        if chat_id in sessions:
            del sessions[chat_id]
        bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text and m.text[0] in 'ABCD')
def handle_answer(message):
    try:
        chat_id = message.chat.id
        s = sessions.get(chat_id)
        
        if not s:
            return
        if s['q'] >= len(s['questions']):
            return
        
        letter = message.text[0]
        q = s['questions'][s['q']]
        
        s['answers'].append(letter)
        s['scores'].append(q['scores'][letter])
        s['q'] += 1
        
        send_question(chat_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_answer: {e}")
        logger.error(traceback.format_exc())

def finish_test(chat_id):
    try:
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
        
        bot.send_message(chat_id, f"📊 Тест завершен!\nРезультат: {score} из {total}\n⏳ Анализирую...")
        
        analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
        
        if analysis:
            bot.send_message(chat_id, f"🔍 АНАЛИЗ\n\n{analysis}", reply_markup=get_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ GigaChat не ответил. Попробуй позже.", reply_markup=get_main_menu(chat_id))
        
        if chat_id in sessions:
            del sessions[chat_id]
            
    except Exception as e:
        logger.error(f"❌ Ошибка в finish_test: {e}")
        logger.error(traceback.format_exc())

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "👑 Админ-панель", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        bot.send_message(message.chat.id, "⏳ Генерация поста...")
        
        post, theme = generate_post()
        
        if not post:
            bot.send_message(message.chat.id, "❌ GigaChat не ответил.", reply_markup=admin_menu())
            return
        
        try:
            c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
            conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения: {e}")
        
        try:
            bot.send_message(CHANNEL_ID, post)
            bot.send_message(message.chat.id, "✅ Пост отправлен!", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
            
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_post: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def admin_post_with_image(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        bot.send_message(message.chat.id, "⏳ Генерация поста и картинки...")
        
        post, theme = generate_post()
        
        if not post:
            bot.send_message(message.chat.id, "❌ GigaChat не ответил.", reply_markup=admin_menu())
            return
        
        # Генерация картинки
        image_path = None
        try:
            clean_prompt = f"{theme} psychological illustration".replace(' ', '%20')
            url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=768&nologo=true"
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200 and len(response.content) > 1000:
                image_path = f"/tmp/image_{int(time.time())}.jpg"
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                logger.info("✅ Картинка создана")
        except Exception as e:
            logger.error(f"❌ Ошибка генерации картинки: {e}")
        
        try:
            c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
            conn.commit()
        except:
            pass
        
        try:
            if image_path:
                with open(image_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption=post)
                os.remove(image_path)
            else:
                bot.send_message(CHANNEL_ID, post)
            bot.send_message(message.chat.id, "✅ Пост с картинкой отправлен!", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
            
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_post_with_image: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        bot.send_message(message.chat.id, "⏳ Генерация теста...")
        
        topic = random.choice(list(TEST_TOPICS.keys()))
        questions = generate_test_questions(topic, 10)
        
        if not questions:
            bot.send_message(message.chat.id, "❌ GigaChat не ответил.", reply_markup=admin_menu())
            return
        
        try:
            c.execute("INSERT INTO daily_tests (topic, questions, created_at, is_paid) VALUES (?, ?, ?, ?)",
                      (topic, json.dumps(questions), datetime.now().isoformat(), 0))
            conn.commit()
            test_id = c.lastrowid
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            test_id = int(time.time())
        
        bot_info = bot.get_me()
        test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
        bot.send_message(CHANNEL_ID, f"🔮 Тест: «{topic.title()}»\n\nПройти: {test_url}")
        bot.send_message(message.chat.id, "✅ Тест отправлен!", reply_markup=admin_menu())
        
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_test_to_channel: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        
        c.execute("SELECT free_count, paid_count, promo_used FROM stats")
        stats_row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        stats_text = f"📊 Статистика\n\n👥 Пользователей: {users_count}\n🧠 Бесплатных: {stats_row[0] if stats_row else 0}\n💎 Платных: {stats_row[1] if stats_row else 0}\n🎫 Промокодов: {stats_row[2] if stats_row else 0}"
        bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())
        
    except Exception as e:
        logger.error(f"❌ Ошибка в admin_stats: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    try:
        if message.chat.id not in ADMIN_IDS:
            return
        bot.send_message(message.chat.id, "🎫 Введите код (латиница, 3+ символов):")
        bot.register_next_step_handler(message, process_create_promo)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

def process_create_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        
        if code == "ОТМЕНА":
            bot.send_message(chat_id, "❌ Отменено")
            return
        
        if not code or len(code) < 3:
            bot.send_message(chat_id, "❌ Минимум 3 символа", reply_markup=admin_menu())
            return
        
        c.execute("INSERT INTO promocodes (code, created_by, created_at) VALUES (?, ?, ?)",
                  (code, chat_id, datetime.now().isoformat()))
        conn.commit()
        bot.send_message(chat_id, f"✅ Промокод: `{code}`", reply_markup=admin_menu())
        
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Уже существует", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    try:
        bot.send_message(message.chat.id, "🎫 Введите промокод:", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, process_promo)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

def process_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        
        c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
        row = c.fetchone()
        
        if not row:
            bot.send_message(chat_id, "❌ Неверный код", reply_markup=get_main_menu(chat_id))
            return
        
        promo_id, used_by = row
        
        if used_by != 0:
            bot.send_message(chat_id, "❌ Уже использован", reply_markup=get_main_menu(chat_id))
            return
        
        c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
                  (chat_id, datetime.now().isoformat(), promo_id))
        conn.commit()
        c.execute("UPDATE stats SET promo_used = promo_used + 1")
        conn.commit()
        
        bot.send_message(chat_id, "🎉 Промокод активирован!", reply_markup=get_main_menu(chat_id))
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_promo: {e}")
        logger.error(traceback.format_exc())

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info("🤖 ЗАПУСК БОТА...")
    try:
        kill_409()
        time.sleep(2)
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    logger.info("🚀 ПОДГОТОВКА К ЗАПУСКУ...")
    for i in range(3):
        kill_409()
        time.sleep(2)
    run_bot()
