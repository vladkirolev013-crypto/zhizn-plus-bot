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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================
# СУПЕР-УБИЙЦА 409 (10+ способов)
# ============================================

def super_kill_409():
    try:
        # 1. Удаляем вебхук 15 раз
        for i in range(15):
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
            requests.post(url, json={"drop_pending_updates": True}, timeout=10)
            time.sleep(0.3)
        
        # 2. Сбрасываем вебхук
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
        
        # 3. Через GET
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", params={"drop_pending_updates": "true"})
        
        # 4. Удаляем все файлы
        for pattern in ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid', '*.offset']:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                except:
                    pass
        
        # 5. Проверяем статус
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=10)
        logger.info(f"Вебхук: {response.json()}")
        
        logger.info("🔥 409 УНИЧТОЖЕН")
        return True
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

# Тройное уничтожение
super_kill_409()
time.sleep(2)
super_kill_409()
time.sleep(2)
super_kill_409()
time.sleep(2)

# ============================================
# GIGACHAT (МАКСИМАЛЬНОЕ ОЖИДАНИЕ)
# ============================================

giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
    for attempt in range(5):
        try:
            auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logger.info(f"🔄 Попытка {attempt+1}/5 получения токена...")
            
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data='scope=GIGACHAT_API_PERS',
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('access_token')
                if token:
                    giga_token_cache["token"] = token
                    giga_token_cache["expires"] = time.time() + 3500
                    logger.info("✅ Токен получен")
                    return token
            else:
                logger.error(f"❌ Ошибка: {response.status_code} - {response.text[:200]}")
            
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            time.sleep(2)
    
    return None

def ask_giga(system, user, max_tokens=4000):
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
    
    for attempt in range(3):
        try:
            start_time = time.time()
            logger.info(f"📤 Запрос к GigaChat...")
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=90,
                verify=False
            )
            
            elapsed = time.time() - start_time
            logger.info(f"⏱ Ответ за {elapsed:.1f} сек")
            
            # ГАРАНТИРОВАННОЕ ОЖИДАНИЕ 35 СЕКУНД
            if elapsed < 35:
                wait_time = 35 - elapsed
                logger.info(f"⏳ Ожидание {wait_time:.1f} сек (гарантия генерации)")
                time.sleep(wait_time)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                logger.info(f"✅ Ответ получен ({len(content)} символов)")
                return content
            else:
                logger.error(f"❌ Ошибка: {response.status_code} - {response.text[:300]}")
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            time.sleep(2)
    
    return None

# ============================================
# ГЕНЕРАЦИЯ КАРТИНОК (С ЗАПАСНЫМ API)
# ============================================

def generate_image(prompt, width=1024, height=768):
    """Генерация картинки с повторными попытками"""
    
    # Очищаем промпт
    clean_prompt = prompt[:200].replace(' ', '%20').replace('"', '').replace("'", "")
    full_prompt = f"{clean_prompt}, high quality, detailed, beautiful, professional, 4k"
    
    # Список API для генерации (если один не работает - используем другой)
    apis = [
        f"https://image.pollinations.ai/prompt/{full_prompt}?width={width}&height={height}&nologo=true&seed={random.randint(1,999999)}",
        f"https://pollinations.ai/prompt/{full_prompt}?width={width}&height={height}",
    ]
    
    for api_url in apis:
        try:
            logger.info(f"🖼 Попытка генерации картинки...")
            response = requests.get(api_url, timeout=60)
            
            if response.status_code == 200 and len(response.content) > 1000:
                filename = f"/tmp/image_{int(time.time())}_{random.randint(1000,999999)}.jpg"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                
                file_size = os.path.getsize(filename)
                logger.info(f"✅ Картинка создана: {filename} ({file_size} байт)")
                return filename
            else:
                logger.warning(f"⚠️ Ошибка: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            time.sleep(1)
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ КАРТИНКУ")
    return None

def generate_post_image(theme):
    prompts = [
        f"inspiring abstract art {theme}, warm colors, motivational, peaceful, spiritual growth",
        f"beautiful landscape {theme}, sunrise, hope, positive energy, meditation",
        f"minimalist illustration {theme}, soft pastel, calm, self discovery, healing",
        f"surreal art {theme}, emotional depth, transformation, bright colors, wisdom",
        f"philosophical illustration {theme}, deep thinking, clarity, dreamy atmosphere"
    ]
    return generate_image(random.choice(prompts))

def generate_test_image(topic):
    prompts = [
        f"psychological test illustration {topic}, brain, mind, introspection, deep colors, spiritual",
        f"abstract psychology art {topic}, meditation, self reflection, calm, serene",
        f"mental health awareness {topic}, healing, balance, harmony, soothing",
        f"mindfulness illustration {topic}, inner peace, growth, positive, wisdom"
    ]
    return generate_image(random.choice(prompts))

# ============================================
# БАЗА ДАННЫХ (РАСШИРЕННАЯ)
# ============================================

DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS daily_tests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              topic TEXT, 
              questions TEXT, 
              created_at TEXT,
              is_paid INTEGER DEFAULT 0,
              image_path TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS stats 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              free_count INTEGER DEFAULT 0, 
              paid_count INTEGER DEFAULT 0,
              promo_used INTEGER DEFAULT 0,
              users_count INTEGER DEFAULT 0,
              posts_count INTEGER DEFAULT 0)''')

c.execute("SELECT COUNT(*) FROM stats")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO stats (free_count, paid_count, promo_used, users_count, posts_count) VALUES (0, 0, 0, 0, 0)")

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
              image_path TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS users
             (chat_id INTEGER PRIMARY KEY,
              username TEXT,
              first_name TEXT,
              last_name TEXT,
              registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              tests_passed INTEGER DEFAULT 0)''')

