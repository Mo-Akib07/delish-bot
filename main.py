"""
main.py — Delish Restaurant Telegram Bot
Entry point. Registers all handlers and starts the bot.
"""

import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode, ChatAction

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Imports
from database import init_db
from agent import process_message, get_session, clear_session_flow
from utils.keyboards import main_menu_keyboard, back_to_main_keyboard

# Handler imports
from handlers.order import (
    start_order, handle_order_type, handle_time_slot,
    handle_category_select, handle_add_item, handle_item_info,
    handle_cart_view, handle_cart_clear, handle_quantity_change,
    handle_checkout, handle_checkout_confirm, handle_order_text_input,
    handle_skip_email
)
from handlers.banquet import (
    start_banquet, handle_banquet_callback, handle_banquet_text,
    handle_banquet_skip
)
from handlers.gift_card import (
    start_gift_card, handle_gift_callback, handle_gift_text
)
from handlers.reservation import (
    start_reservation, handle_reservation_callback, handle_reservation_text
)
from handlers.waitlist import (
    start_waitlist, handle_waitlist_callback, handle_waitlist_text
)
from handlers.order_ahead import start_order_ahead
from handlers.group_order import (
    start_group_order, handle_group_callback, handle_group_text
)
from handlers.catering import (
    start_catering, handle_catering_callback, handle_catering_text,
    handle_catering_skip_email
)


# ─── /start COMMAND ───────────────────────────────────────────

