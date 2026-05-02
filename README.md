---
title: Delish Bot
emoji: 🍽️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---
# 🍽️ Delish Bot — AI Restaurant Telegram Bot

A fully-featured Telegram bot for **Delish** restaurant, powered by **Google Gemini AI** and **Firecrawl** live menu scraping.

## Features

| Feature | Description |
|---------|-------------|
| 🛍️ **Food Ordering** | Browse menu, add to cart, pickup/delivery, checkout |
| ⏭️ **Order Ahead** | Schedule pickup with time slot selection |
| 🏛️ **Banquet Hall** | 6-step event inquiry (weddings, corporate, etc.) |
| 🎁 **Gift Cards** | Purchase digital gift cards ($25-$500+) |
| 📅 **Reserve Table** | Book tables with date/time selection |
| 👥 **Group Order** | Create/join group orders with shared code |
| 🍱 **Catering** | Full catering inquiry with all details |
| ⏳ **Join Waitlist** | Join waitlist with estimated wait time |

## Tech Stack

- **Python 3.11+** with async/await
- **python-telegram-bot v20** — Async Telegram bot framework
- **Google Gemini 2.0 Flash** — AI agent brain with function calling
- **Firecrawl** — Live menu scraping (JS rendering)
- **SQLite + aiosqlite** — Persistent storage
- **APScheduler** — Scheduled notifications

## Setup

### 1. Install Dependencies

```bash
cd delish-bot
pip install -r requirements.txt
```

### 2. Configure `.env`

The `.env` file is pre-configured. Update if needed:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

### 3. Run the Bot

```bash
python main.py
```

### 4. Test in Telegram

1. Open your bot in Telegram (search for it by the name you gave it in BotFather)
2. Send `/start` to see the main menu
3. Try each feature!

## Testing Each Feature

| Feature | How to Test |
|---------|------------|
| **Order Food** | Tap 🛍️ → Choose Pickup → Pick time → Browse categories → Add items → Checkout |
| **Order Ahead** | Tap ⏭️ → Pick a time slot → Browse and order |
| **Banquet** | Tap 🏛️ → Follow 6 steps → Submit inquiry |
| **Gift Card** | Tap 🎁 → Choose amount → Enter recipient → Confirm |
| **Reservation** | Tap 📅 → Party size → Date → Time → Name/Phone |
| **Group Order** | Tap 👥 → Create → Share code → Others join and add items |
| **Catering** | Tap 🍱 → Event type → Date → Headcount → Submit |
| **Waitlist** | Tap ⏳ → Party size → Name → Phone → Confirm |
| **AI Chat** | Just type naturally! "What's good here?" / "Do you have vegan options?" |

## Project Structure

```
delish-bot/
├── main.py              # Entry point, handler registration
├── agent.py             # Gemini AI agent with tool calling
├── scraper.py           # Firecrawl + fallback menu data
├── database.py          # SQLite CRUD operations
├── handlers/
│   ├── order.py         # Food ordering flow
│   ├── order_ahead.py   # Scheduled ordering
│   ├── banquet.py       # Banquet hall inquiry
│   ├── gift_card.py     # Gift card purchase
│   ├── reservation.py   # Table reservation
│   ├── group_order.py   # Group order management
│   ├── catering.py      # Catering inquiry
│   └── waitlist.py      # Waitlist management
├── utils/
│   ├── keyboards.py     # All Telegram inline keyboards
│   └── formatters.py    # Message formatting & code generators
├── .env                 # API keys & config
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Commands

- `/start` — Main menu
- `/help` — Help & feature list
- `/cart` — View current cart
- `/menu` — Browse menu directly

## Architecture

```
User Message
    │
    ├── Button Click → Callback Handler (direct flow)
    │
    └── Text Message → Flow Handler → AI Agent (Gemini)
                                         │
                                         ├── Tool: get_menu_categories
                                         ├── Tool: get_menu_items
                                         ├── Tool: search_menu
                                         ├── Tool: get_time_slots
                                         └── Tool: get_user_cart
```