conn.commit()
logger.info("✅ База данных инициализирована")

# ============================================
# 200+ ТЕМ ДЛЯ ПОСТОВ
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
    "как выйти из созависимости", "искусство принимать",
    "как полюбить свою работу", "сила дыхания",
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
    "как перестать быть удобным", "сила рода и предков",
    "как выстроить здоровую самооценку", "психология отношений",
    "как перестать обесценивать достижения", "искусство радоваться жизни",
    "как найти силу в слабости", "сила намерения",
    "как пережить развод", "искусство быть в потоке денег",
    "как полюбить несовершенства", "сила благословения",
    "как выстроить отношения с собой", "психология счастья",
    "как перестать бояться осуждения", "искусство быть честным",
    "как найти миссию", "сила дисциплины",
    "как исцелить травмы прошлого", "искусство быть в гармонии с миром",
    "как перестать искать виноватых", "сила прощения",
    "как выстроить здоровые отношения с деньгами", "психология самореализации",
    "как перестать играть роли", "искусство быть подлинным",
    "как найти внутреннюю опору", "сила каждого нового дня",
    "как пережить эмоциональное выгорание", "искусство быть с душой",
    "как выстроить отношения мечты", "сила благодарности",
    "как перестать жить чужими ожиданиями", "искусство быть свободным",
    "как найти радость в процессе", "сила принятия себя",
    "как исцелить отношения с деньгами", "психология достатка",
    "как выйти из кризиса", "искусство быть в моменте",
    "как найти силы для перемен", "сила благодарности к себе",
    "как перестать искать идеалы", "искусство быть реалистом",
    "как полюбить одиночество", "сила природы",
    "как выстроить здоровые привычки", "психология мотивации",
    "как перестать откладывать жизнь", "искусство быть в действии",
    "как найти баланс", "сила женской мудрости",
    "как исцелить детские травмы", "искусство быть мужчиной",
    "как перестать бояться будущего", "сила настоящего момента"
]

# ============================================
# ТЕМЫ ТЕСТОВ
# ============================================

TEST_TOPICS = {
    "психология": "🧠 Глубинная психология",
    "отношения": "💕 Отношения",
    "карьера": "💼 Карьера",
    "здоровье": "💪 Здоровье",
    "финансы": "💰 Финансы",
    "личность": "🌟 Личность",
    "самооценка": "⚡️ Самооценка",
    "эмоции": "🔥 Эмоции"
}

# ============================================
# ГЕНЕРАТОР ПОСТА (800+ СИМВОЛОВ)
# ============================================

