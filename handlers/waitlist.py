"""
handlers/waitlist.py — Join Waitlist handler.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow
from database import add_to_waitlist, notify_waitlist, get_waitlist_entry
from utils.keyboards import (
    party_size_keyboard, waitlist_confirm_keyboard,
    main_menu_keyboard, back_to_main_keyboard
)
from utils.formatters import format_waitlist_confirmation, format_waitlist_ready

logger = logging.getLogger(__name__)


async def start_waitlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start waitlist flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "waitlist"
    session["flow_state"] = "party_size"
    session["flow_data"] = {}

    await query.edit_message_text(
        "⏳ *Join Waitlist*\n"
        "~5 min estimated wait\n\n"
        "How many in your party?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=party_size_keyboard("wait")
    )


async def handle_waitlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle waitlist callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data.startswith("wait:size:"):
        size = data.replace("wait:size:", "")
        session["flow_data"]["party_size"] = size
        session["flow_state"] = "name"
        await query.edit_message_text(
            f"👥 Party Size: *{size}*\n\n"
            "Enter your *name*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data == "wait:confirm":
        est_wait = max(3, int(session["flow_data"].get("party_size", "2")) * 2 + 1)
        wl_id = await add_to_waitlist(
            user_id=user_id,
            party_size=int(str(session["flow_data"].get("party_size", 2)).replace("+", "")),
            name=session["flow_data"].get("name", ""),
            phone=session["flow_data"].get("phone", ""),
            estimated_wait=est_wait,
        )
        text = format_waitlist_confirmation(wl_id, session["flow_data"], est_wait)
        clear_session_flow(user_id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )


async def handle_waitlist_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during waitlist flow."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["flow"] != "waitlist":
        return False

    text = update.message.text.strip()
    state = session["flow_state"]

    if state == "name":
        session["flow_data"]["name"] = text
        session["flow_state"] = "phone"
        await update.message.reply_text(
            f"👤 Name: *{text}*\n\n"
            "Enter your *phone number*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "phone":
        phone = text.replace(" ", "").replace("-", "")
        if len(phone) < 7:
            await update.message.reply_text(
                "❌ Please enter a valid phone number:",
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        session["flow_data"]["phone"] = text
        session["flow_state"] = "confirm"
        size = session["flow_data"].get("party_size", "2")
        est_wait = max(3, int(str(size).replace("+", "")) * 2 + 1)

        summary = (
            "⏳ *Waitlist Summary*\n\n"
            f"👥 Party: *{size}*\n"
            f"👤 Name: *{session['flow_data']['name']}*\n"
            f"📱 Phone: *{text}*\n"
            f"⏰ Estimated Wait: *~{est_wait} minutes*\n\n"
            "Join the waitlist?"
        )
        await update.message.reply_text(
            summary, parse_mode=ParseMode.MARKDOWN,
            reply_markup=waitlist_confirm_keyboard()
        )
        return True

    return False


async def send_table_ready(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send table-ready notification. Can be triggered manually or by scheduler."""
    entry = await get_waitlist_entry(user_id)
    if entry:
        await notify_waitlist(entry["id"])
        await context.bot.send_message(
            chat_id=user_id,
            text=format_waitlist_ready(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )
