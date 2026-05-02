"""
handlers/gift_card.py — Gift card purchase handler.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow
from database import create_gift_card
from utils.keyboards import (
    gift_card_amounts_keyboard, gift_card_confirm_keyboard,
    main_menu_keyboard, back_to_main_keyboard
)
from utils.formatters import format_gift_card_confirmation, generate_gift_card_code

logger = logging.getLogger(__name__)


async def start_gift_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start gift card purchase flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "gift_card"
    session["flow_state"] = "select_amount"
    session["flow_data"] = {}

    await query.edit_message_text(
        "🎁 *Give the Gift of Great Food!*\n\n"
        "Buy a Delish gift card for someone special.\n\n"
        "Choose an amount:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=gift_card_amounts_keyboard()
    )


async def handle_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle gift card callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data.startswith("gift:amount:"):
        amount = data.replace("gift:amount:", "")
        if amount == "custom":
            session["flow_state"] = "custom_amount"
            await query.edit_message_text(
                "💰 Enter a *custom amount* (e.g., 75):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_to_main_keyboard()
            )
        else:
            session["flow_data"]["amount"] = float(amount)
            session["flow_state"] = "recipient_name"
            await query.edit_message_text(
                f"💰 Amount: *${float(amount):.2f}*\n\n"
                "Who is this gift card for?\n"
                "Enter the *recipient's name*:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_to_main_keyboard()
            )

    elif data == "gift:confirm":
        code = generate_gift_card_code()
        amount = session["flow_data"]["amount"]

        await create_gift_card(
            user_id=user_id,
            code=code,
            amount=amount,
            recipient_name=session["flow_data"].get("recipient_name"),
            recipient_contact=session["flow_data"].get("recipient_contact"),
            message=session["flow_data"].get("personal_message"),
        )

        text = format_gift_card_confirmation(code, amount, session["flow_data"])
        clear_session_flow(user_id)

        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )

    elif data == "gift:edit":
        session["flow_state"] = "select_amount"
        session["flow_data"] = {}
        await query.edit_message_text(
            "🎁 *Gift Card*\n\nChoose an amount:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=gift_card_amounts_keyboard()
        )

    elif data == "gift:skip_message":
        session["flow_state"] = "confirm"
        amount = session["flow_data"]["amount"]
        text = (
            "🎁 *Gift Card Summary*\n\n"
            f"💰 Amount: *${amount:.2f}*\n"
            f"👤 Recipient: *{session['flow_data'].get('recipient_name', '—')}*\n"
            f"📱 Contact: *{session['flow_data'].get('recipient_contact', '—')}*\n"
        )
        if session["flow_data"].get("personal_message"):
            text += f"💌 Message: _{session['flow_data']['personal_message']}_\n"
        text += "\n✅ Confirm your gift card purchase?"

        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=gift_card_confirm_keyboard()
        )


async def handle_gift_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during gift card flow."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["flow"] != "gift_card":
        return False

    text = update.message.text.strip()
    state = session["flow_state"]

    if state == "custom_amount":
        try:
            amount = float(text.replace("$", "").replace(",", ""))
            if amount < 5:
                await update.message.reply_text(
                    "❌ Minimum gift card amount is *$5.00*.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return True
            session["flow_data"]["amount"] = amount
            session["flow_state"] = "recipient_name"
            await update.message.reply_text(
                f"💰 Amount: *${amount:.2f}*\n\n"
                "Enter the *recipient's name*:",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid number (e.g., 75):",
                parse_mode=ParseMode.MARKDOWN
            )
        return True

    elif state == "recipient_name":
        session["flow_data"]["recipient_name"] = text
        session["flow_state"] = "recipient_contact"
        await update.message.reply_text(
            f"👤 Recipient: *{text}*\n\n"
            "Enter the recipient's *phone number or email*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "recipient_contact":
        session["flow_data"]["recipient_contact"] = text
        session["flow_state"] = "personal_message"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="gift:skip_message")]
        ])
        await update.message.reply_text(
            "💌 Add a *personal message* (optional) — or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "personal_message":
        session["flow_data"]["personal_message"] = text
        session["flow_state"] = "confirm"
        amount = session["flow_data"]["amount"]
        summary = (
            "🎁 *Gift Card Summary*\n\n"
            f"💰 Amount: *${amount:.2f}*\n"
            f"👤 Recipient: *{session['flow_data'].get('recipient_name', '—')}*\n"
            f"📱 Contact: *{session['flow_data'].get('recipient_contact', '—')}*\n"
            f"💌 Message: _{text}_\n\n"
            "✅ Confirm your gift card purchase?"
        )
        await update.message.reply_text(
            summary, parse_mode=ParseMode.MARKDOWN,
            reply_markup=gift_card_confirm_keyboard()
        )
        return True

    return False
