"""
Автоматический постер новостей о войне Россия–Украина в Telegram-канал.

Как это работает:
- Берёт те же RSS-источники, что и сайт-агрегатор (BBC, Guardian, Google News, Meduza).
- Фильтрует материалы по ключевым словам, связанным с войной.
- Хранит список уже отправленных ссылок в state.json, чтобы не дублировать посты.
- При первом запуске НИЧЕГО не отправляет, а просто запоминает текущие новости
  (иначе в канал улетело бы сразу 50+ старых сообщений).
- Отправляет не больше MAX_POSTS_PER_RUN новостей за один запуск, чтобы не спамить.
"""

import os
import json
import time
import hashlib
import feedparser
import requests

STATE_FILE = "state.json"
MAX_POSTS_PER_RUN = 15
SLEEP_BETWEEN_POSTS = 2  # секунды, чтобы не упереться в лимиты Telegram

FEEDS = [
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "filter_keywords": True},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/ukraine/rss", "filter_keywords": False},
    {"name": "Google News", "url": "https://news.google.com/rss/search?q=Ukraine%20Russia%20war%20when:1d&hl=en-US&gl=US&ceid=US:en", "filter_keywords": False},
    {"name": "BBC Russian", "url": "https://feeds.bbci.co.uk/russian/rss.xml", "filter_keywords": True},
    {"name": "BBC Ukrainian", "url": "https://feeds.bbci.co.uk/ukrainian/rss.xml", "filter_keywords": True},
    {"name": "Meduza (EN)", "url": "https://meduza.io/rss/en/all", "filter_keywords": True},
]

KEYWORDS = [
    "ukrain", "russia", "putin", "zelensk", "kyiv", "kiev", "kremlin", "moscow",
    "donbas", "donetsk", "luhansk", "crimea", "front line", "frontline",
    "invasion", "drone strike", "missile strike",
    "украин", "россия", "росси", "путин", "зеленськ", "зеленск", "київ", "киев",
    "кремль", "москв", "донбас", "донецьк", "луганськ", "крим", "крым", "фронт",
    "війна", "война", "вторгнення", "вторжение", "санкц", "обстріл", "обстрел",
]


def matches_keywords(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def link_hash(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def load_state():
    if not os.path.exists(STATE_FILE):
        return None  # означает "первый запуск"
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_state(posted_hashes):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(posted_hashes), f, ensure_ascii=False, indent=2)


def fetch_all_items():
    items = []
    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as e:
            print(f"[warn] Не удалось загрузить {feed['name']}: {e}")
            continue

        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            if not title or not link:
                continue
            if feed["filter_keywords"] and not matches_keywords(title + " " + summary):
                continue
            items.append({
                "source": feed["name"],
                "title": title,
                "link": link,
            })
    return items


def send_to_telegram(bot_token: str, chat_id: str, item: dict):
    text = f"<b>{item['source']}</b>\n{item['title']}\n{item['link']}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }, timeout=20)
    if not resp.ok:
        print(f"[error] Telegram API ответил {resp.status_code}: {resp.text}")
    return resp.ok


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise SystemExit("Не заданы переменные окружения TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

    items = fetch_all_items()
    print(f"Найдено материалов после фильтрации: {len(items)}")

    state = load_state()
    first_run = state is None
    if first_run:
        state = set()
        print("Первый запуск — сообщения отправляться не будут, только сохраним текущее состояние.")

    new_items = [it for it in items if link_hash(it["link"]) not in state]
    print(f"Новых материалов: {len(new_items)}")

    if not first_run:
        to_send = new_items[:MAX_POSTS_PER_RUN]
        for item in to_send:
            ok = send_to_telegram(bot_token, chat_id, item)
            if ok:
                print(f"[ok] Отправлено: {item['title'][:70]}")
            time.sleep(SLEEP_BETWEEN_POSTS)

    # В состояние записываем ВСЕ увиденные материалы (даже те, что не отправляли из-за лимита),
    # чтобы не пытаться отправить их повторно на следующем запуске бесконечно.
    for it in items:
        state.add(link_hash(it["link"]))
    save_state(state)


if __name__ == "__main__":
    main()
