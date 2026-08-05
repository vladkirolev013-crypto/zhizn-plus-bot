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
import hashlib
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# НАСТРОЙКИ
# ============================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
CHANNEL_ID = "@zhizn_plus"
ADMIN_IDS = [8746212340]

# ⚠️ Authorization key (уже в Base64) - НЕ КОДИРУЕМ!
AUTH_KEY = "MDE5ZmM3YTItOGQ0Ni03MGNiLTkwMjgtZmNmYzVhMWQ0ZDBlOjg2YzE3MTRiLTc0NzYtNDhiYS05YjZiLTk5MGRhZmFiYWNjOQ=="

# Версия бота
BOT_VERSION = "6.0.0"
BOT_NAME = "Жизнь+ Трансформационный Бот"

# Пути
DB_PATH = 'channel.db'
LOG_PATH = 'bot_logs.txt'
TEMP_IMAGE_PATH = '/tmp/'

# ============================================
# МАКСИМАЛЬНОЕ ЛОГИРОВАНИЕ
# ============================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")

# ============================================
# СУПЕР-УБИЙЦА 409 (30 СПОСОБОВ)
# ============================================

def super_kill_409():
    """Уничтожает 409 всеми способами"""
    logger.info("🔥 НАЧАЛО УНИЧТОЖЕНИЯ 409")
    success_count = 0
    
    try:
        # 1-15: Многократное удаление вебхука
        for i in range(15):
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                response = requests.post(url, json={"drop_pending_updates": True}, timeout=10)
                if response.status_code == 200:
                    success_count += 1
                time.sleep(0.2)
            except:
                pass
        
        # 16: Сброс вебхука
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            response = requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
            if response.status_code == 200:
                success_count += 1
        except:
            pass
        
        # 17: Через GET
        try:
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", params={"drop_pending_updates": "true"})
            success_count += 1
        except:
            pass
        
        # 18-25: Удаление файлов
        patterns = ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid', '*.offset', '*.cache', '*.tmp']
        for pattern in patterns:
            try:
                for f in glob.glob(pattern):
                    try:
                        os.remove(f)
                        logger.info(f"Удален файл: {f}")
                    except:
                        pass
            except:
                pass
        
        # 26-28: Очистка временных папок
        temp_dirs = ['/tmp', '/var/tmp', '/dev/shm']
        for temp_dir in temp_dirs:
            try:
                for f in glob.glob(f"{temp_dir}/telegram_*.json") + glob.glob(f"{temp_dir}/update-*.json"):
                    try:
                        os.remove(f)
                    except:
                        pass
            except:
                pass
        
        # 29: Проверка статуса
        try:
            response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=10)
            logger.info(f"Вебхук статус: {response.json()}")
        except:
            pass
        
        # 30: Финальный проход
        time.sleep(1)
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", json={"drop_pending_updates": True}, timeout=10)
            success_count += 1
        except:
            pass
        
        logger.info(f"🔥 409 УНИЧТОЖЕН! Успешных операций: {success_count}/30")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

# ПЯТИКРАТНОЕ УНИЧТОЖЕНИЕ
for i in range(5):
    logger.info(f"🔄 Проход уничтожения 409 #{i+1}/5")
    super_kill_409()
    time.sleep(2)

# ============================================
# GIGACHAT (С ОЖИДАНИЕМ 30-40 СЕКУНД)
# ============================================

giga_token_cache = {"token": None, "expires": 0, "error_count": 0}

