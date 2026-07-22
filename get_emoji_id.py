"""
Помощник для получения custom_emoji_id анимированных Premium-эмодзи.

Как использовать:
1. Найди в Telegram своего бота (по username) и открой с ним личный чат.
2. Отправь боту сообщение, в котором есть нужный анимированный emoji
   (просто вставь его из панели эмодзи, как обычно печатаешь).
3. Запусти этот скрипт (python get_emoji_id.py) — он покажет ID каждого
   найденного кастомного эмодзи в последних сообщениях, отправленных боту.
4. Скопируй ID и сохрани как переменную окружения EMOJI_ID_BALLISTIC
   или EMOJI_ID_KAB в Railway.
"""

import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates")
data = resp.json()

results = data.get("result", [])
if not results:
    print("Нет новых сообщений для бота.")
    print("Напиши боту в личку сообщение с нужным анимированным эмодзи и запусти скрипт снова.")
else:
    found_any = False
    for update in results:
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        text = msg.get("text", "")
        entities = msg.get("entities", [])
        for e in entities:
            if e.get("type") == "custom_emoji":
                found_any = True
                piece = text[e["offset"]:e["offset"] + e["length"]]
                print(f"Emoji: {piece}   custom_emoji_id: {e.get('custom_emoji_id')}")
    if not found_any:
        print("В последних сообщениях кастомных эмодзи не найдено.")
        print("Убедись, что отправил боту именно анимированный emoji из Premium-панели.")
