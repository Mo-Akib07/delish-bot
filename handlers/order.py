"""
handlers/order.py — Food ordering handler.
Handles the complete ordering flow: type selection, time slots, menu browsing, cart, checkout.
"""

import logging
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from agent import (
    get_session, add_to_cart, remove_from_cart, update_cart_qty,
    get_cart, get_cart_total, clear_cart, clear_session_flow
)
from scraper import (
    scrape_live_menu, scrape_time_slots, get_categories,
    get_items_by_category, FALLBACK_MENU
)
from database import create_order
from utils.keyboards import (
    order_type_keyboard, time_slots_keyboard, categories_keyboard,
    items_keyboard, cart_keyboard, checkout_confirm_keyboard,
    back_to_main_keyboard, main_menu_keyboard
)
from utils.formatters import (
    format_cart, format_order_confirmation, format_menu_items
)

logger = logging.getLogger(__name__)


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the food ordering flow."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    session = get_session(user_id)
    session["flow"] = "order"
    session["flow_state"] = "select_type"
    session["flow_data"] = {}

    text = (
        "🛍️ *Let's order some delicious food!*\n\n"
        "How would you like to receive your order?"
    )

    if query:
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=order_type_keyboard()
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=order_type_keyboard()
        )


async def handle_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pickup/delivery selection."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)

    order_type = query.data.split(":")[-1]  # pickup or delivery

    if order_type == "pickup":
        session["flow_data"]["order_type"] = "pickup"
        session["flow_state"] = "select_time"

        # Get time slots
        slots = scrape_time_slots()
        text = (
            "📍 *Pickup Order*\n"
            "Ready in ~20-30 min • Free\n\n"
            "Choose a pickup time slot:"
        )

        # Build keyboard with ASAP at the top
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        buttons = [[InlineKeyboardButton("⚡ ASAP (~20-30 min)", callback_data="slot:pick:ASAP")]]
        for period, slot_list in slots.items():
            buttons.append([InlineKeyboardButton(
                f"━━ {period} ━━", callback_data=f"slot:header:{period}"
            )])
            for slot in slot_list:
                left = slot.get("slots_left", "?")
                try:
                    left_int = int(str(left))
                    emoji = "🟢" if left_int > 3 else "🟡" if left_int > 1 else "🔴"
                except Exception:
                    emoji = "🟢"
                buttons.append([InlineKeyboardButton(
                    f"{emoji} {slot['time']}  ({left} left)",
                    callback_data=f"slot:pick:{slot['time']}"
                )])
        buttons.append([InlineKeyboardButton("◀️ Back", callback_data="order:back_type")])
        kb = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif order_type == "delivery":
        session["flow_data"]["order_type"] = "delivery"
        session["flow_state"] = "delivery_address"
        await query.edit_message_text(
            "🚗 *Delivery Order*\n\n"
            "Please type your *delivery address*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )


async def handle_time_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time slot selection."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)

    data = query.data
    if data.startswith("slot:header:"):
        # Just a section header, ignore
        return

    time_slot = data.replace("slot:pick:", "")
    session["flow_data"]["pickup_time"] = time_slot
    session["flow_state"] = "browse_menu"

    # Show menu categories
    await _show_categories(query, user_id)


async def _show_categories(query_or_msg, user_id: int):
    """Show menu categories."""
    categories = get_categories()
    text = (
        "📋 *Delish Menu*\n\n"
        "Choose a category to browse:\n"
        "_Tap a category to see items, then ➕ to add to cart_"
    )
    kb = categories_keyboard(categories)
    if isinstance(query_or_msg, CallbackQuery):
        await query_or_msg.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )
    else:
        await query_or_msg.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )


async def handle_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show items in a selected category."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    category = query.data.replace("cat:", "")
    items = get_items_by_category(category)

    if not items:
        await query.answer("No items found in this category", show_alert=True)
        return

    # Show items with formatted text and add buttons
    text = format_menu_items(items, category)

    # Add cart total if cart is not empty
    cart = get_cart(user_id)
    if cart:
        text += f"\n🛒 Cart: {len(cart)} items • ${get_cart_total(user_id):.2f}"

    kb = items_keyboard(items, category)
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )


