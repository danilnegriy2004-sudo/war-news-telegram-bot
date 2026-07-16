"""
Одноразовый скрипт: логинит твой Telegram-аккаунт и печатает session string,
который потом нужно сохранить как переменную окружения TELEGRAM_SESSION_STRING.

ВАЖНО: запускать только один раз, интерактивно (в Railway Console или локально).
Понадобится: номер телефона, код подтверждения из Telegram (и, если включена
двухфакторная аутентификация, пароль от неё).
"""

import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    session_string = client.session.save()
    print("\n\n===== ТВОЯ SESSION STRING (сохрани как TELEGRAM_SESSION_STRING) =====\n")
    print(session_string)
    print("\n=====================================================================\n")
