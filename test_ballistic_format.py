"""
Разовая проверка нового формата поста о баллистике.
"""

import os
import requests

bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not bot_token or not chat_id:
    raise SystemExit("Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

example_original_text = "Загроза застосування балістичного озброєння з північного сходу"

caption = "\n\n".join([
    "⚠️⚠️ <b>УВАГА! Балістика!</b>",
    example_original_text,
])

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
resp = requests.post(url, data={
    "chat_id": chat_id,
    "text": caption,
    "parse_mode": "HTML",
    "disable_web_page_preview": "true",
})

print("Status code:", resp.status_code)
print("Response:", resp.text)
