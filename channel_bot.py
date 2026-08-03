# === ПРОВЕРКА ПРАВ ===
def check_bot_in_channel():
    """Проверяет, может ли бот отправлять сообщения в канал"""
    try:
        bot_id = bot.get_me().id
        member = bot.get_chat_member(CHANNEL_ID, bot_id)
        logger.info(f"Статус бота в канале: {member.status}")
        
        if member.status in ['administrator', 'creator']:
            logger.info("✅ Бот имеет права администратора")
            return True
        elif member.status == 'member':
            logger.warning("⚠️ Бот просто участник, не может постить")
            return False
        else:
            logger.error(f"❌ Бот не в канале! Статус: {member.status}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки прав: {e}")
        logger.error("Убедитесь, что:")
        logger.error(f"1. Бот добавлен в канал {CHANNEL_ID}")
        logger.error("2. Бот имеет права на отправку сообщений")
        logger.error("3. CHANNEL_ID указан правильно")
        return False

# === ГЕНЕРАЦИЯ ПОСТА С ЗАПАСНЫМ ВАРИАНТОМ ===
def generate_post(theme):
    """Генерирует пост с fallback при ошибке"""
    try:
        logger.info(f"Генерирую пост на тему: {theme}")
        
        system = """Ты — позитивный психолог и мотивационный спикер. Пиши вдохновляющие посты для Telegram-канала о жизни и саморазвитии."""
        user = f"""Напиши пост для Telegram на тему: {theme}.
        Требования:
        - Заголовок с эмодзи
        - Основной текст (400-600 символов)
        - Практический совет или упражнение
        - Мотивационная фраза в конце
        - 3-5 хештегов
        - Без Markdown разметки
        - Только текст"""
        
        text = ask_giga(system, user)
        
        if not text or len(text) < 50:
            raise Exception("GigaChat вернул пустой или короткий ответ")
            
        logger.info(f"✅ Пост сгенерирован: {len(text)} символов")
        return text
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        # Запасной текст
        return f"""✨ {theme.title()}

Каждый день — это новая возможность стать лучше!

🌟 Помните:
• Вы сильнее, чем думаете
• Каждый шаг имеет значение
• Верьте в свои мечты

💫 Начните сегодня с маленького доброго дела!

#жизньплюс #мотивация #саморазвитие #позитив"""

# === ОТПРАВКА ПОСТА С ПОДРОБНЫМ ЛОГИРОВАНИЕМ ===
def post_to_channel(theme):
    """Отправляет пост в канал с подробным логированием"""
    try:
        logger.info("=" * 50)
        logger.info(f"📝 ОТПРАВКА ПОСТА: {theme}")
        logger.info("=" * 50)
        
        # 1. Проверка прав
        if not check_bot_in_channel():
            error_msg = f"❌ Бот не может постить в {CHANNEL_ID}"
            logger.error(error_msg)
            return False
        
        # 2. Генерация текста
        text = generate_post(theme)
        logger.info(f"Текст готов: {len(text)} символов")
        
        # 3. Отправка
        logger.info(f"Отправляю в {CHANNEL_ID}...")
        
        # Разбиваем если текст длинный
        if len(text) > 4096:
            parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for i, part in enumerate(parts):
                bot.send_message(CHANNEL_ID, part)
                logger.info(f"Часть {i+1}/{len(parts)} отправлена")
        else:
            bot.send_message(CHANNEL_ID, text)
            logger.info("✅ Пост отправлен!")
        
        # 4. Попробуем отправить картинку отдельно
        try:
            img_path = generate_image(theme)
            if img_path:
                with open(img_path, 'rb') as photo:
                    bot.send_photo(CHANNEL_ID, photo, caption="✨ Дополнительное вдохновение")
                    logger.info("✅ Картинка отправлена")
        except Exception as e:
            logger.warning(f"Картинка не отправлена: {e}")
        
        logger.info("=" * 50)
        return True
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(traceback.format_exc())
        logger.info("=" * 50)
        return False

# === ТЕСТОВАЯ КОМАНДА С ПРОВЕРКОЙ ===
@bot.message_handler(commands=['testpost'])
def test_post(message):
    """Тестовая отправка для диагностики"""
    msg = bot.send_message(message.chat.id, "🔍 Проверяю настройки...")
    
    # Проверка 1: Бот в канале
    try:
        bot_info = bot.get_chat_member(CHANNEL_ID, bot.get_me().id)
        status = bot_info.status
        bot.edit_message_text(
            f"✅ Бот в канале: {CHANNEL_ID}\n"
            f"Статус: {status}\n"
            f"Может постить: {bot_info.can_post_messages if hasattr(bot_info, 'can_post_messages') else 'неизвестно'}",
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
    
    # Проверка 2: Отправка тестового сообщения
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
