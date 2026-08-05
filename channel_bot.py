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

# ============================================
# СУПЕР-УБИЙЦА 409 (25 СПОСОБОВ)
# ============================================

def super_kill_409():
    try:
        # 1-15: Многократное удаление вебхука
        for i in range(25):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            requests.post(url, json={"drop_pending_updates": True}, timeout=10)
            time.sleep(0.2)
        
        # 16: Сброс вебхука
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
        
        # 17: Через GET
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", params={"drop_pending_updates": "true"})
        
        # 18-22: Удаление всех файлов
        patterns = ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid', '*.offset', '*.cache', '*.tmp']
        for pattern in patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                except:
                    pass
        
        # 23: Очистка временной папки
        temp_files = glob.glob('/tmp/*.json') + glob.glob('/tmp/*.lock')
        for f in temp_files:
            try:
                os.remove(f)
            except:
                pass
        
        # 24: Проверка статуса
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=10)
        logger.info(f"Вебхук статус: {response.json()}")
        
        # 25: Еще один проход
        time.sleep(1)
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", json={"drop_pending_updates": True}, timeout=10)
        
        logger.info("🔥 409 УНИЧТОЖЕН НАВСЕГДА (25 способов)")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

# ТРОЙНОЕ УНИЧТОЖЕНИЕ
super_kill_409()
time.sleep(2)
super_kill_409()
time.sleep(2)
super_kill_409()
time.sleep(2)

# ============================================
# GIGACHAT (С ДЕТАЛЬНЫМ ЛОГИРОВАНИЕМ)
# ============================================

giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    logger.info("🔑 НАЧАЛО ПОЛУЧЕНИЯ ТОКЕНА")
    
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        logger.info("✅ Токен из кэша (ещё действителен)")
        return giga_token_cache["token"]
    
    for attempt in range(1, 6):
        try:
            logger.info(f"🔄 Попытка {attempt}/6 получить токен...")
            
            auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logger.info(f"📤 Отправка запроса на https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
            
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data='scope=GIGACHAT_API_PERS',
                timeout=30,
                verify=False
            )
            
            logger.info(f"📡 Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('access_token')
                if token:
                    giga_token_cache["token"] = token
                    giga_token_cache["expires"] = time.time() + 3500
                    logger.info("✅ ТОКЕН ПОЛУЧЕН УСПЕШНО!")
                    return token
                else:
                    logger.error("❌ Токен не найден в ответе")
            else:
                logger.error(f"❌ Ошибка HTTP {response.status_code}: {response.text[:200]}")
            
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Исключение при получении токена: {e}")
            time.sleep(2)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ТОКЕН ПОСЛЕ 6 ПОПЫТОК")
    return None

def ask_giga(system, user, max_tokens=5000):
    logger.info("="*80)
    logger.info("📤 НАЧАЛО ЗАПРОСА К GIGACHAT")
    logger.info(f"📝 Системный промпт: {system[:150]}...")
    logger.info(f"📝 Пользовательский запрос: {user[:150]}...")
    
    token = get_giga_token()
    if not token:
        logger.error("❌ НЕТ ТОКЕНА — ЗАПРОС ОТМЕНЁН")
        return None
    
    logger.info("🔑 Токен получен, формирую запрос...")
    
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
    
    logger.info(f"📦 Размер запроса: {len(json.dumps(payload))} байт")
    logger.info(f"🌐 URL: https://gigachat.devices.sberbank.ru/api/v1/chat/completions")
    
    for attempt in range(1, 4):
        try:
            logger.info(f"🔄 Попытка {attempt}/4 отправить запрос...")
            
            start_time = time.time()
            logger.info("⏳ Отправка...")
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=90,
                verify=False
            )
            
            elapsed = time.time() - start_time
            logger.info(f"⏱ Ответ получен за {elapsed:.2f} секунд")
            logger.info(f"📡 HTTP Статус: {response.status_code}")
            
            if elapsed < 35:
                wait_time = 35 - elapsed
                logger.info(f"⏳ Ожидание {wait_time:.2f} сек (гарантия 35 сек)")
                time.sleep(wait_time)
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                logger.info(f"📄 Длина ответа: {len(content)} символов")
                logger.info(f"📄 Первые 150 символов: {content[:150]}...")
                
                if content and len(content) > 50:
                    logger.info("✅ ЗАПРОС УСПЕШНО ВЫПОЛНЕН!")
                    return content
                else:
                    logger.error("❌ Ответ пустой или слишком короткий")
            else:
                logger.error(f"❌ ОШИБКА HTTP {response.status_code}")
                logger.error(f"📄 Текст ошибки: {response.text[:300]}")
            
            time.sleep(2)
        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ (90 секунд)")
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ ИСКЛЮЧЕНИЕ: {e}")
            time.sleep(2)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ОТВЕТ ПОСЛЕ 4 ПОПЫТОК")
    return None

