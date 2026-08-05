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
import signal
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

GIGA_CLIENT_ID = "019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e"
GIGA_CLIENT_SECRET = "MDE5ZmM3YTItOGQ0Ni03MGNiLTkwMjgtZmNmYzVhMWQ0ZDBlOjljMmUzNTI3LWI3NzAtNDU0NS1iMTFmLTBiZDljNDMxNWU1Mw=="

# Версия бота
BOT_VERSION = "4.0.0"
BOT_NAME = "Жизнь+ Трансформационный Бот"

# Пути и файлы
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
# СУПЕР-МЕГА-УБИЙЦА 409 (50 СПОСОБОВ)
# ============================================

def super_kill_409():
    """Уничтожает 409 всеми мыслимыми и немыслимыми способами"""
    
    logger.info("🔥 НАЧАЛО УНИЧТОЖЕНИЯ 409 (50 способов)")
    success_count = 0
    
    try:
        # 1-20: Многократное удаление вебхука через POST
        for i in range(20):
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                response = requests.post(url, json={"drop_pending_updates": True}, timeout=10)
                if response.status_code == 200:
                    success_count += 1
                time.sleep(0.1)
            except:
                pass
        
        # 21-25: Многократное удаление через GET
        for i in range(5):
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
                response = requests.get(url, params={"drop_pending_updates": "true"}, timeout=10)
                if response.status_code == 200:
                    success_count += 1
                time.sleep(0.1)
            except:
                pass
        
        # 26: Сброс вебхука в ноль
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            response = requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
            if response.status_code == 200:
                success_count += 1
        except:
            pass
        
        # 27: Сброс через GET
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            response = requests.get(url, params={"url": "", "drop_pending_updates": "true"}, timeout=10)
            if response.status_code == 200:
                success_count += 1
        except:
            pass
        
        # 28-35: Удаление всех возможных файлов блокировки
        patterns = [
            'update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid', 
            '*.offset', '*.cache', '*.tmp', '*.log', '*.db-journal', '*.wal',
            '*.shm', '*-journal', '*-wal', '*-shm', 'bot.lock', 'session.lock'
        ]
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
        
        # 36-40: Удаление временных файлов
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
        
        # 41: Проверка статуса вебхука
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
            response = requests.get(url, timeout=10)
            webhook_data = response.json()
            logger.info(f"📡 Вебхук статус: {webhook_data}")
            
            # Если вебхук всё ещё висит - пробуем удалить его через параметры
            if webhook_data.get('result', {}).get('url'):
                logger.warning("⚠️ Вебхук всё ещё висит! Пробую жесткое удаление...")
                
                # 42-45: Жесткое удаление с разными параметрами
                for method in ['deleteWebhook', 'setWebhook']:
                    for drop in [True, False]:
                        try:
                            url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
                            requests.post(url, json={"drop_pending_updates": drop, "url": ""}, timeout=10)
                        except:
                            pass
        except:
            pass
        
        # 46-50: Финальная очистка
        time.sleep(1)
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            requests.post(url, json={"drop_pending_updates": True}, timeout=10)
        except:
            pass
        
        logger.info(f"🔥 409 УНИЧТОЖЕН! Успешных операций: {success_count}/50")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при уничтожении 409: {e}")
        return False

# ПЯТИКРАТНОЕ УНИЧТОЖЕНИЕ ДЛЯ ГАРАНТИИ
for i in range(5):
    logger.info(f"🔄 Проход уничтожения 409 #{i+1}/5")
    super_kill_409()
    time.sleep(2)

# ============================================
# GIGACHAT (С МАКСИМАЛЬНЫМ КОНТРОЛЕМ)
# ============================================

giga_token_cache = {"token": None, "expires": 0, "last_error": None, "error_count": 0}

