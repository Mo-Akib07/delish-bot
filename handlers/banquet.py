"""
handlers/banquet.py — Banquet Hall inquiry handler.
Multi-step flow matching the DirectTap banquet booking experience.
"""

import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow
from database import create_banquet_inquiry, search_banquet_by_contact
from utils.keyboards import (
    banquet_event_types_keyboard, banquet_food_keyboard, banquet_bar_keyboard,
    banquet_room_keyboard, banquet_confirm_keyboard, banquet_track_keyboard,
    main_menu_keyboard, back_to_main_keyboard
)
from utils.formatters import format_banquet_summary, format_banquet_confirmation

logger = logging.getLogger(__name__)


async def start_banquet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the banquet inquiry flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "banquet"
    session["flow_state"] = "event_type"
    session["flow_data"] = {}

    text = (
        "🏛️ *Book Our Banquet Hall*\n\n"
        "Weddings · Corporate · Celebrations\n"
        "Minimum 20 guests\n\n"
        "*Step 1/6 — What type of event?*"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=banquet_event_types_keyboard()
    )


async def handle_banquet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all banquet-related callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    # Event type selection
    if data.startswith("banquet:event:"):
        event = data.replace("banquet:event:", "")
        session["flow_data"]["event_type"] = event
        session["flow_state"] = "event_date"
        await query.edit_message_text(
            f"✅ Event: *{event}*\n\n"
            "*Step 1/6 — Event Date*\n\n"
            "Please type the event date (YYYY-MM-DD format):\n"
            f"_Minimum 14 days from today ({(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')})_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    # Food service selection
    elif data.startswith("banquet:food:"):
        food = data.replace("banquet:food:", "")
        session["flow_data"]["food_service"] = food
        session["flow_state"] = "bar_service"
        await query.edit_message_text(
            f"✅ Food Service: *{food}*\n\n"
            "*Step 3/6 — Bar Service*\n\n"
            "Select your bar service preference:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_bar_keyboard()
        )

    # Bar service selection
    elif data.startswith("banquet:bar:"):
        bar = data.replace("banquet:bar:", "")
        session["flow_data"]["bar_service"] = bar
        session["flow_state"] = "room_setup"
        await query.edit_message_text(
            f"✅ Bar Service: *{bar}*\n\n"
            "*Step 4/6 — Room Setup*\n\n"
            "Choose your preferred room arrangement:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_room_keyboard()
        )

    # Room setup selection
    elif data.startswith("banquet:room:"):
        room = data.replace("banquet:room:", "")
        session["flow_data"]["room_setup"] = room
        session["flow_state"] = "contact_name"
        await query.edit_message_text(
            f"✅ Room Setup: *{room}*\n\n"
            "*Step 5/6 — Contact Details*\n\n"
            "Please type your *full name*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    # Submit inquiry
    elif data == "banquet:submit":
        inquiry_id = await create_banquet_inquiry(user_id, session["flow_data"])
        text = format_banquet_confirmation(inquiry_id)
        clear_session_flow(user_id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_track_keyboard()
        )

    # Track inquiry
    elif data == "banquet:track":
        session["flow"] = "banquet_track"
        session["flow_state"] = "track_input"
        await query.edit_message_text(
            "🔍 *Track Banquet Inquiry*\n\n"
            "Type your *phone number* or *name* to find your inquiry:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    # Back buttons
    elif data == "banquet:back_event":
        session["flow_state"] = "event_type"
        await query.edit_message_text(
            "🏛️ *Step 1/6 — Event Type*\n\nSelect your event type:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_event_types_keyboard()
        )
    elif data == "banquet:back_food":
        session["flow_state"] = "food_service"
        await query.edit_message_text(
            "🏛️ *Step 2/6 — Food & Service*\n\nSelect your food service:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_food_keyboard()
        )
    elif data == "banquet:back_bar":
        session["flow_state"] = "bar_service"
        await query.edit_message_text(
            "🏛️ *Step 3/6 — Bar Service*\n\nSelect your bar service:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_bar_keyboard()
        )
    elif data == "banquet:edit":
        # Restart from beginning
        session["flow_state"] = "event_type"
        session["flow_data"] = {}
        await query.edit_message_text(
            "🏛️ *Let's start over!*\n\n*Step 1/6 — Event Type*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_event_types_keyboard()
        )


async def handle_banquet_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during banquet flow. Returns True if handled."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    text = update.message.text.strip()

    if session["flow"] == "banquet_track":
        # Track inquiry by phone or name
        results = await search_banquet_by_contact(name=text, phone=text)
        if results:
            response = "🔍 *Your Banquet Inquiries:*\n\n"
            for r in results:
                response += (
                    f"🆔 *BNQ-{r['id']:05d}*\n"
                    f"  Event: {r['event_type']} | {r['event_date']}\n"
                    f"  Guests: {r['guest_count']} | Status: *{r['status'].upper()}*\n\n"
                )
        else:
            response = "❌ No inquiries found for that name/phone.\nTry again or go back to main menu."
        clear_session_flow(user_id)
        await update.message.reply_text(
            response, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )
        return True

    if session["flow"] != "banquet":
        return False

    state = session["flow_state"]

    if state == "event_date":
        # Validate date
        try:
            event_date = datetime.strptime(text, "%Y-%m-%d")
            min_date = datetime.now() + timedelta(days=14)
            if event_date < min_date:
                await update.message.reply_text(
                    f"❌ Event must be at least *14 days* from today.\n"
                    f"Earliest date: *{min_date.strftime('%Y-%m-%d')}*\n\n"
                    f"Please enter a valid date:",
                    parse_mode=ParseMode.MARKDOWN
                )
                return True
            session["flow_data"]["event_date"] = text
            session["flow_state"] = "guest_count"
            await update.message.reply_text(
                f"✅ Date: *{text}*\n\n"
                "How many *guests* are you expecting?\n"
                "_(Minimum 20 guests)_",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid date format. Please use *YYYY-MM-DD*\n"
                "Example: *2026-06-15*",
                parse_mode=ParseMode.MARKDOWN
            )
        return True

    elif state == "guest_count":
        try:
            guests = int(text)
            if guests < 20:
                await update.message.reply_text(
                    "❌ Minimum *20 guests* required for banquet bookings.\n"
                    "Please enter a number ≥ 20:",
                    parse_mode=ParseMode.MARKDOWN
                )
                return True
            session["flow_data"]["guest_count"] = guests
            session["flow_state"] = "start_time"
            await update.message.reply_text(
                f"✅ Guests: *{guests}*\n\n"
                "What *start time* for your event?\n"
                "_(e.g., 18:00 or 6:00 PM)_",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a number (e.g., 50):",
                parse_mode=ParseMode.MARKDOWN
            )
        return True

    elif state == "start_time":
        session["flow_data"]["start_time"] = text
        session["flow_state"] = "end_time"
        await update.message.reply_text(
            f"✅ Start: *{text}*\n\n"
            "What *end time*?\n"
            "_(e.g., 23:00 or 11:00 PM)_",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "end_time":
        session["flow_data"]["end_time"] = text
        session["flow_state"] = "food_service"
        await update.message.reply_text(
            f"✅ Time: *{session['flow_data']['start_time']} – {text}*\n\n"
            "*Step 2/6 — Food & Service*\n\n"
            "Select your food service:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_food_keyboard()
        )
        return True

    elif state == "contact_name":
        session["flow_data"]["contact_name"] = text
        session["flow_state"] = "contact_phone"
        await update.message.reply_text(
            f"✅ Name: *{text}*\n\n"
            "Your *phone number* (WhatsApp preferred):",
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
            [InlineKeyboardButton("⏭️ Skip", callback_data="banquet:skip_email")]
        ])
        await update.message.reply_text(
            "📧 *Email* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "contact_email":
        session["flow_data"]["contact_email"] = text
        session["flow_state"] = "company"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="banquet:skip_company")]
        ])
        await update.message.reply_text(
            "🏢 *Company/Organization* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "company":
        session["flow_data"]["company"] = text
        session["flow_state"] = "special_requests"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="banquet:skip_requests")]
        ])
        await update.message.reply_text(
            "📝 *Special requests* (dietary restrictions, décor, etc.) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "special_requests":
        session["flow_data"]["special_requests"] = text
        session["flow_state"] = "confirm"
        summary = format_banquet_summary(session["flow_data"])
        await update.message.reply_text(
            f"*Step 6/6 — Review & Confirm*\n\n{summary}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_confirm_keyboard()
        )
        return True

    return False


async def handle_banquet_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle skip buttons in banquet flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data == "banquet:skip_email":
        session["flow_state"] = "company"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="banquet:skip_company")]
        ])
        await query.edit_message_text(
            "🏢 *Company/Organization* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=skip_kb
        )
    elif data == "banquet:skip_company":
        session["flow_state"] = "special_requests"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="banquet:skip_requests")]
        ])
        await query.edit_message_text(
            "📝 *Special requests* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=skip_kb
        )
    elif data == "banquet:skip_requests":
        session["flow_state"] = "confirm"
        summary = format_banquet_summary(session["flow_data"])
        await query.edit_message_text(
            f"*Step 6/6 — Review & Confirm*\n\n{summary}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=banquet_confirm_keyboard()
        )