# ============================================
# ГЕНЕРАЦИЯ КАРТИНОК (3 API + ПОВТОРНЫЕ ПОПЫТКИ)
# ============================================

def generate_image(prompt, width=1024, height=768):
    """Генерация картинки с несколькими API и повторными попытками"""
    
    clean_prompt = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "").replace(',', '%2C')
    full_prompt = f"{clean_prompt}, high quality, detailed, beautiful, professional, 4k, masterpiece"
    
    apis = [
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&nologo=true&seed={random.randint(1,999999)}",
        f"https://pollinations.ai/prompt/{full_prompt}?width={width}&height={height}",
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&model=flux"
    ]
    
    for attempt in range(3):
        for api_url in apis:
            try:
                logger.info(f"🖼 Генерация картинки (попытка {attempt+1}/3)...")
                response = requests.get(api_url, timeout=60)
                
                if response.status_code == 200 and len(response.content) > 1000:
                    filename = f"/tmp/image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    
                    file_size = os.path.getsize(filename)
                    logger.info(f"✅ Картинка создана: {filename} ({file_size} байт)")
                    return filename
                else:
                    logger.warning(f"⚠️ Ошибка API: {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Ошибка генерации: {e}")
                time.sleep(1)
        time.sleep(2)
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ КАРТИНКУ")
    return None

def generate_post_image(theme):
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational, peaceful, spiritual growth, masterpiece",
        f"beautiful landscape {theme}, sunrise, hope, positive energy, meditation, 4k",
        f"minimalist illustration {theme}, soft pastel, calm, self discovery, healing, art",
        f"surreal art {theme}, emotional depth, transformation, bright colors, wisdom, creative",
        f"philosophical illustration {theme}, deep thinking, clarity, dreamy atmosphere, professional"
    ]
    return generate_image(random.choice(prompts))

def generate_test_image(topic):
    prompts = [
        f"psychological test illustration {topic}, brain, mind, introspection, deep colors, spiritual, professional",
        f"abstract psychology art {topic}, meditation, self reflection, calm, serene, masterpiece",
        f"mental health awareness {topic}, healing, balance, harmony, soothing, 4k",
        f"mindfulness illustration {topic}, inner peace, growth, positive, wisdom, art"
    ]
    return generate_image(random.choice(prompts))

# ============================================
# БАЗА ДАННЫХ (РАСШИРЕННАЯ)
# ============================================

DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Таблица тестов
c.execute('''CREATE TABLE IF NOT EXISTS daily_tests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              topic TEXT, 
              questions TEXT, 
              created_at TEXT,
              is_paid INTEGER DEFAULT 0,
              image_path TEXT,
              views INTEGER DEFAULT 0)''')

# Таблица статистики
c.execute('''CREATE TABLE IF NOT EXISTS stats 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              free_count INTEGER DEFAULT 0, 
              paid_count INTEGER DEFAULT 0,
              promo_used INTEGER DEFAULT 0,
              users_count INTEGER DEFAULT 0,
              posts_count INTEGER DEFAULT 0,
              tests_created INTEGER DEFAULT 0,
              images_generated INTEGER DEFAULT 0,
              giga_requests INTEGER DEFAULT 0,
              giga_errors INTEGER DEFAULT 0)''')

c.execute("SELECT COUNT(*) FROM stats")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO stats (free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated, giga_requests, giga_errors) VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0)")

# Таблица сессий
c.execute('''CREATE TABLE IF NOT EXISTS user_sessions 
             (chat_id INTEGER PRIMARY KEY, 
              topic TEXT, 
              questions TEXT, 
              current_q INTEGER, 
              answers TEXT, 
              scores TEXT, 
              is_paid INTEGER, 
              result TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Таблица промокодов
c.execute('''CREATE TABLE IF NOT EXISTS promocodes 
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT UNIQUE,
              created_by INTEGER,
              created_at TEXT,
              used_by INTEGER DEFAULT 0,
              used_at TEXT)''')

# Таблица постов
c.execute('''CREATE TABLE IF NOT EXISTS posts_history
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              content TEXT,
              topic TEXT,
              image_path TEXT,
              views INTEGER DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Таблица пользователей
