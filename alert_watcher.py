"""
Мониторинг воздушных тревог по всей Украине (alerts.in.ua), но постим ТОЛЬКО:
- баллистику — сразу, каждый случай отдельным постом
- КАБ / Іскандер / дрони — копим и шлём ОДНИМ сводным постом раз в 2 часа
  (если за эти 2 часа ничего не было — молчим, спама нет)

Обычные "просто повітряна тривога" (без этих категорий) НЕ постим — их слишком
много и это будет спамить канал.

Нужные переменные окружения:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- ALERTS_API_TOKEN
Необязательные (для анимированных Premium-эмодзи, см. get_emoji_id.py):
- EMOJI_ID_BALLISTIC
- EMOJI_ID_KAB
"""

import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

ALERTS_URL = "https://api.alerts.in.ua/v1/alerts/active.json"
STATE_FILE = "alert_state.json"

POLL_INTERVAL = 30  # секунд между проверками
KAB_FLUSH_INTERVAL = 2 * 60 * 60  # раз в 2 часа шлём сводку по КАБ/Іскандер/дрони

KYIV_TZ = ZoneInfo("Europe/Kyiv")

BALLISTIC_KEYWORDS = ["балістик", "балістичн", "ballistic", "аеробалістичн"]
KAB_KEYWORDS = ["каб", "іскандер", "искандер", "шахед", "shahed", "дрон", "бпла"]

EMOJI_ID_BALLISTIC = os.environ.get("EMOJI_ID_BALLISTIC")  # опционально
EMOJI_ID_KAB = os.environ.get("EMOJI_ID_KAB")  # опционально


def emoji_tag(unicode_emoji: str, custom_id: str | None) -> str:
    """Оборачивает эмодзи в tg-emoji, если задан custom_id (анимация для Premium),
    иначе просто возвращает обычный юникод-эмодзи."""
    if custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{unicode_emoji}</tg-emoji>'
    return unicode_emoji


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"active": {}, "kab_batch": {"items": [], "last_flush": time.time()}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("active", {})
            data.setdefault("kab_batch", {"items": [], "last_flush": time.time()})
            return data
    except Exception:
        return {"active": {}, "kab_batch": {"items": [], "last_flush": time.time()}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_active_alerts(api_token: str):
    resp = requests.get(
        ALERTS_URL,
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("alerts", [])


def send_to_telegram(bot_token: str, chat_id: str, caption: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }, timeout=20)
    if not resp.ok:
        print(f"[error] Telegram API ответил {resp.status_code}: {resp.text}")
    return resp.ok


def build_ballistic_caption(location: str, notes: str) -> str:
    icon = emoji_tag("⚠️", EMOJI_ID_BALLISTIC)
    body = notes.strip() if notes else location
    lines = [
        f"{icon} <b>БАЛІСТИЧНА ЗАГРОЗА</b>",
        "⬛⬛⬛⬛⬛⬛⬛⬛",
        "",
        f"<blockquote>🚀 {body}</blockquote>",
        "",
        "🩹 Будьте обережні❗",
    ]
    return "\n".join(lines)


def build_kab_batch_caption(items: list) -> str:
    icon = emoji_tag("🛩️", EMOJI_ID_KAB)
    now_str = datetime.now(KYIV_TZ).strftime("%H:%M")
    lines = [
        f"{icon} <b>КАБ / ІСКАНДЕР / ДРОНИ (за 2 год.)</b> {icon}",
        "▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️",
        f"Зафіксовано випадків: {len(items)}",
        "",
    ]
    for item in items:
        lines.append(f"• {item['time']} — {item['location']}")
    lines.append("")
    lines.append(f"📡 alerts.in.ua  •  🕐 {now_str}")
    return "\n".join(lines)


def categorize(notes: str):
    lowered = notes.lower()
    if any(k in lowered for k in BALLISTIC_KEYWORDS):
        return "ballistic"
    if any(k in lowered for k in KAB_KEYWORDS):
        return "kab"
    return None


def run_once(bot_token, chat_id, api_token, state):
    try:
        alerts = fetch_active_alerts(api_token)
    except Exception as e:
        print(f"[warn] Не удалось получить тревоги: {e}")
        return state

    active_now = {}
    for alert in alerts:
        uid = str(alert.get("location_uid") or alert.get("location_title"))
        active_now[uid] = alert

    previous_uids = set(state["active"].keys())
    current_uids = set(active_now.keys())
    new_uids = current_uids - previous_uids

    for uid in new_uids:
        alert = active_now[uid]
        notes = alert.get("notes") or ""
        location = alert.get("location_title", "Україна")
        category = categorize(notes)

        if category == "ballistic":
            caption = build_ballistic_caption(location, notes)
            ok = send_to_telegram(bot_token, chat_id, caption)
            print(f"[{'ok' if ok else 'FAIL'}] Балістика: {location}")

        elif category == "kab":
            now_str = datetime.now(KYIV_TZ).strftime("%H:%M")
            state["kab_batch"]["items"].append({"time": now_str, "location": location})
            print(f"[batch] Додано до зведення КАБ/Іскандер/дрони: {location}")

        else:
            pass  # обычная тревога без нужных ключевых слов — не постим, чтобы не спамить

    state["active"] = {uid: True for uid in current_uids}

    # Проверка: не пора ли слать сводку по КАБ/Іскандер/дрони
    batch = state["kab_batch"]
    elapsed = time.time() - batch.get("last_flush", time.time())
    if batch["items"] and elapsed >= KAB_FLUSH_INTERVAL:
        caption = build_kab_batch_caption(batch["items"])
        ok = send_to_telegram(bot_token, chat_id, caption)
        print(f"[{'ok' if ok else 'FAIL'}] Надіслано зведення КАБ/Іскандер/дрони ({len(batch['items'])} випадків)")
        batch["items"] = []
        batch["last_flush"] = time.time()

    save_state(state)
    return state


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    api_token = os.environ.get("ALERTS_API_TOKEN")

    if not bot_token or not chat_id or not api_token:
        raise SystemExit(
            "Не заданы переменные окружения "
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / ALERTS_API_TOKEN"
        )

    state = load_state()
    print(f"Стартуємо моніторинг тривог. У стані вже {len(state['active'])} активних записів.")

    while True:
        state = run_once(bot_token, chat_id, api_token, state)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