WELCOME_MSG = """🍽️ *Welcome to Delish!*

Your AI-powered restaurant concierge ✨

_American cuisine with Indian influences_
📍 New York, NY • ⭐ 4.2 (5 direct) • 🟢 Open now

What would you like to do today?"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command — show main menu."""
    user_id = update.effective_user.id
    clear_session_flow(user_id)

    await update.message.reply_text(
        WELCOME_MSG,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "🆘 *Delish Bot Help*\n\n"
        "*Commands:*\n"
        "/start — Main menu\n"
        "/order — Order by text (e.g. /order chicken tikka)\n"
        "/menu — Browse the menu\n"
        "/cart — View your cart\n"
        "/cancel — Cancel current flow \u0026 go back\n"
        "/help — This help message\n\n"
        "*Chat ordering:*\n"
        "_\"order 2 samosas\"_ — adds to cart\n"
        "_\"checkout\"_ — start checkout\n"
        "_\"do you have burgers?\"_ — search menu\n\n"
        "Or use the *buttons* below! 👇"
    )
    await update.message.reply_text(
        help_text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard()
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel and /back — escape any flow, go back to main menu."""
    user_id = update.effective_user.id
    from agent import clear_cart
    session = get_session(user_id)
    flow = session.get("flow")
    clear_session_flow(user_id)

    if flow:
        await update.message.reply_text(
            f"↩️ Left the *{flow.replace('_', ' ').title()}* flow.\n\n"
            "What would you like to do?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            WELCOME_MSG,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )


async def cmd_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cart command."""
    from utils.formatters import format_cart
    from agent import get_cart, get_cart_total
    from utils.keyboards import cart_keyboard

    user_id = update.effective_user.id
    cart = get_cart(user_id)
    text = format_cart(cart)
    if cart:
        text += f"\n\n💰 *Total: ${get_cart_total(user_id):.2f}*"
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=cart_keyboard(has_items=bool(cart))
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command — show menu categories."""
    from scraper import get_categories
    from utils.keyboards import categories_keyboard

    user_id = update.effective_user.id
    session = get_session(user_id)
    session["flow"] = "order"
    session["flow_state"] = "browse_menu"
    if "order_type" not in session.get("flow_data", {}):
        session["flow_data"] = {"order_type": "pickup", "pickup_time": "ASAP"}

    categories = get_categories()
    await update.message.reply_text(
        "📋 *Delish Menu*\n\nChoose a category:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=categories_keyboard(categories)
    )


# ─── MAIN MENU CALLBACK ROUTER ───────────────────────────────

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route main menu button presses."""
    query = update.callback_query
    data = query.data

    if data == "main:order":
        await start_order(update, context)
    elif data == "main:gift_card":
        await start_gift_card(update, context)
    elif data == "main:banquet":
        await start_banquet(update, context)
    elif data == "main:reservation":
        await start_reservation(update, context)
    elif data == "main:order_ahead":
        await start_order_ahead(update, context)
    elif data == "main:group_order":
        await start_group_order(update, context)
    elif data == "main:catering":
        await start_catering(update, context)
    elif data == "main:waitlist":
        await start_waitlist(update, context)
    elif data == "main:back":
        await query.answer()
        clear_session_flow(query.from_user.id)
        await query.edit_message_text(
            WELCOME_MSG,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )


# ─── /order COMMAND ────────────────────────────────────────────

async def cmd_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /order command — order by text, e.g. /order chicken tikka masala"""
    user_id = update.effective_user.id
    args = update.message.text.replace("/order", "").strip()

    if not args:
        await update.message.reply_text(
            "🛍️ *Order by Text!*\n\n"
            "Usage:\n"
            "  /order chicken tikka masala\n"
            "  /order 2 samosas\n"
            "  /order mango lassi\n\n"
            "Or just type naturally:\n"
            "  _\"I want chicken kabob\"_\n"
            "  _\"add 2 nachos\"_\n"
            "  _\"order burger\"_\n\n"
            "When done, type _\"checkout\"_ to place your order!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )
        return

    # Process as an order intent
    from agent import _detect_order_intent, _find_best_match, add_to_cart as agent_add
    qty, search_term = _detect_order_intent(f"order {args}")
    if not search_term:
        search_term = args
        qty = 1

    match = _find_best_match(search_term)
    if match:
        agent_add(user_id, match["name"], match["price"], qty, match.get("category", ""))
        from agent import get_cart_total as agent_total
        total = agent_total(user_id)
        cart_count = len(get_session(user_id)["cart"])
        await update.message.reply_text(
            f"✅ Added to cart!\n\n"
            f"*{match['name']}* × {qty}  —  ${match['price'] * qty:.2f}\n"
            f"_{match.get('desc', '')[:80]}_\n\n"
            f"🛒 Cart: *{cart_count} items* • *${total:.2f}*\n\n"
            f"Add more with /order or type _\"checkout\"_ when ready!",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"🔍 Couldn't find *\"{search_term}\"* on our menu.\n\n"
            f"Try: /order chicken tikka, /order samosa, /order burger\n"
            f"Or /menu to browse categories!",
            parse_mode=ParseMode.MARKDOWN,
        )


# ─── TEXT MESSAGE HANDLER ─────────────────────────────────────

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages. Smart keyboard: only show main menu when idle."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    # Handle text checkout flow (no menu buttons during checkout)
    if session.get("flow") == "text_checkout":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        from agent import handle_text_checkout
        response = await handle_text_checkout(user_id, update.message.text)
        if response:
            # Check if order was just completed (flow cleared)
            is_done = session.get("flow") is None
            if is_done:
                # Order placed! Show response then auto-show fresh start menu
                await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text(
                    "🍽️ *What else can I help with?*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_menu_keyboard()
                )
            else:
                # Still in checkout flow, no menu buttons
                hint = "\n\n_💡 /cancel to go back to main menu_"
                await update.message.reply_text(
                    response + hint, parse_mode=ParseMode.MARKDOWN
                )
            return

    # Try flow-specific text handlers (no menu buttons during flows)
    if session.get("flow"):
        handled = False
        if session["flow"] in ("order",):
            handled = await handle_order_text_input(update, context)
        elif session["flow"] in ("banquet", "banquet_track"):
            handled = await handle_banquet_text(update, context)
        elif session["flow"] == "gift_card":
            handled = await handle_gift_text(update, context)
        elif session["flow"] == "reservation":
            handled = await handle_reservation_text(update, context)
        elif session["flow"] == "waitlist":
            handled = await handle_waitlist_text(update, context)
        elif session["flow"] == "group_order":
            handled = await handle_group_text(update, context)
        elif session["flow"] == "catering":
            handled = await handle_catering_text(update, context)
        if handled:
            return

    # AI agent for natural language (show menu only when not in a flow)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    response = await process_message(user_id, update.message.text)

    # If the response triggered a flow (like checkout), don't show menu
    if session.get("flow"):
        hint = "\n\n_💡 /cancel to go back to main menu_"
        await update.message.reply_text(response + hint, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            response, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
        )


# ─── NOOP HANDLER ─────────────────────────────────────────────

async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle no-op callbacks (like qty display buttons)."""
    query = update.callback_query
    await query.answer()


# ─── DUMMY WEB SERVER FOR RENDER ─────────────────────────────────

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Dummy server started on port {port}")


# ─── APPLICATION SETUP ────────────────────────────────────────

def main():
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env!")
        return

    # Start dummy server to pass Render health checks
    start_dummy_server()

    # Build application
    app = ApplicationBuilder().token(token).build()



    # ── Commands ──
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cart", cmd_cart))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("order", cmd_order))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("back", cmd_cancel))

    # ── Main menu callbacks ──
    app.add_handler(CallbackQueryHandler(handle_main_menu, pattern=r"^main:"))

    # ── Order callbacks ──
    app.add_handler(CallbackQueryHandler(handle_order_type, pattern=r"^order:(pickup|delivery)$"))
    app.add_handler(CallbackQueryHandler(handle_time_slot, pattern=r"^slot:"))
    app.add_handler(CallbackQueryHandler(handle_category_select, pattern=r"^cat:"))
    app.add_handler(CallbackQueryHandler(handle_add_item, pattern=r"^item:add:"))
    app.add_handler(CallbackQueryHandler(handle_item_info, pattern=r"^item:info:"))
    app.add_handler(CallbackQueryHandler(handle_cart_view, pattern=r"^cart:view$"))
    app.add_handler(CallbackQueryHandler(handle_cart_clear, pattern=r"^cart:clear$"))
    app.add_handler(CallbackQueryHandler(handle_checkout, pattern=r"^cart:checkout$"))
    app.add_handler(CallbackQueryHandler(handle_quantity_change, pattern=r"^qty:"))
    app.add_handler(CallbackQueryHandler(handle_checkout_confirm, pattern=r"^checkout:confirm$"))
    app.add_handler(CallbackQueryHandler(handle_skip_email, pattern=r"^checkout:skip_email$"))
    async def _show_cats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        from scraper import get_categories
        from utils.keyboards import categories_keyboard
        cats = get_categories()
        await query.edit_message_text(
            "📋 *Delish Menu*\n\nChoose a category:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=categories_keyboard(cats)
        )

    app.add_handler(CallbackQueryHandler(_show_cats_handler, pattern=r"^order:show_cats$"))
    app.add_handler(CallbackQueryHandler(
        lambda u, c: start_order(u, c), pattern=r"^order:back_type$"
    ))
    app.add_handler(CallbackQueryHandler(
        lambda u, c: _show_cats_handler(u, c), pattern=r"^order:back_slots$"
    ))

    # ── Banquet callbacks ──
    app.add_handler(CallbackQueryHandler(handle_banquet_callback, pattern=r"^banquet:(?!skip)"))
    app.add_handler(CallbackQueryHandler(handle_banquet_skip, pattern=r"^banquet:skip"))

    # ── Gift card callbacks ──
    app.add_handler(CallbackQueryHandler(handle_gift_callback, pattern=r"^gift:"))

    # ── Reservation callbacks ──
    app.add_handler(CallbackQueryHandler(handle_reservation_callback, pattern=r"^res:"))

    # ── Waitlist callbacks ──
    app.add_handler(CallbackQueryHandler(handle_waitlist_callback, pattern=r"^wait:"))

    # ── Group order callbacks ──
    app.add_handler(CallbackQueryHandler(handle_group_callback, pattern=r"^group:"))

    # ── Catering callbacks ──
    app.add_handler(CallbackQueryHandler(handle_catering_callback, pattern=r"^cater:(?!skip)"))
    app.add_handler(CallbackQueryHandler(handle_catering_skip_email, pattern=r"^cater:skip_email$"))

    # ── Order flow callbacks (back/show_cats) ──
    app.add_handler(CallbackQueryHandler(handle_noop, pattern=r"^qty:noop$"))

    # ── Text message handler (must be last) ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # ── Start ──
    logger.info("🍽️ Delish Bot starting...")
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_db())
    logger.info("📦 Database initialized")
    
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        port = int(os.environ.get("PORT", 10000))
        logger.info(f"🚀 Starting WEBHOOK mode on {webhook_url}:{port}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        logger.info("🚀 Starting POLLING mode (local). Press Ctrl+C to stop.")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