async def handle_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add an item to the cart."""
    query = update.callback_query
    user_id = query.from_user.id

    parts = query.data.split(":")
    # item:add:NAME:PRICE
    item_name = parts[2]
    price = float(parts[3])

    # Find full item name from fallback menu
    full_name = item_name
    for cat, items in FALLBACK_MENU.items():
        for item in items:
            if item["name"][:30] == item_name:
                full_name = item["name"]
                break

    add_to_cart(user_id, full_name, price, qty=1)
    cart_total = get_cart_total(user_id)
    cart_count = len(get_cart(user_id))

    await query.answer(
        f"✅ Added {full_name}! Cart: {cart_count} items (${cart_total:.2f})",
        show_alert=False
    )


async def handle_item_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show item details."""
    query = update.callback_query
    await query.answer()

    item_name = query.data.replace("item:info:", "")

    # Find the item
    for cat, items in FALLBACK_MENU.items():
        for item in items:
            if item["name"][:30] == item_name:
                text = (
                    f"*{item['name']}*\n"
                    f"💰 ${item['price']:.2f}\n\n"
                    f"_{item.get('desc', 'No description available')}_"
                )
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        f"➕ Add to Cart (${item['price']:.2f})",
                        callback_data=f"item:add:{item['name'][:30]}:{item['price']}"
                    )],
                    [InlineKeyboardButton("◀️ Back", callback_data=f"cat:{cat}")],
                ])
                await query.edit_message_text(
                    text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
                )
                return


async def handle_cart_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current cart."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    cart = get_cart(user_id)
    text = format_cart(cart)
    has_items = len(cart) > 0

    if has_items:
        text += f"\n\n💰 *Total: ${get_cart_total(user_id):.2f}*"

    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=cart_keyboard(has_items)
    )


async def handle_cart_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the cart."""
    query = update.callback_query
    await query.answer("🗑️ Cart cleared!")
    user_id = query.from_user.id
    clear_cart(user_id)

    await query.edit_message_text(
        "🛒 Your cart is empty!\n\nBrowse our menu to add items.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=cart_keyboard(has_items=False)
    )


async def handle_quantity_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quantity increment/decrement."""
    query = update.callback_query
    user_id = query.from_user.id
    parts = query.data.split(":")

    action = parts[1]  # inc, dec, remove
    item_name = parts[2]

    # Find full item name
    full_name = item_name
    for cat, items in FALLBACK_MENU.items():
        for item in items:
            if item["name"][:30] == item_name:
                full_name = item["name"]
                break

    if action == "inc":
        update_cart_qty(user_id, full_name, 1)
        await query.answer(f"Added one more {full_name}")
    elif action == "dec":
        update_cart_qty(user_id, full_name, -1)
        await query.answer(f"Removed one {full_name}")
    elif action == "remove":
        remove_from_cart(user_id, full_name)
        await query.answer(f"Removed {full_name} from cart")

    # Refresh cart view
    cart = get_cart(user_id)
    text = format_cart(cart)
    has_items = len(cart) > 0
    if has_items:
        text += f"\n\n💰 *Total: ${get_cart_total(user_id):.2f}*"

    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=cart_keyboard(has_items)
    )


async def handle_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show checkout summary."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    cart = get_cart(user_id)
    if not cart:
        await query.answer("Your cart is empty!", show_alert=True)
        return

    session = get_session(user_id)
    order_type = session["flow_data"].get("order_type", "pickup")
    pickup_time = session["flow_data"].get("pickup_time", "ASAP")

    text = "📋 *Order Summary*\n━━━━━━━━━━━━━━━━━━━━\n"
    total = 0
    for item in cart:
        subtotal = item["price"] * item["qty"]
        total += subtotal
        text += f"  • {item['name']} ×{item['qty']}  —  ${subtotal:.2f}\n"

    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 *Total: ${total:.2f}*\n\n"
    text += f"📦 Type: *{order_type.title()}*\n"

    if order_type == "pickup":
        text += f"⏰ Pickup: *{pickup_time}*\n"
        text += f"📍 Location: *Delish, New York, NY*\n"
    else:
        addr = session["flow_data"].get("delivery_address", "Not set")
        text += f"🚗 Delivery to: *{addr}*\n"
        text += f"⏰ Est. delivery: *25-40 min*\n"

    # Check if we need customer info
    if not session["flow_data"].get("customer_name"):
        session["flow_state"] = "checkout_name"
        text += "\n\nPlease enter your *full name*:"
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )
        return

    text += "\n\n✅ Tap 'Confirm Order' to place your order!"
    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=checkout_confirm_keyboard()
    )


