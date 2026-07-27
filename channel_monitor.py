"""
Мониторинг официального Telegram-канала Повітряних Сил ЗСУ (@kpszsu) в реальном
времени. Постим ТОЛЬКО баллистику — сразу, каждый случай отдельным постом.

Нужные переменные окружения:
- API_ID, API_HASH, TELEGRAM_SESSION_STRING (см. generate_session.py)
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Необязательные (для анимированного Premium-эмодзи, см. get_emoji_id.py):
- EMOJI_ID_BALLISTIC
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

EMOJI_ID_BALLISTIC = os.environ.get("EMOJI_ID_BALLISTIC")  # опционально

BALLISTIC_KEYWORDS = ["балістик", "балістичн", "аеробалістичн", "орєшник", "кинджал"]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def emoji_tag(unicode_emoji: str, custom_id):
    """Оборачивает эмодзи в tg-emoji, если задан custom_id (анимация для Premium),
    иначе просто возвращает обычный юникод-эмодзи."""
    if custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{unicode_emoji}</tg-emoji>'
    return unicode_emoji


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


def build_ballistic_caption(original_text: str) -> str:
    icon = emoji_tag("⚡", EMOJI_ID_BALLISTIC)
    lines = [
        f"{icon} <b>БАЛІСТИЧНА ЗАГРОЗА</b>",
        "⬛⬛⬛⬛⬛⬛⬛⬛",
        "",
        f"<blockquote>🚀 {original_text.strip()}</blockquote>",
        "",
        "🩹 Будьте обережні❗",
    ]
    return "\n".join(lines)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    text = event.raw_text or ""
    lowered = text.lower()

    if any(k in lowered for k in BALLISTIC_KEYWORDS):
        caption = build_ballistic_caption(text)
        ok = send_to_telegram(caption)
        print(f"[{'ok' if ok else 'FAIL'}] Балістика надіслана")
    else:
        print("[skip] Повідомлення без згадки балістики, пропущено")


def main():
    print(f"Стартуємо прослуховування каналу @{SOURCE_CHANNEL}...")
    client.start()
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
