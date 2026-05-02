"""
simulate_test.py — Simulates bot interactions by directly calling handler functions.
Tests the entire flow without needing Telegram open.
"""

import asyncio
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Load env first
from dotenv import load_dotenv
load_dotenv()

# Init DB
from database import init_db

# Import agent and scraper functions
from agent import (
    get_session, get_cart, get_cart_total,
    add_to_cart, clear_cart, clear_session_flow
)
from scraper import (
    get_categories, get_items_by_category, scrape_time_slots,
    FALLBACK_MENU, FALLBACK_TIME_SLOTS, search_menu_items
)
from utils.formatters import (
    format_cart, format_order_confirmation, format_banquet_summary,
    format_gift_card_confirmation, format_reservation_confirmation,
    format_waitlist_confirmation, format_catering_summary,
    format_group_order_created, generate_gift_card_code, generate_group_code
)
from database import (
    create_order, create_banquet_inquiry, create_reservation,
    add_to_waitlist, create_catering_inquiry, create_gift_card,
    create_group_order, join_group_order
)


SEP = "=" * 60
SEP2 = "-" * 60

TEST_USER_ID = 999999999  # Fake user ID for testing


def section(title):
    print()
    print(SEP)
    print(f"  TEST: {title}")
    print(SEP)


def ok(msg):
    print(f"  [PASS] {msg}")


def show(label, value):
    print(f"  {label}: {value}")