async def handle_checkout_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and place the order."""
    query = update.callback_query
    await query.answer("🎉 Placing your order...")
    user_id = query.from_user.id

    session = get_session(user_id)
    cart = get_cart(user_id)
    total = get_cart_total(user_id)

    if not cart:
        await query.answer("Cart is empty!", show_alert=True)
        return

    # Save to database
    order_id = await create_order(
        user_id=user_id,
        items=cart,
        total=total,
        order_type=session["flow_data"].get("order_type", "pickup"),
        delivery_address=session["flow_data"].get("delivery_address"),
        delivery_phone=session["flow_data"].get("delivery_phone"),
        pickup_time=session["flow_data"].get("pickup_time"),
        name=session["flow_data"].get("customer_name"),
        phone=session["flow_data"].get("customer_phone"),
        email=session["flow_data"].get("customer_email"),
    )

    # Format confirmation
    text = format_order_confirmation(
        order_id=order_id,
        items=cart,
        total=total,
        order_type=session["flow_data"].get("order_type", "pickup"),
        pickup_time=session["flow_data"].get("pickup_time"),
        delivery_address=session["flow_data"].get("delivery_address"),
    )

    # Clear cart and flow
    clear_cart(user_id)
    clear_session_flow(user_id)

    await query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard()
    )


async def handle_order_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle text input during order flow.
    Returns True if the message was handled, False otherwise.
    """
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session["flow"] != "order":
        return False

    text = update.message.text.strip()
    state = session["flow_state"]

    if state == "delivery_address":
        session["flow_data"]["delivery_address"] = text
        session["flow_state"] = "delivery_phone"
        await update.message.reply_text(
            "📱 Please enter your *phone number* for the delivery driver:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_main_keyboard()
        )
        return True

    elif state == "delivery_phone":
        # Basic phone validation
        phone = text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if len(phone) < 7:
            await update.message.reply_text(
                "❌ Please enter a valid phone number (at least 7 digits):",
                parse_mode=ParseMode.MARKDOWN
            )
            return True

        session["flow_data"]["delivery_phone"] = text
        session["flow_state"] = "browse_menu"

        # Show menu categories
        categories = get_categories()
        msg_text = (
            f"📍 Delivering to: *{session['flow_data']['delivery_address']}*\n"
            f"📱 Phone: *{text}*\n\n"
            "📋 *Delish Menu*\n\n"
            "Choose a category to browse:"
        )
        await update.message.reply_text(
            msg_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=categories_keyboard(categories)
        )
        return True

    elif state == "checkout_name":
        session["flow_data"]["customer_name"] = text
        session["flow_state"] = "checkout_phone"
        await update.message.reply_text(
            f"Thanks, *{text}*! 👋\n\nNow enter your *phone number* (for order updates):",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "checkout_phone":
        phone = text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if len(phone) < 7:
            await update.message.reply_text(
                "❌ Please enter a valid phone number:",
                parse_mode=ParseMode.MARKDOWN
            )
            return True

        session["flow_data"]["customer_phone"] = text
        session["flow_state"] = "checkout_email"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        skip_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip", callback_data="checkout:skip_email")]
        ])
        await update.message.reply_text(
            "📧 Enter your *email* (optional) or tap Skip:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=skip_kb
        )
        return True

    elif state == "checkout_email":
        session["flow_data"]["customer_email"] = text
        session["flow_state"] = "checkout_confirm"
        # Show final confirmation
        await _show_final_checkout(update.message, user_id)
        return True

    return False


async def handle_skip_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip email during checkout."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = get_session(user_id)
    session["flow_state"] = "checkout_confirm"
    await _show_final_checkout(query, user_id)


async def _show_final_checkout(msg_or_query, user_id):
    """Show the final checkout confirmation."""
    session = get_session(user_id)
    cart = get_cart(user_id)
    total = get_cart_total(user_id)
    order_type = session["flow_data"].get("order_type", "pickup")

    text = "📋 *Final Order Summary*\n━━━━━━━━━━━━━━━━━━━━\n"
    for item in cart:
        subtotal = item["price"] * item["qty"]
        text += f"  • {item['name']} ×{item['qty']}  —  ${subtotal:.2f}\n"

    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 *Total: ${total:.2f}*\n\n"
    text += f"👤 Name: *{session['flow_data'].get('customer_name', '—')}*\n"
    text += f"📱 Phone: *{session['flow_data'].get('customer_phone', '—')}*\n"

    if order_type == "pickup":
        text += f"📍 Pickup: *{session['flow_data'].get('pickup_time', 'ASAP')}*\n"
    else:
        text += f"🚗 Delivery: *{session['flow_data'].get('delivery_address', '—')}*\n"

    text += "\n✅ Ready to order? Tap Confirm!"

    if isinstance(msg_or_query, CallbackQuery):
        await msg_or_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=checkout_confirm_keyboard()
        )
    else:
        await msg_or_query.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=checkout_confirm_keyboard()
        )