def generate_post():
    """Генерация поста длиной 800+ символов"""
    
    theme = random.choice(POST_THEMES)
    
    system = """ТЫ - АВТОР КАНАЛА О ПСИХОЛОГИИ И САМОРАЗВИТИИ.
    
    ПИШИ ДЛИННЫЕ, ГЛУБОКИЕ ПОСТЫ - МИНИМУМ 800 СИМВОЛОВ.
    
    СТРУКТУРА:
    1. ЗАГОЛОВОК (с эмодзи)
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ - затронь душу читателя
    3. ОСНОВНАЯ ЧАСТЬ - раскрой тему, дай инсайты
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ - что можно сделать прямо сейчас
    5. ВОПРОС К ЧИТАТЕЛЮ - чтобы задумался
    6. МОТИВИРУЮЩИЙ ФИНАЛ - заряди энергией
    7. ХЕШТЕГИ
    
    ВАЖНО:
    - МИНИМУМ 800 СИМВОЛОВ
    - Пиши как живой человек
    - Без воды, но содержательно
    - Не давай готовых решений - только вопросы и инсайты
    """
    
    user = f"""Напиши пост на тему: "{theme}"
    
    Сделай его глубоким, длинным (800+ символов) и трансформирующим.
    Используй метафоры и истории из жизни.
    
    Время писать шедевр!"""
    
    response = ask_giga(system, user, 4000)
    
    # Если пост короткий - пробуем еще раз
    if response and len(response) < 700:
        logger.warning(f"⚠️ Пост короткий ({len(response)} символов), генерирую снова...")
        response = ask_giga(
            system + " ТРЕБОВАНИЕ: НАПИШИ МИНИМУМ 800 СИМВОЛОВ! РАСКРОЙ ТЕМУ ГЛУБЖЕ!",
            user,
            4000
        )
    
    if response and len(response) > 600:
        return response, theme
    
    # Резервные длинные посты
    fallbacks = [
        f"""🌟 {theme.title()}

Задумайся на минутку. Что для тебя сейчас самое важное в этой теме?

Я знаю, что ответ уже есть внутри тебя. Просто прислушайся. Часто мы ищем ответы снаружи, забывая, что вся мудрость уже заключена в нас самих. 

Мы привыкли жить в шуме мыслей, в бесконечном потоке дел и обязательств. Мы бежим, чтобы успеть, чтобы соответствовать, чтобы не отстать. А потом останавливаемся и понимаем: мы не знаем, куда бежим.

Тишина внутри — это не пустота. Это пространство для истины. Это место, где рождаются ответы.

Что бы ты услышал, если бы остановился? Что бы сказал тебе твой внутренний голос, если бы ты дал ему слово?

Сегодня я предлагаю тебе простую практику. Остановись на минуту. Закрой глаза. Сделай три глубоких вдоха. И спроси себя: что я чувствую на самом деле?

Не анализируй. Не оценивай. Просто почувствуй.

Я знаю, что это сложно. Мы привыкли быть в движении. Но именно в остановке рождается ясность.

Какой вопрос ты давно боишься себе задать?

#жизньплюс #саморазвитие #внутренниймир #осознанность #тишина""",
        
        f"""💫 {theme.title()}

Иногда лучший ответ — это правильный вопрос.

Я заметил, что мы слишком часто ищем готовые решения. Мы хотим, чтобы кто-то сказал нам, как жить, что делать, куда идти. Но правда в том, что никто не знает твоего пути лучше тебя.

Ты уже держишь ответ в руках. Просто ты привык смотреть на него, не замечая.

Посмотри на свою жизнь. На то, что тебя радует и что огорчает. На то, что приносит энергию и что её забирает. На то, что ты выбираешь и что выбирает тебя.

Задай себе один вопрос: почему я все еще здесь? Почему я не там, где хочу быть?

Возможно, ответ удивит тебя. Возможно, он окажется проще, чем ты думал. Возможно, тебе нужно разрешить себе быть счастливым прямо сейчас, без условий.

Сегодня я хочу, чтобы ты задал себе этот вопрос. Не завтра. Не когда будет время. А прямо сейчас.

Твоя жизнь — это не репетиция. Это главный спектакль. И ты в нем главный герой.

Какой выбор ты сделаешь сегодня?

#жизньплюс #осознанность #саморазвитие #выбор #путьксебе"""
    ]
    
    return random.choice(fallbacks), theme

