"""
handlers/catering.py — Catering inquiry handler.
Multi-step form for catering requests.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow
from database import create_catering_inquiry
from utils.keyboards import (
    catering_event_keyboard, catering_service_keyboard,
    catering_cuisine_keyboard, catering_budget_keyboard,
    catering_confirm_keyboard, main_menu_keyboard, back_to_main_keyboard
)
from utils.formatters import format_catering_summary, format_catering_confirmation

logger = logging.getLogger(__name__)


async def start_catering(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start catering inquiry flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "catering"
    session["flow_state"] = "event_type"
    session["flow_data"] = {}

    await query.edit_message_text(
        "🍱 *Book Catering*\n"
        "Corporate lunch, weddings, private events\n\n"
        "What type of event?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=catering_event_keyboard()
    )


async def handle_catering_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle catering callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data.startswith("cater:event:"):
        event = data.replace("cater:event:", "")
        session["flow_data"]["event_type"] = event
        session["flow_state"] = "event_date"
        await query.edit_message_text(
            f"✅ Event: *{event}*\n\n"
            "Enter the *event date* (YYYY-MM-DD):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data.startswith("cater:style:"):
        style = data.replace("cater:style:", "")
        session["flow_data"]["service_style"] = style
        session["flow_state"] = "cuisine"
        await query.edit_message_text(
            f"✅ Service: *{style}*\n\n"
            "Any *dietary preferences/restrictions*?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_cuisine_keyboard()
        )

    elif data.startswith("cater:diet:"):
        diet = data.replace("cater:diet:", "")
        session["flow_data"]["cuisine_prefs"] = diet
        session["flow_state"] = "location"
        await query.edit_message_text(
            f"✅ Dietary: *{diet}*\n\n"
            "Enter the *event location/address*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data.startswith("cater:budget:"):
        budget = data.replace("cater:budget:", "")
        session["flow_data"]["budget_range"] = budget
        session["flow_state"] = "contact_name"
        await query.edit_message_text(
            f"✅ Budget: *{budget}*\n\n"
            "Enter your *full name*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data == "cater:submit":
        inquiry_id = await create_catering_inquiry(user_id, session["flow_data"])
        text = format_catering_confirmation(inquiry_id)
        clear_session_flow(user_id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )

    elif data == "cater:edit":
        session["flow_state"] = "event_type"
        session["flow_data"] = {}
        await query.edit_message_text(
            "🍱 *Catering*\n\nWhat type of event?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_event_keyboard()
        )

    # Back buttons
    elif data == "cater:back":
        session["flow_state"] = "event_type"
        await query.edit_message_text(
            "🍱 *Event Type*:", parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_event_keyboard()
        )
    elif data == "cater:back_style":
        session["flow_state"] = "service_style"
        await query.edit_message_text(
            "🍱 *Service Style*:", parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_service_keyboard()
        )
    elif data == "cater:back_diet":
        session["flow_state"] = "cuisine"
        await query.edit_message_text(
            "🍱 *Dietary Preferences*:", parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_cuisine_keyboard()
        )

    elif data == "cater:skip_requests":
        session["flow_state"] = "confirm"
        summary = format_catering_summary(session["flow_data"])
        await query.edit_message_text(
            summary + "\n\n✅ Submit your catering inquiry?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_confirm_keyboard()
        )


async def handle_catering_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during catering flow."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["flow"] != "catering":
        return False

    text = update.message.text.strip()
    state = session["flow_state"]

    if state == "event_date":
        from datetime import datetime
        try:
            datetime.strptime(text, "%Y-%m-%d")
            session["flow_data"]["event_date"] = text
            session["flow_state"] = "headcount"
            await update.message.reply_text(
                f"✅ Date: *{text}*\n\n"
                "How many people are you catering for? _(headcount)_",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Please use *YYYY-MM-DD* format (e.g., 2026-06-15):",
                parse_mode=ParseMode.MARKDOWN
            )
        return True

    elif state == "headcount":
        try:
            count = int(text)
            if count < 5:
                await update.message.reply_text(
                    "❌ Minimum *5 people* for catering.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return True
            session["flow_data"]["headcount"] = count
            session["flow_state"] = "service_style"
            await update.message.reply_text(
                f"✅ Headcount: *{count}*\n\n"
                "Select *service style*:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=catering_service_keyboard()
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a number:", parse_mode=ParseMode.MARKDOWN
            )
        return True

    elif state == "location":
        session["flow_data"]["event_location"] = text
        session["flow_state"] = "budget"
        await update.message.reply_text(
            f"✅ Location: *{text}*\n\n"
            "Select a *budget range* (optional):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_budget_keyboard()
        )
        return True

    elif state == "contact_name":
        session["flow_data"]["contact_name"] = text
        session["flow_state"] = "contact_phone"
        await update.message.reply_text(
            f"✅ Name: *{text}*\n\n"
            "Your *phone number*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "contact_phone":
        phone = text.replace(" ", "").replace("-", "")
        if len(phone) < 7:
            await update.message.reply_text(
                "❌ Please enter a valid phone number:",
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        session["flow_data"]["contact_phone"] = text
        session["flow_state"] = "contact_email"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="cater:skip_email")]
        ])
        await update.message.reply_text(
            "📧 *Email* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "contact_email":
        session["flow_data"]["contact_email"] = text
        session["flow_state"] = "special_requests"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="cater:skip_requests")]
        ])
        await update.message.reply_text(
            "📝 *Special requests* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "special_requests":
        session["flow_data"]["special_requests"] = text
        session["flow_state"] = "confirm"
        summary = format_catering_summary(session["flow_data"])
        await update.message.reply_text(
            summary + "\n\n✅ Submit your catering inquiry?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=catering_confirm_keyboard()
        )
        return True

    return False


async def handle_catering_skip_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle skip email in catering flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)

    session["flow_state"] = "special_requests"
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    skip_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Skip", callback_data="cater:skip_requests")]
    ])
    await query.edit_message_text(
        "📝 *Special requests* (optional) — or tap Skip:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=skip_kb
    )
