"""
formatters.py — Message formatting utilities for the Delish Bot.
Pretty-prints orders, carts, confirmations, and summaries.
"""

import json
import random
import string
from datetime import datetime


def format_cart(cart: list) -> str:
    """Format cart items into a readable message."""
    if not cart:
        return "🛒 Your cart is empty!"

    lines = ["🛒 *Your Cart*\n━━━━━━━━━━━━━━━━━━━━"]
    total = 0.0
    for i, item in enumerate(cart, 1):
        subtotal = item["price"] * item["qty"]
        total += subtotal
        lines.append(
            f"{i}. {item['name']}  ×{item['qty']}  —  ${subtotal:.2f}"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"*Subtotal: ${total:.2f}*")
    return "\n".join(lines)


def format_order_confirmation(order_id: int, items: list, total: float,
                               order_type: str, pickup_time=None,
                               delivery_address=None) -> str:
    """Format the order confirmation message."""
    lines = [
        "✅ *ORDER CONFIRMED!*",
        "",
        f"🆔 Order ID: *DEL-{order_id:05d}*",
        f"📋 Type: *{order_type.title()}*",
        "",
        "━━ Items ━━━━━━━━━━━━━━━━"
    ]
    for item in items:
        lines.append(f"  • {item['name']} ×{item['qty']}  —  ${item['price'] * item['qty']:.2f}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 *Total: ${total:.2f}*")
    lines.append("")

    if order_type == "pickup":
        lines.append(f"⏰ Pickup Time: *{pickup_time or 'ASAP (~20-30 min)'}*")
        lines.append("📍 Pickup at: *Delish, New York, NY*")
    else:
        lines.append(f"🚗 Delivery to: *{delivery_address}*")
        lines.append("⏰ Estimated delivery: *25-40 minutes*")

    lines.append("")
    lines.append("🍽️ *Your order has been received by Delish kitchen!*")
    lines.append("Thank you for ordering with us! 🎉")
    return "\n".join(lines)


