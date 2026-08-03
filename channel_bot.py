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
import io

# === НАСТРОЙКИ ===
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

def ask_giga(system_prompt, user_prompt, max_tokens=2000):
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
              total_score INTEGER, topic TEXT, ai_analysis TEXT, recommendations TEXT, created_at TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS daily_tests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              topic TEXT, questions TEXT, created_at TEXT)''')

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

# === ГЕНЕРАЦИЯ 20 УНИКАЛЬНЫХ ВОПРОСОВ ДЛЯ ПЛАТНОГО ТЕСТА ===
def generate_test_questions(topic, count=10):
    """Генерирует УНИКАЛЬНЫЕ вопросы для теста. Для платного - 20 уникальных."""
    try:
        logger.info(f"🔄 Генерирую НОВЫЙ тест по теме: {topic}, {count} вопросов")
        
        # Если нужно 20 вопросов - запрашиваем 25, чтобы был запас
        request_count = count + 5 if count == 20 else count
        
        system = """Ты — профессиональный психолог и коуч с 20-летним опытом. 
        Ты составляешь глубокие психологические тесты. 
        Вопросы должны быть небанальными, заставлять задуматься, раскрывать личность.
        Каждый вопрос должен иметь 4 варианта ответа с разными баллами (от 0 до 3).
        ВАЖНО: Каждый раз составляй НОВЫЕ, РАЗНЫЕ вопросы. Не повторяйся!"""
        
        user = f"""Составь тест на тему "{topic}" из {request_count} РАЗНЫХ, НЕ ПОВТОРЯЮЩИХСЯ вопросов.
        
        Требования:
        1. Вопросы должны быть глубокими, психологическими, заставлять задуматься
        2. Каждый вопрос с 4 вариантами ответов (A, B, C, D)
        3. Для каждого варианта укажи баллы (0-3), где 0 - наименее здоровый ответ, 3 - наиболее здоровый
        4. Вопросы должны раскрывать РАЗНЫЕ аспекты темы
        5. ВАЖНО: Все вопросы должны быть РАЗНЫМИ! НИ ОДИН ВОПРОС НЕ ДОЛЖЕН ПОВТОРЯТЬСЯ!
        6. Вопросы должны быть развернутыми и интересными
        
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
        
        response = ask_giga(system, user, max_tokens=4000 if count == 20 else 3000)
        
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end != -1:
            json_str = response[start:end]
            data = json.loads(json_str)
            questions = data.get('questions', [])
            
            if len(questions) >= count:
                # Оставляем только уникальные вопросы
                unique = []
                seen = set()
                for q in questions:
                    q_text = q.get('question', '')
                    if q_text not in seen:
                        seen.add(q_text)
                        unique.append(q)
                
                if len(unique) >= count:
                    logger.info(f"✅ Сгенерировано {len(unique)} УНИКАЛЬНЫХ вопросов")
                    # Перемешиваем и берем первые count
                    random.shuffle(unique)
                    return unique[:count]
                else:
                    logger.warning(f"⚠️ Только {len(unique)} уникальных, нужно {count}")
                    # Добираем запасными, но проверяем на дубликаты
                    fallback = get_fallback_questions(topic, count - len(unique))
                    # Убираем дубликаты с уже имеющимися
                    existing = {q.get('question', '') for q in unique}
                    final_fallback = []
                    for q in fallback:
                        if q.get('question', '') not in existing:
                            final_fallback.append(q)
                            existing.add(q.get('question', ''))
                    return unique + final_fallback[:count - len(unique)]
            else:
                logger.warning(f"⚠️ Получено {len(questions)} вопросов, нужно {count}")
                fallback = get_fallback_questions(topic, count - len(questions))
                return questions + fallback
        else:
            raise Exception("Не удалось извлечь JSON из ответа")
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации теста: {e}")
        return get_fallback_questions(topic, count)

def get_fallback_questions(topic, count=10):
    """Запасные вопросы - все разные"""
    all_questions = {
        "психология": [
            {"question": "Как часто вы чувствуете внутреннее напряжение?", "options": {"A": "Постоянно", "B": "Часто", "C": "Иногда", "D": "Редко"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с негативными мыслями?", "options": {"A": "Подавляю", "B": "Игнорирую", "C": "Анализирую", "D": "Трансформирую"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы оцениваете свою самооценку?", "options": {"A": "Занижена", "B": "Нестабильна", "C": "Адекватна", "D": "Здоровая"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как часто вы чувствуете тревогу без причины?", "options": {"A": "Ежедневно", "B": "Часто", "C": "Иногда", "D": "Почти никогда"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы относитесь к своим ошибкам?", "options": {"A": "Критикую себя", "B": "Избегаю вспоминать", "C": "Анализирую", "D": "Учусь"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с эмоциональным выгоранием?", "options": {"A": "Игнорирую", "B": "Терплю", "C": "Отдыхаю", "D": "Меняю подход"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Насколько вы осознаете свои эмоции?", "options": {"A": "Слабо", "B": "Иногда", "C": "Хорошо", "D": "Отлично"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы восстанавливаетесь после стресса?", "options": {"A": "Не восстанавливаюсь", "B": "Медленно", "C": "Быстро", "D": "Эффективно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как часто вы практикуете самонаблюдение?", "options": {"A": "Никогда", "B": "Редко", "C": "Регулярно", "D": "Ежедневно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы относитесь к психотерапии?", "options": {"A": "Отрицательно", "B": "Скептически", "C": "Нейтрально", "D": "Позитивно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с прокрастинацией?", "options": {"A": "Не справляюсь", "B": "С трудом", "C": "Дисциплинирую", "D": "Использую техники"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы относитесь к изменениям в жизни?", "options": {"A": "Боюсь", "B": "Сопротивляюсь", "C": "Принимаю", "D": "Использую"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с ответственностью?", "options": {"A": "Избегаю", "B": "С трудом", "C": "Принимаю", "D": "Ищу"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы видите свое будущее?", "options": {"A": "Негативно", "B": "Неопределенно", "C": "Оптимистично", "D": "Четко"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы относитесь к саморазвитию?", "options": {"A": "Не интересуюсь", "B": "Скептически", "C": "Интересуюсь", "D": "Активно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с неуверенностью?", "options": {"A": "Сдаюсь", "B": "С трудом", "C": "Преодолеваю", "D": "Расту"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы принимаете важные решения?", "options": {"A": "Импульсивно", "B": "С трудом", "C": "Взвешенно", "D": "Стратегически"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы строите отношения с людьми?", "options": {"A": "Сложно", "B": "Сдержанно", "C": "Открыто", "D": "Гармонично"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с критикой?", "options": {"A": "Защищаюсь", "B": "Обижаюсь", "C": "Слушаю", "D": "Анализирую"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы заботитесь о своем ментальном здоровье?", "options": {"A": "Не забочусь", "B": "Редко", "C": "Регулярно", "D": "Системно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}}
        ],
        "отношения": [
            {"question": "Как вы решаете конфликты в отношениях?", "options": {"A": "Агрессивно", "B": "Ухожу от конфликта", "C": "Обсуждаю", "D": "Ищу компромисс"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы выражаете любовь и заботу?", "options": {"A": "Не выражаю", "B": "Редко", "C": "Словами", "D": "Действиями"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Насколько вы доверяете близким людям?", "options": {"A": "Не доверяю", "B": "С трудом", "C": "В основном", "D": "Полностью"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как часто вы проводите время с близкими?", "options": {"A": "Редко", "B": "Иногда", "C": "Часто", "D": "Регулярно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с недопониманием?", "options": {"A": "Ссора", "B": "Молчание", "C": "Объяснение", "D": "Диалог"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Насколько вы открыты в отношениях?", "options": {"A": "Закрыт", "B": "Осторожен", "C": "Открыт", "D": "Искренен"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы поддерживаете отношения на расстоянии?", "options": {"A": "Не могу", "B": "С трудом", "C": "Нормально", "D": "Легко"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы показываете благодарность партнеру?", "options": {"A": "Не показываю", "B": "Изредка", "C": "Регулярно", "D": "Всегда"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы реагируете на критику в свой адрес?", "options": {"A": "Защищаюсь", "B": "Обижаюсь", "C": "Слушаю", "D": "Анализирую"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Что для вас главное в отношениях?", "options": {"A": "Стабильность", "B": "Страсть", "C": "Доверие", "D": "Понимание"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с ревностью?", "options": {"A": "Не контролирую", "B": "Подавляю", "C": "Обсуждаю", "D": "Работаю над собой"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы строите доверие в паре?", "options": {"A": "Не строю", "B": "Требую", "C": "Даю постепенно", "D": "Строим вместе"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с одиночеством в отношениях?", "options": {"A": "Паникую", "B": "Терплю", "C": "Ищу контакт", "D": "Работаю над собой"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы празднуете важные даты?", "options": {"A": "Не праздную", "B": "Формально", "C": "Тепло", "D": "Создаю ритуалы"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы поддерживаете партнера в трудные моменты?", "options": {"A": "Не замечаю", "B": "Сочувствую", "C": "Помогаю", "D": "Будьте рядом"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы решаете финансовые вопросы в паре?", "options": {"A": "Ссоры", "B": "Раздельно", "C": "Обсуждаем", "D": "Планируем вместе"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}}
        ],
        "карьера": [
            {"question": "Как вы ставите профессиональные цели?", "options": {"A": "Не ставлю", "B": "Планирую смутно", "C": "Конкретно", "D": "Стратегически"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с профессиональными вызовами?", "options": {"A": "Боюсь", "B": "Откладываю", "C": "Решаю", "D": "Использую как рост"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы развиваете свои навыки?", "options": {"A": "Не развиваю", "B": "Пассивно", "C": "Регулярно", "D": "Системно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с синдромом самозванца?", "options": {"A": "Не справляюсь", "B": "С трудом", "C": "Осознаю", "D": "Преодолеваю"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы используете профессиональные неудачи?", "options": {"A": "Ругаю себя", "B": "Забываю", "C": "Анализирую", "D": "Учусь"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы строите профессиональные отношения?", "options": {"A": "Избегаю", "B": "Формально", "C": "Дружелюбно", "D": "Стратегически"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с прокрастинацией?", "options": {"A": "Не справляюсь", "B": "С трудом", "C": "Дисциплинирую", "D": "Использую техники"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы ищете новые возможности?", "options": {"A": "Не ищу", "B": "Пассивно", "C": "Регулярно", "D": "Создаю"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы поддерживаете баланс работа-жизнь?", "options": {"A": "Нет баланса", "B": "С трудом", "C": "Стараюсь", "D": "Эффективно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}}
        ],
        "здоровье": [
            {"question": "Как часто вы заботитесь о своем здоровье?", "options": {"A": "Никогда", "B": "Редко", "C": "Регулярно", "D": "Системно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы оцениваете качество своего сна?", "options": {"A": "Плохое", "B": "Удовлетворительное", "C": "Хорошее", "D": "Отличное"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как часто вы занимаетесь физической активностью?", "options": {"A": "Никогда", "B": "Редко", "C": "Регулярно", "D": "Ежедневно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы питаетесь?", "options": {"A": "Бесконтрольно", "B": "Как придется", "C": "Сбалансированно", "D": "Осознанно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь со стрессом?", "options": {"A": "Срываюсь", "B": "Заедаю", "C": "Практикую релаксацию", "D": "Комплексно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}}
        ],
        "финансы": [
            {"question": "Как вы относитесь к деньгам?", "options": {"A": "Страх", "B": "Тревога", "C": "Уверенность", "D": "Спокойствие"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы планируете свой бюджет?", "options": {"A": "Не планирую", "B": "Стихийно", "C": "Регулярно", "D": "Системно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы относитесь к инвестициям?", "options": {"A": "Боюсь", "B": "Не верю", "C": "Интересуюсь", "D": "Активно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с финансовыми трудностями?", "options": {"A": "Паникую", "B": "Откладываю", "C": "Решаю", "D": "Планирую"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы относитесь к долгам и кредитам?", "options": {"A": "Страх", "B": "Принимаю", "C": "Контролирую", "D": "Избегаю"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}}
        ],
        "личность": [
            {"question": "Как вы оцениваете свои личностные качества?", "options": {"A": "Критично", "B": "Сомневаюсь", "C": "Объективно", "D": "Позитивно"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы справляетесь с изменениями в жизни?", "options": {"A": "Боюсь", "B": "Сопротивляюсь", "C": "Принимаю", "D": "Использую"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Насколько вы осознаете свои сильные стороны?", "options": {"A": "Не осознаю", "B": "Слабо", "C": "Хорошо", "D": "Отлично"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы принимаете важные решения?", "options": {"A": "Импульсивно", "B": "С трудом", "C": "Взвешенно", "D": "Стратегически"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}},
            {"question": "Как вы строите отношения с людьми?", "options": {"A": "Сложно", "B": "Сдержанно", "C": "Открыто", "D": "Гармонично"}, "scores": {"A": 0, "B": 1, "C": 2, "D": 3}}
        ]
    }
    
    questions = all_questions.get(topic, all_questions["психология"])
    while len(questions) < count:
        # Берем случайные вопросы из других тем если не хватает
        other_topics = [t for t in all_questions.keys() if t != topic]
        if other_topics:
            extra = all_questions[random.choice(other_topics)]
            questions.extend(extra)
    # Убираем дубликаты
    unique = []
    seen = set()
    for q in questions:
        q_text = q.get('question', '')
        if q_text not in seen:
            seen.add(q_text)
            unique.append(q)
    return unique[:count]

# === ГЕНЕРАЦИЯ СЕРТИФИКАТА ===
def generate_certificate(user_name, topic, score, total_questions):
    try:
        img = Image.new('RGB', (1200, 800), color='white')
        draw = ImageDraw.Draw(img)
        
        backgrounds = {
            "психология": (200, 230, 255),
            "отношения": (255, 200, 220),
            "карьера": (200, 255, 220),
            "здоровье": (220, 255, 200),
            "финансы": (255, 220, 200),
            "личность": (230, 200, 255)
        }
        
        bg_color = backgrounds.get(topic, (200, 230, 255))
        
        for i in range(800):
            r = int(bg_color[0] * (1 - i/1600) + 255 * (i/1600))
            g = int(bg_color[1] * (1 - i/1600) + 215 * (i/1600))
            b = int(bg_color[2] * (1 - i/1600) + 200 * (i/1600))
            draw.line([(0, i), (1200, i)], fill=(r, g, b), width=1)
        
        draw.rectangle([(20, 20), (1180, 780)], outline=(100, 100, 100), width=3)
        
        title = "СЕРТИФИКАТ О ПРОХОЖДЕНИИ"
        draw.text((600, 80), title, fill=(50, 50, 150), font=None, anchor="mt")
        
        name_text = f"🌟 {user_name} 🌟"
        draw.text((600, 200), name_text, fill=(50, 50, 150), font=None, anchor="mt")
        
        draw.text((600, 280), "успешно прошел(ла) тест", fill=(80, 80, 80), font=None, anchor="mt")
        
        topic_text = f"📌 {topic.upper()}"
        draw.text((600, 350), topic_text, fill=(100, 50, 150), font=None, anchor="mt")
        
        result_text = f"Результат: {score} из {total_questions * 3} баллов"
        draw.text((600, 430), result_text, fill=(50, 50, 50), font=None, anchor="mt")
        
        percentage = int((score / (total_questions * 3)) * 100)
        if percentage >= 70:
            emoji = "🌟"
            status = "Отличный результат!"
        elif percentage >= 40:
            emoji = "💫"
            status = "Хороший результат!"
        else:
            emoji = "🌱"
            status = "Есть к чему стремиться!"
        
        draw.text((600, 490), f"{emoji} {status}", fill=(50, 50, 150), font=None, anchor="mt")
        
        date_text = f"📅 {datetime.now().strftime('%d.%m.%Y')}"
        draw.text((600, 580), date_text, fill=(100, 100, 100), font=None, anchor="mt")
        
        draw.text((600, 670), "Жизнь+ | Психология и саморазвитие", fill=(80, 80, 80), font=None, anchor="mt")
        
        filename = f'/tmp/certificate_{int(time.time())}.png'
        img.save(filename)
        return filename
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации сертификата: {e}")
        return None

# === ГЛУБОКИЙ АНАЛИЗ РЕЗУЛЬТАТОВ С РЕКОМЕНДАЦИЯМИ ===
def analyze_results(topic, answers, scores, total_questions, is_paid=False):
    try:
        min_length = 1400 if is_paid else 700
        logger.info(f"Анализирую результаты теста по теме: {topic}, длина: {min_length}+ знаков")
        
        percentage = int((scores / (total_questions * 3)) * 100)
        if percentage >= 70:
            rec_count = 4
            level = "высокий"
        elif percentage >= 40:
            rec_count = 5
            level = "средний"
        else:
            rec_count = 6
            level = "начальный"
        
        system = """Ты — команда из двух экспертов:
        1. Клинический психолог с 25-летним опытом, доктор наук
        2. Бизнес-коуч и коуч по личностному росту, автор бестселлеров
        
        Вы проводите глубокий анализ результатов психологического теста.
        Ваш анализ должен быть максимально полезным, глубоким и персонализированным.
        Пишите тепло, профессионально, с примерами и конкретикой.
        Используйте эмодзи, переносы строк, структурируйте текст.
        ВСЕ РЕКОМЕНДАЦИИ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ."""
        
        user = f"""Проведи анализ результатов теста по теме "{topic}".
        
        Ответы пользователя (A, B, C, D):
        {answers}
        
        Общий балл: {scores} из {total_questions * 3}
        Процент: {percentage}%
        Уровень результата: {level}
        
        Напиши развернутый анализ МИНИМУМ на {min_length} знаков:
        
        1. 🧠 Оценка от клинического психолога (30% текста):
           - Глубокий анализ личности на основе ответов
           - Выявление сильных сторон и зон роста
           - Психологический портрет с деталями
           - Рекомендации по работе над собой
        
        2. 💼 Коучинговый разбор от эксперта (30% текста):
           - Оценка потенциала и возможностей
           - Конкретные шаги для развития
           - Мотивационные техники
           - Практические упражнения
        
        3. 🌟 Интегральный вывод (20% текста):
           - Общая картина состояния
           - 3 конкретных действия для улучшения
           - Мотивирующая поддержка
        
        4. 📚 ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ ОТ ЭКСПЕРТОВ (20% текста, ВАЖНО!):
           Подбери для этого человека:
           - {rec_count} КНИГ на русском языке, которые помогут в развитии по теме "{topic}"
           - {rec_count} ПРАКТИЧЕСКИХ УПРАЖНЕНИЙ на русском языке
           - {rec_count} ВИДЕО или КАНАЛОВ на русском языке для саморазвития
           
           Все рекомендации должны быть:
           - Конкретными и полезными
           - На русском языке
           - Подходить именно под этот уровень результата ({level})
           - С кратким пояснением, почему это рекомендовано
        
        Пиши максимально полезно, конкретно и вдохновляюще.
        ВСЕ РЕКОМЕНДАЦИИ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ!"""
        
        response = ask_giga(system, user, max_tokens=4000 if is_paid else 2500)
        
        if len(response) < min_length:
            logger.warning(f"⚠️ Анализ слишком короткий: {len(response)} знаков, нужно {min_length}")
            extension = f"\n\n💫 Дополнительные рекомендации для вас:\n\n"
            if scores < total_questions * 3 * 0.4:
                extension += "Рекомендуем начать с малого: выберите одну область для работы и уделяйте ей 15 минут в день. Помните, что путь к изменениям начинается с первого шага!"
            elif scores < total_questions * 3 * 0.7:
                extension += "У вас хороший фундамент! Сфокусируйтесь на системном подходе: ведите дневник прогресса, отмечайте даже маленькие победы."
            else:
                extension += "Вы на правильном пути! Продолжайте развиваться и делитесь своим опытом с другими - это усилит ваш рост."
            response += extension
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}")
        return get_fallback_analysis(topic, scores, total_questions)

def get_fallback_analysis(topic, scores, total_questions):
    max_score = total_questions * 3
    percentage = int((scores / max_score) * 100)
    
    if percentage >= 70:
        status = "отличное психологическое состояние"
        recommendation = "поддерживать баланс и заниматься профилактикой"
        detail = "Вы демонстрируете высокий уровень психологического благополучия и осознанности."
        emoji = "🌟"
        level = "высокий"
    elif percentage >= 40:
        status = "удовлетворительное состояние с потенциалом для роста"
        recommendation = "работать над эмоциональным интеллектом и стрессоустойчивостью"
        detail = "У вас хороший фундамент, но есть зоны для развития."
        emoji = "💫"
        level = "средний"
    else:
        status = "требуется внимание к психологическому состоянию"
        recommendation = "обратиться к психологу и начать практиковать mindfulness"
        detail = "Важно уделить время себе и своему внутреннему состоянию."
        emoji = "🌱"
        level = "начальный"
    
    books = {
        "психология": [
            "📚 «Психология влияния» — Роберт Чалдини",
            "📚 «Думай медленно... решай быстро» — Даниэль Канеман",
            "📚 «Поток» — Михай Чиксентмихайи"
        ],
        "отношения": [
            "📚 «Пять языков любви» — Гэри Чепмен",
            "📚 «Искусство любить» — Эрих Фромм",
            "📚 «Мужчины с Марса, женщины с Венеры» — Джон Грэй"
        ],
        "карьера": [
            "📚 «Джедайские техники» — Максим Дорофеев",
            "📚 «Эссенциализм» — Грег МакКеон",
            "📚 «От хорошего к великому» — Джим Коллинз"
        ],
        "здоровье": [
            "📚 «Почему мы спим» — Мэттью Уокер",
            "📚 «Еда и мозг» — Дэвид Перлмуттер",
            "📚 «Исцеление стрессом» — Майкл Грегер"
        ],
        "финансы": [
            "📚 «Богатый папа, бедный папа» — Роберт Кийосаки",
            "📚 «Самый богатый человек в Вавилоне» — Джордж Клейсон",
            "📚 «Думай как миллионер» — Т. Харв Экер"
        ],
        "личность": [
            "📚 «Атомные привычки» — Джеймс Клир",
            "📚 «Трансерфинг реальности» — Вадим Зеланд",
            "📚 «Сила воли» — Келли Макгонигал"
        ]
    }
    
    topic_books = books.get(topic, books["психология"])
    
    exercises = [
        "1. Практика благодарности: каждый день записывайте 3 вещи, за которые вы благодарны",
        "2. Дыхательная практика: 5 минут глубокого дыхания утром и вечером",
        "3. Дневник эмоций: записывайте свои чувства и мысли каждый вечер"
    ]
    
    videos = [
        "1. TED Talks на русском: «Как перестать беспокоиться и начать жить»",
        "2. YouTube-канал: «Психология с Анной» (русский язык)",
        "3. Лекции по саморазвитию на канале «Душевный вечер» (русский язык)"
    ]
    
    text = f"""🔍 РЕЗУЛЬТАТЫ ТЕСТА
📌 Тема: {topic.title()}

{emoji} ВАШ РЕЗУЛЬТАТ: {scores} из {max_score} баллов ({percentage}%)
Уровень: {level}

🧠 АНАЛИЗ КЛИНИЧЕСКОГО ПСИХОЛОГА:
Ваше состояние характеризуется как {status}.
{detail}
{scores} баллов отражают ваш текущий уровень психологического благополучия.

💼 РЕКОМЕНДАЦИИ ОТ КОУЧА:
Для дальнейшего развития {recommendation}.
Рекомендуем практиковать осознанность и работать над своими целями.

📚 ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ ОТ ЭКСПЕРТОВ:

КНИГИ НА РУССКОМ ЯЗЫКЕ:
{topic_books[0]}
{topic_books[1]}
{topic_books[2]}

УПРАЖНЕНИЯ:
{exercises[0]}
{exercises[1]}
{exercises[2]}

ВИДЕО НА РУССКОМ ЯЗЫКЕ:
{videos[0]}
{videos[1]}
{videos[2]}

🌟 ПРАКТИЧЕСКИЕ ШАГИ ДЛЯ УЛУЧШЕНИЯ:
1. Начните вести дневник эмоций (5 минут в день)
2. Практикуйте благодарность — записывайте 3 хороших события каждый день
3. Найдите время для саморефлексии и отдыха

💫 ЗАКЛЮЧЕНИЕ:
Ваш результат показывает, что у вас есть потенциал для роста. 
Каждый день — это возможность стать лучше. Доверяйте себе и своему пути!

#саморазвитие #психология #коучинг #жизньплюс"""
    
    while len(text) < 700:
        text += "\n\n✨ Помните: каждый день - это новая возможность стать лучше!"
    
    return text

# === ГЕНЕРАЦИЯ КАРТИНКИ РЕЗУЛЬТАТА ===
def generate_result_image(score, total, topic):
    try:
        percentage = int((score / total) * 100)
        
        if percentage >= 70:
            prompt = "beautiful sunset motivational success happiness celebration gold"
        elif percentage >= 40:
            prompt = "peaceful nature landscape meditation growth green"
        else:
            prompt = "motivational sunrise new beginning hope inspiration"
        
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1080&height=720&nologo=true"
        img = requests.get(url, timeout=30).content
        filename = f'/tmp/result_{int(time.time())}.jpg'
        with open(filename, 'wb') as f:
            f.write(img)
        return filename
    except Exception as e:
        logger.error(f"Ошибка генерации картинки результата: {e}")
        return None

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

# === ГЕНЕРАЦИЯ ПОСТА (1000+ ЗНАКОВ) ===
def generate_post(theme):
    try:
        logger.info(f"Генерирую ДЛИННЫЙ пост на тему: {theme}")
        
        system = """Ты — позитивный психолог и мотивационный спикер с 20-летним опытом.
        Ты пишешь глубокие, вдохновляющие посты для Telegram-канала о жизни и саморазвитии.
        Твои посты меняют жизни людей, дают практические советы и мотивируют на действия.
        Пиши развернуто, с душой, используй эмодзи, структурируй текст."""
        
        user = f"""Напиши РАЗВЕРНУТЫЙ пост для Telegram на тему: "{theme}".

        ТРЕБОВАНИЯ К ПОСТУ (ОБЯЗАТЕЛЬНО ВСЕ ПУНКТЫ):
        
        1. ЗАГОЛОВОК — яркий, привлекающий внимание, с эмодзи (1-2 строки)
        
        2. ОСНОВНАЯ ЧАСТЬ — минимум 500-600 символов:
           - Глубокое раскрытие темы с психологической точки зрения
           - Практический разбор проблемы
           - Конкретные примеры из жизни
           - Научно обоснованные факты или исследования
        
        3. ПРАКТИЧЕСКИЙ СОВЕТ (100-150 символов):
           - Конкретное упражнение или действие, которое можно сделать сегодня
           - Техника из психологии или коучинга
        
        4. ВДОХНОВЛЯЮЩАЯ ИСТОРИЯ ИЛИ ПРИТЧА (100-150 символов):
           - Маленькая история, которая иллюстрирует тему
           - Мотивирующий пример
        
        5. ВЫВОД — краткое резюме поста (2-3 предложения)
        
        6. МОТИВАЦИОННАЯ ФРАЗА — цитата или афоризм, подходящий к теме
        
        7. ХЕШТЕГИ — 5-7 шт. (#жизньплюс #мотивация #психология и т.д.)
        
        ОБЩАЯ ДЛИНА ПОСТА: 1000-1300 знаков (НЕ МЕНЬШЕ 1000!)
        
        Формат: Только текст, без Markdown разметки. Используй эмодзи для структурирования.
        Пиши тепло, душевно, профессионально и вдохновляюще."""
        
        text = ask_giga(system, user, max_tokens=2000)
        
        if not text or len(text) < 800:
            logger.warning(f"⚠️ Пост слишком короткий: {len(text) if text else 0} символов")
            extension = """
            
💫 ДОПОЛНИТЕЛЬНАЯ МЫСЛЬ НА СЕГОДНЯ:

Помните, что каждый день — это новая страница вашей жизни.
То, что вы делаете сегодня, создает ваше завтра.
Не бойтесь начинать сначала, бойтесь стоять на месте.

Сделайте один маленький шаг в сторону своей мечты прямо сейчас! ✨

#жизньплюс #мотивация #саморазвитие #вдохновение #психология"""
            text = text + extension if text else extension
        
        if text and len(text) < 1000:
            extension2 = """
            
🌟 ВАЖНОЕ НАПОМИНАНИЕ:

Каждая победа начинается с решения попробовать.
Каждый большой успех — это результат маленьких ежедневных действий.
Вы сильнее, чем думаете. Вы способны на большее, чем кажется.

Начните действовать сегодня! 💪

#жизньплюс #мотивация #саморазвитие #психология #успех"""
            text = text + extension2
        
        logger.info(f"✅ Пост сгенерирован: {len(text)} символов")
        return text
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        return """✨ УТРЕННЯЯ МОТИВАЦИЯ: Путь к лучшей версии себя

Каждый день мы сталкиваемся с вызовами, которые проверяют нас на прочность. Но именно в этих моментах скрыта наша сила.

🌟 ПОЧЕМУ ЭТО ВАЖНО:
Наша жизнь — это непрерывный процесс роста и развития. Когда мы останавливаемся, мы начинаем терять энергию и смысл. Движение вперед — это естественное состояние человека.

💡 ЧТО МОЖНО СДЕЛАТЬ СЕГОДНЯ:
Возьмите лист бумаги и напишите 5 вещей, за которые вы благодарны сегодня. Это простое упражнение переключает мозг с поиска проблем на поиск возможностей.

📖 МАЛЕНЬКАЯ ИСТОРИЯ:
Однажды ученик спросил мастера: "Как достичь успеха?" Мастер ответил: "Делай каждый день одно маленькое дело, которое приближает тебя к цели. Через год ты не узнаешь себя".

💫 ГЛАВНЫЙ ВЫВОД:
Не ждите идеального момента — начните с того, что есть, используйте то, что имеете, и делайте то, что можете. Каждый шаг имеет значение.

🌟 ЦИТАТА ДНЯ:
"Путь в тысячу миль начинается с первого шага" — Лао-Цзы

Действуйте, верьте в себя и помните: вы способны на великие дела! 🚀

#жизньплюс #мотивация #саморазвитие #психология #успех #цели #рост #вдохновение #сила"""

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
                time.sleep(1)
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

# === ЕЖЕДНЕВНЫЙ ТЕСТ В КАНАЛЕ ===
def post_daily_test():
    try:
        topics = list(TEST_TOPICS.keys())
        random.shuffle(topics)
        
        sent_count = 0
        for topic in topics:
            try:
                questions = generate_test_questions(topic, 10)
                
                if not questions:
                    continue
                
                questions_json = json.dumps(questions)
                c.execute("INSERT INTO daily_tests (topic, questions, created_at) VALUES (?,?,?)",
                          (topic, questions_json, datetime.now().isoformat()))
                conn.commit()
                
                test_id = c.lastrowid
                
                post_text = (
                    f"🧠 **ЕЖЕДНЕВНЫЙ ТЕСТ ДНЯ!**\n\n"
                    f"📌 Тема: **{topic.title()}**\n"
                    f"📊 Вопросов: 10\n\n"
                    f"Проверьте себя прямо сейчас!\n"
                    f"Узнайте больше о своем психологическом состоянии\n"
                    f"и получите персональные рекомендации!\n\n"
                    f"Нажмите кнопку ниже, чтобы пройти тест в боте 👇"
                )
                
                bot_username = bot.get_me().username
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton(
                    "🎯 Пройти тест в боте",
                    url=f"https://t.me/{bot_username}?start=daily_{topic}_{test_id}"
                ))
                
                bot.send_message(
                    CHANNEL_ID,
                    post_text,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
                
                sent_count += 1
                logger.info(f"✅ Ежедневный тест отправлен в канал: {topic}")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки теста по теме {topic}: {e}")
                continue
        
        return sent_count > 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки ежедневных тестов: {e}")
        return False

# === ОБРАБОТЧИК START С ПАРАМЕТРАМИ ===
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
                    
                    if topic in TEST_TOPICS:
                        c.execute("SELECT questions FROM daily_tests WHERE id = ?", (test_id,))
                        row = c.fetchone()
                        
                        if row:
                            questions = json.loads(row[0])
                            
                            bot.send_message(
                                chat_id,
                                f"🧠 Вы перешли по ежедневному тесту!\n"
                                f"📌 Тема: {topic.title()}\n"
                                f"Начинаем тест прямо сейчас!"
                            )
                            
                            user_test_data[chat_id] = {
                                'test_id': f"daily_{test_id}",
                                'topic': topic,
                                'type': 'free',
                                'questions': questions,
                                'answers': [],
                                'current_q': 0,
                                'scores': [],
                                'total_questions': len(questions),
                                'is_paid': False,
                                'is_daily': True
                            }
                            
                            send_question(chat_id)
                            return
                        else:
                            bot.send_message(chat_id, "❌ Тест не найден. Попробуйте начать новый.")
                            start_menu(message)
                            return
            except Exception as e:
                logger.error(f"❌ Ошибка обработки daily параметра: {e}")
                bot.send_message(chat_id, "❌ Произошла ошибка. Попробуйте снова.")
                start_menu(message)
                return
    
    start_menu(message)

def start_menu(message):
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

# === ОСНОВНОЕ МЕНЮ ===
def get_main_keyboard():
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
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        telebot.types.KeyboardButton('🧠 Бесплатный тест (10 вопр.)'),
        telebot.types.KeyboardButton('💎 Платный тест (20 вопр.) — 50 ₽')
    )
    markup.add(
        telebot.types.KeyboardButton('🔙 На главную')
    )
    return markup

# === КОМАНДЫ БОТА ===
@bot.message_handler(func=lambda m: m.text == '🎯 Пройти тест')
def show_test_selection(message):
    text = (
        "🎯 ВЫБЕРИТЕ ТИП ТЕСТА:\n\n"
        "🧠 Бесплатный тест (10 вопросов)\n"
        "• Глубокие психологические вопросы\n"
        "• Развернутый анализ (700+ знаков)\n"
        "• Рекомендации от психолога\n\n"
        "💎 Платный тест (20 вопросов) — 50 ₽\n"
        "• 20 УНИКАЛЬНЫХ вопросов\n"
        "• Расширенная диагностика\n"
        "• Глубокий анализ (1400+ знаков)\n"
        "• Персональные рекомендации от экспертов\n"
        "• Подбор книг по вашей теме (русский язык)\n"
        "• Практические упражнения (русский язык)\n"
        "• Рекомендации видео (русский язык)\n"
        "• Индивидуально под ваш результат\n\n"
        "Выберите вариант ниже:"
    )
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=get_test_type_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '🧠 Бесплатный тест (10 вопр.)')
def start_free_test(message):
    show_topic_selection(message, "free", 10)

@bot.message_handler(func=lambda m: m.text == '💎 Платный тест (20 вопр.) — 50 ₽')
def start_paid_test(message):
    chat_id = message.chat.id
    
    if chat_id in ADMIN_IDS:
        bot.send_message(
            chat_id,
            "👑 Вы модератор канала! Платный тест доступен БЕСПЛАТНО."
        )
        show_topic_selection(message, "paid_free", 20)
    else:
        bot.send_message(
            chat_id,
            "💎 ПЛАТНЫЙ ТЕСТ — 50 ₽\n\n"
            "Вы получаете:\n"
            "✅ 20 УНИКАЛЬНЫХ глубоких психологических вопросов\n"
            "✅ Развернутый анализ от психолога и коуча\n"
            "✅ Персональные рекомендации:\n"
            "   • Книги на русском языке\n"
            "   • Практические упражнения\n"
            "   • Видео на русском языке\n"
            "✅ Сертификат о прохождении\n\n"
            "💰 Стоимость: 50 ₽\n\n"
            "Оплата скоро будет доступна через Telegram Stars.\n"
            "А пока вы можете пройти БЕСПЛАТНЫЙ тест (10 вопросов)."
        )
        show_topic_selection(message, "free", 10)

def show_topic_selection(message, test_type, count):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    for topic, description in TEST_TOPICS.items():
        short_desc = description.split(',')[0] if ',' in description else description
        markup.add(telebot.types.InlineKeyboardButton(
            f"{short_desc}", 
            callback_data=f"topic_{test_type}_{topic}_{count}"
        ))
    
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    if test_type == "paid_free":
        text = f"🎯 Выберите тему платного теста (БЕСПЛАТНО для модератора):\n\n"
    else:
        text = f"🎯 Выберите тему теста:\n\n"
    
    text += f"Каждый раз генерируются НОВЫЕ уникальные вопросы!\n\n"
    text += f"📊 {count} вопросов + развернутый анализ от экспертов"
    
    if count == 20:
        text += f"\n\n💎 Персональные рекомендации на русском языке:\n"
        text += f"   📚 Книги\n"
        text += f"   🧘 Упражнения\n"
        text += f"   🎥 Видео"
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('topic_'))
def handle_topic_selection(call):
    try:
        parts = call.data.split('_')
        test_type = parts[1]
        topic = parts[2]
        count = int(parts[3]) if len(parts) > 3 else 10
        
        is_paid = test_type in ['paid', 'paid_free']
        
        bot.edit_message_text(
            f"🔄 Генерирую НОВЫЙ тест по теме «{topic.title()}»...\n"
            f"Это может занять несколько секунд.\n"
            f"Пожалуйста, подождите...",
            call.message.chat.id,
            call.message.message_id
        )
        
        questions = generate_test_questions(topic, count)
        
        if not questions or len(questions) < count:
            bot.send_message(
                call.message.chat.id,
                f"❌ Не удалось сгенерировать тест. Получено {len(questions) if questions else 0} вопросов, нужно {count}. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
            return
        
        test_id = f"temp_{int(time.time())}_{call.message.chat.id}"
        user_test_data[call.message.chat.id] = {
            'test_id': test_id,
            'topic': topic,
            'type': test_type,
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
        logger.error(f"❌ Ошибка выбора темы: {e}")
        bot.send_message(
            call.message.chat.id,
            f"❌ Произошла ошибка: {str(e)[:100]}",
            reply_markup=get_main_keyboard()
        )

def send_question(chat_id):
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
    chat_id = message.chat.id
    state = user_test_data.get(chat_id)
    
    if not state:
        bot.send_message(
            chat_id,
            "❌ Активный тест не найден. Начните новый через кнопку «🎯 Пройти тест»",
            reply_markup=get_main_keyboard()
        )
        return
    
    current_q = state['current_q']
    if current_q >= len(state['questions']):
        finish_test(chat_id)
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

def finish_test(chat_id):
    state = user_test_data.get(chat_id)
    if not state:
        return
    
    total_score = sum(state['scores'])
    max_score = len(state['questions']) * 3
    answers_str = ', '.join(state['answers'])
    is_paid = state.get('is_paid', False)
    
    bot.send_message(
        chat_id,
        f"📊 Тест завершен!\n\n"
        f"✅ Вы ответили на {len(state['questions'])} УНИКАЛЬНЫХ вопросов\n"
        f"📊 Ваш результат: {total_score} из {max_score}\n\n"
        f"⏳ Генерирую глубокий анализ от экспертов...\n"
        f"Это займет до 30 секунд. Пожалуйста, подождите!"
    )
    
    try:
        analysis = analyze_results(
            state['topic'],
            answers_str,
            total_score,
            len(state['questions']),
            is_paid
        )
        
        c.execute("""INSERT INTO user_results 
                     (user_id, test_id, answers, total_score, topic, ai_analysis, recommendations, created_at) 
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (chat_id, state['test_id'], answers_str, total_score, 
                   state['topic'], analysis, "", datetime.now().isoformat()))
        conn.commit()
        
        try:
            user_name = bot.get_chat(chat_id).first_name or "Пользователь"
            cert_path = generate_certificate(user_name, state['topic'], total_score, len(state['questions']))
            
            if cert_path and os.path.exists(cert_path):
                with open(cert_path, 'rb') as cert:
                    bot.send_document(chat_id, cert, caption="🏆 Ваш сертификат о прохождении теста!")
                os.remove(cert_path)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сертификата: {e}")
        
        img_path = generate_result_image(total_score, max_score, state['topic'])
        
        result_text = f"🔍 РЕЗУЛЬТАТЫ ТЕСТА\n\n{analysis}"
        
        if img_path and os.path.exists(img_path):
            caption = f"🌟 Ваш результат: {total_score} из {max_score}\n📌 Тема: {state['topic'].title()}"
            with open(img_path, 'rb') as photo:
                bot.send_photo(chat_id, photo, caption=caption)
            os.remove(img_path)
            
            if len(result_text) > 4096:
                parts = [result_text[i:i+4096] for i in range(0, len(result_text), 4096)]
                for part in parts:
                    bot.send_message(chat_id, part)
            else:
                bot.send_message(chat_id, result_text)
        else:
            if len(result_text) > 4096:
                parts = [result_text[i:i+4096] for i in range(0, len(result_text), 4096)]
                for part in parts:
                    bot.send_message(chat_id, part)
            else:
                bot.send_message(chat_id, result_text)
        
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            telebot.types.KeyboardButton('🎯 Пройти тест'),
            telebot.types.KeyboardButton('📊 Мои результаты')
        )
        markup.add(
            telebot.types.KeyboardButton('📤 Поделиться результатом'),
            telebot.types.KeyboardButton('📋 О тестах')
        )
        markup.add(
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
    
    if chat_id in user_test_data:
        del user_test_data[chat_id]

# === ПОДЕЛИТЬСЯ РЕЗУЛЬТАТОМ ===
@bot.message_handler(func=lambda m: m.text == '📤 Поделиться результатом')
def share_result(message):
    chat_id = message.chat.id
    
    c.execute("""SELECT topic, total_score, created_at 
                 FROM user_results 
                 WHERE user_id = ? 
                 ORDER BY created_at DESC 
                 LIMIT 1""", (chat_id,))
    
    result = c.fetchone()
    
    if not result:
        bot.send_message(
            chat_id,
            "📭 У вас пока нет результатов для публикации.\n"
            "Пройдите тест и получите свой результат!",
            reply_markup=get_main_keyboard()
        )
        return
    
    topic, score, date = result
    
    share_text = (
        f"🌟 Я прошел(ла) тест «{topic.title()}» в боте Жизнь+!\n\n"
        f"📊 Мой результат: {score} баллов\n\n"
        f"Хочешь проверить себя? Проходи тест в боте:\n"
        f"@{bot.get_me().username}\n\n"
        f"#жизньплюс #психология #саморазвитие"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "🎯 Пройти тест",
        url=f"https://t.me/{bot.get_me().username}?start"
    ))
    
    bot.send_message(
        chat_id,
        "📤 Вот что можно опубликовать в соцсетях:\n\n"
        f"{share_text}",
        reply_markup=markup
    )

# === ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ===
@bot.message_handler(func=lambda m: m.text == '📊 Мои результаты')
def show_results(message):
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
    text = (
        "📋 ЧТО ТАКОЕ ТЕСТЫ ЖИЗНЬ+?\n\n"
        "Это уникальные психологические тесты, созданные с помощью искусственного интеллекта.\n"
        "Каждый раз генерируются НОВЫЕ уникальные вопросы!\n\n"
        "🔹 Как это работает:\n"
        "1. Вы выбираете тему теста\n"
        "2. Отвечаете на вопросы (10 или 20)\n"
        "3. Получаете глубокий анализ от двух экспертов\n\n"
        "🔹 Кто анализирует результаты:\n"
        "🧠 Клинический психолог — оценивает ваше состояние\n"
        "💼 Коуч — дает практические рекомендации\n\n"
        "🔹 Объем анализа:\n"
        "• Бесплатный тест: 700+ знаков\n"
        "• Платный тест (50 ₽): 1400+ знаков\n\n"
        "🔹 Что дает платный тест (50 ₽):\n"
        "• 20 УНИКАЛЬНЫХ вопросов (НЕ повторяются!)\n"
        "• Персональные рекомендации от психолога и коуча\n"
        "• 4-6 книг по вашей теме (русский язык)\n"
        "• 4-6 практических упражнений (русский язык)\n"
        "• 4-6 рекомендаций видео (русский язык)\n"
        "• Индивидуально под ваш результат\n\n"
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
    start_menu(message)

@bot.callback_query_handler(func=lambda call: call.data == 'go_to_test')
def callback_go_to_test(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_test_selection(call.message)

@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def callback_cancel(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
        "❌ Выбор темы отменен.",
        reply_markup=get_main_keyboard()
    )

# === АДМИН-КОМАНДЫ ===
@bot.message_handler(commands=['daily'])
def manual_daily_test(message):
    """Ручная отправка ежедневных тестов в канал"""
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📤 Отправляю ежедневные тесты в канал...")
        try:
            result = post_daily_test()
            if result:
                bot.send_message(message.chat.id, "✅ Ежедневные тесты отправлены в канал!")
            else:
                bot.send_message(message.chat.id, "❌ Ошибка отправки. Проверьте логи.")
        except Exception as e:
            logger.error(f"Ошибка в /daily: {e}")
            bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)[:100]}")
    else:
        bot.send_message(message.chat.id, "⛔ У вас нет прав для этой команды.")

@bot.message_handler(commands=['post'])
def manual_post(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "📤 Запрашиваю пост...")
        if post_to_channel("утренняя мотивация"):
            bot.send_message(message.chat.id, "✅ Пост отправлен в канал!")
        else:
            bot.send_message(message.chat.id, "❌ Ошибка отправки. Проверьте логи.")
    else:
        bot.send_message(message.chat.id, "⛔ У вас нет прав для этой команды.")

@bot.message_handler(commands=['testpost'])
def test_post(message):
    if message.chat.id in ADMIN_IDS:
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
    else:
        bot.send_message(message.chat.id, "⛔ У вас нет прав для этой команды.")

@bot.message_handler(commands=['testlink'])
def send_test_link(message):
    if message.chat.id in ADMIN_IDS:
        topics = list(TEST_TOPICS.keys())
        text = "📋 Ссылки для ежедневных тестов:\n\n"
        bot_username = bot.get_me().username
        for topic in topics:
            text += f"📌 {topic.title()}: `https://t.me/{bot_username}?start=daily_{topic}_ID`\n"
        text += "\nВместо ID подставьте ID теста из базы"
        bot.send_message(message.chat.id, text, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "⛔ У вас нет прав для этой команды.")

# === ПЛАНИРОВЩИК ===
scheduler = BackgroundScheduler()

def post_morning():
    post_to_channel("утренняя мотивация")

def post_daily_test_job():
    post_daily_test()

def post_success():
    post_to_channel("финансы и успех")

scheduler.add_job(post_morning, 'cron', hour=8, minute=0)
scheduler.add_job(post_daily_test_job, 'cron', hour=10, minute=0)
scheduler.add_job(post_success, 'cron', hour=19, minute=0)
scheduler.start()
logger.info("✅ Планировщик запущен")

# === СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ===
user_test_data = {}

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
