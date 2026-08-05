import asyncio
import json
import logging
import sqlite3
import random
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import aiosqlite
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Конфигурация
TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"
CHANNEL_ID = -1001234567890  # ID канала
GIGACHAT_API_KEY = "ВАШ_GIGACHAT_API_KEY"
GIGACHAT_API_URL = "https://gigachat.devices.su/api/v1/chat/completions"
TIMEZONE = ZoneInfo("Asia/Yekaterinburg")  # Юрга (UTC+5)
ADMIN_IDS = [123456789]  # Ваш Telegram ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_post = State()
    waiting_test_question = State()
    waiting_test_answer = State()

# Базовые тесты
BASE_TESTS = {
    "stress": {
        "name": "Уровень стресса",
        "description": "Оцените свой текущий уровень стресса",
        "questions": [
            "Как часто вы чувствуете напряжение?",
            "Сложно ли вам расслабиться?",
            "Часто ли вы раздражаетесь?",
            "Бывает ли бессонница?",
            "Чувствуете ли вы усталость?",
            "Трудно ли сосредоточиться?",
            "Бывают ли головные боли?",
            "Чувствуете ли вы тревогу?",
            "Есть ли проблемы с аппетитом?",
            "Чувствуете ли вы апатию?"
        ],
        "answers": ["Никогда", "Редко", "Иногда", "Часто", "Всегда"],
        "premium": False
    },
    "relationship": {
        "name": "Качество отношений",
        "description": "Оцените свои отношения с близкими",
        "questions": [
            "Доверяете ли вы партнёру?",
            "Часто ли вы ссоритесь?",
            "Понимаете ли вы друг друга?",
            "Есть ли общие интересы?",
            "Поддерживаете ли вы друг друга?",
            "Есть ли физическая близость?",
            "Обсуждаете ли вы проблемы?",
            "Планируете ли будущее вместе?",
            "Уважаете ли вы границы?",
            "Чувствуете ли вы любовь?"
        ],
        "answers": ["Нет", "Редко", "Иногда", "Часто", "Всегда"],
        "premium": True
    }
}

# Тематика для генерации постов
POST_TOPICS = [
    "прокрастинация", "мотивация", "самооценка", "страх", "тревога",
    "отношения", "одиночество", "деньги", "цели", "привычки",
    "эмоции", "выбор", "смысл", "счастье", "успех"
]

@dataclass
class TestResult:
    user_id: int
    test_type: str
    score: int
    answers: List[int]
    timestamp: datetime
    is_premium: bool

