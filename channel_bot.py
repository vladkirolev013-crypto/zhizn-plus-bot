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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# СУПЕР-УБИЙЦА 409 - 10 СПОСОБОВ СРАЗУ
# ============================================

def super_kill_409():
    """Уничтожает 409 всеми возможными способами"""
    
    logger.info("🔥 НАЧИНАЮ УНИЧТОЖЕНИЕ 409...")
    
    # СПОСОБ 1: Удаляем вебхук через API
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        response = requests.post(url, json={"drop_pending_updates": True}, timeout=10)
        logger.info(f"1. deleteWebhook: {response.json()}")
    except Exception as e:
        logger.error(f"1. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 2: Сбрасываем вебхук в ноль
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.post(url, json={"url": "", "drop_pending_updates": True}, timeout=10)
        logger.info(f"2. setWebhook пустой: {response.json()}")
    except Exception as e:
        logger.error(f"2. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 3: Проверяем статус вебхука
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url, timeout=10)
        logger.info(f"3. getWebhookInfo: {response.json()}")
    except Exception as e:
        logger.error(f"3. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 4: Удаляем все offset-файлы
    try:
        for pattern in ['update-offset-*.json', '*.lock', '*.session', '*.state', '*.pid', '*.offset']:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                    logger.info(f"4. Удален файл: {f}")
                except:
                    pass
    except Exception as e:
        logger.error(f"4. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 5: Удаляем через requests с другими параметрами
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        response = requests.get(url, params={"drop_pending_updates": "true"}, timeout=10)
        logger.info(f"5. deleteWebhook GET: {response.json()}")
    except Exception as e:
        logger.error(f"5. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 6: Еще раз сброс с пустым url через GET
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.get(url, params={"url": "", "drop_pending_updates": "true"}, timeout=10)
        logger.info(f"6. setWebhook GET: {response.json()}")
    except Exception as e:
        logger.error(f"6. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 7: Отправка запроса с force=True
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        response = requests.post(url, json={"drop_pending_updates": True, "force": True}, timeout=10)
        logger.info(f"7. deleteWebhook force: {response.json()}")
    except Exception as e:
        logger.error(f"7. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 8: Пробуем через telebot
    try:
        bot_temp = telebot.TeleBot(BOT_TOKEN)
        bot_temp.remove_webhook()
        logger.info("8. remove_webhook через telebot: OK")
    except Exception as e:
        logger.error(f"8. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 9: Удаляем файлы блокировки в текущей директории
    try:
        for f in os.listdir('.'):
            if f.endswith('.lock') or f.endswith('.session') or f.startswith('update-offset'):
                try:
                    os.remove(f)
                    logger.info(f"9. Удален: {f}")
                except:
                    pass
    except Exception as e:
        logger.error(f"9. Ошибка: {e}")
    
    time.sleep(1)
    
    # СПОСОБ 10: Финальная проверка
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url, timeout=10)
        webhook_data = response.json()
        logger.info(f"10. ФИНАЛЬНЫЙ СТАТУС ВЕБХУКА: {webhook_data}")
        if webhook_data.get('result', {}).get('url'):
            logger.warning("⚠️ ВЕБХУК ВСЕ ЕЩЕ ВИСИТ!")
        else:
            logger.info("✅ ВЕБХУК УНИЧТОЖЕН!")
    except Exception as e:
        logger.error(f"10. Ошибка: {e}")
    
    logger.info("🔥 УНИЧТОЖЕНИЕ 409 ЗАВЕРШЕНО!")
    return True

# ============================================
# ВЫПОЛНЯЕМ УБИЙСТВО 409 ПРИ СТАРТЕ
# ============================================

super_kill_409()
time.sleep(3)

# ВТОРОЙ ПРОХОД ДЛЯ НАДЕЖНОСТИ
logger.info("🔄 ВТОРОЙ ПРОХОД УНИЧТОЖЕНИЯ...")
super_kill_409()
time.sleep(2)

# ============================================
# GIGACHAT С МАКСИМАЛЬНЫМ ОЖИДАНИЕМ
# ============================================

giga_token_cache = {"token": None, "expires": 0}

def get_giga_token():
    """Получение токена с повторными попытками"""
    
    if giga_token_cache["token"] and time.time() < giga_token_cache["expires"]:
        return giga_token_cache["token"]
    
    for attempt in range(3):
        try:
            auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logger.info(f"🔄 Получение токена GigaChat (попытка {attempt+1}/3)...")
            
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data='scope=GIGACHAT_API_PERS',
                timeout=30,
                verify=False
            )
            
            logger.info(f"📡 Статус токена: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('access_token')
                
                if token:
                    giga_token_cache["token"] = token
                    giga_token_cache["expires"] = time.time() + 3500
                    logger.info("✅ Токен GigaChat получен успешно!")
                    return token
            
            logger.error(f"❌ Ошибка получения токена: {response.status_code} - {response.text[:200]}")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            time.sleep(2)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ТОКЕН ПОСЛЕ 3 ПОПЫТОК")
    return None

def ask_giga(system, user, max_tokens=3000):
    """Запрос к GigaChat с гарантированным ожиданием 30 секунд"""
    
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
    
    for attempt in range(2):
        try:
            logger.info("📤 Отправка запроса к GigaChat...")
            start_time = time.time()
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=90,
                verify=False
            )
            
            elapsed = time.time() - start_time
            logger.info(f"⏱ Ответ за {elapsed:.1f} секунд")
            
            # ГАРАНТИРОВАННОЕ ОЖИДАНИЕ 30 СЕКУНД
            if elapsed < 30:
                wait_time = 30 - elapsed
                logger.info(f"⏳ Ожидание {wait_time:.1f} секунд (гарантия генерации)")
                time.sleep(wait_time)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                logger.info("✅ Ответ GigaChat получен")
                return content
            else:
                logger.error(f"❌ Ошибка GigaChat: {response.status_code} - {response.text[:200]}")
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            logger.error("❌ Таймаут GigaChat (90 секунд)")
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            time.sleep(2)
    
    logger.error("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ОТВЕТ ПОСЛЕ 2 ПОПЫТОК")
    return None

# ============================================
# БАЗА ДАННЫХ (РАСШИРЕННАЯ)
# ============================================

DB_PATH = 'channel.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# Все таблицы с индексами
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
              promo_used INTEGER DEFAULT 0,
              users_count INTEGER DEFAULT 0)''')

c.execute("SELECT COUNT(*) FROM stats")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO stats (free_count, paid_count, promo_used, users_count) VALUES (0, 0, 0, 0)")

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
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS users
             (chat_id INTEGER PRIMARY KEY,
              username TEXT,
              first_name TEXT,
              last_name TEXT,
              registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              tests_passed INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS feedback
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id INTEGER,
              message TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

conn.commit()
logger.info("✅ База данных инициализирована")

# ============================================
# 150+ ТЕМ ДЛЯ ПОСТОВ
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
    "отношения": "💕 Трансформация отношений",
    "карьера": "💼 Самореализация",
    "здоровье": "💪 Психосоматика",
    "финансы": "💰 Денежное мышление",
    "личность": "🌟 Самость и архетипы",
    "самооценка": "⚡️ Уверенность и самоценность",
    "тревожность": "🌀 Управление тревогой",
    "эмоции": "🔥 Эмоциональный интеллект",
    "предназначение": "🎯 Путь и миссия"
}

# ============================================
# ГЕНЕРАТОР ПОСТА (РАСШИРЕННЫЙ)
# ============================================

def generate_post():
    """Генерация уникального поста"""
    
    theme = random.choice(POST_THEMES)
    
    system = """ТЫ - МИРОВОЙ ЭКСПЕРТ В ПСИХОЛОГИИ, КОУЧИНГЕ И НЛП.
    
    ТВОЙ СТИЛЬ:
    - Глубокий, мудрый, трансформирующий
    - Используешь НЛП-язык: предикаты, якоря, метамодель
    - Каждый пост - мини-сеанс терапии
    - Энергия текста заряжает и мотивирует
    - Пишешь как живой человек, без пафоса
    - Используешь метафоры и истории
    - Затрагиваешь душу и сознание
    
    СТРУКТУРА ПОСТА:
    1. ЗАХВАТЫВАЮЩИЙ ЗАГОЛОВОК (с эмодзи)
    2. ГЛУБОКОЕ ВСТУПЛЕНИЕ (затрагивает струны души)
    3. ОСНОВНАЯ ЧАСТЬ (инсайты, открытия, прозрения)
    4. ПРАКТИЧЕСКОЕ ЗАДАНИЕ (конкретное, выполнимое сегодня)
    5. ВОПРОС К ЧИТАТЕЛЮ (провокационный, пробуждающий)
    6. МОТИВИРУЮЩИЙ ФИНАЛ (крылья и энергия)
    7. ХЕШТЕГИ (#жизньплюс #саморазвитие)
    
    ДЛИНА: 800-1200 знаков
    ЯЗЫК: русский, живой, честный
    
    ВАЖНО:
    - Пиши от первого лица
    - Будь честным и уязвимым
    - Дай читателю ощущение "ЭТО ПРО МЕНЯ"
    - Заряди энергией действия
    - Оставь послевкусие трансформации
    - НИКОГДА НЕ ПОВТОРЯЙСЯ - каждый пост уникален"""
    
    user = f"""Напиши глубокий, трансформирующий пост на тему: "{theme}"
    
    Ты уже писал на эту тему? Отлично! Напиши СОВЕРШЕННО ПО-НОВОМУ.
    Используй свой 25-летний опыт работы с людьми.
    Сделай этот пост откровением для каждого читателя.
    
    Время писать ШЕДЕВР!"""
    
    response = ask_giga(system, user, 3000)
    
    if response and len(response) > 500:
        return response
    
    # Резервный пост если GigaChat не ответил
    fallback_posts = [
        """🌟 ОДИН ШАГ, КОТОРЫЙ МЕНЯЕТ ВСЁ

Сегодня я хочу поделиться простым, но мощным открытием.

Всё, что мы хотим изменить в жизни, начинается с одного маленького шага. Не с грандиозного плана. Не с идеальных условий. А с ДЕЙСТВИЯ.

Прямо сейчас, в эту секунду.

Я знаю, страшно. Я знаю, хочется подготовиться. Но мир устроен так, что подготовка никогда не заканчивается. Совершенство — это ловушка.

Вот что работает:
1. Выбери ОДНО действие
2. Сделай его сейчас
3. Повтори завтра

И через неделю ты не узнаешь себя.

Какой твой первый шаг сегодня? Напиши в комментариях.

#жизньплюс #шагксебе #саморазвитие""",

        """💫 ПЕРЕСТАНЬ ЖДАТЬ РАЗРЕШЕНИЯ

Сколько ты уже ждешь? Разрешения от родителей? Одобрения от начальника? Знака от вселенной?

А может быть, всё это время разрешение было у тебя?

Ты уже достаточно взрослый. Ты уже достаточно прошел. Ты уже готов.

Вот что я понял: никто не даст тебе разрешения жить свою жизнь. Никто не скажет "теперь можно". Потому что ты и есть тот, кто решает.

Сделай это сегодня. Начни то, что откладывал. Скажи то, что молчал. Стань тем, кем всегда хотел.

Твоя жизнь ждет ТВОЕГО разрешения.

Что ты решишь сделать сегодня?

#жизньплюс #смелость #осознанность"""
    ]
    
    return random.choice(fallback_posts)

# ============================================
# ГЕНЕРАТОР ТЕСТА (Б ВАРИАНТ - РАСШИРЕННЫЙ)
# ============================================

def generate_test_questions(topic, count=10):
    """Генерация теста: 10 вопросов (диагностика) или 20 (полный разбор)"""
    
    if count == 10:
        system = """ТЫ - ЭКСПЕРТ ПО КЛИНИЧЕСКОЙ ПСИХОЛОГИИ И КПТ.
        
        Создай СКРИНИНГОВЫЙ тест из 10 вопросов.
        Каждый вопрос должен задевать МАКСИМУМ сфер жизни.
        
        Вопросы как рентген: коротко, но видно всю суть.
        Результат должен показать самую слабую зону человека.
        
        Используй провокационные, цепляющие формулировки.
        Верни ТОЛЬКО JSON массив.
        
        ФОРМАТ:
        [
            {
                "question": "вопрос?",
                "options": {"A": "вариант 1", "B": "вариант 2", "C": "вариант 3", "D": "вариант 4"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]"""
        
        user = f"""Составь 10 вопросов для БЫСТРОЙ ДИАГНОСТИКИ личности по теме "{topic}".
        
        Требования:
        1. Каждый вопрос затрагивает 2-3 сферы жизни одновременно
        2. Варианты ответов должны быть реалистичными и разными
        3. После ответа на все вопросы должна быть понятна ГЛАВНАЯ проблема
        
        Верни ТОЛЬКО JSON."""
    
    else:
        system = """ТЫ - КЛИНИЧЕСКИЙ ПСИХОЛОГ С 25-ЛЕТНИМ СТАЖЕМ.
        
        Проведи ПОЛНУЮ ДИАГНОСТИКУ личности через 20 вопросов.
        Вопросы должны проникать вглубь, вскрывать травмы, сценарии и убеждения.
        
        Это как 2 сеанса психотерапии за один тест.
        Используй проективные техники, вопросы о детстве и жизненных сценариях.
        
        Каждый вопрос - ключ к разгадке личности.
        Верни ТОЛЬКО JSON массив.
        
        ФОРМАТ:
        [
            {
                "question": "глубокий вопрос?",
                "options": {"A": "ответ 1", "B": "ответ 2", "C": "ответ 3", "D": "ответ 4"},
                "scores": {"A": 0, "B": 1, "C": 2, "D": 3}
            }
        ]"""
        
        user = f"""Составь 20 ГЛУБИННЫХ вопросов для полного разбора личности по теме "{topic}".
        
        Требования:
        1. Вопросы должны выявлять КОРЕНЬ проблемы, а не симптомы
        2. Используй техники: "Как в детстве...", "Что бы вы сказали себе в прошлом..."
        3. Варианты ответов показывают разные психотипы
        4. Вопросы должны удивлять и открывать новое о себе
        
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
        
        # Добавляем баллы если их нет
        for q in questions:
            if 'scores' not in q:
                q['scores'] = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        
        return questions[:count]
        
    except Exception as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return None

# ============================================
# ГЕНЕРАТОР АНАЛИЗА (Б ВАРИАНТ - РАСШИРЕННЫЙ)
# ============================================

def generate_analysis(topic, answers, score, total, is_paid):
    """Генерация анализа: диагностика (бесплатно) или лечение (платно)"""
    
    if not is_paid:
        system = """ТЫ - ОПЫТНЫЙ ПСИХОЛОГ-ДИАГНОСТ.
        
        По результатам 10 вопросов определи ГЛАВНУЮ проблему человека.
        
        СТРУКТУРА ОТВЕТА:
        1. НАЗОВИ ТОП-1 ПРОБЛЕМУ (что мешает жить прямо сейчас)
        2. ДАЙ 1 МОЩНЫЙ ИНСАЙТ (почему это происходит)
        3. ЗАДАЙ 1 ВОПРОС ДЛЯ РАЗМЫШЛЕНИЯ (чтобы человек сам пришел к решению)
        4. ДАЙ 1 КОНКРЕТНЫЙ ШАГ (что сделать сегодня)
        
        Говори прямо, честно, без воды.
        Будь полезным и практичным.
        Объем: 600-800 знаков."""
        
        user = f"""Проведи диагностику личности.
        
        ТЕМА: {topic}
        ОТВЕТЫ: {answers}
        БАЛЛЫ: {score} из {total}
        
        Определи главную проблему.
        Дай ценный, практичный ответ.
        Помоги человеку начать путь к изменениям."""
    
    else:
        system = """ТЫ - МЕЖДУНАРОДНАЯ КОМАНДА ЭКСПЕРТОВ:
        1. КЛИНИЧЕСКИЙ ПСИХОЛОГ (диагностика причин)
        2. МЕЖДУНАРОДНЫЙ КОУЧ (стратегия и план)
        3. НЛП-ТЕРАПЕВТ (техники и якоря)
        
        Твоя задача — дать ПОЛНУЮ ТРАНСФОРМАЦИЮ.
        Это как месяц терапии за один анализ.
        
        СТРУКТУРА ОТВЕТА:
        1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ: кто этот человек на самом деле
        2. 2-3 ГЛУБИННЫХ ИНСАЙТА: что он не видел в себе
        3. КОРЕНЬ ПРОБЛЕМЫ: откуда это взялось (детство, сценарии)
        4. ПЛАН НА НЕДЕЛЮ: 3 конкретных шага
        5. РЕКОМЕНДАЦИИ КНИГ: 2 книги по теме
        6. УПРАЖНЕНИЕ: 1 мощная практика на каждый день
        7. ВИДЕО: 1 видео известного психолога/спикера
        
        Язык: честный, глубокий, трансформирующий.
        Объем: 1500+ знаков."""
        
        user = f"""Проведи полный разбор личности.
        
        ТЕМА: {topic}
        ОТВЕТЫ: {answers}
        БАЛЛЫ: {score} из {total}
        
        Сделай так, чтобы человек после прочтения:
        - Понял себя на 100% глубже
        - Увидел свои слепые зоны
        - Получил готовый план действий
        - Почувствовал надежду и энергию
        
        Время создавать трансформацию!"""
    
    response = ask_giga(system, user, 4000 if is_paid else 2500)
    
    if response:
        return response
    
    # Резервный анализ
    if is_paid:
        return f"""🔮 ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ

📊 Результат: {score} из {total}

🧠 ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
У вас высокий уровень осознанности. Вы чувствуете больше, чем показываете. Ваша главная сила — глубина, главная слабость — излишняя самокритика.

💡 ИНСАЙТЫ
1. Вы слишком много требуете от себя
2. Ваша чувствительность — это дар, а не проклятие

🎯 ПЛАН НА НЕДЕЛЮ
1. Практикуйте принятие своих чувств
2. Научитесь говорить НЕТ
3. Делайте маленькие шаги каждый день

📚 КНИГИ
1. «Эмоциональный интеллект» — Дэниел Гоулман
2. «Искусство быть счастливым» — Далай-лама

🧘 УПРАЖНЕНИЕ
Каждый день утром: 5 минут тишины и дыхания.

#жизньплюс #трансформация"""
    else:
        return f"""🔍 ДИАГНОСТИКА

📊 Результат: {score} из {total}

🎯 ГЛАВНАЯ ПРОБЛЕМА
Вы склонны обесценивать свои достижения и зацикливаться на недостатках.

💡 ИНСАЙТ
То, как вы говорите с собой, становится вашей реальностью.

❓ ВОПРОС
Если бы вы верили в себя на 100%, что бы вы сделали сегодня?

✅ ШАГ
Запишите сегодня 3 своих достижения, даже самых маленьких.

#жизньплюс #диагностика"""

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
    mk.add('📤 Отправить пост', '🧠 Тест в канал')
    mk.add('📊 Статистика', '🎫 Создать промокод')
    mk.add('🔄 Перезапустить бота', '👑 Главное меню')
    return mk

def test_type_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add('🧠 Бесплатный (10 вопросов)')
    mk.add('💎 Платный (20 вопросов)')
    mk.add('🔙 Назад')
    return mk

# ============================================
# СЕССИИ И ПОЛЬЗОВАТЕЛИ
# ============================================

sessions = {}

def save_user(chat_id, username=None, first_name=None, last_name=None):
    try:
        c.execute("""INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name, registered_at)
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                  (chat_id, username, first_name, last_name))
        conn.commit()
    except:
        pass

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user = message.from_user
    
    save_user(chat_id, user.username, user.first_name, user.last_name)
    
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
        f"🔮 ВЫБЕРИ СФЕРУ ИССЛЕДОВАНИЯ:\n\n"
        f"Количество вопросов: {count}\n"
        f"⏱ Время: ~{count // 2} минут",
        reply_markup=mk
    )

# ============================================
# ОБРАБОТЧИКИ ТЕСТОВ
# ============================================

@bot.callback_query_handler(func=lambda c: c.data.startswith(('free', 'paid')))
def topic_callback(c):
    try:
        test_type, topic, count = c.data.split('_')
        is_paid = test_type == 'paid'
        count = int(count)
        
        bot.edit_message_text(
            "🌀 ГЕНЕРАЦИЯ ТЕСТА...\n\n"
            "Создаю уникальные вопросы специально для тебя.\n"
            "⏱ Это займет до 30 секунд — дыши глубоко.",
            c.message.chat.id,
            c.message.message_id
        )
        
        questions = generate_test_questions(topic, count)
        
        if not questions:
            bot.send_message(
                c.message.chat.id,
                "❌ Не удалось сгенерировать тест.\n"
                "Возможно, вселенная готовит для тебя что-то другое.\n"
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
        logger.error(f"Ошибка в topic_callback: {e}")
        bot.send_message(c.message.chat.id, f"❌ Ошибка: {str(e)}")
    
    c.answer()

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
    
    # Обновляем статистику
    if is_paid:
        c.execute("UPDATE stats SET paid_count = paid_count + 1")
    else:
        c.execute("UPDATE stats SET free_count = free_count + 1")
    conn.commit()
    
    # Обновляем пользователя
    try:
        c.execute("UPDATE users SET tests_passed = tests_passed + 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()
    except:
        pass
    
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
            result = f"🔮 ПОЛНЫЙ РАЗБОР ЛИЧНОСТИ\n\n{analysis}"
        else:
            result = f"🔍 ДИАГНОСТИКА\n\n{analysis}"
        
        bot.send_message(chat_id, result, reply_markup=get_main_menu(chat_id))
    else:
        bot.send_message(
            chat_id,
            "❌ Не удалось сгенерировать анализ.\n"
            "Но твои ответы уже начали процесс трансформации.\n"
            "Попробуй еще раз позже.",
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
        "⏱ Это займет до 30 секунд — создается магия."
    )
    
    text = generate_post()
    
    if not text:
        bot.send_message(
            message.chat.id,
            "❌ Не удалось создать пост.\n"
            "Вселенная готовит что-то особенное, попробуй позже."
        )
        return
    
    # Сохраняем в историю
    try:
        c.execute("INSERT INTO posts_history (content) VALUES (?)", (text,))
        conn.commit()
    except:
        pass
    
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
    
    try:
        c.execute("INSERT INTO daily_tests (topic, questions, created_at, is_paid) VALUES (?, ?, ?, ?)",
                  (topic, json.dumps(questions), datetime.now().isoformat(), 0))
        conn.commit()
        test_id = c.lastrowid
    except:
        test_id = int(time.time())
    
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
    
    try:
        c.execute("SELECT free_count, paid_count, promo_used FROM stats")
        stats_row = c.fetchone()
        
        c.execute("SELECT COUNT(*) FROM daily_tests")
        tests_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM posts_history")
        posts_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        stats_text = f"""📊 СТАТИСТИКА ТРАНСФОРМАЦИЙ

👥 Пользователей: {users_count}
📝 Тестов в канале: {tests_count}
📤 Постов создано: {posts_count}
🧠 Бесплатных тестов: {stats_row[0] if stats_row else 0}
💎 Платных тестов: {stats_row[1] if stats_row else 0}
🎫 Промокодов активировано: {stats_row[2] if stats_row else 0}

Каждая цифра — чья-то трансформация."""
        
        bot.send_message(message.chat.id, stats_text, reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == '🔄 Перезапустить бота')
def restart_bot(message):
    if message.chat.id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "🔄 ПЕРЕЗАПУСК БОТА...\n\n"
        "Удаляю вебхук и перезапускаю соединение."
    )
    
    # Убиваем 409
    super_kill_409()
    
    # Перезапускаем polling
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
    logger.info("🤖 ЗАПУСК ТРАНСФОРМАЦИОННОГО БОТА...")
    
    try:
        # Еще раз убиваем 409 перед стартом
        super_kill_409()
        time.sleep(2)
        
        # Запускаем бота
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
        
        # Если 409, пробуем перезапустить
        if "409" in str(e):
            logger.info("🔄 Обнаружена ошибка 409, жесткий перезапуск...")
            super_kill_409()
            time.sleep(3)
            run_bot()
        else:
            time.sleep(5)
            run_bot()

if __name__ == "__main__":
    # Тройное уничтожение 409 перед запуском
    super_kill_409()
    time.sleep(2)
    super_kill_409()
    time.sleep(2)
    super_kill_409()
    time.sleep(2)
    
    run_bot()