def get_giga_token():
    """Получение токена GigaChat с обработкой ошибок"""
    
    logger.info("🔑 НАЧАЛО ПОЛУЧЕНИЯ ТОКЕНА")
    
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        logger.info("✅ Токен из кэша")
        return giga_token_cache["token"]
    
    for attempt in range(1, 4):
        try:
            logger.info(f"🔄 Попытка {attempt}/3 получить токен...")
            
            auth_b64 = AUTH_KEY
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
            
            logger.info(f"📡 Статус: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('access_token')
                if token:
                    giga_token_cache["token"] = token
                    giga_token_cache["expires"] = time.time() + 3500
                    logger.info("✅ ТОКЕН ПОЛУЧЕН!")
                    return token
                else:
                    logger.error("❌ Токен не найден в ответе")
            else:
                logger.error(f"❌ Ошибка: {response.status_code} - {response.text[:200]}")
            
            time.sleep(2)
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ")
            time.sleep(3)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            time.sleep(2)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ТОКЕН")
    return None

def ask_giga(system, user, max_tokens=5000, retries=3):
    """Запрос к GigaChat с гарантированным ожиданием 35 секунд"""
    
    logger.info("="*80)
    logger.info("📤 ЗАПРОС К GIGACHAT")
    logger.info(f"📝 Система (первые 100 символов): {system[:100]}...")
    logger.info(f"📝 Запрос (первые 100 символов): {user[:100]}...")
    logger.info(f"⚙️ Параметры: max_tokens={max_tokens}, retries={retries}")
    
    token = get_giga_token()
    if not token:
        logger.error("❌ НЕТ ТОКЕНА")
        return None
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.95,
        "max_tokens": max_tokens,
        "stream": False,
        "repetition_penalty": 1.1
    }
    
    logger.info(f"📦 Размер запроса: {len(json.dumps(payload))} байт")
    
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"🔄 Попытка {attempt}/{retries}...")
            
            start_time = time.time()
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=90,
                verify=False
            )
            
            elapsed = time.time() - start_time
            logger.info(f"⏱ Ответ за {elapsed:.2f} сек")
            logger.info(f"📡 Статус: {response.status_code}")
            
            # ⚠️ ГАРАНТИРОВАННОЕ ОЖИДАНИЕ 35 СЕКУНД
            if elapsed < 35:
                wait_time = 35 - elapsed
                logger.info(f"⏳ ОЖИДАНИЕ {wait_time:.1f} СЕКУНД (гарантия генерации)")
                time.sleep(wait_time)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    if content and len(content) > 10:
                        logger.info(f"✅ ОТВЕТ ПОЛУЧЕН ({len(content)} символов)")
                        logger.info(f"📄 Первые 150 символов: {content[:150]}...")
                        return content
                    else:
                        logger.error(f"❌ ПУСТОЙ ОТВЕТ (длина: {len(content)})")
                except json.JSONDecodeError as je:
                    logger.error(f"❌ ОШИБКА ПАРСИНГА JSON: {je}")
                    logger.debug(f"📄 Текст: {response.text[:300]}")
            else:
                logger.error(f"❌ ОШИБКА HTTP {response.status_code}")
                logger.debug(f"📄 Текст: {response.text[:300]}")
                
                if response.status_code == 401:
                    logger.warning("⚠️ ТОКЕН УМЕР, СБРАСЫВАЕМ КЭШ")
                    giga_token_cache["token"] = None
                    giga_token_cache["expires"] = 0
                    time.sleep(2)
                    continue
            
            if attempt < retries:
                logger.info(f"⏳ Пауза 2 сек перед следующей попыткой...")
                time.sleep(2)
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ (90 сек)")
            if attempt < retries:
                time.sleep(3)
        except Exception as e:
            logger.error(f"❌ ОШИБКА: {e}")
            logger.error(traceback.format_exc())
            if attempt < retries:
                time.sleep(3)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ОТВЕТ ПОСЛЕ ВСЕХ ПОПЫТОК")
    return None

# ============================================
# ГЕНЕРАЦИЯ КАРТИНОК (С ОЖИДАНИЕМ И ПОВТОРАМИ)
# ============================================

def generate_image(prompt, width=1024, height=768, attempts=3):
    """Генерация картинки через API с повторными попытками"""
    
    logger.info(f"🖼 ГЕНЕРАЦИЯ КАРТИНКИ")
    logger.info(f"📝 Промпт: {prompt[:100]}...")
    
    clean_prompt = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "").replace(',', '%2C')
    full_prompt = f"{clean_prompt}, high quality, detailed, beautiful, professional, 4k, masterpiece"
    
    apis = [
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&nologo=true&seed={random.randint(1,999999)}",
        f"https://pollinations.ai/prompt/{full_prompt}?width={width}&height={height}",
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&model=flux"
    ]
    
    for attempt in range(1, attempts + 1):
        for api_idx, api_url in enumerate(apis):
            try:
                logger.info(f"🔄 Попытка {attempt}/{attempts}, API {api_idx + 1}/{len(apis)}")
                
                start_time = time.time()
                response = requests.get(api_url, timeout=60)
                elapsed = time.time() - start_time
                
                logger.info(f"⏱ Ответ за {elapsed:.2f} сек, статус: {response.status_code}")
                
                if response.status_code == 200 and len(response.content) > 5000:
                    filename = f"{TEMP_IMAGE_PATH}image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    
                    file_size = os.path.getsize(filename)
                    logger.info(f"✅ КАРТИНКА СОЗДАНА: {filename} ({file_size} байт)")
                    return filename
                else:
                    logger.warning(f"⚠️ Ошибка API: статус {response.status_code}, размер {len(response.content)} байт")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка API: {e}")
            time.sleep(1)
        
        if attempt < attempts:
            logger.info(f"⏳ Пауза 3 сек перед следующей попыткой...")
            time.sleep(3)
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ КАРТИНКУ")
    return None

def generate_post_image(theme):
    """Генерация картинки для поста"""
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational, peaceful, spiritual growth, masterpiece",
        f"beautiful landscape {theme}, sunrise, hope, positive energy, meditation, 4k",
        f"minimalist illustration {theme}, soft pastel, calm, self discovery, healing, art",
        f"surreal art {theme}, emotional depth, transformation, bright colors, wisdom, creative",
        f"philosophical illustration {theme}, deep thinking, clarity, dreamy atmosphere, professional"
    ]
    return generate_image(random.choice(prompts))

def generate_test_image(topic):
    """Генерация картинки для теста"""
    prompts = [
        f"psychological test illustration {topic}, brain, mind, introspection, deep colors, spiritual, professional",
        f"abstract psychology art {topic}, meditation, self reflection, calm, serene, masterpiece",
        f"mental health awareness {topic}, healing, balance, harmony, soothing, 4k",
        f"mindfulness illustration {topic}, inner peace, growth, positive, wisdom, art"
    ]
    return generate_image(random.choice(prompts))

