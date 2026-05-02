"""
handlers/order_ahead.py — Order Ahead handler.
Schedule a pickup order with time slot selection, then browse menu.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow
from scraper import scrape_time_slots, get_categories
from utils.keyboards import (
    time_slots_keyboard, categories_keyboard, main_menu_keyboard
)

logger = logging.getLogger(__name__)


async def start_order_ahead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start order ahead flow — show time slots first."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "order"  # Reuse order flow
    session["flow_state"] = "select_time"
    session["flow_data"] = {"order_type": "pickup", "is_order_ahead": True}

    slots = scrape_time_slots()
    text = (
        "⏭️ *Order Ahead*\n"
        "Skip the wait — choose your pickup time!\n\n"
        "Select a time slot:"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=time_slots_keyboard(slots)
    )
