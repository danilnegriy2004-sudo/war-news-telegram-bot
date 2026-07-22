"""
Мониторинг официального Telegram-канала Повітряних Сил ЗСУ (@kpszsu) в реальном
времени. Постим:
- баллистику — сразу, каждый случай отдельным постом
- КАБ / Іскандер / дрони — копим и шлём ОДНИМ сводным постом раз в 2 часа
  (если за эти 2 часа ничего не было — молчим, спама нет)

Нужные переменные окружения:
- API_ID, API_HASH, TELEGRAM_SESSION_STRING (см. generate_session.py)
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Необязательные (для анимированных Premium-эмодзи, см. get_emoji_id.py):
- EMOJI_ID_BALLISTIC
- EMOJI_ID_KAB
"""

import os
import json
import time
import asyncio
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION_STRING"]

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "kpszsu")
KYIV_TZ = ZoneInfo("Europe/Kyiv")

EMOJI_ID_BALLISTIC = os.environ.get("EMOJI_ID_BALLISTIC")  # опционально
EMOJI_ID_KAB = os.environ.get("EMOJI_ID_KAB")  # опционально

BALLISTIC_KEYWORDS = ["балістик", "балістичн", "аеробалістичн", "орєшник", "кинджал"]
KAB_KEYWORDS = ["каб", "іскандер", "искандер", "шахед", "shahed", "гербер", "італмас", "бпла", "дрон"]

KAB_FLUSH_INTERVAL = 2 * 60 * 60  # раз в 2 часа
STATE_FILE = "channel_monitor_state.json"
FLUSH_CHECK_INTERVAL = 300  # проверяем раз в 5 минут, не пора ли слать сводку


def emoji_tag(unicode_emoji: str, custom_id):
    """Оборачивает эмодзи в tg-emoji, если задан custom_id (анимация для Premium),
    иначе просто возвращает обычный юникод-эмодзи."""
    if custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{unicode_emoji}</tg-emoji>'
    return unicode_emoji


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"kab_batch": {"items": [], "last_flush": time.time()}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("kab_batch", {"items": [], "last_flush": time.time()})
            return data
    except Exception:
        return {"kab_batch": {"items": [], "last_flush": time.time()}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


state = load_state()

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


def build_kab_batch_caption(items: list) -> str:
    icon = emoji_tag("✈️", EMOJI_ID_KAB)
    now_str = datetime.now(KYIV_TZ).strftime("%H:%M")
    lines = [
        f"{icon} <b>ЗВЕДЕННЯ ЗА 2 ГОДИНИ</b> {icon}",
        "КАБ / Іскандер / Дрони",
        "⬛⬛⬛⬛⬛⬛⬛⬛",
        "",
        f"Зафіксовано випадків: {len(items)}",
        "",
    ]
    for item in items:
        lines.append(f"• {item['time']} — {item['text']}")
    lines.append("")
    lines.append(f"📡 Повітряні сили ЗСУ  •  🕐 {now_str}")
    return "\n".join(lines)


def check_kab_flush():
    batch = state["kab_batch"]
    elapsed = time.time() - batch.get("last_flush", time.time())
    if batch["items"] and elapsed >= KAB_FLUSH_INTERVAL:
        caption = build_kab_batch_caption(batch["items"])
        ok = send_to_telegram(caption)
        print(f"[{'ok' if ok else 'FAIL'}] Надіслано зведення КАБ/Іскандер/дрони ({len(batch['items'])} випадків)")
        batch["items"] = []
        batch["last_flush"] = time.time()
        save_state(state)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    text = event.raw_text or ""
    lowered = text.lower()

    if any(k in lowered for k in BALLISTIC_KEYWORDS):
        caption = build_ballistic_caption(text)
        ok = send_to_telegram(caption)
        print(f"[{'ok' if ok else 'FAIL'}] Балістика надіслана")

    elif any(k in lowered for k in KAB_KEYWORDS):
        now_str = datetime.now(KYIV_TZ).strftime("%H:%M")
        snippet = text.strip().split("\n")[0][:100]
        state["kab_batch"]["items"].append({"time": now_str, "text": snippet})
        save_state(state)
        print(f"[batch] Додано до зведення КАБ/Іскандер/дрони: {snippet}")

    else:
        print("[skip] Повідомлення без відповідних ключових слів, пропущено")

    check_kab_flush()


async def periodic_flush_checker():
    while True:
        await asyncio.sleep(FLUSH_CHECK_INTERVAL)
        check_kab_flush()


def main():
    print(f"Стартуємо прослуховування каналу @{SOURCE_CHANNEL}...")
    client.start()
    client.loop.create_task(periodic_flush_checker())
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