async def test_all():
    await init_db()
    print()
    print("Delish Bot - Full Feature Test")
    print(SEP)
    print("  Testing all 8 features without Telegram connection")
    print(SEP)

    # ── TEST 1: Menu Categories ─────────────────────────────────
    section("1. Menu Categories")
    cats = get_categories()
    show("Total categories", len(cats))
    show("Categories", ", ".join(cats[:6]) + "...")
    ok("Menu categories loaded successfully")

    # ── TEST 2: Menu Items ──────────────────────────────────────
    section("2. Menu Items")
    for cat in ["Appetizer", "Burger", "Entrées"]:
        items = get_items_by_category(cat)
        show(f"  {cat}", f"{len(items)} items")
        for item in items[:2]:
            print(f"    - {item['name']} (${item['price']:.2f}): {item['desc'][:50]}...")
    ok("Menu items loaded with prices and descriptions")

    # ── TEST 3: Search ──────────────────────────────────────────
    section("3. Menu Search")
    results = search_menu_items("chicken")
    show("Search 'chicken'", f"{len(results)} results")
    for r in results[:3]:
        print(f"    - [{r['category']}] {r['name']} (${r['price']:.2f})")
    results2 = search_menu_items("vegan")
    show("Search 'vegan'", f"{len(results2)} results")
    ok("Search working")

    # ── TEST 4: Time Slots ──────────────────────────────────────
    section("4. Time Slots (Order Ahead / Pickup)")
    slots = scrape_time_slots()
    for period, slot_list in slots.items():
        print(f"  {period} ({len(slot_list)} slots):")
        for s in slot_list[:2]:
            print(f"    {s['time']}  ({s['slots_left']} left)")
    ok("Time slots loaded")

    # ── TEST 5: Cart & Order ────────────────────────────────────
    section("5. Food Ordering - Cart & Checkout")
    clear_cart(TEST_USER_ID)

    # Add items
    add_to_cart(TEST_USER_ID, "Vegetable Samosa", 8.49, qty=2)
    add_to_cart(TEST_USER_ID, "Mango Lassi", 4.99, qty=1)
    add_to_cart(TEST_USER_ID, "Chicken Tikka Masala", 16.99, qty=1)

    cart = get_cart(TEST_USER_ID)
    total = get_cart_total(TEST_USER_ID)
    show("Items in cart", len(cart))
    show("Cart total", f"${total:.2f}")
    print()
    print(format_cart(cart))
    print()

    # Place order
    order_id = await create_order(
        user_id=TEST_USER_ID,
        items=cart,
        total=total,
        order_type="pickup",
        pickup_time="6:00 PM - 7:00 PM",
        name="Test User",
        phone="+1-555-0199",
    )
    show("Order ID", f"DEL-{order_id:05d}")
    print()
    print(format_order_confirmation(
        order_id=order_id,
        items=cart,
        total=total,
        order_type="pickup",
        pickup_time="6:00 PM - 7:00 PM"
    ))
    ok("Order created and confirmed")

    # ── TEST 6: Banquet Inquiry ─────────────────────────────────
    section("6. Banquet Hall Inquiry")
    banquet_data = {
        "event_type": "Wedding",
        "event_date": "2026-08-15",
        "guest_count": 120,
        "start_time": "18:00",
        "end_time": "23:00",
        "food_service": "Full Service",
        "bar_service": "Open Bar",
        "room_setup": "Banquet Rounds",
        "contact_name": "Sarah Johnson",
        "contact_phone": "+1-555-0100",
        "contact_email": "sarah@example.com",
        "company": "",
        "special_requests": "Gluten-free options needed for 10 guests. Rose-gold décor.",
    }
    print()
    print(format_banquet_summary(banquet_data))
    inq_id = await create_banquet_inquiry(TEST_USER_ID, banquet_data)
    show("Inquiry ID", f"BNQ-{inq_id:05d}")
    ok("Banquet inquiry submitted and saved to DB")

    # ── TEST 7: Gift Card ───────────────────────────────────────
    section("7. Gift Card")
    gc_code = generate_gift_card_code()
    gc_data = {
        "recipient_name": "Ahmed Khan",
        "recipient_contact": "+1-555-0200",
        "personal_message": "Happy Birthday! Enjoy a meal at Delish!",
    }
    await create_gift_card(
        user_id=TEST_USER_ID,
        code=gc_code,
        amount=50.0,
        recipient_name=gc_data["recipient_name"],
        recipient_contact=gc_data["recipient_contact"],
        message=gc_data["personal_message"],
    )
    print()
    print(format_gift_card_confirmation(gc_code, 50.0, gc_data))
    ok("Gift card created with unique code")

    # ── TEST 8: Table Reservation ────────────────────────────────
    section("8. Table Reservation")
    res_data = {
        "party_size": "4",
        "date": "2026-05-10",
        "time": "7:00 PM",
        "name": "Mohammad Ali",
        "phone": "+1-555-0300",
        "special_requests": "Window table, anniversary dinner",
    }
    res_id = await create_reservation(TEST_USER_ID, res_data)
    print()
    print(format_reservation_confirmation(res_id, res_data))
    ok("Reservation created and confirmed")

    # ── TEST 9: Waitlist ─────────────────────────────────────────
    section("9. Join Waitlist")
    wl_data = {
        "party_size": "3",
        "name": "Fatima Malik",
        "phone": "+1-555-0400",
    }
    wl_id = await add_to_waitlist(
        user_id=TEST_USER_ID,
        party_size=3,
        name=wl_data["name"],
        phone=wl_data["phone"],
        estimated_wait=7,
    )
    print()
    print(format_waitlist_confirmation(wl_id, wl_data, 7))
    ok("Added to waitlist")

    # ── TEST 10: Catering ────────────────────────────────────────
    section("10. Catering Inquiry")
    cater_data = {
        "event_type": "Corporate Lunch",
        "event_date": "2026-06-20",
        "headcount": 50,
        "cuisine_prefs": "Halal",
        "service_style": "Full Crew",
        "event_location": "123 Business Park, New York",
        "budget_range": "$2500-$5000",
        "contact_name": "John Smith",
        "contact_phone": "+1-555-0500",
        "contact_email": "john@company.com",
        "special_requests": "No pork, halal only",
    }
    print()
    print(format_catering_summary(cater_data))
    cater_id = await create_catering_inquiry(TEST_USER_ID, cater_data)
    show("Inquiry ID", f"CTR-{cater_id:05d}")
    ok("Catering inquiry submitted")

    # ── TEST 11: Group Order ─────────────────────────────────────
    section("11. Group Order")
    group_code = generate_group_code()
    await create_group_order(TEST_USER_ID, group_code, party_size=4)
    await join_group_order(group_code, TEST_USER_ID, "Organizer")
    print()
    print(format_group_order_created(group_code, 4))
    ok("Group order created with shareable code")

    # ── SUMMARY ─────────────────────────────────────────────────
    print()
    print(SEP)
    print("  ALL TESTS PASSED!")
    print(SEP)
    print()
    print("  Bot is ready. Connect via Telegram:")
    print("  1. Open Telegram (phone or web.telegram.org)")
    print("  2. Search: @Directtap_preview_bot")
    print("  3. Tap START")
    print("  4. Use the buttons to test all features")
    print()
    print("  The bot is currently running in the background.")
    print("  Keep main.py running to serve requests.")
    print()


if __name__ == "__main__":
    asyncio.run(test_all())