def get_giga_token():
    """Получение токена GigaChat с полным логированием"""
    
    logger.info("🔑 НАЧАЛО ПОЛУЧЕНИЯ ТОКЕНА GIGACHAT")
    
    # Проверяем кэш
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        logger.info("✅ Токен из кэша (действителен до " + 
                   datetime.fromtimestamp(giga_token_cache["expires"]).strftime('%H:%M:%S') + ")")
        return giga_token_cache["token"]
    
    # Если были ошибки - делаем паузу
    if giga_token_cache["error_count"] > 3:
        logger.warning(f"⚠️ Слишком много ошибок ({giga_token_cache['error_count']}), делаю паузу 5 сек...")
        time.sleep(5)
    
    # Пробуем получить токен
    for attempt in range(1, 7):
        try:
            logger.info(f"🔄 Попытка {attempt}/6...")
            
            # Формируем авторизацию
            auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': str(uuid.uuid4())
            }
            
            logger.debug(f"📤 Отправка запроса к https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
            
            start_time = time.time()
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data='scope=GIGACHAT_API_PERS',
                timeout=30,
                verify=False
            )
            elapsed = time.time() - start_time
            
            logger.info(f"📡 Статус: {response.status_code}, время: {elapsed:.2f} сек")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    token = data.get('access_token')
                    
                    if token:
                        expires_in = data.get('expires_in', 3600)
                        giga_token_cache["token"] = token
                        giga_token_cache["expires"] = time.time() + expires_in - 100
                        giga_token_cache["error_count"] = 0
                        logger.info(f"✅ ТОКЕН ПОЛУЧЕН! Действителен {expires_in} сек")
                        return token
                    else:
                        logger.error("❌ Токен не найден в ответе")
                        logger.debug(f"📄 Ответ: {json.dumps(data, indent=2)[:500]}")
                except json.JSONDecodeError as je:
                    logger.error(f"❌ Ошибка парсинга JSON: {je}")
                    logger.debug(f"📄 Текст ответа: {response.text[:300]}")
            else:
                logger.error(f"❌ Ошибка HTTP {response.status_code}")
                logger.debug(f"📄 Текст ошибки: {response.text[:500]}")
                
                # Если 400 - возможно неверные ключи
                if response.status_code == 400:
                    logger.error("❌ ВОЗМОЖНО НЕВЕРНЫЕ CLIENT_ID ИЛИ CLIENT_SECRET!")
                    giga_token_cache["error_count"] += 1
            
            time.sleep(2)
            
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ при получении токена (30 сек)")
            giga_token_cache["error_count"] += 1
            time.sleep(3)
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {ce}")
            giga_token_cache["error_count"] += 1
            time.sleep(5)
        except Exception as e:
            logger.error(f"❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")
            giga_token_cache["error_count"] += 1
            time.sleep(3)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ТОКЕН ПОСЛЕ 6 ПОПЫТОК")
    giga_token_cache["last_error"] = datetime.now().isoformat()
    return None

def ask_giga(system, user, max_tokens=5000, temperature=0.95):
    """Запрос к GigaChat с полным контролем и логированием"""
    
    logger.info("="*80)
    logger.info("📤 ЗАПРОС К GIGACHAT")
    logger.info(f"📝 Системный промпт (первые 150 символов): {system[:150]}...")
    logger.info(f"📝 Пользовательский запрос (первые 150 символов): {user[:150]}...")
    logger.info(f"⚙️ Параметры: max_tokens={max_tokens}, temperature={temperature}")
    
    # Получаем токен
    token = get_giga_token()
    if not token:
        logger.error("❌ ТОКЕН НЕ ПОЛУЧЕН - ЗАПРОС ОТМЕНЁН")
        return None
    
    # Формируем запрос
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4())
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "repetition_penalty": 1.1,
        "top_p": 0.95
    }
    
    logger.info(f"📦 Размер запроса: {len(json.dumps(payload))} байт")
    
    # Отправляем запрос с повторными попытками
    for attempt in range(1, 5):
        try:
            logger.info(f"🔄 Попытка {attempt}/4...")
            
            start_time = time.time()
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=90,
                verify=False
            )
            elapsed = time.time() - start_time
            
            logger.info(f"⏱ Ответ получен за {elapsed:.2f} сек")
            logger.info(f"📡 HTTP Статус: {response.status_code}")
            
            # Ждём гарантированное время (если ответ пришёл рано)
            if elapsed < 35:
                wait_time = 35 - elapsed
                logger.info(f"⏳ Ожидание {wait_time:.2f} сек (гарантия 35 сек)")
                time.sleep(wait_time)
            
            # Обрабатываем ответ
            if response.status_code == 200:
                try:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    logger.info(f"📄 Длина ответа: {len(content)} символов")
                    logger.info(f"📄 Первые 150 символов: {content[:150]}...")
                    
                    # Проверяем что ответ не пустой
                    if content and len(content) > 10:
                        logger.info("✅ ЗАПРОС УСПЕШНО ВЫПОЛНЕН!")
                        
                        # Обновляем статистику использования
                        usage = result.get('usage', {})
                        logger.info(f"📊 Использование токенов: {json.dumps(usage)}")
                        
                        return content
                    else:
                        logger.error("❌ ПУСТОЙ ИЛИ СЛИШКОМ КОРОТКИЙ ОТВЕТ")
                        logger.debug(f"📄 Полный ответ: {json.dumps(result, indent=2)[:300]}")
                except json.JSONDecodeError as je:
                    logger.error(f"❌ ОШИБКА ПАРСИНГА JSON: {je}")
                    logger.debug(f"📄 Текст ответа: {response.text[:500]}")
            else:
                logger.error(f"❌ ОШИБКА HTTP {response.status_code}")
                logger.error(f"📄 Текст ошибки: {response.text[:500]}")
                
                # Если 401 - токен умер, пробуем обновить
                if response.status_code == 401:
                    logger.warning("⚠️ Токен умер, сбрасываем кэш...")
                    giga_token_cache["token"] = None
                    giga_token_cache["expires"] = 0
                    time.sleep(2)
            
            time.sleep(2)
            
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ (90 секунд)")
            time.sleep(3)
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {ce}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"❌ НЕИЗВЕСТНАЯ ОШИБКА: {e}")
            time.sleep(3)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ОТВЕТ ПОСЛЕ 4 ПОПЫТОК")
    return None

