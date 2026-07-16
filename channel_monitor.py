"""
Мониторинг официального Telegram-канала Повітряних Сил ЗСУ (@kpszsu) в реальном
времени и пересылка в свой канал сообщений, где упоминается баллистическая угроза.
"""

import os
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION_STRING"]

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "kpszsu")

CHANNEL_NAME = "Українські News"
CHANNEL_LINK = "https://t.me/ukrainenews68"

BALLISTIC_KEYWORDS = [
    "балістик", "балістичн", "аеробалістичн", "орєшник", "кинджал",
]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }, timeout=20)
    if not resp.ok:
        print(f"[error] Telegram API ответил {resp.status_code}: {resp.text}")
    return resp.ok


def build_caption(original_text: str) -> str:
    lines = [
        "⚠️⚠️ <b>УВАГА! Балістика!</b>",
        original_text.strip(),
    ]
    return "\n\n".join(lines)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    text = event.raw_text or ""
    lowered = text.lower()

    if any(k in lowered for k in BALLISTIC_KEYWORDS):
        caption = build_caption(text)
        ok = send_to_telegram(caption)
        print(f"[{'ok' if ok else 'FAIL'}] Переслано повідомлення про балістику")
    else:
        print("[skip] Повідомлення без згадки балістики, пропущено")


def main():
    print(f"Стартуємо прослуховування каналу @{SOURCE_CHANNEL}...")
    client.start()
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
