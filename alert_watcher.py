"""
Мониторинг воздушных тревог по всей Украине (alerts.in.ua) и постинг в Telegram-канал
в реальном времени (проверка каждые POLL_INTERVAL секунд).

Как это работает:
- Постоянно (в бесконечном цикле) опрашивает официальный API alerts.in.ua/v1/alerts/active.json
- Сравнивает список активных тревог с тем, что было на предыдущей проверке
- Если для области тревога ТОЛЬКО ЧТО началась — шлёт пост "🚨 Тривога"
- Если для области тревога ТОЛЬКО ЧТО закончилась — шлёт пост "✅ Відбій"
- Если в примечаниях (notes) от alerts.in.ua встречаются слова про баллистику —
  помечает пост как "⚠️ Загроза балістики" (более тревожный формат)
- Стейт держит в памяти процесса, но также пишет на диск (alert_state.json),
  чтобы после перезапуска сервиса не спамить повторными постами о том, что уже было.

Важно: этот скрипт НЕ для GitHub Actions — он должен работать как постоянный
процесс (Railway / Render / любой VPS), иначе задержка будет не 30-60 секунд,
а 5-15 минут (ограничение cron у GitHub Actions).

Нужные переменные окружения:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- ALERTS_API_TOKEN   (токен от alerts.in.ua/api-request)
"""

import os
import json
import time
import requests

ALERTS_URL = "https://api.alerts.in.ua/v1/alerts/active.json"
STATE_FILE = "alert_state.json"

POLL_INTERVAL = 30  # секунд между проверками
POST_ALL_CLEAR = True  # слать ли сообщение "відбій", когда тревога снята

CHANNEL_NAME = "Українські News"
CHANNEL_LINK = "https://t.me/ukrainenews68"

BALLISTIC_KEYWORDS = [
    "балістик", "балістичн", "ballistic", "иская ракета", "аеробалістичн",
]

ALERT_TYPE_LABELS = {
    "air_raid": "Повітряна тривога",
    "artillery_shelling": "Загроза артобстрілу",
    "urban_fights": "Вуличні бої",
    "chemical": "Хімічна загроза",
    "nuclear": "Ядерна загроза",
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


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


def is_ballistic(alert: dict) -> bool:
    notes = (alert.get("notes") or "").lower()
    return any(k in notes for k in BALLISTIC_KEYWORDS)


def build_start_caption(alert: dict) -> str:
    location = alert.get("location_title", "Україна")
    alert_type = alert.get("alert_type", "air_raid")
    label = ALERT_TYPE_LABELS.get(alert_type, "Тривога")

    if is_ballistic(alert):
        header = f"⚠️ <b>Загроза балістики — {location}</b>"
    else:
        header = f"🚨 <b>{label} — {location}</b>"

    lines = [header]
    if alert.get("notes"):
        lines.append(alert["notes"])
    lines.append(f"<a href=\"{CHANNEL_LINK}\">{CHANNEL_NAME}</a>")
    return "\n\n".join(lines)


def build_clear_caption(alert: dict) -> str:
    location = alert.get("location_title", "Україна")
    lines = [
        f"✅ <b>Відбій тривоги — {location}</b>",
        f"<a href=\"{CHANNEL_LINK}\">{CHANNEL_NAME}</a>",
    ]
    return "\n\n".join(lines)


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


def run_once(bot_token, chat_id, api_token, state):
    try:
        alerts = fetch_active_alerts(api_token)
    except Exception as e:
        print(f"[warn] Не удалось получить тревоги: {e}")
        return state

    # ключ — уникальный id локации (location_uid), значение — данные тревоги
    active_now = {}
    for alert in alerts:
        uid = str(alert.get("location_uid") or alert.get("location_title"))
        active_now[uid] = alert

    previous_uids = set(state.keys())
    current_uids = set(active_now.keys())

    # новые тревоги
    for uid in current_uids - previous_uids:
        alert = active_now[uid]
        caption = build_start_caption(alert)
        ok = send_to_telegram(bot_token, chat_id, caption)
        print(f"[{'ok' if ok else 'FAIL'}] Нова тривога: {alert.get('location_title')}")
        state[uid] = alert

    # снятые тревоги
    for uid in previous_uids - current_uids:
        old_alert = state.get(uid, {})
        if POST_ALL_CLEAR:
            caption = build_clear_caption(old_alert)
            ok = send_to_telegram(bot_token, chat_id, caption)
            print(f"[{'ok' if ok else 'FAIL'}] Відбій: {old_alert.get('location_title')}")
        state.pop(uid, None)

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
    print(f"Стартуем мониторинг тревог. В состоянии уже {len(state)} активных записей.")

    while True:
        state = run_once(bot_token, chat_id, api_token, state)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

