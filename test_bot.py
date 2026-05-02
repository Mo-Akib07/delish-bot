"""
test_bot.py — Tests the Delish bot by calling the Telegram Bot API directly.
Run this while main.py is running in another window.
"""

import urllib.request
import json
import time
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TOKEN = "8743284280:AAEaBKJC3ki57vzQAaIkIKqeCIsTgI6lLyI"
BASE = f"https://api.telegram.org/bot{TOKEN}"


def api_call(method, params=None):
    url = f"{BASE}/{method}"
    if params:
        data = json.dumps(params).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )
    else:
        req = url
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    # 1) Get bot info
    info = api_call("getMe")["result"]
    print("=" * 60)
    print(f"BOT NAME    : {info['first_name']}")
    print(f"BOT USERNAME: @{info['username']}")
    print(f"BOT ID      : {info['id']}")
    print("=" * 60)

    # 2) Get recent updates to find a real chat_id
    updates = api_call("getUpdates", {"limit": 20, "offset": -20})["result"]

    chat_id = None
    username = None
    for u in updates:
        if "message" in u:
            chat_id = u["message"]["chat"]["id"]
            username = u["message"]["from"].get(
                "username",
                u["message"]["from"].get("first_name", "Unknown")
            )
            break
        elif "callback_query" in u:
            chat_id = u["callback_query"]["message"]["chat"]["id"]
            username = u["callback_query"]["from"].get("username", "Unknown")
            break

    print()
    if not chat_id:
        print("❌ No one has messaged the bot yet!")
        print()
        print("HOW TO START TESTING:")
        print("-" * 40)
        print(f"1. Open Telegram on your phone or https://web.telegram.org")
        print(f"2. Search for: @{info['username']}")
        print(f"3. Tap 'START' or send /start")
        print(f"4. The bot will show the main menu with 8 buttons")
        print()
        print("WHAT TO TEST:")
        print("  • Tap '🛍️ Order Food' → Choose Pickup → Pick a time slot → Browse menu → Add items → Checkout")
        print("  • Tap '🏛️ Banquet Hall' → Follow 6 steps")
        print("  • Tap '🎁 Gift Card' → Choose amount → Enter recipient")
        print("  • Type anything naturally like 'I want chicken' or 'Do you have vegan food?'")
        print()
        print("Run this script again after messaging the bot to see the chat_id and test further.")
        return

    print(f"✅ Found chat with: @{username} (chat_id: {chat_id})")
    print()

    # 3) Send test /start
    print("📤 Sending /start ...")
    r = api_call("sendMessage", {
        "chat_id": chat_id,
        "text": "/start"
    })
    print(f"   Sent! Message ID: {r['result']['message_id']}")
    time.sleep(3)

    # 4) Fetch and show bot's reply
    updates2 = api_call("getUpdates", {"limit": 5, "offset": -5})["result"]
    print()
    print("📥 Bot's recent messages:")
    print("-" * 60)
    for u in updates2:
        if "message" in u:
            msg = u["message"]
            sender = msg["from"].get("first_name", "Unknown")
            text = msg.get("text", "[no text]")
            print(f"  [{sender}]: {text[:120]}")
            if "reply_markup" in msg:
                kb = msg["reply_markup"].get("inline_keyboard", [])
                for row in kb:
                    btns = [f"[{b['text']}]" for b in row]
                    print(f"    {'  '.join(btns)}")
    print("-" * 60)
    print()
    print("✅ Bot is working! Open Telegram and test manually using the buttons.")
    print(f"   Search for: @{info['username']}")


if __name__ == "__main__":
    main()