def format_banquet_summary(data: dict) -> str:
    """Format banquet inquiry summary."""
    lines = [
        "🏛️ *Banquet Inquiry Summary*",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"  Event     │ {data.get('event_type', '—')}",
        f"  Date      │ {data.get('event_date', '—')}",
        f"  Time      │ {data.get('start_time', '—')} – {data.get('end_time', '—')}",
        f"  Guests    │ {data.get('guest_count', '—')}",
        f"  Food      │ {data.get('food_service', '—')}",
        f"  Bar       │ {data.get('bar_service', '—')}",
        f"  Room      │ {data.get('room_setup', '—')}",
        f"  Contact   │ {data.get('contact_name', '—')}",
        f"  Phone     │ {data.get('contact_phone', '—')}",
    ]
    if data.get("contact_email"):
        lines.append(f"  Email     │ {data['contact_email']}")
    if data.get("company"):
        lines.append(f"  Company   │ {data['company']}")
    if data.get("special_requests"):
        lines.append(f"  Requests  │ {data['special_requests']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_banquet_confirmation(inquiry_id: int) -> str:
    """Format banquet inquiry submission confirmation."""
    return (
        f"✅ *Inquiry Submitted!*\n\n"
        f"🆔 Inquiry ID: *BNQ-{inquiry_id:05d}*\n\n"
        f"This is an inquiry only. No payment until you receive and accept a quote.\n\n"
        f"📞 Our team will contact you within *4 hours*.\n\n"
        f"_You can track your inquiry anytime by tapping 'Track my banquet inquiry'._"
    )


def format_reservation_confirmation(res_id: int, data: dict) -> str:
    """Format reservation confirmation."""
    return (
        f"✅ *Reservation Confirmed!*\n\n"
        f"🆔 Reservation ID: *RSV-{res_id:05d}*\n\n"
        f"👤 Name: *{data.get('name', '—')}*\n"
        f"👥 Party Size: *{data.get('party_size', '—')}*\n"
        f"📅 Date: *{data.get('date', '—')}*\n"
        f"⏰ Time: *{data.get('time', '—')}*\n"
        f"📱 Phone: *{data.get('phone', '—')}*\n"
        + (f"📝 Requests: _{data['special_requests']}_\n" if data.get("special_requests") else "")
        + f"\n📍 *Delish — New York, NY*\n"
        f"We look forward to seeing you! 🎉"
    )


def format_waitlist_confirmation(waitlist_id: int, data: dict, wait_min: int = 5) -> str:
    """Format waitlist join confirmation."""
    return (
        f"✅ *Added to Waitlist!*\n\n"
        f"🆔 Waitlist ID: *WL-{waitlist_id:05d}*\n\n"
        f"👤 Name: *{data.get('name', '—')}*\n"
        f"👥 Party Size: *{data.get('party_size', '—')}*\n"
        f"📱 Phone: *{data.get('phone', '—')}*\n\n"
        f"⏳ Estimated Wait: *~{wait_min} minutes*\n\n"
        f"We'll notify you when your table is ready! 🔔"
    )


def format_waitlist_ready() -> str:
    """Format table-ready notification."""
    return (
        "🔔 *Your table is ready!*\n\n"
        "🍽️ Please arrive at *Delish* within *10 minutes*.\n\n"
        "📍 Delish — New York, NY\n\n"
        "See you soon! 🎉"
    )


def format_gift_card_confirmation(code: str, amount: float, data: dict) -> str:
    """Format gift card purchase confirmation."""
    return (
        f"🎁 *Gift Card Created!*\n\n"
        f"💳 Code: `{code}`\n"
        f"💰 Amount: *${amount:.2f}*\n\n"
        f"👤 Recipient: *{data.get('recipient_name', '—')}*\n"
        f"📱 Contact: *{data.get('recipient_contact', '—')}*\n"
        + (f"💌 Message: _{data.get('personal_message')}_\n" if data.get("personal_message") else "")
        + f"\n✨ Share this code with the recipient to redeem at Delish!"
    )


def format_catering_summary(data: dict) -> str:
    """Format catering inquiry summary."""
    lines = [
        "🍱 *Catering Inquiry Summary*",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"  Event        │ {data.get('event_type', '—')}",
        f"  Date         │ {data.get('event_date', '—')}",
        f"  Headcount    │ {data.get('headcount', '—')}",
        f"  Cuisine      │ {data.get('cuisine_prefs', '—')}",
        f"  Service      │ {data.get('service_style', '—')}",
        f"  Location     │ {data.get('event_location', '—')}",
        f"  Budget       │ {data.get('budget_range', '—')}",
        f"  Contact      │ {data.get('contact_name', '—')}",
        f"  Phone        │ {data.get('contact_phone', '—')}",
    ]
    if data.get("contact_email"):
        lines.append(f"  Email        │ {data['contact_email']}")
    if data.get("special_requests"):
        lines.append(f"  Requests     │ {data['special_requests']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_catering_confirmation(inquiry_id: int) -> str:
    """Format catering submission confirmation."""
    return (
        f"✅ *Catering Inquiry Submitted!*\n\n"
        f"🆔 Inquiry ID: *CTR-{inquiry_id:05d}*\n\n"
        f"Our catering team will review your request and contact you within *24 hours* "
        f"with a custom quote.\n\n"
        f"Thank you for choosing Delish Catering! 🍽️"
    )


def format_group_order_created(code: str, party_size: int) -> str:
    """Format group order creation message."""
    return (
        f"👥 *Group Order Created!*\n\n"
        f"🔗 Share this code with your group:\n\n"
        f"📋 Code: `{code}`\n"
        f"👥 Party Size: *{party_size}*\n\n"
        f"Each member can join using this code and add their own items.\n"
        f"When everyone is done, tap 'Close & Compile Order' to finalize."
    )


def format_group_order_summary(code: str, members: list, all_items: list) -> str:
    """Format compiled group order summary."""
    lines = [
        f"👥 *Group Order Summary*",
        f"📋 Code: `{code}`",
        "",
        "━━ Members & Items ━━━━━━━━━━"
    ]
    total = 0.0
    for member in members:
        items = json.loads(member.get("items_json", "[]"))
        member_total = sum(i["price"] * i["qty"] for i in items)
        total += member_total
        lines.append(f"\n👤 *{member.get('user_name', 'Member')}* — ${member_total:.2f}")
        for item in items:
            lines.append(f"  • {item['name']} ×{item['qty']}")
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 *Grand Total: ${total:.2f}*")
    return "\n".join(lines)


def format_menu_items(items: list, category: str) -> str:
    """Format menu items for display."""
    lines = [f"📋 *{category}*\n"]
    for item in items:
        lines.append(f"  *{item['name']}* — ${item['price']:.2f}")
        if item.get("desc"):
            lines.append(f"  _{item['desc']}_")
        lines.append("")
    return "\n".join(lines)


def generate_order_id() -> str:
    """Generate a readable order reference."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def generate_gift_card_code() -> str:
    """Generate a gift card code like DEAR-XXXX-XXXX."""
    part1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"DLSH-{part1}-{part2}"


def generate_group_code() -> str:
    """Generate a group order code."""
    return "GRP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
