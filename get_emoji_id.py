"""
Помощник для получения custom_emoji_id анимированных Premium-эмодзи.
Показывает точное значение эмодзи (включая скрытые модификаторы), чтобы не
ошибиться при переносе в код.

Как использовать:
1. Найди в Telegram своего бота (по username) и открой с ним личный чат.
2. Отправь боту ОТДЕЛЬНЫМ сообщением нужный анимированный emoji (просто вставь
   его из панели эмодзи, ничего больше не пиши в этом сообщении).
3. Запусти этот скрипт (python get_emoji_id.py).
4. Скопируй ЦЕЛИКОМ строку "COPY THIS:" (не перепечатывай вручную!).
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
        # Telegram считает offset/length в UTF-16 code units, а не в python-символах.
        # Поэтому конвертируем текст в UTF-16 и режем именно по этим границам.
        utf16 = text.encode("utf-16-le")
        entities = msg.get("entities", [])
        for e in entities:
            if e.get("type") == "custom_emoji":
                found_any = True
                start = e["offset"] * 2
                end = (e["offset"] + e["length"]) * 2
                piece_bytes = utf16[start:end]
                piece = piece_bytes.decode("utf-16-le")
                codepoints = [f"U+{ord(c):04X}" for c in piece]
                print(f"custom_emoji_id: {e.get('custom_emoji_id')}")
                print(f"  Codepoints: {' '.join(codepoints)}")
                print(f"  COPY THIS: {piece!r}")
                print()
    if not found_any:
        print("В последних сообщениях кастомных эмодзи не найдено.")
        print("Убедись, что отправил боту именно анимированный emoji из Premium-панели.")
