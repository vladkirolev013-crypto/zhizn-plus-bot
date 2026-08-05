import telebot
import requests
import os
import json
import time
import logging
import base64
import sys

# ============================================
# 1. НАСТРОЙКИ
# ============================================

BOT_TOKEN = "8799965983:AAG5cvQiwSMy9KAy9WlAlv-wWTrokLqb2Iw"
GIGA_CLIENT_ID = "019fc7a2-8d46-70cb-9028-fcfc5a1d4d0e"
GIGA_CLIENT_SECRET = "MDE5ZmM3YTItOGQ0Ni03MGNiLTkwMjgtZmNmYzVhMWQ0ZDBlOjljMmUzNTI3LWI3NzAtNDU0NS1iMTFmLTBiZDljNDMxNWU1Mw=="

# ============================================
# 2. ЛОГИРОВАНИЕ (КАЖДЫЙ ШАГ)
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

print("\n" + "="*60)
print("🔍 ЗАПУСК ДИАГНОСТИКИ БОТА")
print("="*60 + "\n")

# ============================================
# 3. ШАГ 1: ПРОВЕРКА ТОКЕНА БОТА
# ============================================

logger.info("ШАГ 1: ПРОВЕРКА ТОКЕНА БОТА")

try:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        bot_data = response.json()
        logger.info(f"✅ Токен бота РАБОТАЕТ! Бот: @{bot_data['result']['username']}")
    else:
        logger.error(f"❌ Токен бота НЕ РАБОТАЕТ! Статус: {response.status_code}")
        sys.exit(1)
except Exception as e:
    logger.error(f"❌ Ошибка при проверке токена: {e}")
    sys.exit(1)

print("\n" + "-"*60 + "\n")

# ============================================
# 4. ШАГ 2: ПРОВЕРКА КЛЮЧЕЙ GIGACHAT
# ============================================

logger.info("ШАГ 2: ПРОВЕРКА КЛЮЧЕЙ GIGACHAT")

if not GIGA_CLIENT_ID or not GIGA_CLIENT_SECRET:
    logger.error("❌ Client ID или Client Secret пустые!")
    sys.exit(1)
else:
    logger.info(f"✅ Client ID: {GIGA_CLIENT_ID[:20]}...")
    logger.info(f"✅ Client Secret: {GIGA_CLIENT_SECRET[:20]}...")

print("\n" + "-"*60 + "\n")

# ============================================
# 5. ШАГ 3: ПОЛУЧЕНИЕ ТОКЕНА GIGACHAT
# ============================================

logger.info("ШАГ 3: ПОЛУЧЕНИЕ ТОКЕНА GIGACHAT")

def get_giga_token():
    try:
        auth_string = f"{GIGA_CLIENT_ID}:{GIGA_CLIENT_SECRET}"
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        
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
        
        logger.info(f"📡 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            if token:
                logger.info("✅ ТОКЕН GIGACHAT ПОЛУЧЕН!")
                return token
            else:
                logger.error(f"❌ Токен не найден в ответе: {data}")
                return None
        else:
            logger.error(f"❌ Ошибка {response.status_code}: {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Исключение: {e}")
        return None

giga_token = get_giga_token()

if giga_token:
    logger.info("✅ ШАГ 3 УСПЕШНО ЗАВЕРШЕН")
else:
    logger.error("❌ ШАГ 3 ПРОВАЛЕН - токен GigaChat не получен")
    sys.exit(1)

print("\n" + "-"*60 + "\n")

# ============================================
# 6. ШАГ 4: ПРОВЕРКА ЗАПРОСА К GIGACHAT
# ============================================

logger.info("ШАГ 4: ПРОВЕРКА ЗАПРОСА К GIGACHAT")

def ask_giga_test():
    try:
        token = giga_token
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "Ты - помощник. Ответь коротко."},
                {"role": "user", "content": "Скажи 'OK'"}
            ],
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        logger.info("📤 Отправка тестового запроса к GigaChat API...")
        start_time = time.time()
        
        response = requests.post(
            'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60,
            verify=False
        )
        
        elapsed = time.time() - start_time
        logger.info(f"⏱ Время ответа: {elapsed:.2f} сек")
        logger.info(f"📡 Статус: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            logger.info(f"📄 Ответ GigaChat: {content}")
            
            if content and len(content) > 0:
                logger.info("✅ ЗАПРОС К GIGACHAT РАБОТАЕТ!")
                return True
            else:
                logger.error("❌ Пустой ответ от GigaChat")
                return False
        else:
            logger.error(f"❌ Ошибка {response.status_code}: {response.text[:300]}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Исключение: {e}")
        return False

giga_works = ask_giga_test()

if giga_works:
    logger.info("✅ ШАГ 4 УСПЕШНО ЗАВЕРШЕН")
else:
    logger.error("❌ ШАГ 4 ПРОВАЛЕН - GigaChat не отвечает")
    sys.exit(1)

print("\n" + "-"*60 + "\n")

# ============================================
# 7. ШАГ 5: ПРОВЕРКА ОТПРАВКИ СООБЩЕНИЯ
# ============================================

logger.info("ШАГ 5: ПРОВЕРКА ОТПРАВКИ СООБЩЕНИЯ В TELEGRAM")

def send_test_message():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": 8746212340,
            "text": "🔍 ДИАГНОСТИКА ЗАВЕРШЕНА!\n\n✅ Токен бота: OK\n✅ Токен GigaChat: OK\n✅ Запрос к GigaChat: OK\n\nБот готов к работе!",
            "parse_mode": "HTML"
        }
        
        logger.info("📤 Отправка тестового сообщения...")
        response = requests.post(url, json=data, timeout=30)
        
        if response.status_code == 200:
            logger.info("✅ Тестовое сообщение ОТПРАВЛЕНО!")
            return True
        else:
            logger.error(f"❌ Ошибка отправки: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Исключение: {e}")
        return False

send_ok = send_test_message()

print("\n" + "="*60)
print("📊 ИТОГИ ДИАГНОСТИКИ")
print("="*60)

if giga_works and send_ok:
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
    print("✅ GigaChat работает!")
    print("✅ Бот работает!")
    print("\n🚀 МОЖНО ЗАПУСКАТЬ ПОЛНУЮ ВЕРСИЮ БОТА!")
else:
    print("\n❌ ЕСТЬ ПРОБЛЕМЫ:")
    if not giga_works:
        print("❌ GigaChat не отвечает")
    if not send_ok:
        print("❌ Не удалось отправить сообщение")