# ============================================
# ГЕНЕРАТОР ТЕСТА (ПРОВЕРЕННЫЙ)
# ============================================

def generate_test_questions(topic, count=10):
    """Генерация теста с несколькими попытками"""
    
    if count == 10:
        system = """ТЫ - ПСИХОЛОГ-ДИАГНОСТ.
        
        Составь 10 вопросов для диагностики личности.
        Верни ТОЛЬКО JSON массив.
        
        ФОРМАТ (точно как в примере):
        [
            {"question": "текст вопроса?", "options": {"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"}}
        ]
        
        НЕ ДОБАВЛЯЙ НИЧЕГО КРОМЕ JSON.
        НЕ ИСПОЛЬЗУЙ КАВЫЧКИ ВНУТРИ ТЕКСТА.
        """
        
        user = f"""Тема: {topic}
        Составь 10 вопросов для диагностики.
        Верни ТОЛЬКО JSON массив."""
    
    else:
        system = """ТЫ - КЛИНИЧЕСКИЙ ПСИХОЛОГ.
        
        Составь 20 глубоких вопросов для разбора личности.
        Верни ТОЛЬКО JSON массив.
        
        ФОРМАТ (точно как в примере):
        [
            {"question": "текст вопроса?", "options": {"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"}}
        ]
        
        НЕ ДОБАВЛЯЙ НИЧЕГО КРОМЕ JSON.
        """
        
        user = f"""Тема: {topic}
        Составь 20 вопросов.
        Верни ТОЛЬКО JSON массив."""
    
    # Пробуем 3 раза
    for attempt in range(3):
        response = ask_giga(system, user, 4000)
        
        if not response:
            logger.error(f"❌ Попытка {attempt+1}: GigaChat не ответил")
            time.sleep(2)
            continue
        
        response = response.strip()
        logger.info(f"📥 Ответ GigaChat ({len(response)} символов)")
        
        # Ищем JSON
        start = response.find('[')
        end = response.rfind(']') + 1
        
        if start == -1 or end == -1:
            logger.error(f"❌ Попытка {attempt+1}: JSON не найден")
            logger.error(f"📄 Текст: {response[:300]}")
            time.sleep(2)
            continue
        
        json_str = response[start:end]
        
        try:
            questions = json.loads(json_str)
            
            if not questions or len(questions) == 0:
                logger.error(f"❌ Попытка {attempt+1}: Пустой массив")
                continue
            
            # Добавляем баллы
            for q in questions:
                if 'scores' not in q:
                    q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
                if 'options' not in q:
                    q['options'] = {'A': 'Да', 'B': 'Скорее да', 'C': 'Скорее нет', 'D': 'Нет'}
            
            logger.info(f"✅ Тест создан: {len(questions)} вопросов")
            return questions[:count]
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Попытка {attempt+1}: Ошибка JSON - {e}")
            logger.error(f"📄 Строка: {json_str[:200]}")
            time.sleep(2)
            continue
    
    logger.error("❌ НЕ УДАЛОСЬ СОЗДАТЬ ТЕСТ ПОСЛЕ 3 ПОПЫТОК")
    
    # Резервный тест
    return [
        {"question": f"Как ты оцениваешь свой уровень {topic}?", "options": {"A": "Высокий", "B": "Средний", "C": "Низкий", "D": "Не знаю"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
        {"question": f"Что тебе мешает в {topic}?", "options": {"A": "Страх", "B": "Лень", "C": "Неуверенность", "D": "Все вместе"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
    ] * 5

# ============================================
# ГЕНЕРАТОР АНАЛИЗА
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    if not is_paid:
        system = """Ты - психолог-диагност.
        
        Дай краткий анализ по результатам теста.
        
        СТРУКТУРА:
        1. Главная проблема
        2. 1 инсайт
        3. 1 вопрос для размышления
        4. 1 конкретный шаг
        
        БЕЗ КНИГ. БЕЗ УПРАЖНЕНИЙ.
        """
        
        user = f"""ТЕМА: {topic}
ОТВЕТЫ: {answers}
БАЛЛЫ: {score} из {total}
Сделай честный анализ."""
    
    else:
        system = """Ты - клинический психолог и коуч.
        
        Сделай полный разбор личности.
        
        СТРУКТУРА:
        1. Психологический портрет
        2. 2-3 глубоких инсайта
        3. Корень проблемы
        4. План на неделю
        
        БЕЗ КНИГ. БЕЗ УПРАЖНЕНИЙ.
        """
        
        user = f"""ТЕМА: {topic}
ОТВЕТЫ: {answers}
БАЛЛЫ: {score} из {total}
Сделай глубокий анализ."""
    
    response = ask_giga(system, user, 4000 if is_paid else 2500)
    
    if response:
        return response
    
    # Резервный анализ
    if is_paid:
        return f"""🔮 ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ

📊 Результат: {score} из {total}

🧠 ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
Вы человек с богатым внутренним миром. Вы чувствуете глубже, чем показываете.

💡 ИНСАЙТЫ
1. Ваша главная сила - способность к рефлексии
2. Вы слишком самокритичны

🎯 ПЛАН НА НЕДЕЛЮ
1. Записывайте 3 достижения в день
2. Учитесь принимать комплименты
3. Делайте то, что давно откладывали"""
    else:
        return f"""🔍 ДИАГНОСТИКА

📊 Результат: {score} из {total}

🎯 ГЛАВНАЯ ПРОБЛЕМА
Вы склонны сомневаться в себе и своих силах.

💡 ИНСАЙТ
Ваши сомнения - это не правда, а привычка.

❓ ВОПРОС
Что вы сделали бы, если бы знали, что у вас все получится?

✅ ШАГ
Сегодня сделайте одно маленькое дело, которое откладывали."""

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

sessions = {}

# ============================================
# ОБРАБОТЧИКИ
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user = message.from_user
    
    try:
        c.execute("INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                  (chat_id, user.username, user.first_name, user.last_name))
        conn.commit()
    except:
        pass
    
    welcome = """🌟 ДОБРО ПОЖАЛОВАТЬ!

Я - бот канала Жизнь+.

Здесь ты можешь:
• 🎯 Пройти психологический тест
• 🔍 Получить анализ
• 📖 Читать посты

Нажми «🎯 Пройти тест» или «🎫 Активировать промокод»."""
    
    bot.send_message(chat_id, welcome, reply_markup=get_main_menu(chat_id))

@bot.message_handler(func=lambda m: m.text == '🚀 Старт')
def start_button(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '❤️ О канале')
def about_channel(message):
    text = """💫 ЖИЗНЬ+ - канал о психологии и саморазвитии.

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
        "🧠 БЕСПЛАТНЫЙ - 10 вопросов\n"
        "💎 ПЛАТНЫЙ - 20 вопросов",
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
        f"🔮 ВЫБЕРИ ТЕМУ:\n\n{count} вопросов",
        reply_markup=mk
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n⏱ До 30 секунд",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, count)
        
        if not questions:
            bot.send_message(
                c.message.chat.id,
                "❌ Не удалось создать тест. Попробуй позже."
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

📌 {s['topic'].title()}

{q['question']}"""
    
    bot.send_message(chat_id, message, reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == '⏹ Прервать тест')
def stop_test(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    bot.send_message(chat_id, "⏹ Тест прерван", reply_markup=get_main_menu(chat_id))

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
        f"⏳ Анализирую..."
    )
    
    analysis = generate_analysis(s['topic'], answers, score, len(s['questions']), is_paid)
    
    if analysis:
        if is_paid:
            result = f"🔮 ГЛУБИННЫЙ АНАЛИЗ\n\n{analysis}"
        else:
            result = f"🔍 ДИАГНОСТИКА\n\n{analysis}"
        
        bot.send_message(chat_id, result, reply_markup=get_main_menu(chat_id))
    else:
        bot.send_message(
            chat_id,
            "❌ Не удалось сгенерировать анализ.",
            reply_markup=get_main_menu(chat_id)
        )
    
    if chat_id in sessions:
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
        "👑 АДМИН-ПАНЕЛЬ",
        reply_markup=admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == '👑 Главное меню')
def back_to_main_from_admin(message):
    start(message)

@bot.message_handler(func=lambda m: m.text == '📤 Отправить пост')
def admin_post(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "📝 Генерация поста...\n⏱ До 30 секунд")
    
    post, theme = generate_post()
    
    if not post:
        bot.send_message(message.chat.id, "❌ Ошибка")
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
        bot.send_message(message.chat.id, "✅ ПОСТ ОТПРАВЛЕН!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🖼 Пост с картинкой')
def admin_post_with_image(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "📝 Генерация поста и картинки...\n⏱ До 60 секунд"
    )
    
    post, theme = generate_post()
    
    if not post:
        bot.send_message(message.chat.id, "❌ Не удалось создать пост")
        return
    
    bot.send_message(message.chat.id, "🖼 Создание картинки...")
    image_path = generate_post_image(theme)
    
    try:
        c.execute("INSERT INTO posts_history (content, topic, image_path) VALUES (?, ?, ?)", 
                  (post, theme, image_path if image_path else ""))
        conn.commit()
        c.execute("UPDATE stats SET posts_count = posts_count + 1")
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
            bot.send_message(message.chat.id, "✅ ПОСТ С КАРТИНКОЙ ОТПРАВЛЕН!", reply_markup=admin_menu())
        else:
            bot.send_message(CHANNEL_ID, post)
            bot.send_message(message.chat.id, "✅ ПОСТ ОТПРАВЛЕН (без картинки)", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🧠 Тест в канал')
def admin_test_to_channel(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🧠 Генерация теста для канала...")
    
    topic = random.choice(list(TEST_TOPICS.keys()))
    questions = generate_test_questions(topic, 10)
    
    if not questions:
        bot.send_message(message.chat.id, "❌ Ошибка")
        return
    
    image_path = generate_test_image(topic)
    
    try:
        c.execute("INSERT INTO daily_tests (topic, questions, created_at, is_paid, image_path) VALUES (?, ?, ?, ?, ?)",
                  (topic, json.dumps(questions), datetime.now().isoformat(), 0, image_path if image_path else ""))
        conn.commit()
        test_id = c.lastrowid
    except:
        test_id = int(time.time())
    
    bot_info = bot.get_me()
    test_url = f"https://t.me/{bot_info.username}?start=daily_{topic}_{test_id}"
    
    test_text = f"""🔮 ТЕСТ: «{topic.title()}»

Пройди тест прямо сейчас!

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
        
        bot.send_message(message.chat.id, "✅ ТЕСТ ОТПРАВЛЕН!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '📊 Статистика')
def admin_stats(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    try:
        c.execute("SELECT free_count, paid_count, promo_used, users_count, posts_count FROM stats")
        stats_row = c.fetchone()
        
        c.execute("SELECT COUNT(*) FROM daily_tests")
        tests_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM posts_history")
        posts_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        stats_text = f"""📊 СТАТИСТИКА

👥 Пользователей: {users_count}
📝 Тестов: {tests_count}
📤 Постов: {posts_count}
🧠 Бесплатных: {stats_row[0] if stats_row else 0}
💎 Платных: {stats_row[1] if stats_row else 0}
🎫 Промокодов: {stats_row[2] if stats_row else 0}"""
        
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
        bot.send_message(chat_id, "❌ Уже существует", reply_markup=admin_menu())

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
    
    bot.send_message(
        chat_id,
        "🎉 ПРОМОКОД АКТИВИРОВАН!\n\nТеперь доступен платный тест!",
        reply_markup=get_main_menu(chat_id)
    )

@bot.message_handler(func=lambda m: m.text == '🔄 Перезапустить бота')
def restart_bot(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(message.chat.id, "🔄 Перезапуск бота...")
    super_kill_409()
    time.sleep(2)
    
    try:
        bot.stop_polling()
        time.sleep(2)
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=0, timeout=20)
        bot.send_message(message.chat.id, "✅ БОТ ПЕРЕЗАПУЩЕН!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

# ============================================
# ЗАПУСК БОТА
# ============================================

def run_bot():
    logger.info("🤖 ЗАПУСК БОТА...")
    
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
        logger.error(f"❌ Ошибка: {e}")
        time.sleep(5)
        run_bot()

if __name__ == "__main__":
    super_kill_409()
    time.sleep(2)
    super_kill_409()
    time.sleep(2)
    run_bot()