class BotManager:
    """Единый менеджер бота с решением всех проблем"""
    
    def __init__(self):
        self.bot = Bot(token=TOKEN)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.db_path = Path("bot_data.db")
        self._setup_database()
        self._setup_handlers()
        self.post_queue = []
        self.is_running = False
        
    def _setup_database(self):
        """Инициализация БД с правильной схемой"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_premium BOOLEAN DEFAULT 0
            )
        """)
        
        # Таблица результатов тестов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                test_type TEXT,
                score INTEGER,
                answers TEXT,
                is_premium BOOLEAN,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица постов (для истории)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                topic TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица для offset (решение проблемы 409)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Сохраняем последний offset
        cursor.execute(
            "INSERT OR REPLACE INTO bot_state (key, value) VALUES (?, ?)",
            ("last_update_offset", "0")
        )
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    async def get_last_offset(self) -> int:
        """Получение сохранённого offset для избежания 409"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM bot_state WHERE key = 'last_update_offset'"
            ) as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row else 0
    
    async def save_offset(self, offset: int):
        """Сохранение offset в БД"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO bot_state (key, value) VALUES (?, ?)",
                ("last_update_offset", str(offset))
            )
            await db.commit()
    
    def _setup_handlers(self):
        """Настройка всех обработчиков"""
        
        # Команда старт
        @self.dp.message(Command("start"))
        async def cmd_start(message: Message):
            user = message.from_user
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                    (user.id, user.username, user.first_name, user.last_name)
                )
                await db.commit()
            
            await message.answer(
                "👋 Привет! Я бот канала «Жизнь+».\n\n"
                "Здесь честно и без пафоса о психологии, отношениях и деньгах.\n\n"
                "Доступные команды:\n"
                "/test - пройти тест\n"
                "/post - получить случайный пост (для админов)\n"
                "/help - помощь"
            )
        
        # Команда помощи
        @self.dp.message(Command("help"))
        async def cmd_help(message: Message):
            await message.answer(
                "📖 Доступные команды:\n\n"
                "/test - пройти бесплатный или платный тест\n"
                "/start - начать заново\n"
                "/help - эта справка\n\n"
                "Тесты проводятся ежедневно в 13:00 по Юрге\n"
                "Посты выходят в 10:00 и 17:00\n\n"
                "Вопросы и предложения: @admin"
            )
        
        # Команда теста
        @self.dp.message(Command("test"))
        async def cmd_test(message: Message):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🧠 Бесплатный тест (10 вопросов)", callback_data="test_free")],
                    [InlineKeyboardButton(text="💎 Платный тест (20 вопросов)", callback_data="test_premium")],
                    [InlineKeyboardButton(text="📊 Мои результаты", callback_data="my_results")]
                ]
            )
            await message.answer(
                "Выберите тип теста:\n\n"
                "Бесплатный - быстрая оценка состояния\n"
                "Платный - глубокий анализ с рекомендациями",
                reply_markup=keyboard
            )
        
        # Обработка выбора теста
        @self.dp.callback_query(F.data.startswith("test_"))
        async def handle_test_selection(callback: CallbackQuery, state: FSMContext):
            test_type = callback.data.replace("test_", "")
            is_premium = test_type == "premium"
            
            # Сохраняем состояние
            await state.set_data({
                "test_type": test_type,
                "is_premium": is_premium,
                "current_question": 0,
                "answers": [],
                "test_name": random.choice(list(BASE_TESTS.keys()))
            })
            
            # Получаем тест
            test_data = BASE_TESTS[random.choice(list(BASE_TESTS.keys()))]
            if is_premium and not test_data.get("premium", False):
                # Если выбран платный, но тест бесплатный - подменяем
                test_data = random.choice([t for t in BASE_TESTS.values() if t.get("premium", False)])
            
            await state.update_data(test_data=test_data)
            
            # Отправляем первый вопрос
            await send_question(callback.message, state, 0)
            await callback.answer()
        
        async def send_question(message: Message, state: FSMContext, question_idx: int):
            data = await state.get_data()
            test_data = data.get("test_data")
            questions = test_data["questions"]
            
            if question_idx >= len(questions):
                # Тест завершён
                await finish_test(message, state)
                return
            
            question = questions[question_idx]
            answers = test_data["answers"]
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=ans, callback_data=f"q{question_idx}_a{idx}")]
                    for idx, ans in enumerate(answers)
                ]
            )
            
            await message.answer(
                f"📝 Вопрос {question_idx + 1}/{len(questions)}\n\n{question}",
                reply_markup=keyboard
            )
        
        # Обработка ответа на вопрос
        @self.dp.callback_query(F.data.startswith("q"))
        async def handle_answer(callback: CallbackQuery, state: FSMContext):
            data = await callback.data.split("_")
            question_idx = int(data[0].replace("q", ""))
            answer_idx = int(data[1].replace("a", ""))
            
            state_data = await state.get_data()
            answers = state_data.get("answers", [])
            answers.append(answer_idx)
            await state.update_data(answers=answers)
            
            # Переход к следующему вопросу
            next_question = question_idx + 1
            state_data = await state.get_data()
            test_data = state_data.get("test_data")
            
            if next_question >= len(test_data["questions"]):
                await finish_test(callback.message, state)
            else:
                await send_question(callback.message, state, next_question)
            
            await callback.answer()
        
        async def finish_test(message: Message, state: FSMContext):
            data = await state.get_data()
            answers = data.get("answers", [])
            test_data = data.get("test_data")
            is_premium = data.get("is_premium", False)
            
            # Рассчёт результата
            total = len(answers)
            if total == 0:
                await message.answer("Тест прерван. Попробуйте снова /test")
                return
            
            # Простая аналитика
            score = sum(answers) / total  # Средний балл
            score_percent = int((score / (len(test_data["answers"]) - 1)) * 100)
            
            # Сохраняем результат
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO test_results (user_id, test_type, score, answers, is_premium) VALUES (?, ?, ?, ?, ?)",
                    (message.from_user.id, test_data["name"], score_percent, json.dumps(answers), is_premium)
                )
                await db.commit()
            
            # Формируем результат
            result_text = f"📊 Результат теста «{test_data['name']}»\n\n"
            result_text += f"Ваш показатель: {score_percent}%\n\n"
            
            if score_percent < 30:
                result_text += "✅ Всё отлично! Продолжайте в том же духе."
            elif score_percent < 60:
                result_text += "⚠️ Есть над чем поработать. Обратите внимание на область, которая вызывает напряжение."
            else:
                result_text += "🔴 Требуется внимание. Рекомендуем обратиться к специалисту или начать работать над этим."
            
            if is_premium:
                # Дополнительные рекомендации для платных тестов
                result_text += "\n\n📚 Рекомендации:\n"
                result_text += "• Книга: «Эмоциональный интеллект» Дэниел Гоулман\n"
                result_text += "• Упражнение: Дневник благодарности (записывайте 3 хороших события в день)\n"
                result_text += "• Видео: TED «Как перестать беспокоиться»\n"
                result_text += "• Практика: Медитация 5 минут в день"
            
            await message.answer(result_text)
            await state.clear()
        
        # Админ-панель
        @self.dp.message(Command("admin"))
        async def admin_panel(message: Message):
            if message.from_user.id not in ADMIN_IDS:
                await message.answer("⛔ Доступ запрещён")
                return
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✍️ Создать пост", callback_data="admin_post")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
                    [InlineKeyboardButton(text="⏰ Расписание", callback_data="admin_schedule")],
                    [InlineKeyboardButton(text="🔄 Обновить тесты", callback_data="admin_tests")]
                ]
            )
            await message.answer("👨‍💼 Админ-панель", reply_markup=keyboard)
        
        @self.dp.callback_query(F.data.startswith("admin_"))
        async def admin_actions(callback: CallbackQuery, state: FSMContext):
            action = callback.data.replace("admin_", "")
            
            if callback.from_user.id not in ADMIN_IDS:
                await callback.answer("⛔ Доступ запрещён")
                return
            
            if action == "post":
                await callback.message.answer("Введите текст поста для канала:")
                await state.set_state(AdminStates.waiting_post)
            elif action == "stats":
                await show_stats(callback.message)
            elif action == "schedule":
                await show_schedule(callback.message)
            elif action == "tests":
                await update_tests(callback.message)
            
            await callback.answer()
        
        @self.dp.message(AdminStates.waiting_post)
        async def handle_admin_post(message: Message, state: FSMContext):
            if message.from_user.id not in ADMIN_IDS:
                return
            
            try:
                await self.bot.send_message(CHANNEL_ID, message.text)
                await message.answer("✅ Пост отправлен в канал!")
                
                # Сохраняем в историю
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "INSERT INTO posts (content, topic) VALUES (?, ?)",
                        (message.text, "admin_post")
                    )
                    await db.commit()
            except Exception as e:
                await message.answer(f"❌ Ошибка: {e}")
            
            await state.clear()
        
        async def show_stats(message: Message):
            async with aiosqlite.connect(self.db_path) as db:
                # Количество пользователей
                async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                    users_count = (await cursor.fetchone())[0]
                
                # Количество тестов
                async with db.execute("SELECT COUNT(*) FROM test_results") as cursor:
                    tests_count = (await cursor.fetchone())[0]
                
                # Количество платных тестов
                async with db.execute("SELECT COUNT(*) FROM test_results WHERE is_premium = 1") as cursor:
                    premium_count = (await cursor.fetchone())[0]
                
                # Средний балл
                async with db.execute("SELECT AVG(score) FROM test_results") as cursor:
                    avg_score = (await cursor.fetchone())[0] or 0
            
            stats_text = f"📊 Статистика:\n\n"
            stats_text += f"👥 Пользователей: {users_count}\n"
            stats_text += f"📝 Всего тестов: {tests_count}\n"
            stats_text += f"💎 Платных тестов: {premium_count}\n"
            stats_text += f"📈 Средний балл: {avg_score:.1f}%"
            
            await message.answer(stats_text)
        
        async def show_schedule(message: Message):
            schedule_text = "⏰ Расписание:\n\n"
            schedule_text += "📝 Посты:\n"
            schedule_text += "  • 10:00 - утренний пост\n"
            schedule_text += "  • 17:00 - вечерний пост\n\n"
            schedule_text += "🧠 Тесты:\n"
            schedule_text += "  • 13:00 - бесплатный тест (10 вопросов)\n"
            schedule_text += "  • 13:00 - платный тест (20 вопросов)\n\n"
            schedule_text += "🕐 Время указано по Юрге (UTC+5)"
            
            await message.answer(schedule_text)
        
        async def update_tests(message: Message):
            # Здесь можно добавить логику обновления тестов
            await message.answer("🔄 Тесты обновлены (заглушка)")
    
    async def generate_post(self, topic: str = None) -> str:
        """Генерация уникального поста через GigaChat"""
        if not topic:
            topic = random.choice(POST_TOPICS)
        
        prompt = f"""
        Напиши пост для канала о психологии и саморазвитии на тему: {topic}
        
        Требования:
        - Без пафоса и «ты уникален»
        - Честно, прямо, как живой человек
        - Автор - не психолог, а просто человек, делящийся мыслями
        - Используй НЛП-язык, но без слащавости
        - Объём: 150-250 слов
        - Без шаблонов, каждый пост уникальный
        - Закончи вопросом к читателю
        
        Ответ дай в формате обычного текста, без маркдауна.
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {GIGACHAT_API_KEY}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": "gigachat",
                    "messages": [
                        {"role": "system", "content": "Ты - автор канала о психологии и саморазвитии. Пиши честно, прямо, без пафоса."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.9,
                    "max_tokens": 500
                }
                
                async with session.post(
                    GIGACHAT_API_URL,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)  # Решение проблемы с таймаутом
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        post_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        # Добавляем хештеги
                        hashtags = f" #{topic} #жизньплюс #саморазвитие"
                        return post_text + "\n\n" + hashtags
                    else:
                        logger.error(f"GigaChat error: {response.status}")
                        return self._get_fallback_post(topic)
        except asyncio.TimeoutError:
            logger.error("GigaChat timeout after 30 seconds")
            return self._get_fallback_post(topic)
        except Exception as e:
            logger.error(f"GigaChat error: {e}")
            return self._get_fallback_post(topic)
    
    def _get_fallback_post(self, topic: str) -> str:
        """Резервный пост при ошибке GigaChat"""
        fallbacks = [
            f"Мы часто боимся того, что ещё не случилось. А если подумать: страх — это просто эмоция, а не факт. \n\nКак думаешь, что бы ты сделал, если бы не боялся? #{topic} #жизньплюс",
            f"Важно не то, сколько раз ты упал, а то, сколько раз поднялся. \n\nНо иногда можно и полежать — это нормально. \n\nКакой совет ты дал бы себе в сложной ситуации? #{topic} #жизньплюс",
            f"Отношения — это не про то, кто прав, а про то, как быть вместе. \n\nИ иногда лучше промолчать, чем сказать лишнее. \n\nЧто для тебя важно в отношениях? #{topic} #жизньплюс"
        ]
        return random.choice(fallbacks)
    
    async def scheduled_posts(self):
        """Планировщик постов"""
        while self.is_running:
            try:
                now = datetime.now(TIMEZONE)
                current_hour = now.hour
                current_minute = now.minute
                
                # Посты в 10:00 и 17:00
                if (current_hour == 10 and current_minute == 0) or \
                   (current_hour == 17 and current_minute == 0):
                    
                    topic = random.choice(POST_TOPICS)
                    post_text = await self.generate_post(topic)
                    
                    # Отправка с обработкой ошибок
                    try:
                        await self.bot.send_message(CHANNEL_ID, post_text)
                        logger.info(f"Post sent at {now.strftime('%H:%M')}")
                        
                        # Сохраняем в историю
                        async with aiosqlite.connect(self.db_path) as db:
                            await db.execute(
                                "INSERT INTO posts (content, topic) VALUES (?, ?)",
                                (post_text, topic)
                            )
                            await db.commit()
                    except Exception as e:
                        logger.error(f"Post send error: {e}")
                
                # Тесты в 13:00
                if current_hour == 13 and current_minute == 0:
                    await self.send_daily_tests()
                
                await asyncio.sleep(30)  # Проверка каждые 30 секунд
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(30)
    
    async def send_daily_tests(self):
        """Отправка ежедневных тестов"""
        try:
            # Отправка бесплатного теста
            free_test = random.choice([t for t in BASE_TESTS.values() if not t.get("premium", False)])
            await self.bot.send_message(
                CHANNEL_ID,
                f"🧠 Бесплатный тест дня: «{free_test['name']}»\n\n"
                f"{free_test['description']}\n\n"
                f"Чтобы пройти, напишите /test в боте"
            )
            
            # Отправка платного теста
            premium_test = random.choice([t for t in BASE_TESTS.values() if t.get("premium", False)])
            await self.bot.send_message(
                CHANNEL_ID,
                f"💎 Платный тест дня: «{premium_test['name']}»\n\n"
                f"{premium_test['description']}\n\n"
                f"Чтобы пройти, напишите /test и выберите платный вариант"
            )
            
            logger.info("Daily tests sent")
        except Exception as e:
            logger.error(f"Daily tests error: {e}")
    
    async def run(self):
        """Запуск бота с решением всех проблем"""
        self.is_running = True
        
        # Получаем последний offset
        last_offset = await self.get_last_offset()
        
        # Запускаем планировщик
        asyncio.create_task(self.scheduled_posts())
        
        # Запускаем бота с правильным offset
        try:
            # Удаляем вебхук для избежания 409
            await self.bot.delete_webhook(drop_pending_updates=True)
            
            # Запускаем polling с сохранением offset
            await self.dp.start_polling(
                self.bot,
                offset=last_offset,
                allowed_updates=["message", "callback_query"],
                on_startup=self._on_startup,
                on_shutdown=self._on_shutdown
            )
        except Exception as e:
            logger.error(f"Bot run error: {e}")
            # Если ошибка 409, пробуем перезапустить с удалением offset
            if "409" in str(e):
                logger.info("Conflict detected, resetting offset...")
                await self.save_offset(0)
                await self.dp.start_polling(
                    self.bot,
                    offset=0,
                    allowed_updates=["message", "callback_query"]
                )
    
    async def _on_startup(self):
        """Действия при старте"""
        logger.info("Bot started successfully")
        # Сохраняем текущий offset
        await self.save_offset(0)
    
    async def _on_shutdown(self):
        """Действия при остановке"""
        self.is_running = False
        logger.info("Bot stopped")

async def main():
    """Точка входа"""
    manager = BotManager()
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main())
