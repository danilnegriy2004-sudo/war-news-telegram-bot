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
from deep_translator import GoogleTranslator

STATE_FILE = "state.json"
MAX_POSTS_PER_RUN = 1
SLEEP_BETWEEN_POSTS = 3  # секунды, чтобы не упереться в лимиты Telegram

SOURCE_EMOJI = {
    "BBC World": "🌍",
    "The Guardian": "🗞",
    "Google News": "📡",
    "BBC Russian": "🇷🇺",
    "BBC Ukrainian": "🇺🇦",
    "Meduza (EN)": "📰",
}

FEEDS = [
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "filter_keywords": True, "lang": "en"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/ukraine/rss", "filter_keywords": False, "lang": "en"},
    {"name": "Google News", "url": "https://news.google.com/rss/search?q=Ukraine%20Russia%20war%20when:1d&hl=en-US&gl=US&ceid=US:en", "filter_keywords": False, "lang": "en"},
    {"name": "BBC Russian", "url": "https://feeds.bbci.co.uk/russian/rss.xml", "filter_keywords": True, "lang": "ru"},
    {"name": "BBC Ukrainian", "url": "https://feeds.bbci.co.uk/ukrainian/rss.xml", "filter_keywords": True, "lang": "uk"},
    {"name": "Meduza (EN)", "url": "https://meduza.io/rss/en/all", "filter_keywords": True, "lang": "en"},
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


def get_image_url(entry):
    """Пытается найти картинку в записи RSS (media:thumbnail, media:content, enclosure)."""
    media_thumb = entry.get("media_thumbnail")
    if media_thumb:
        url = media_thumb[0].get("url")
        if url:
            return url

    media_content = entry.get("media_content")
    if media_content:
        for m in media_content:
            url = m.get("url")
            medium = m.get("medium", "")
            if url and (medium == "image" or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
                return url

    for enc in entry.get("enclosures", []):
        etype = enc.get("type", "")
        url = enc.get("href") or enc.get("url")
        if url and etype.startswith("image"):
            return url

    return None


def translate_to_ukrainian(text: str, source_lang: str) -> str:
    """Переводит текст на украинский. Если перевод не удался — возвращает оригинал."""
    if not text or source_lang == "uk":
        return text
    try:
        return GoogleTranslator(source=source_lang, target="uk").translate(text)
    except Exception as e:
        print(f"[warn] Перевод не удался: {e}")
        return text


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

            lang = feed.get("lang", "en")
            clean_summary = strip_html(summary)[:300]

            items.append({
                "source": feed["name"],
                "title": translate_to_ukrainian(title, lang),
                "link": link,
                "summary": translate_to_ukrainian(clean_summary, lang),
                "image": get_image_url(entry),
            })
    return items


def strip_html(raw: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", raw or "")
    return " ".join(text.split())


CHANNEL_NAME = "Українські News"
CHANNEL_LINK = "https://t.me/ukrainenews68"


def build_caption(item: dict) -> str:
    parts = [f"❗ <b>{item['title']}</b>"]
    if item.get("summary"):
        parts.append(item["summary"])
    parts.append(f"<a href=\"{CHANNEL_LINK}\">{CHANNEL_NAME}</a>")
    return "\n\n".join(parts)


def send_to_telegram(bot_token: str, chat_id: str, item: dict):
    caption = build_caption(item)

    if item.get("image"):
        # Caption у фото ограничен 1024 символами — на всякий случай подрежем
        safe_caption = caption if len(caption) <= 1024 else caption[:1000] + "…"
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        resp = requests.post(url, data={
            "chat_id": chat_id,
            "photo": item["image"],
            "caption": safe_caption,
            "parse_mode": "HTML",
        }, timeout=20)
        if resp.ok:
            return True
        print(f"[warn] sendPhoto не удался ({resp.status_code}: {resp.text[:200]}), пробуем как текст")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": caption,
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
                state.add(link_hash(item["link"]))
                save_state(state)  # сохраняем сразу, чтобы прерывание не привело к повтору
            time.sleep(SLEEP_BETWEEN_POSTS)

    # В состояние записываем ВСЕ увиденные материалы (даже те, что не отправляли из-за лимита),
    # чтобы не пытаться отправить их повторно на следующем запуске бесконечно.
    for it in items:
        state.add(link_hash(it["link"]))
    save_state(state)


if __name__ == "__main__":
    main()
