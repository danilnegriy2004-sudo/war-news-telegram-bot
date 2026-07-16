"""
Мониторинг официального Telegram-канала Повітряних Сил ЗСУ (@kpszsu) в реальном
времени и пересылка в свой канал сообщений про баллистику и шахеды.
"""

import os
import time
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION_STRING"]

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "kpszsu")

CATEGORIES = {
    "ballistic": {
        "keywords": ["балістик", "балістичн", "аеробалістичн", "орєшник", "кинджал"],
        "header": "⚠️⚠️ <b>УВАГА! Балістика!</b>",
        "cooldown_seconds": 0,
    },
    "shahed": {
        "keywords": ["шахед", "shahed", "гербер", "італмас"],
        "header": "🛩️ <b>Атака дронами (Shahed)</b>",
        "cooldown_seconds": 60 * 60,
    },
}

last_sent_at = {name: 0.0 for name in CATEGORIES}

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


def build_caption(header: str, original_text: str) -> str:
    lines = [header, original_text.strip()]
    return "\n\n".join(lines)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    text = event.raw_text or ""
    lowered = text.lower()
    now = time.time()

    matched_any = False
    for name, cfg in CATEGORIES.items():
        if any(k in lowered for k in cfg["keywords"]):
            matched_any = True
            cooldown = cfg["cooldown_seconds"]
            elapsed = now - last_sent_at[name]

            if cooldown and elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                print(f"[cooldown] '{name}' пропущено, ще {remaining}с паузи")
                continue

            caption = build_caption(cfg["header"], text)
            ok = send_to_telegram(caption)
            last_sent_at[name] = now
            print(f"[{'ok' if ok else 'FAIL'}] Переслано повідомлення категорії '{name}'")

    if not matched_any:
        print("[skip] Повідомлення без відповідних ключових слів, пропущено")


def main():
    print(f"Стартуємо прослуховування каналу @{SOURCE_CHANNEL}...")
    client.start()
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