# ============================================
# БАЗА ДАННЫХ (ПОЛНАЯ ВЕРСИЯ)
# ============================================

def init_database():
    """Инициализация базы данных со всеми таблицами"""
    
    logger.info("🗄️ ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ")
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    c.execute("PRAGMA foreign_keys = ON")
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tests_passed INTEGER DEFAULT 0,
        last_activity TIMESTAMP,
        language_code TEXT,
        is_premium INTEGER DEFAULT 0,
        total_score INTEGER DEFAULT 0
    )''')
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_registered ON users(registered_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_activity ON users(last_activity)")
    
    # Таблица статистики
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        free_count INTEGER DEFAULT 0,
        paid_count INTEGER DEFAULT 0,
        promo_used INTEGER DEFAULT 0,
        users_count INTEGER DEFAULT 0,
        posts_count INTEGER DEFAULT 0,
        tests_created INTEGER DEFAULT 0,
        images_generated INTEGER DEFAULT 0,
        giga_requests INTEGER DEFAULT 0,
        giga_errors INTEGER DEFAULT 0,
        messages_received INTEGER DEFAULT 0,
        messages_sent INTEGER DEFAULT 0,
        total_users INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO stats (free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated, giga_requests, giga_errors, messages_received, messages_sent, total_users, active_users) VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)")
    
    # Таблица сессий
    c.execute('''CREATE TABLE IF NOT EXISTS user_sessions (
        chat_id INTEGER PRIMARY KEY,
        topic TEXT,
        questions TEXT,
        current_q INTEGER DEFAULT 0,
        answers TEXT,
        scores TEXT,
        is_paid INTEGER DEFAULT 0,
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_question_at TIMESTAMP
    )''')
    
    # Таблица промокодов
    c.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used_by INTEGER DEFAULT 0,
        used_at TIMESTAMP,
        expires_at TIMESTAMP,
        max_uses INTEGER DEFAULT 1,
        uses_count INTEGER DEFAULT 0
    )''')
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_promocodes_code ON promocodes(code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_promocodes_used ON promocodes(used_by)")
    
    # Таблица постов
    c.execute('''CREATE TABLE IF NOT EXISTS posts_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        topic TEXT,
        image_path TEXT,
        views INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        channel_message_id INTEGER,
        is_scheduled INTEGER DEFAULT 0,
        scheduled_at TIMESTAMP
    )''')
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts_history(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts_history(topic)")
    
    # Таблица тестов
    c.execute('''CREATE TABLE IF NOT EXISTS daily_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT,
        questions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_paid INTEGER DEFAULT 0,
        image_path TEXT,
        views INTEGER DEFAULT 0,
        completions INTEGER DEFAULT 0,
        average_score REAL DEFAULT 0
    )''')
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_tests_topic ON daily_tests(topic)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tests_created ON daily_tests(created_at)")
    
    # Таблица обратной связи
    c.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        message TEXT,
        rating INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        feedback_type TEXT,
        is_processed INTEGER DEFAULT 0
    )''')
    
    # Таблица использованных тем
    c.execute('''CREATE TABLE IF NOT EXISTS used_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used_count INTEGER DEFAULT 1
    )''')
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_used_topics ON used_topics(topic)")
    
    # Таблица ошибок
    c.execute('''CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        error_type TEXT,
        error_message TEXT,
        stack_trace TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_resolved INTEGER DEFAULT 0
    )''')
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_errors_created ON error_logs(created_at)")
    
    # Таблица настроек
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('bot_version', ?)", (BOT_VERSION,))
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('last_start', ?)", (datetime.now().isoformat(),))
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('timezone', 'Asia/Yekaterinburg')")
    
    conn.commit()
    conn.close()
    
    logger.info("✅ БАЗА ДАННЫХ ИНИЦИАЛИЗИРОВАНА")

init_database()

# Подключаемся к базе
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ============================================
# 300+ УНИКАЛЬНЫХ ТЕМ ДЛЯ ПОСТОВ
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
    "как перестать сравнивать", "сила рода и предков",
    "как выйти из созависимости", "искусство принимать комплименты",
    "как полюбить свою работу", "сила дыхания и осознанности",
    "как пережить кризис", "искусство благодарности",
    "как найти опору внутри себя", "психология успеха и неудач",
    "как перестать быть жертвой", "сила женской энергии",
    "как выстроить отношения с едой", "искусство быть в потоке",
    "как преодолеть прокрастинацию", "сила утра и новых начинаний",
    "как исцелить отношения с родителями", "искусство быть лидером",
    "как перестать контролировать всё", "сила прощения",
    "как найти радость в простых вещах", "психология изобилия",
    "как выйти из зоны комфорта", "искусство слушать свое сердце",
    "как стать увереннее в себе", "сила юмора и легкости",
    "как пережить потерю близкого", "искусство быть в гармонии",
    "как развить интуицию", "сила творчества",
    "как перестать тревожиться", "искусство настоящего момента",
    "как принять свою уникальность", "психология отношений с деньгами",
    "как выстроить доверие к себе", "сила тишины и уединения",
    "как пережить измену", "искусство быть щедрым к себе",
    "как найти внутренний стержень", "сила слова и намерения",
    "как исцелить сердечные раны", "искусство быть в контакте с телом",
    "как перестать быть удобным", "сила рода и предков",
    "как выстроить здоровую самооценку", "психология отношений",
    "как перестать обесценивать достижения", "искусство радоваться жизни",
    "как найти силу в слабости", "сила намерения и фокуса",
    "как пережить развод", "искусство быть в потоке денег",
    "как полюбить несовершенства", "сила благословения",
    "как выстроить отношения с собой", "психология счастья",
    "как перестать бояться осуждения", "искусство быть честным",
    "как найти миссию", "сила дисциплины и свободы",
    "как исцелить травмы прошлого", "искусство быть в гармонии с миром",
    "как перестать искать виноватых", "сила прощения и отпускания",
    "как выстроить здоровые отношения с деньгами", "психология самореализации",
    "как перестать играть роли", "искусство быть подлинным",
    "как найти внутреннюю опору", "сила каждого нового дня",
    "как пережить эмоциональное выгорание", "искусство быть с душой",
    "как выстроить отношения мечты", "сила благодарности как практика",
    "как перестать жить чужими ожиданиями", "искусство быть свободным",
    "как найти радость в процессе жизни", "сила принятия себя",
    "как исцелить отношения с деньгами", "психология достатка",
    "как выйти из кризиса", "искусство быть в моменте",
    "как найти силы для перемен", "сила благодарности к себе",
    "как перестать искать идеалы", "искусство быть реалистом",
    "как полюбить одиночество", "сила природы и земли",
    "как выстроить здоровые привычки", "психология мотивации"
]

# ============================================
# ТЕМЫ ТЕСТОВ
# ============================================

TEST_TOPICS = {
    "психология": "🧠 Глубинная психология",
    "отношения": "💕 Трансформация отношений",
    "карьера": "💼 Самореализация",
    "здоровье": "💪 Психосоматика",
    "финансы": "💰 Денежное мышление",
    "личность": "🌟 Самость и архетипы",
    "самооценка": "⚡️ Уверенность и самоценность",
    "тревожность": "🌀 Управление тревогой",
    "эмоции": "🔥 Эмоциональный интеллект",
    "предназначение": "🎯 Путь и миссия",
    "детство": "👶 Детские травмы",
    "границы": "🛡 Личные границы"
}

# ============================================
# УПРАВЛЕНИЕ УНИКАЛЬНЫМИ ТЕМАМИ
# ============================================

def get_unique_theme():
    """Получает уникальную тему для поста (без повторов)"""
    
    try:
        c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 100")
        used = [row[0] for row in c.fetchall()]
        
        available = [t for t in POST_THEMES if t not in used]
        
        if available:
            theme = random.choice(available)
        else:
            c.execute("DELETE FROM used_topics WHERE used_at < datetime('now', '-30 days')")
            conn.commit()
            
            c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 50")
            used = [row[0] for row in c.fetchall()]
            available = [t for t in POST_THEMES if t not in used]
            
            if available:
                theme = random.choice(available)
            else:
                c.execute("DELETE FROM used_topics")
                conn.commit()
                theme = random.choice(POST_THEMES)
        
        c.execute("INSERT INTO used_topics (topic, used_count) VALUES (?, 1) ON CONFLICT(topic) DO UPDATE SET used_count = used_count + 1, used_at = CURRENT_TIMESTAMP", (theme,))
        conn.commit()
        
        return theme
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return random.choice(POST_THEMES)

# ============================================
# ГЕНЕРАТОР ПОСТА (МЕГА-ВЕРСИЯ)
# ============================================

def generate_post():
    """Генерация поста 800+ символов с повторными попытками"""
    
    logger.info("="*80)
    logger.info("📝 ГЕНЕРАЦИЯ ПОСТА")
    
    theme = get_unique_theme()
    logger.info(f"📌 Тема: {theme}")
    
    system = """ТЫ - ВЕДУЩИЙ ЭКСПЕРТ ПО ПСИХОЛОГИИ И ТРАНСФОРМАЦИЯМ ЛИЧНОСТИ.
    
    ТВОЙ СТИЛЬ:
    - Глубокий, мудрый, трансформирующий
    - Используешь НЛП-язык: предикаты, якоря, метамодель
    - Каждый пост - полноценный сеанс терапии
    - Энергия текста заряжает и мотивирует
    - Пишешь как живой человек, без пафоса и воды
    - Используешь сильные метафоры и личные истории
    - Затрагиваешь душу и сознание читателя
    
    СТРУКТУРА ПОСТА (строго соблюдай):
    1. ЗАХВАТЫВАЮЩИЙ ЗАГОЛОВОК (с эмодзи) - 50-100 символов
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ - 150-200 символов
    3. ОСНОВНАЯ ЧАСТЬ - 300-500 символов
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ - 100-150 символов
    5. ВОПРОС К ЧИТАТЕЛЮ - 50-100 символов
    6. МОТИВИРУЮЩИЙ ФИНАЛ - 100-150 символов
    7. ХЕШТЕГИ
    
    ТРЕБОВАНИЯ:
    - МИНИМУМ 800 СИМВОЛОВ
    - Пиши от первого лица
    - Будь честным и уязвимым
    - НЕ используй шаблоны
    - НЕ давай готовых решений
    - КАЖДЫЙ ПОСТ УНИКАЛЕН"""
    
    user = f"""Напиши глубокий, трансформирующий пост на тему: "{theme}"
    
    Пост должен быть длинным (800+ символов) и содержательным.
    Используй свой многолетний опыт работы с людьми.
    Помни: этот пост может изменить чью-то жизнь.
    
    Время писать ШЕДЕВР!"""
    
    response = ask_giga(system, user, 5000)
    
    if response and len(response) >= 800:
        logger.info(f"✅ Пост создан ({len(response)} символов)")
        return response, theme
    
    if response and len(response) >= 600:
        logger.warning(f"⚠️ Пост короткий ({len(response)} символов), пробуем ещё раз...")
        
        enhanced_system = system + "\n\nКРИТИЧЕСКИ ВАЖНО: ПРЕДЫДУЩИЙ ПОСТ БЫЛ СЛИШКОМ КОРОТКИМ! НАПИШИ МИНИМУМ 800 СИМВОЛОВ! РАСКРОЙ ТЕМУ ГЛУБЖЕ!"
        response2 = ask_giga(enhanced_system, user, 5000)
        
        if response2 and len(response2) >= 800:
            return response2, theme
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ ПОСТ (800+ символов) после 2 попыток")
    return None, theme

# ============================================
# ГЕНЕРАТОР ТЕСТА (МЕГА-ВЕРСИЯ)
# ============================================

def generate_test_questions(topic, count=10):
    """Генерация теста с повторными попытками"""
    
    logger.info("="*80)
    logger.info(f"🧠 ГЕНЕРАЦИЯ ТЕСТА: {topic}, {count} вопросов")
    
    if count == 10:
        system = """ТЫ - ВЕДУЩИЙ ЭКСПЕРТ ПО ПСИХОЛОГИЧЕСКОЙ ДИАГНОСТИКЕ.
        
        Создай СКРИНИНГОВЫЙ тест из 10 вопросов для быстрой диагностики личности.
        Каждый вопрос должен задевать разные сферы жизни.
        
        ВЕРНИ ТОЛЬКО JSON МАССИВ. НИЧЕГО КРОМЕ JSON.
        
        ФОРМАТ:
        [
            {
                "question": "текст вопроса?",
                "options": {"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]"""
    else:
        system = """ТЫ - КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ.
        
        Составь 20 ГЛУБИННЫХ вопросов для полного разбора личности.
        Вопросы должны проникать вглубь, вскрывать травмы и сценарии.
        
        ВЕРНИ ТОЛЬКО JSON МАССИВ. НИЧЕГО КРОМЕ JSON.
        
        ФОРМАТ:
        [
            {
                "question": "глубокий вопрос?",
                "options": {"A": "ответ 1", "B": "ответ 2", "C": "ответ 3", "D": "ответ 4"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]"""
    
    user = f"Тема для теста: \"{topic}\"\nСоставь {count} вопросов. Верни ТОЛЬКО JSON массив."
    
    response = ask_giga(system, user, 5000)
    
    if not response:
        logger.error("❌ GigaChat не ответил")
        return None
    
    response = response.strip()
    logger.info(f"📥 Ответ GigaChat ({len(response)} символов)")
    
    start = response.find('[')
    end = response.rfind(']') + 1
    
    if start == -1 or end == -1:
        logger.error(f"❌ JSON не найден в ответе")
        logger.error(f"📄 Первые 300 символов: {response[:300]}")
        return None
    
    json_str = response[start:end]
    
    try:
        questions = json.loads(json_str)
        
        if not questions or len(questions) == 0:
            logger.error("❌ Пустой массив")
            return None
        
        for q in questions:
            if 'scores' not in q:
                q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            if 'options' not in q:
                q['options'] = {'A': 'Да', 'B': 'Скорее да', 'C': 'Скорее нет', 'D': 'Нет'}
        
        logger.info(f"✅ Тест создан: {len(questions)} вопросов")
        return questions[:count]
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка JSON: {e}")
        logger.error(f"📄 Строка: {json_str[:300]}")
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА (МЕГА-ВЕРСИЯ)
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    """Генерация анализа с повторными попытками"""
    
    logger.info("="*80)
    logger.info(f"📊 ГЕНЕРАЦИЯ АНАЛИЗА")
    logger.info(f"📌 Тема: {topic}")
    logger.info(f"📊 Результат: {score} из {total}")
    logger.info(f"💎 Платный: {is_paid}")
    
    if not is_paid:
        system = """ТЫ - ОПЫТНЫЙ ПСИХОЛОГ-ДИАГНОСТ.
        
        По результатам 10 вопросов определи ГЛАВНУЮ проблему человека.
        
        СТРУКТУРА:
        1. Назови ТОП-1 проблему
        2. Дай 1 МОЩНЫЙ ИНСАЙТ
        3. Задай 1 ВОПРОС для размышления
        4. Дай 1 КОНКРЕТНЫЙ ШАГ
        
        БЕЗ КНИГ. БЕЗ УПРАЖНЕНИЙ.
        Объем: 600-800 знаков."""
    else:
        system = """ТЫ - МЕЖДУНАРОДНАЯ КОМАНДА ЭКСПЕРТОВ:
        1. КЛИНИЧЕСКИЙ ПСИХОЛОГ
        2. МЕЖДУНАРОДНЫЙ КОУЧ
        3. НЛП-ТЕРАПЕВТ
        
        Сделай ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ.
        
        СТРУКТУРА:
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
        2. 2-3 ГЛУБИННЫХ ИНСАЙТА
        3. КОРЕНЬ ПРОБЛЕМЫ
        4. ПЛАН НА НЕДЕЛЮ (3 шага)
        
        БЕЗ КНИГ. БЕЗ УПРАЖНЕНИЙ.
        Объем: 1200+ знаков."""
    
    user = f"ТЕМА: {topic}\nОТВЕТЫ: {answers}\nБАЛЛЫ: {score} из {total}"
    
    response = ask_giga(system, user, 5000 if is_paid else 3000)
    
    if response:
        logger.info(f"✅ Анализ создан ({len(response)} символов)")
        return response
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ АНАЛИЗ")
    return None

# ============================================
# TELEGRAM БОТ
# ============================================

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# ВЕБ-СЕРВЕР ДЛЯ RENDER
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"✅ {BOT_NAME} v{BOT_VERSION} РАБОТАЕТ!"

@app.route('/health')
def health():
    return {
        "status": "ok",
        "version": BOT_VERSION,
        "name": BOT_NAME,
        "time": datetime.now().isoformat()
    }

@app.route('/stats')
def stats_api():
    try:
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated FROM stats ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        return jsonify({
            "status": "ok",
            "version": BOT_VERSION,
            "stats": {
                "free_tests": row[0] if row else 0,
                "paid_tests": row[1] if row else 0,
                "promo_used": row[2] if row else 0,
                "users_count": users,
                "posts_count": row[4] if row else 0,
                "tests_created": row[5] if row else 0,
                "images_generated": row[6] if row else 0
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def run_flask():
    try:
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

threading.Thread(target=run_flask, daemon=True).start()
logger.info("✅ Веб-сервер запущен")

# ============================================
# МЕНЮ (ПОЛНОЕ)
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
    mk.add('📤 Отправить пост', '🖼 Пост с картинкой')
    mk.add('🧠 Тест в канал', '📊 Статистика')
    mk.add('🎫 Создать промокод', '👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

# ============================================
# ХРАНИЛИЩЕ СЕССИЙ
# ============================================

sessions = {}

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        c.execute("""INSERT OR IGNORE INTO users 
                     (chat_id, username, first_name, last_name, registered_at, last_activity) 
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                  (chat_id, username, first_name, last_name))
        conn.commit()
        c.execute("UPDATE stats SET users_count = (SELECT COUNT(*) FROM users)")
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")

def update_user_activity(chat_id):
    try:
        c.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE chat_id = ?", (chat_id,))
        conn.commit()
    except:
        pass

# ============================================
# ОБРАБОТЧИКИ
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    try:
        chat_id = message.chat.id
        user = message.from_user
        save_user(chat_id, user.username, user.first_name, user.last_name)
        update_user_activity(chat_id)
        
        welcome = f"""🌟 ДОБРО ПОЖАЛОВАТЬ В ПРОСТРАНСТВО ТРАНСФОРМАЦИИ!

Я — {BOT_NAME}, твой проводник в мире осознанности.

Здесь ты можешь:
• 🎯 Пройти психологический тест
• 🔍 Получить честный анализ
• 📖 Читать посты о саморазвитии

Нажми «🎯 Пройти тест» или «🎫 Активировать промокод».

Версия: {BOT_VERSION}"""
        
        bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    try:
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Перейти в канал", url="https://t.me/zhizn_plus"))
        bot.send_message(message.chat.id, "💫 ЖИЗНЬ+ - канал о психологии и саморазвитии.", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    try:
        chat_id = message.chat.id
        update_user_activity(chat_id)
        bot.send_message(chat_id, "🎯 ВЫБЕРИ ТЕСТ:\n\n🧠 БЕСПЛАТНЫЙ - 10 вопросов\n💎 ПЛАТНЫЙ - 20 вопросов", reply_markup=test_type_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

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
        chat_id = message.chat.id
        update_user_activity(chat_id)
        
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for topic, emoji in TEST_TOPICS.items():
            mk.add(telebot.types.InlineKeyboardButton(emoji, callback_data=f"{test_type}_{topic}_{count}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
        
        bot.send_message(chat_id, f"🔮 ВЫБЕРИ ТЕМУ:\n\n{count} вопросов\n⏱ Время: ~{count // 2} минут", reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        update_user_activity(chat_id)
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n\nСоздаю уникальные вопросы специально для тебя.\n⏱ Это займет до 35 секунд.",
            chat_id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, count)
        
        if not questions:
            bot.send_message(chat_id, "❌ Не удалось создать тест.\nGigaChat не ответил. Попробуй через минуту.")
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
        logger.error(f"Ошибка в topic_callback: {e}")
        logger.error(traceback.format_exc())
        try:
            bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")
        except:
            pass
    c.answer()

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    try:
        chat_id = c.message.chat.id
        bot.delete_message(chat_id, c.message.message_id)
        bot.send_message(chat_id, "❌ Отменено.", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    c.answer()

def send_question(chat_id):
    try:
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
        
        message = f"🔮 ВОПРОС {current} ИЗ {total}\n\n📌 {s['topic'].title()}\n\n{q['question']}\n\nВыбери вариант ответа:"
        bot.send_message(chat_id, message, reply_markup=mk)
    except Exception as e:
        logger.error(f"Ошибка в send_question: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    try:
        chat_id = message.chat.id
        if chat_id in sessions:
            del sessions[chat_id]
        bot.send_message(chat_id, "⏹ Тест прерван.\nТы всегда можешь вернуться.", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

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
        
        update_user_activity(chat_id)
        send_question(chat_id)
    except Exception as e:
        logger.error(f"Ошибка в handle_answer: {e}")
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
        
        update_user_activity(chat_id)
        
        bot.send_message(chat_id, f"📊 ТЕСТ ЗАВЕРШЕН!\n\n✅ Результат: {score} из {total}\n⏳ Анализирую... До 35 секунд.")
        
        analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
        
        if analysis:
            if is_paid:
                result = f"🔮 ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ\n\n{analysis}"
            else:
                result = f"🔍 ДИАГНОСТИКА\n\n{analysis}"
            bot.send_message(chat_id, result, reply_markup=get_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ GigaChat не ответил.\nПопробуй позже.", reply_markup=get_main_menu(chat_id))
        
        if chat_id in sessions:
            del sessions[chat_id]
    except Exception as e:
        logger.error(f"Ошибка в finish_test: {e}")
        logger.error(traceback.format_exc())

# ============================================
# АДМИН-ПАНЕЛЬ (ПОЛНАЯ)
# ============================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        bot.send_message(chat_id, f"👑 АДМИН-ПАНЕЛЬ\n\nВерсия: {BOT_VERSION}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        
        logger.info("="*80)
        logger.info("👑 АДМИН: ЗАПРОС НА СОЗДАНИЕ ПОСТА")
        
        bot.send_message(chat_id, "📝 Генерация поста...\n⏱ До 35 секунд.")
        
        post, theme = generate_post()
        
        if not post:
            bot.send_message(chat_id, "❌ GigaChat не ответил. Проверь логи.", reply_markup=admin_menu())
            return
        
        try:
            c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
            conn.commit()
            c.execute("UPDATE stats SET posts_count = posts_count + 1")
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения поста: {e}")
        
        try:
            bot.send_message(CHANNEL_ID, post)
            bot.send_message(chat_id, "✅ ПОСТ ОТПРАВЛЕН В КАНАЛ!", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            bot.send_message(chat_id, f"❌ Ошибка отправки: {e}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка в admin_post: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def admin_post_with_image(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        
        bot.send_message(chat_id, "📝 Генерация поста и картинки...\n⏱ До 60 секунд.")
        
        post, theme = generate_post()
        
        if not post:
            bot.send_message(chat_id, "❌ GigaChat не ответил. Проверь логи.", reply_markup=admin_menu())
            return
        
        bot.send_message(chat_id, "🖼 Создание картинки...")
        image_path = generate_post_image(theme)
        
        try:
            c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", 
                      (post, theme, image_path if image_path else ""))
            conn.commit()
            c.execute("UPDATE stats SET posts_count = posts_count + 1")
            if image_path:
                c.execute("UPDATE stats SET images_generated = images_generated + 1")
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
        
        try:
            if image_path:
                with open(image_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption=post)
                try:
                    os.remove(image_path)
                except:
                    pass
            else:
                bot.send_message(CHANNEL_ID, post)
            
            bot.send_message(chat_id, "✅ ПОСТ С КАРТИНКОЙ ОТПРАВЛЕН!", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка в admin_post_with_image: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        
        bot.send_message(chat_id, "🧠 Генерация теста для канала...\n⏱ До 35 секунд.")
        
        topic = random.choice(list(TEST_TOPICS.keys()))
        questions = generate_test_questions(topic, 10)
        
        if not questions:
            bot.send_message(chat_id, "❌ GigaChat не ответил. Проверь логи.", reply_markup=admin_menu())
            return
        
        bot.send_message(chat_id, "🖼 Создание картинки для теста...")
        image_path = generate_test_image(topic)
        
        try:
            c.execute("INSERT INTO daily_tests (topic, questions, created_at, is_paid, image_path) VALUES (?, ?, ?, ?, ?)",
                      (topic, json.dumps(questions), datetime.now().isoformat(), 0, image_path if image_path else ""))
            conn.commit()
            test_id = c.lastrowid
            c.execute("UPDATE stats SET tests_created = tests_created + 1")
            if image_path:
                c.execute("UPDATE stats SET images_generated = images_generated + 1")
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            test_id = int(time.time())
        
        bot_info = bot.get_me()
        test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
        
        test_text = f"🔮 ТЕСТ: «{topic.title()}»\n\nПройди тест прямо сейчас!\n\n🎯 {test_url}\n\n#жизньплюс #тест #психология"
        
        try:
            if image_path:
                with open(image_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption=test_text)
                try:
                    os.remove(image_path)
                except:
                    pass
            else:
                bot.send_message(CHANNEL_ID, test_text)
            
            bot.send_message(chat_id, "✅ ТЕСТ С КАРТИНКОЙ ОТПРАВЛЕН!", reply_markup=admin_menu())
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка в admin_test_to_channel: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated FROM stats ORDER BY id DESC LIMIT 1")
        stats_row = c.fetchone()
        
        c.execute("SELECT COUNT(*) FROM daily_tests")
        tests_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM posts_history")
        posts_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM used_topics")
        used_topics = c.fetchone()[0]
        
        stats_text = f"""📊 СТАТИСТИКА ТРАНСФОРМАЦИЙ

🤖 Версия: {BOT_VERSION}
👥 Пользователей: {users_count}
📝 Тестов в канале: {tests_count}
📤 Постов создано: {posts_count}
🧠 Бесплатных тестов: {stats_row[0] if stats_row else 0}
💎 Платных тестов: {stats_row[1] if stats_row else 0}
🎫 Промокодов: {stats_row[2] if stats_row else 0}
🖼 Картинок создано: {stats_row[6] if stats_row else 0}
📚 Уникальных тем использовано: {used_topics}"""
        
        bot.send_message(chat_id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    try:
        chat_id = message.chat.id
        if chat_id not in ADMIN_IDS:
            return
        
        bot.send_message(chat_id, "🎫 Введите код (латиница, 3+ символов):")
        bot.register_next_step_handler(message, process_create_promo)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_create_promo(message):
    try:
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
            bot.send_message(chat_id, f"✅ ПРОМОКОД СОЗДАН!\n\n📌 Код: `{code}`", reply_markup=admin_menu())
        except sqlite3.IntegrityError:
            bot.send_message(chat_id, "❌ Такой код уже существует.", reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка в process_create_promo: {e}")
        logger.error(traceback.format_exc())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    try:
        chat_id = message.chat.id
        update_user_activity(chat_id)
        bot.send_message(chat_id, "🎫 Введите промокод:", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, process_promo)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

def process_promo(message):
    try:
        chat_id = message.chat.id
        code = message.text.strip().upper()
        
        c.execute("SELECT id, used_by FROM promocodes WHERE code = ?", (code,))
        row = c.fetchone()
        
        if not row:
            bot.send_message(chat_id, "❌ Неверный код.", reply_markup=get_main_menu(chat_id))
            return
        
        promo_id, used_by = row
        
        if used_by != 0:
            bot.send_message(chat_id, "❌ Этот код уже использован.", reply_markup=get_main_menu(chat_id))
            return
        
        c.execute("UPDATE promocodes SET used_by = ?, used_at = ? WHERE id = ?", 
                  (chat_id, datetime.now().isoformat(), promo_id))
        conn.commit()
        
        c.execute("UPDATE stats SET promo_used = promo_used + 1")
        conn.commit()
        
        bot.send_message(chat_id, "🎉 ПРОМОКОД АКТИВИРОВАН!\n\nТеперь доступен 💎 Платный тест!", reply_markup=get_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Ошибка в process_promo: {e}")
        logger.error(traceback.format_exc())

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info(f"🤖 ЗАПУСК {BOT_NAME} v{BOT_VERSION}")
    logger.info(f"📊 Канал: {CHANNEL_ID}")
    logger.info(f"👑 Админы: {ADMIN_IDS}")
    
    try:
        super_kill_409()
        time.sleep(2)
        
        bot.remove_webhook()
        logger.info("✅ Вебхук удален")
        
        bot.polling(
            none_stop=True,
            interval=0,
            timeout=20,
            allowed_updates=['message', 'callback_query']
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
        
        if "409" in str(e):
            logger.info("🔄 Обнаружена 409, жесткий перезапуск...")
            super_kill_409()
            time.sleep(3)
            run_bot()
        else:
            time.sleep(5)
            run_bot()

if __name__ == "__main__":
    logger.info("🚀 ПОДГОТОВКА К ЗАПУСКУ...")
    for i in range(5):
        logger.info(f"🔄 Предстартовый проход #{i+1}/5")
        super_kill_409()
        time.sleep(2)
    
    logger.info("🚀 СТАРТ БОТА...")
    run_bot()