c.execute('''CREATE TABLE IF NOT EXISTS users
             (chat_id INTEGER PRIMARY KEY,
              username TEXT,
              first_name TEXT,
              last_name TEXT,
              registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              tests_passed INTEGER DEFAULT 0,
              last_activity TIMESTAMP)''')

# Таблица обратной связи
c.execute('''CREATE TABLE IF NOT EXISTS feedback
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id INTEGER,
              message TEXT,
              rating INTEGER DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# Таблица для хранения тем постов
c.execute('''CREATE TABLE IF NOT EXISTS used_topics
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              topic TEXT UNIQUE,
              used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

conn.commit()
logger.info("✅ База данных инициализирована (максимальная версия)")

# ============================================
# 300+ ТЕМ ДЛЯ ПОСТОВ (НИКОГДА НЕ ПОВТОРЯЮТСЯ)
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
    "как полюбить свои эмоции", "психология эмоциональной зрелости"
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

def get_unique_theme():
    """Получает уникальную тему для поста (без повторов)"""
    
    c.execute("SELECT topic FROM used_topics ORDER BY used_at DESC LIMIT 50")
    used = [row[0] for row in c.fetchall()]
    
    available = [t for t in POST_THEMES if t not in used]
    
    if available:
        theme = random.choice(available)
    else:
        c.execute("DELETE FROM used_topics")
        conn.commit()
        theme = random.choice(POST_THEMES)
    
    try:
        c.execute("INSERT INTO used_topics (topic) VALUES (?)", (theme,))
        conn.commit()
    except:
        pass
    
    return theme

# ============================================
# ГЕНЕРАТОР ПОСТА (800+ СИМВОЛОВ, ТОЛЬКО GIGACHAT)
# ============================================

def generate_post():
    """Генерация поста длиной 800+ символов только через GigaChat"""
    
    logger.info("="*80)
    logger.info("📝 ГЕНЕРАЦИЯ ПОСТА")
    
    theme = get_unique_theme()
    logger.info(f"📌 Тема: {theme}")
    
    system = """ТЫ - АВТОР КАНАЛА О ПСИХОЛОГИИ И САМОРАЗВИТИИ.
    
    ТВОЙ СТИЛЬ:
    - Глубокий, мудрый, трансформирующий
    - Используешь НЛП-язык: предикаты, якоря, метамодель
    - Каждый пост - мини-сеанс терапии
    - Энергия текста заряжает и мотивирует
    - Пишешь как живой человек, без пафоса
    - Используешь метафоры и истории
    - Затрагиваешь душу и сознание
    
    СТРУКТУРА ПОСТА:
    1. ЗАХВАТЫВАЮЩИЙ ЗАГОЛОВОК (с эмодзи) - 50-100 символов
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ - затронь струны души читателя
    3. ОСНОВНАЯ ЧАСТЬ - раскрой тему, дай инсайты и открытия
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ - конкретное, выполнимое сегодня
    5. ВОПРОС К ЧИТАТЕЛЮ - провокационный, пробуждающий
    6. МОТИВИРУЮЩИЙ ФИНАЛ - крылья и энергия
    7. ХЕШТЕГИ
    
    ТРЕБОВАНИЯ:
    - МИНИМУМ 800 СИМВОЛОВ
    - Максимум 1200 символов
    - Пиши от первого лица
    - Будь честным и уязвимым
    - НЕ используй шаблонные фразы
    - НЕ давай готовых решений - только вопросы и инсайты
    """
    
    user = f"""Напиши глубокий, трансформирующий пост на тему: "{theme}"
    
    Сделай этот пост откровением для каждого читателя.
    Пост должен быть длинным (800+ символов) и содержательным.
    Используй свой 25-летний опыт работы с людьми.
    
    Время писать ШЕДЕВР!"""
    
    response = ask_giga(system, user, 5000)
    
    if response and len(response) >= 800:
        logger.info(f"✅ Пост создан ({len(response)} символов)")
        return response, theme
    
    if response and len(response) >= 600:
        logger.warning(f"⚠️ Пост короткий ({len(response)} символов), пробуем еще раз...")
        response2 = ask_giga(
            system + "\n\nВАЖНО: НАПИШИ МИНИМУМ 800 СИМВОЛОВ! РАСКРОЙ ТЕМУ ГЛУБЖЕ! ДОБАВЬ БОЛЬШЕ СОДЕРЖАНИЯ!",
            user,
            5000
        )
        if response2 and len(response2) >= 800:
            return response2, theme
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ ПОСТ (800+ символов)")
    return None, theme

# ============================================
# ГЕНЕРАТОР ТЕСТА (ТОЛЬКО GIGACHAT)
# ============================================

def generate_test_questions(topic, count=10):
    """Генерация теста только через GigaChat"""
    
    logger.info("="*80)
    logger.info(f"🧠 ГЕНЕРАЦИЯ ТЕСТА: {topic}, {count} вопросов")
    
    if count == 10:
        system = """ТЫ - ЭКСПЕРТ ПО ПСИХОЛОГИИ.
        
        Создай СКРИНИНГОВЫЙ тест из 10 вопросов для диагностики личности.
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
        
        user = f"""Тема для теста: "{topic}"
        Составь 10 вопросов для быстрой диагностики.
        Верни ТОЛЬКО JSON массив."""
    
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
        
        user = f"""Тема для теста: "{topic}"
        Составь 20 глубоких вопросов для полного разбора.
        Верни ТОЛЬКО JSON массив."""
    
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
        logger.error(f"📄 Текст: {response[:300]}")
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
        logger.error(f"📄 Строка: {json_str[:200]}")
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА (ТОЛЬКО GIGACHAT)
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    """Генерация анализа только через GigaChat"""
    
    logger.info("="*80)
    logger.info(f"📊 ГЕНЕРАЦИЯ АНАЛИЗА")
    
    if not is_paid:
        system = """ТЫ - ОПЫТНЫЙ ПСИХОЛОГ-ДИАГНОСТ.
        
        По результатам теста определи ГЛАВНУЮ проблему человека.
        
        СТРУКТУРА:
        1. Назови ТОП-1 проблему
        2. Дай 1 МОЩНЫЙ ИНСАЙТ
        3. Задай 1 ВОПРОС для размышления
        4. Дай 1 КОНКРЕТНЫЙ ШАГ
        
        БЕЗ КНИГ. БЕЗ УПРАЖНЕНИЙ. БЕЗ РЕКОМЕНДАЦИЙ.
        Говори прямо, честно, без воды.
        Объем: 600-800 знаков."""
        
        user = f"""ТЕМА: {topic}
ОТВЕТЫ: {answers}
БАЛЛЫ: {score} из {total}
Сделай честный анализ."""
    
    else:
        system = """ТЫ - МЕЖДУНАРОДНАЯ КОМАНДА ЭКСПЕРТОВ:
        1. КЛИНИЧЕСКИЙ ПСИХОЛОГ
        2. МЕЖДУНАРОДНЫЙ КОУЧ
        3. НЛП-ТЕРАПЕВТ
        
        Сделай ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ.
        
        СТРУКТУРА:
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
        2. 2-3 ГЛУБИННЫХ ИНСАЙТА
        3. КОРЕНЬ ПРОБЛЕМЫ (откуда взялось)
        4. ПЛАН НА НЕДЕЛЮ (3 шага)
        
        БЕЗ КНИГ. БЕЗ УПРАЖНЕНИЙ. БЕЗ ВИДЕО.
        Объем: 1500+ знаков."""
        
        user = f"""ТЕМА: {topic}
ОТВЕТЫ: {answers}
БАЛЛЫ: {score} из {total}
Сделай глубокий анализ."""
    
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
# ВЕБ-СЕРВЕР
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ БОТ ЖИЗНЬ+ РАБОТАЕТ!"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info("✅ Веб-сервер запущен")

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
    mk.add('📤 Отправить пост', '🖼 Пост с картинкой')
    mk.add('🧠 Тест в канал', '📊 Статистика')
    mk.add('🎫 Создать промокод', '🔄 Перезапустить бота')
    mk.add('👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

# ============================================
# СЕССИИ
# ============================================

sessions = {}

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        c.execute("INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                  (chat_id, username, first_name, last_name))
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
    
    welcome = """🌟 ДОБРО ПОЖАЛОВАТЬ В ПРОСТРАНСТВО ТРАНСФОРМАЦИИ!

Я — бот канала Жизнь+.

Здесь ты можешь:
• 🎯 Пройти психологический тест
• 🔍 Получить честный анализ
• 📖 Читать посты о саморазвитии

Нажми «🎯 Пройти тест» или «🎫 Активировать промокод»."""
    
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
    bot.send_message(
        message.chat.id,
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
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    for topic, emoji in TEST_TOPICS.items():
        mk.add(telebot.types.InlineKeyboardButton(
            emoji,
            callback_data=f"{test_type}_{topic}_{count}"
        ))
    mk.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    bot.send_message(
        message.chat.id,
        f"🔮 ВЫБЕРИ ТЕМУ:\n\n{count} вопросов\n⏱ Время: ~{count // 2} минут",
        reply_markup=mk
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n\n"
            "Создаю уникальные вопросы специально для тебя.\n"
            "⏱ Это займет до 35 секунд.",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, count)
        
        if not questions:
            bot.send_message(
                c.message.chat.id,
                "❌ Не удалось создать тест.\n"
                "Попробуй еще раз через минуту."
            )
            return
        
        chat_id = c.message.chat.id
        
        sessions[chat_id] = {
            'topic': topic,
            'questions': questions,
            'answers': [],
            'q': 0,
            'scores': [],
            'is_paid': is_paid
        }
        
        bot.delete_message(c.message.chat.id, c.message.message_id)
        send_question(chat_id)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")
    
    c.answer()

@bot.callback_query_handler(func=lambda c: c.data == 'cancel')
def cancel_callback(c):
    bot.delete_message(c.message.chat.id, c.message.message_id)
    bot.send_message(
        c.message.chat.id,
        "❌ Отменено.",
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
    
    send_question(chat_id)

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
# АДМИН-ПАНЕЛЬ (МАКСИМАЛЬНАЯ)
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
    
    logger.info("="*80)
    logger.info("👑 АДМИН: ЗАПРОС НА СОЗДАНИЕ ПОСТА")
    
    bot.send_message(message.chat.id, "📝 Генерация поста...\n⏱ До 35 секунд.")
    
    post, theme = generate_post()
    
    if not post:
        bot.send_message(message.chat.id, "❌ GigaChat не ответил. Проверь логи.", reply_markup=admin_menu())
        return
    
    try:
        c.execute("INSERT INTO posts_history (content, topic) VALUES (?, ?)", (post, theme))
        conn.commit()
        c.execute("UPDATE stats SET posts_count = posts_count + 1")
        conn.commit()
    except:
        pass
    
    try:
        bot.send_message(CHANNEL_ID, post)
        bot.send_message(
            message.chat.id,
            "✅ ПОСТ ОТПРАВЛЕН В КАНАЛ!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def admin_post_with_image(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "📝 Генерация поста и картинки...\n⏱ До 60 секунд."
    )
    
    post, theme = generate_post()
    
    if not post:
        bot.send_message(message.chat.id, "❌ GigaChat не ответил. Проверь логи.", reply_markup=admin_menu())
        return
    
    bot.send_message(message.chat.id, "🖼 Создание картинки...")
    image_path = generate_post_image(theme)
    
    try:
        c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", 
                  (post, theme, image_path if image_path else ""))
        conn.commit()
        c.execute("UPDATE stats SET posts_count = posts_count + 1")
        if image_path:
            c.execute("UPDATE stats SET images_generated = images_generated + 1")
        conn.commit()
    except:
        pass
    
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
            message.chat.id,
            "✅ ПОСТ С КАРТИНКОЙ ОТПРАВЛЕН!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🧠 Генерация теста для канала...\n⏱ До 35 секунд.")
    
    topic = random.choice(list(TEST_TOPICS.keys()))
    questions = generate_test_questions(topic, 10)
    
    if not questions:
        bot.send_message(message.chat.id, "❌ GigaChat не ответил. Проверь логи.", reply_markup=admin_menu())
        return
    
    bot.send_message(message.chat.id, "🖼 Создание картинки для теста...")
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
    except:
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
            message.chat.id,
            "✅ ТЕСТ С КАРТИНКОЙ ОТПРАВЛЕН!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    try:
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count, tests_created, images_generated, giga_requests, giga_errors FROM stats")
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
        
        bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🎫 Создать промокод')
def create_promo(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🎫 Введите код (латиница, 3+ символов):")
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
    bot.send_message(
        message.chat.id,
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
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
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
            message.chat.id,
            "✅ БОТ ПЕРЕЗАПУЩЕН!",
            reply_markup=admin_menu()
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {e}",
            reply_markup=admin_menu()
        )

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info("🤖 ЗАПУСК ТРАНСФОРМАЦИОННОГО БОТА...")
    
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
    super_kill_409()
    time.sleep(2)
    super_kill_409()
    time.sleep(2)
    super_kill_409()
    time.sleep(2)
    logger.info("🚀 СТАРТ...")
    run_bot()
