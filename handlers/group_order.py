"""
handlers/group_order.py — Group Order handler.
Organizer creates a group, members join and add their items, organizer compiles.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import get_session, clear_session_flow, get_cart, get_cart_total
from database import (
    create_group_order, get_group_order, join_group_order,
    add_member_items, close_group_order, get_group_members
)
from utils.keyboards import (
    group_order_start_keyboard, group_order_manage_keyboard,
    categories_keyboard, main_menu_keyboard, back_to_main_keyboard
)
from utils.formatters import (
    format_group_order_created, format_group_order_summary, generate_group_code
)
from scraper import get_categories

logger = logging.getLogger(__name__)


async def start_group_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start group order flow."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session = get_session(user_id)
    session["flow"] = "group_order"
    session["flow_state"] = "start"
    session["flow_data"] = {}

    await query.edit_message_text(
        "👥 *Group Order*\n"
        "Share a link — everyone picks their own!\n\n"
        "Create a new group order or join an existing one:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=group_order_start_keyboard()
    )


async def handle_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group order callbacks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    data = query.data

    if data == "group:create":
        session["flow_state"] = "party_size"
        await query.edit_message_text(
            "👥 *Create Group Order*\n\n"
            "How many people in your group?\n"
            "_(Enter a number)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data == "group:join":
        session["flow_state"] = "join_code"
        await query.edit_message_text(
            "🔗 *Join Group Order*\n\n"
            "Enter the group order code:\n"
            "_(e.g., GRP-ABC12)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )

    elif data.startswith("group:members:"):
        code = data.replace("group:members:", "")
        members = await get_group_members(code)
        if not members:
            await query.answer("No members have joined yet.", show_alert=True)
            return
        text = f"👥 *Group {code} Members:*\n\n"
        for m in members:
            items = len(eval(m.get("items_json", "[]"))) if m.get("items_json") else 0
            text += f"  • {m.get('user_name', 'Unknown')} — {items} items\n"
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=group_order_manage_keyboard(code)
        )

    elif data.startswith("group:close:"):
        code = data.replace("group:close:", "")
        group = await get_group_order(code)
        if not group or group["organizer_id"] != user_id:
            await query.answer("Only the organizer can close the order.", show_alert=True)
            return

        all_items = await close_group_order(code)
        members = await get_group_members(code)
        text = format_group_order_summary(code, members, all_items)
        text += "\n\n✅ *Group order compiled!* You can now place this as a single order."

        clear_session_flow(user_id)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )

    elif data == "group:save_items":
        # Save current cart as member items
        code = session["flow_data"].get("group_code")
        if code:
            cart = get_cart(user_id)
            import json
            await add_member_items(code, user_id, cart)
            await query.edit_message_text(
                f"✅ Your items have been saved to group order *{code}*!\n\n"
                "The organizer will compile everyone's orders.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard()
            )
            clear_session_flow(user_id)


async def handle_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input during group order flow."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["flow"] != "group_order":
        return False

    text = update.message.text.strip()
    state = session["flow_state"]

    if state == "party_size":
        try:
            size = int(text)
            if size < 2:
                await update.message.reply_text(
                    "❌ Group must have at least *2 people*.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return True

            code = generate_group_code()
            await create_group_order(user_id, code, size)
            # Auto-join the organizer
            name = update.effective_user.first_name or "Organizer"
            await join_group_order(code, user_id, name)

            session["flow_data"]["group_code"] = code
            session["flow_data"]["party_size"] = size
            session["flow_state"] = "manage"

            msg = format_group_order_created(code, size)
            await update.message.reply_text(
                msg, parse_mode=ParseMode.MARKDOWN,
                reply_markup=group_order_manage_keyboard(code)
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a number:", parse_mode=ParseMode.MARKDOWN
            )
        return True

    elif state == "join_code":
        code = text.upper().strip()
        group = await get_group_order(code)

        if not group:
            await update.message.reply_text(
                f"❌ No group order found with code *{code}*.\n"
                "Please check the code and try again:",
                parse_mode=ParseMode.MARKDOWN
            )
            return True

        if not group["is_open"]:
            await update.message.reply_text(
                f"❌ Group order *{code}* is already closed.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard()
            )
            return True

        # Join the group
        name = update.effective_user.first_name or "Member"
        await join_group_order(code, user_id, name)
        session["flow_data"]["group_code"] = code
        session["flow"] = "order"  # Switch to order flow for menu browsing
        session["flow_state"] = "browse_menu"
        session["flow_data"]["order_type"] = "group"

        categories = get_categories()
        save_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 Save My Items", callback_data="group:save_items")],
        ])

        await update.message.reply_text(
            f"✅ Joined group *{code}*!\n\n"
            "Browse the menu and add your items to cart.\n"
            "When done, tap 'Save My Items'.\n\n"
            "📋 *Choose a category:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=categories_keyboard(categories)
        )
        return True

    return False