# ============================================
# ГЕНЕРАЦИЯ КАРТИНОК (МЕГА-ВЕРСИЯ)
# ============================================

def generate_image(prompt, width=1024, height=768, attempts=3):
    """Генерация картинки с несколькими API и повторными попытками"""
    
    logger.info(f"🖼 ГЕНЕРАЦИЯ КАРТИНКИ")
    logger.info(f"📝 Промпт: {prompt[:100]}...")
    
    # Очищаем промпт
    clean_prompt = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "").replace(',', '%2C')
    full_prompt = f"{clean_prompt}, high quality, detailed, beautiful, professional, 4k, masterpiece, award-winning"
    
    # Список API (если один не работает - пробуем другой)
    apis = [
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&nologo=true&seed={random.randint(1,999999)}",
        f"https://pollinations.ai/prompt/{full_prompt}?width={width}&height={height}",
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&model=flux",
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&seed={random.randint(1,999999)}"
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
                    # Сохраняем картинку
                    filename = f"{TEMP_IMAGE_PATH}image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    
                    file_size = os.path.getsize(filename)
                    logger.info(f"✅ КАРТИНКА СОЗДАНА: {filename} ({file_size} байт)")
                    return filename
                else:
                    logger.warning(f"⚠️ Ошибка API: статус {response.status_code}, размер {len(response.content)} байт")
            except requests.exceptions.Timeout:
                logger.warning("⚠️ Таймаут API")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка API: {e}")
            time.sleep(1)
        
        if attempt < attempts:
            logger.info(f"⏳ Пауза перед следующей попыткой...")
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
# БАЗА ДАННЫХ (МЕГА-ВЕРСИЯ)
# ============================================

def init_database():
    """Инициализация базы данных со всеми таблицами и индексами"""
    
    logger.info("🗄️ ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ")
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # Включаем поддержку внешних ключей
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
        referrer_id INTEGER,
        total_score INTEGER DEFAULT 0
    )''')
    
    # Индексы для пользователей
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
    
    # Начальные данные для статистики
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO stats (free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated, giga_requests, giga_errors, messages_received, messages_sent, total_users, active_users) VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)")
    
    # Таблица сессий тестов
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
    
    # Сохраняем настройки
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('bot_version', ?)", (BOT_VERSION,))
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('last_start', ?)", (datetime.now().isoformat(),))
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('timezone', 'Asia/Yekaterinburg')")
    
    conn.commit()
    conn.close()
    
    logger.info("✅ БАЗА ДАННЫХ ИНИЦИАЛИЗИРОВАНА")

# Создаём базу данных
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
    "как пережить кризис среднего возраста", "искусство благодарности",
    "как найти опору внутри себя", "психология успеха и неудач",
    "как перестать быть жертвой", "сила женской энергии",
    "как выстроить отношения с едой", "искусство быть в потоке",
    "как преодолеть прокрастинацию", "сила утра и новых начинаний",
    "как исцелить отношения с родителями", "искусство быть лидером",
    "как перестать контролировать всё", "сила прощения себя и других",
    "как найти радость в простых вещах", "психология изобилия",
    "как выйти из зоны комфорта", "искусство слушать свое сердце",
    "как стать увереннее в себе", "сила юмора и легкости",
    "как пережить потерю близкого", "искусство быть в гармонии с собой",
    "как развить интуицию", "сила творчества и самовыражения",
    "как перестать тревожиться о будущем", "искусство настоящего момента",
    "как принять свою уникальность", "психология отношений с деньгами",
    "как выстроить доверие к себе", "сила тишины и уединения",
    "как пережить измену и предательство", "искусство быть щедрым к себе",
    "как найти внутренний стержень", "сила слова и намерения",
    "как исцелить сердечные раны", "искусство быть в контакте с телом",
    "как перестать быть удобным для всех", "сила рода и предков",
    "как выстроить здоровую самооценку", "психология успешных отношений",
    "как перестать обесценивать свои достижения", "искусство радоваться жизни",
    "как найти силу в слабости", "сила намерения и фокуса",
    "как пережить развод и расставание", "искусство быть в потоке денег",
    "как полюбить свои несовершенства", "сила благословения и благодарности",
    "как выстроить отношения с собой", "психология счастья и удовлетворенности",
    "как перестать бояться осуждения", "искусство быть честным с собой",
    "как найти призвание и миссию", "сила дисциплины и свободы",
    "как исцелить травмы прошлого", "искусство быть в гармонии с миром",
    "как перестать искать виноватых", "сила прощения и отпускания",
    "как выстроить здоровые отношения с деньгами", "психология самореализации",
    "как перестать играть роли", "искусство быть подлинным",
    "как найти внутреннюю опору", "сила каждого нового дня",
    "как пережить эмоциональное выгорание", "искусство быть в контакте с душой",
    "как выстроить отношения мечты", "сила благодарности как практика",
    "как перестать жить чужими ожиданиями", "искусство быть свободным",
    "как найти радость в процессе жизни", "сила принятия себя",
    "как исцелить отношения с деньгами", "психология достатка",
    "как выйти из кризиса", "искусство быть в моменте",
    "как найти силы для перемен", "сила благодарности к себе",
    "как перестать искать идеалы", "искусство быть реалистом",
    "как полюбить одиночество", "сила природы и земли",
    "как выстроить здоровые привычки", "психология мотивации",
    "как перестать откладывать жизнь", "искусство быть в действии",
    "как найти баланс", "сила женской мудрости",
    "как исцелить детские травмы", "искусство быть мужчиной",
    "как перестать бояться будущего", "сила настоящего момента",
    "как доверять себе", "искусство быть спонтанным",
    "как пережить неудачу", "сила упорства и терпения",
    "как найти поддержку в себе", "искусство быть верным себе",
    "как полюбить свою историю", "сила простых решений",
    "как исцелить отношения с миром", "психология внутреннего ребенка",
    "как найти смысл жизни", "сила любви и принятия",
    "как перестать быть перфекционистом", "искусство быть достаточно хорошим",
    "как исцелить родовые сценарии", "сила мужской энергии",
    "как выстроить здоровую коммуникацию", "психология доверия",
    "как перестать спасать всех", "искусство быть немного эгоистом",
    "как найти свое место в мире", "сила внутренней тишины",
    "как исцелить зависимость от чужого мнения", "искусство быть автором своей жизни",
    "как перестать жить в прошлом", "сила нового начала",
    "как полюбить свои эмоции", "психология эмоциональной зрелости",
    "как найти свой голос", "сила быть собой",
    "как перестать доказывать", "искусство быть в потоке",
    "как исцелить отношения с телом", "психология здоровья",
    "как выстроить отношения с успехом", "сила веры в себя",
    "как перестать бежать от себя", "искусство быть в контакте с собой",
    "как найти тишину в шуме", "сила внутреннего покоя",
    "как исцелить отношения с мамой", "психология материнской любви",
    "как выстроить отношения с папой", "сила отцовского принятия",
    "как перестать искать идеального партнера", "искусство здоровых отношений"
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
    "границы": "🛡 Личные границы",
    "отношения с деньгами": "💰 Финансовое мышление",
    "отношения с телом": "💪 Здоровье и тело",
    "отношения с партнером": "💕 Любовь и партнерство"
}

# ============================================
# УПРАВЛЕНИЕ УНИКАЛЬНЫМИ ТЕМАМИ
# ============================================

def get_unique_theme():
    """Получает уникальную тему для поста (без повторов)"""
    
    try:
        # Получаем последние 100 использованных тем
        c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 100")
        used = [row[0] for row in c.fetchall()]
        
        # Ищем тему, которой нет в использованных
        available = [t for t in POST_THEMES if t not in used]
        
        if available:
            theme = random.choice(available)
        else:
            # Если все темы использованы - удаляем старые записи
            c.execute("DELETE FROM used_topics WHERE used_at < datetime('now', '-30 days')")
            conn.commit()
            
            # Пробуем снова
            c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 50")
            used = [row[0] for row in c.fetchall()]
            available = [t for t in POST_THEMES if t not in used]
            
            if available:
                theme = random.choice(available)
            else:
                # Если всё равно нет - очищаем полностью
                c.execute("DELETE FROM used_topics")
                conn.commit()
                theme = random.choice(POST_THEMES)
        
        # Сохраняем использованную тему
        c.execute("INSERT INTO used_topics (topic, used_count) VALUES (?, 1) ON CONFLICT(topic) DO UPDATE SET used_count = used_count + 1, used_at = CURRENT_TIMESTAMP", (theme,))
        conn.commit()
        
        return theme
        
    except Exception as e:
        logger.error(f"Ошибка при получении уникальной темы: {e}")
        return random.choice(POST_THEMES)

# ============================================
# ГЕНЕРАТОР ПОСТА (МЕГА-ВЕРСИЯ)
# ============================================

def generate_post():
    """Генерация поста длиной 800+ символов только через GigaChat"""
    
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
    1. ЗАХВАТЫВАЮЩИЙ ЗАГОЛОВОК (с эмодзи) - 50-100 символов, который хочется прочитать
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ (150-200 символов) - затронь струны души читателя, создай резонанс
    3. ОСНОВНАЯ ЧАСТЬ (300-500 символов) - раскрой тему, дай инсайты и открытия, покажи новые грани
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ (100-150 символов) - конкретное, выполнимое сегодня, с чёткой инструкцией
    5. ВОПРОС К ЧИТАТЕЛЮ (50-100 символов) - провокационный, пробуждающий, оставляющий след
    6. МОТИВИРУЮЩИЙ ФИНАЛ (100-150 символов) - крылья и энергия, ощущение силы и возможности
    7. ХЕШТЕГИ (3-5 штук) - релевантные, точные
    
    ТРЕБОВАНИЯ К КАЧЕСТВУ:
    - МИНИМУМ 800 СИМВОЛОВ (строго!)
    - Максимум 1200 символов
    - Пиши от первого лица, как личный опыт
    - Будь честным, уязвимым и открытым
    - НЕ используй шаблонные фразы и клише
    - НЕ давай готовых решений - только вопросы и инсайты
    - КАЖДЫЙ ПОСТ УНИКАЛЕН - не повторяйся никогда
    
    ВАЖНО: Пост должен ОСТАВЛЯТЬ СЛЕД в душе читателя, менять его восприятие, давать новый взгляд на привычные вещи."""
    
    user = f"""Напиши глубокий, трансформирующий пост на тему: "{theme}"
    
    Сделай этот пост откровением для каждого читателя.
    Пост должен быть длинным (800+ символов) и содержательным.
    Используй свой многолетний опыт работы с людьми.
    
    Помни: этот пост может изменить чью-то жизнь.
    
    Время писать ШЕДЕВР!"""
    
    # Первая попытка
    response = ask_giga(system, user, 5000)
    
    if response and len(response) >= 800:
        logger.info(f"✅ Пост создан ({len(response)} символов)")
        return response, theme
    
    # Если короткий - вторая попытка с усилением
    if response and len(response) >= 600:
        logger.warning(f"⚠️ Пост короткий ({len(response)} символов), пробуем ещё раз...")
        
        enhanced_system = system + "\n\nКРИТИЧЕСКИ ВАЖНО: ПРЕДЫДУЩИЙ ПОСТ БЫЛ СЛИШКОМ КОРОТКИМ! НАПИШИ МИНИМУМ 800 СИМВОЛОВ! РАСКРОЙ ТЕМУ ГЛУБЖЕ! ДОБАВЬ БОЛЬШЕ СОДЕРЖАНИЯ, ИСТОРИЙ И ИНСАЙТОВ!"
        
        response2 = ask_giga(enhanced_system, user, 5000)
        
        if response2 and len(response2) >= 800:
            return response2, theme
    
    # Если не получилось - третья попытка с полным пересмотром
    logger.warning("⚠️ Пробуем третий раз с упрощённым подходом...")
    
    simplified_system = """Напиши пост на тему. МИНИМУМ 800 СИМВОЛОВ.
    Структура: Заголовок → Вступление → Основная часть → Практика → Вопрос → Финальная мысль.
    Пиши от первого лица, честно и глубоко. Не повторяйся."""
    
    response3 = ask_giga(simplified_system, f"Тема: {theme}. Пост 800+ символов.", 5000)
    
    if response3 and len(response3) >= 800:
        return response3, theme
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ ПОСТ (800+ символов) после 3 попыток")
    return None, theme

# ============================================
# ГЕНЕРАТОР ТЕСТА (МЕГА-ВЕРСИЯ)
# ============================================

def generate_test_questions(topic, count=10):
    """Генерация теста только через GigaChat"""
    
    logger.info("="*80)
    logger.info(f"🧠 ГЕНЕРАЦИЯ ТЕСТА: {topic}, {count} вопросов")
    
    # Создаём промпт в зависимости от количества вопросов
    if count == 10:
        system = """ТЫ - ВЕДУЩИЙ ЭКСПЕРТ ПО ПСИХОЛОГИЧЕСКОЙ ДИАГНОСТИКЕ.
        
        Создай СКРИНИНГОВЫЙ тест из 10 вопросов для быстрой диагностики личности.
        Каждый вопрос должен задевать разные сферы жизни и давать полную картину.
        
        ВЕРНИ ТОЛЬКО JSON МАССИВ. НИЧЕГО КРОМЕ JSON.
        
        ФОРМАТ (точное соблюдение):
        [
            {
                "question": "текст вопроса? (заканчивается вопросительным знаком)",
                "options": {
                    "A": "вариант ответа 1",
                    "B": "вариант ответа 2", 
                    "C": "вариант ответа 3",
                    "D": "вариант ответа 4"
                },
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]
        
        ТРЕБОВАНИЯ К ВОПРОСАМ:
        - Вопросы должны быть глубокими и небанальными
        - Заставлять задуматься и удивить себя
        - Использовать разные формулировки
        - Варианты ответов должны быть реалистичными и разными по смыслу
        - Оценка: 0 - лучший вариант, 3 - худший вариант"""
        
        user = f"""Тема для теста: "{topic}"
        Составь 10 вопросов для быстрой диагностики личности.
        Верни ТОЛЬКО JSON массив."""
    
    else:
        system = """ТЫ - КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ И АВТОР МЕТОДИК.
        
        Составь 20 ГЛУБИННЫХ вопросов для полного разбора личности.
        Вопросы должны проникать вглубь, вскрывать травмы, убеждения и жизненные сценарии.
        
        ВЕРНИ ТОЛЬКО JSON МАССИВ. НИЧЕГО КРОМЕ JSON.
        
        ФОРМАТ (точное соблюдение):
        [
            {
                "question": "глубокий вопрос? (заканчивается вопросительным знаком)",
                "options": {
                    "A": "ответ 1",
                    "B": "ответ 2",
                    "C": "ответ 3",
                    "D": "ответ 4"
                },
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]
        
        ТРЕБОВАНИЯ К ВОПРОСАМ:
        - Используй техники: проективные вопросы, вопросы о детстве
        - Каждый вопрос - ключ к разгадке личности
        - Варианты ответов показывают разные психотипы
        - Вопросы должны быть неожиданными и глубокими"""
        
        user = f"""Тема для теста: "{topic}"
        Составь 20 глубоких вопросов для полного разбора личности.
        Верни ТОЛЬКО JSON массив."""
    
    response = ask_giga(system, user, 5000)
    
    if not response:
        logger.error("❌ GigaChat не ответил")
        return None
    
    response = response.strip()
    logger.info(f"📥 Ответ GigaChat ({len(response)} символов)")
    
    # Ищем JSON
    start = response.find('[')
    end = response.rfind(']') + 1
    
    if start == -1 or end == -1:
        logger.error(f"❌ JSON не найден в ответе")
        logger.error(f"📄 Первые 300 символов: {response[:300]}")
        return None
    
    json_str = response[start:end]
    logger.debug(f"📄 JSON строка: {json_str[:200]}...")
    
    try:
        questions = json.loads(json_str)
        
        if not questions or len(questions) == 0:
            logger.error("❌ Пустой массив вопросов")
            return None
        
        # Проверяем структуру и добавляем баллы при необходимости
        valid_questions = []
        for q in questions:
            if 'question' not in q or 'options' not in q:
                logger.warning(f"⚠️ Неполный вопрос, пропускаем: {q}")
                continue
            
            if 'scores' not in q:
                q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            
            # Проверяем что все опции есть
            for opt in ['A', 'B', 'C', 'D']:
                if opt not in q['options']:
                    q['options'][opt] = f"Вариант {opt}"
            
            valid_questions.append(q)
        
        if len(valid_questions) == 0:
            logger.error("❌ Нет валидных вопросов")
            return None
        
        logger.info(f"✅ Тест создан: {len(valid_questions)} вопросов")
        return valid_questions[:count]
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON: {e}")
        logger.error(f"📄 Ошибочная строка: {json_str[:300]}")
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА (МЕГА-ВЕРСИЯ)
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    """Генерация анализа только через GigaChat"""
    
    logger.info("="*80)
    logger.info(f"📊 ГЕНЕРАЦИЯ АНАЛИЗА")
    logger.info(f"📌 Тема: {topic}")
    logger.info(f"📊 Результат: {score} из {total}")
    logger.info(f"💎 Платный: {is_paid}")
    
    if not is_paid:
        system = """ТЫ - ОПЫТНЫЙ ПСИХОЛОГ-ДИАГНОСТ С МНОГОЛЕТНЕЙ ПРАКТИКОЙ.
        
        По результатам 10 вопросов определи ГЛАВНУЮ проблему человека.
        
        СТРУКТУРА ОТВЕТА:
        1. НАЗОВИ ТОП-1 ПРОБЛЕМУ (коротко и ясно) - что мешает жить прямо сейчас
        2. ДАЙ 1 МОЩНЫЙ ИНСАЙТ (прорывное наблюдение) - почему это происходит
        3. ЗАДАЙ 1 ВОПРОС ДЛЯ РАЗМЫШЛЕНИЯ (проникающий) - чтобы человек сам пришёл к решению
        4. ДАЙ 1 КОНКРЕТНЫЙ ШАГ (выполнимый сегодня) - что сделать прямо сейчас
        
        КРИТЕРИИ:
        - Говори прямо, честно, без воды и сахара
        - Будь полезным и практичным
        - Используй язык, который отзывается в душе
        - Никаких книг, упражнений и рекомендаций - только анализ и вопросы
        - Объём: 600-800 знаков"""
        
        user = f"""ТЕМА: {topic}
        ОТВЕТЫ: {answers}
        БАЛЛЫ: {score} из {total}
        
        Проведи диагностику и дай честный анализ."""
    
    else:
        system = """ТЫ - МЕЖДУНАРОДНАЯ КОМАНДА ЭКСПЕРТОВ:
        1. КЛИНИЧЕСКИЙ ПСИХОЛОГ (диагностика причин)
        2. ТРАНСФОРМАЦИОННЫЙ КОУЧ (стратегия и план)
        3. НЛП-МАСТЕР (техники изменения мышления)
        
        Сделай ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ на основе 20 вопросов.
        
        СТРУКТУРА ОТВЕТА:
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ (кто этот человек на самом деле, его суть)
        2. 2-3 ГЛУБИННЫХ ИНСАЙТА (что он не видел в себе, прорывные наблюдения)
        3. КОРЕНЬ ПРОБЛЕМЫ (откуда это взялось - детство, сценарии, травмы)
        4. ПЛАН НА НЕДЕЛЮ (3 конкретных шага с объяснением)
        
        КРИТЕРИИ:
        - Максимальная глубина и точность
        - Язык: честный, трансформирующий
        - Дай человеку увидеть себя по-новому
        - Никаких книг, упражнений, видео - только анализ
        - Объём: 1200+ знаков"""
        
        user = f"""ТЕМА: {topic}
        ОТВЕТЫ: {answers}
        БАЛЛЫ: {score} из {total}
        
        Проведи полный разбор личности."""
    
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
        "time": datetime.now().isoformat(),
        "uptime": "running"
    }

@app.route('/stats')
def stats_api():
    try:
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated, giga_requests, giga_errors FROM stats ORDER BY id DESC LIMIT 1")
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
                "images_generated": row[6] if row else 0,
                "giga_requests": row[7] if row else 0,
                "giga_errors": row[8] if row else 0
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Веб-сервер запущен (v{BOT_VERSION})")

# ============================================
# МЕНЮ (МЕГА-ВЕРСИЯ)
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
    mk.add('🎫 Создать промокод', '🔄 Перезапустить бота')
    mk.add('📋 Показать логи', '👑 Главное меню')
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

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        c.execute("""INSERT OR IGNORE INTO users 
                     (chat_id, username, first_name, last_name, registered_at, last_activity) 
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                  (chat_id, username, first_name, last_name))
        conn.commit()
        
        # Обновляем количество пользователей
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

Версия бота: {BOT_VERSION}"""
    
    bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = """💫 ЖИЗНЬ+ — канал о психологии и саморазвитии.

Без пафоса. Честно. Как живой человек.

Подпишись: https://t.me/zhizn_plus"""
    
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton(
        "📢 Перейти в канал",
        url="https://t.me/zhizn_plus"
    ))
    bot.send_message(message.chat.id, text, reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def choose_test_type(message):
    chat_id = message.chat.id
    update_user_activity(chat_id)
    
    bot.send_message(
        chat_id,
        "🎯 ВЫБЕРИ ТЕСТ:\n\n"
        "🧠 БЕСПЛАТНЫЙ — 10 вопросов (диагностика)\n"
        "💎 ПЛАТНЫЙ — 20 вопросов (полный разбор)",
        reply_markup=test_type_menu()
    )

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
    chat_id = message.chat.id
    update_user_activity(chat_id)
    
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    for topic, emoji in TEST_TOPICS.items():
        mk.add(telebot.types.InlineKeyboardButton(
            emoji,
            callback_data=f"{test_type}_{topic}_{count}"
        ))
    mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    bot.send_message(
        chat_id,
        f"🔮 ВЫБЕРИ ТЕМУ:\n\n{count} вопросов\n⏱ Время: ~{count // 2} минут",
        reply_markup=mk
    )

# ============================================
# ОБРАБОТЧИКИ КОЛБЭКОВ
# ============================================

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        chat_id = c.message.chat.id
        
        update_user_activity(chat_id)
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n\n"
            "Создаю уникальные вопросы специально для тебя.\n"
            "⏱ Это займет до 35 секунд.",
            chat_id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, count)
        
        if not questions:
            bot.send_message(
                chat_id,
                "❌ Не удалось создать тест.\n"
                "GigaChat не ответил. Попробуй через минуту."
            )
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
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")
    
    c.answer()

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    chat_id = c.message.chat.id
    bot.delete_message(chat_id, c.message.message_id)
    bot.send_message(
        chat_id,
        "❌ Отменено.",
        reply_markup=get_main_menu(chat_id)
    )
    c.answer()

# ============================================
# ФУНКЦИИ ТЕСТИРОВАНИЯ
# ============================================

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

📌 {s['topic'].title()}

{q['question']}

Выбери вариант ответа:"""
    
    bot.send_message(chat_id, message, reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    bot.send_message(
        chat_id,
        "⏹ Тест прерван.\nТы всегда можешь вернуться.",
        reply_markup=get_main_menu(chat_id)
    )

@bot.message_handler(func=lambda m: m.text and m.text[0] in 'ABCD')
def handle_answer(message):
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

def finish_test(chat_id):
    s = sessions.get(chat_id)
    if not s:
        return
    
    score = sum(s['scores'])
    total = len(s['questions']) * 3
    answers = ', '.join(s['answers'])
    is_paid = s.get('is_paid', False)
    
    # Обновляем статистику
    if is_paid:
        c.execute("UPDATE stats SET paid_count = paid_count + 1")
    else:
        c.execute("UPDATE stats SET free_count = free_count + 1")
    conn.commit()
    
    update_user_activity(chat_id)
    
    bot.send_message(
        chat_id,
        f"📊 ТЕСТ ЗАВЕРШЕН!\n\n"
        f"✅ Результат: {score} из {total}\n"
        f"⏳ Анализирую... До 35 секунд."
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
            "❌ GigaChat не ответил.\nПопробуй позже.",
            reply_markup=get_main_menu(chat_id)
        )
    
    if chat_id in sessions:
        del sessions[chat_id]

# ============================================
# АДМИН-ПАНЕЛЬ (МЕГА-ВЕРСИЯ)
# ============================================

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        return
    
    bot.send_message(
        chat_id,
        f"👑 АДМИН-ПАНЕЛЬ\n\n"
        f"Версия бота: {BOT_VERSION}\n"
        f"Управляй контентом и трансформацией.",
        reply_markup=admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
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
        bot.send_message(
            chat_id,
            "✅ ПОСТ ОТПРАВЛЕН В КАНАЛ!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка отправки: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def admin_post_with_image(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        return
    
    bot.send_message(
        chat_id,
        "📝 Генерация поста и картинки...\n⏱ До 60 секунд."
    )
    
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
        
        bot.send_message(
            chat_id,
            "✅ ПОСТ С КАРТИНКОЙ ОТПРАВЛЕН!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
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
    
    test_text = f"""🔮 ТЕСТ: «{topic.title()}»

Пройди тест прямо сейчас и узнай больше о себе!

🎯 {test_url}

#жизньплюс #тест #психология"""
    
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
        
        bot.send_message(
            chat_id,
            "✅ ТЕСТ С КАРТИНКОЙ ОТПРАВЛЕН!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        return
    
    try:
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated, giga_requests, giga_errors FROM stats ORDER BY id DESC LIMIT 1")
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
📚 Уникальных тем использовано: {used_topics}
📤 Запросов к GigaChat: {stats_row[7] if stats_row else 0}
❌ Ошибок GigaChat: {stats_row[8] if stats_row else 0}"""
        
        bot.send_message(chat_id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '📋 Показать логи')
def admin_show_logs(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        return
    
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-50:] if len(lines) > 50 else lines
                logs = ''.join(last_lines)
                
                if len(logs) > 4000:
                    logs = logs[-4000:]
                
                bot.send_message(chat_id, f"📋 ПОСЛЕДНИЕ 50 СТРОК ЛОГОВ:\n\n```\n{logs}\n```", parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "❌ Файл логов не найден")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        return
    
    bot.send_message(chat_id, "🎫 Введите код (латиница, 3+ символов):")
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
            f"✅ ПРОМОКОД СОЗДАН!\n\n📌 Код: `{code}`",
            reply_markup=admin_menu()
        )
    except sqlite3.IntegrityError:
        bot.send_message(chat_id, "❌ Такой код уже существует.", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Активировать промокод')
def activate_promo(message):
    chat_id = message.chat.id
    update_user_activity(chat_id)
    
    bot.send_message(
        chat_id,
        "🎫 Введите промокод:",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_promo)

def process_promo(message):
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
    
    bot.send_message(
        chat_id,
        "🎉 ПРОМОКОД АКТИВИРОВАН!\n\nТеперь доступен 💎 Платный тест!",
        reply_markup=get_main_menu(chat_id)
    )

@bot.message_handler(func=lambda m: m.text == '🔄 Перезапустить бота')
def restart_bot(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        return
    
    bot.send_message(
        chat_id,
        "🔄 ПЕРЕЗАПУСК БОТА...\n\n"
        "Удаляю вебхук и перезапускаю соединение."
    )
    
    super_kill_409()
    time.sleep(2)
    
    try:
        bot.stop_polling()
        time.sleep(2)
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=0, timeout=20)
        bot.send_message(
            chat_id,
            "✅ БОТ ПЕРЕЗАПУЩЕН!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(
            chat_id,
            f"❌ Ошибка: {e}",
            reply_markup=admin_menu()
        )

# ============================================
# ФУНКЦИЯ ОБРАБОТКИ СООБЩЕНИЙ (ВСЕ ОСТАЛЬНЫЕ)
# ============================================

@bot.message_handler(func=lambda m: True)
def handle_other_messages(message):
    chat_id = message.chat.id
    
    # Проверяем, не является ли это ответом на промокод
    if message.text and message.text.upper() != "ОТМЕНА":
        # Проверяем, есть ли активный процесс ввода промокода
        pass

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
    
    # Пятикратное уничтожение перед запуском
    for i in range(5):
        logger.info(f"🔄 Предстартовый проход #{i+1}/5")
        super_kill_409()
        time.sleep(2)
    
    logger.info("🚀 СТАРТ БОТА...")
    run_bot()
