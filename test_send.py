"""
Разовая проверка: шлёт тестовое сообщение в канал, используя те же
переменные окружения, что и alert_watcher.py.
"""

import os
import requests

bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not bot_token or not chat_id:
    raise SystemExit("Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
resp = requests.post(url, data={
    "chat_id": chat_id,
    "text": "✅ Тест: alert_watcher настроен правильно, бот может писать в канал.",
    "parse_mode": "HTML",
})

print("Status code:", resp.status_code)
print("Response:", resp.text)
