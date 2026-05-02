"""
handlers/reservation.py — Table reservation handler.
"""

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow
from database import create_reservation
from utils.keyboards import (
    party_size_keyboard, reservation_time_keyboard, reservation_confirm_keyboard,
    main_menu_keyboard, back_to_main_keyboard
)
from utils.formatters import format_reservation_confirmation

logger = logging.getLogger(__name__)


async def start_reservation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start table reservation flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "reservation"
    session["flow_state"] = "party_size"
    session["flow_data"] = {}

    await query.edit_message_text(
        "📅 *Reserve a Table*\n"
        "Book for tonight or this weekend!\n\n"
        "How many guests?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=party_size_keyboard("res")
    )


async def handle_reservation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reservation callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data.startswith("res:size:"):
        size = data.replace("res:size:", "")
        session["flow_data"]["party_size"] = size
        session["flow_state"] = "date"

        # Generate date options (today + next 7 days)
        dates = []
        for i in range(8):
            d = datetime.now() + timedelta(days=i)
            label = "Today" if i == 0 else ("Tomorrow" if i == 1 else d.strftime("%a, %b %d"))
            dates.append((label, d.strftime("%Y-%m-%d")))

        buttons = [[InlineKeyboardButton(
            label, callback_data=f"res:date:{date_str}"
        )] for label, date_str in dates]
        buttons.append([InlineKeyboardButton("◀️ Back", callback_data="res:back_size")])

        await query.edit_message_text(
            f"👥 Party: *{size}*\n\n"
            "📅 Choose a date:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("res:date:"):
        date_str = data.replace("res:date:", "")
        session["flow_data"]["date"] = date_str
        session["flow_state"] = "time"

        await query.edit_message_text(
            f"📅 Date: *{date_str}*\n\n"
            "⏰ Choose a time:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reservation_time_keyboard()
        )

    elif data.startswith("res:time:"):
        time_str = data.replace("res:time:", "")
        session["flow_data"]["time"] = time_str
        session["flow_state"] = "name"

        await query.edit_message_text(
            f"⏰ Time: *{time_str}*\n\n"
            "Please enter your *full name*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data == "res:confirm":
        res_id = await create_reservation(user_id, session["flow_data"])
        text = format_reservation_confirmation(res_id, session["flow_data"])
        clear_session_flow(user_id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )

    elif data == "res:edit":
        session["flow_state"] = "party_size"
        session["flow_data"] = {}
        await query.edit_message_text(
            "📅 *Reserve a Table*\n\nHow many guests?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=party_size_keyboard("res")
        )

    elif data == "res:back_size":
        session["flow_state"] = "party_size"
        await query.edit_message_text(
            "📅 *Reserve a Table*\n\nHow many guests?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=party_size_keyboard("res")
        )

    elif data == "res:back_date":
        session["flow_state"] = "date"
        # Re-show date picker
        dates = []
        for i in range(8):
            d = datetime.now() + timedelta(days=i)
            label = "Today" if i == 0 else ("Tomorrow" if i == 1 else d.strftime("%a, %b %d"))
            dates.append((label, d.strftime("%Y-%m-%d")))
        buttons = [[InlineKeyboardButton(
            label, callback_data=f"res:date:{date_str}"
        )] for label, date_str in dates]
        await query.edit_message_text(
            "📅 Choose a date:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "res:skip_requests":
        session["flow_state"] = "confirm"
        fd = session["flow_data"]
        summary = (
            "📅 *Reservation Summary*\n\n"
            f"👥 Party: *{fd.get('party_size', '—')}*\n"
            f"📅 Date: *{fd.get('date', '—')}*\n"
            f"⏰ Time: *{fd.get('time', '—')}*\n"
            f"👤 Name: *{fd.get('name', '—')}*\n"
            f"📱 Phone: *{fd.get('phone', '—')}*\n"
        )
        if fd.get("special_requests"):
            summary += f"📝 Requests: _{fd['special_requests']}_\n"
        summary += "\n✅ Confirm your reservation?"
        await query.edit_message_text(
            summary, parse_mode=ParseMode.MARKDOWN,
            reply_markup=reservation_confirm_keyboard()
        )


async def handle_reservation_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during reservation flow."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["flow"] != "reservation":
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
        session["flow_state"] = "special_requests"
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="res:skip_requests")]
        ])
        await update.message.reply_text(
            "📝 Any *special requests*?\n"
            "(high chair, wheelchair, anniversary, etc.) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "special_requests":
        session["flow_data"]["special_requests"] = text
        session["flow_state"] = "confirm"
        fd = session["flow_data"]
        summary = (
            "📅 *Reservation Summary*\n\n"
            f"👥 Party: *{fd.get('party_size', '—')}*\n"
            f"📅 Date: *{fd.get('date', '—')}*\n"
            f"⏰ Time: *{fd.get('time', '—')}*\n"
            f"👤 Name: *{fd.get('name', '—')}*\n"
            f"📱 Phone: *{fd.get('phone', '—')}*\n"
            f"📝 Requests: _{text}_\n\n"
            "✅ Confirm your reservation?"
        )
        await update.message.reply_text(
            summary, parse_mode=ParseMode.MARKDOWN,
            reply_markup=reservation_confirm_keyboard()
        )
        return True

    return False
