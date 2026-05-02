"""
keyboards.py — Telegram inline keyboard builders for all Delish Bot features.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─── MAIN MENU ────────────────────────────────────────────────

def main_menu_keyboard():
    """Main menu shown at /start and after completing a flow."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛍️ Order Food", callback_data="main:order"),
            InlineKeyboardButton("🎁 Gift Card", callback_data="main:gift_card"),
        ],
        [
            InlineKeyboardButton("🏛️ Banquet Hall", callback_data="main:banquet"),
            InlineKeyboardButton("📅 Reserve Table", callback_data="main:reservation"),
        ],
        [
            InlineKeyboardButton("⏭️ Order Ahead", callback_data="main:order_ahead"),
            InlineKeyboardButton("👥 Group Order", callback_data="main:group_order"),
        ],
        [
            InlineKeyboardButton("🍱 Catering", callback_data="main:catering"),
            InlineKeyboardButton("⏳ Join Waitlist", callback_data="main:waitlist"),
        ],
    ])


# ─── ORDER FLOW ───────────────────────────────────────────────

def order_type_keyboard():
    """Pickup or Delivery selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📍 Pickup (Free)", callback_data="order:pickup"),
            InlineKeyboardButton("🚗 Delivery", callback_data="order:delivery"),
        ],
        [InlineKeyboardButton("◀️ Back to Menu", callback_data="main:back")],
    ])


def time_slots_keyboard(slots_data: dict):
    """Build time slot buttons from scraped/fallback data."""
    buttons = []
    for period, slots in slots_data.items():
        buttons.append([InlineKeyboardButton(
            f"━━ {period} ━━", callback_data=f"slot:header:{period}"
        )])
        for slot in slots:
            left = slot.get("slots_left", "?")
            emoji = "🟢" if int(str(left)) > 3 else "🟡" if int(str(left)) > 1 else "🔴"
            buttons.append([InlineKeyboardButton(
                f"{emoji} {slot['time']}  ({left} left)",
                callback_data=f"slot:pick:{slot['time']}"
            )])
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="order:back_type")])
    return InlineKeyboardMarkup(buttons)


def categories_keyboard(categories: list):
    """Menu category selection buttons."""
    buttons = []
    row = []
    for i, cat in enumerate(categories):
        row.append(InlineKeyboardButton(cat, callback_data=f"cat:{cat}"))
        if len(row) == 3 or i == len(categories) - 1:
            buttons.append(row)
            row = []
    buttons.append([
        InlineKeyboardButton("🛒 View Cart", callback_data="cart:view"),
        InlineKeyboardButton("◀️ Back", callback_data="order:back_slots"),
    ])
    return InlineKeyboardMarkup(buttons)


def items_keyboard(items: list, category: str):
    """Menu items within a category, with add buttons."""
    buttons = []
    for item in items:
        buttons.append([
            InlineKeyboardButton(
                f"{item['name']} — ${item['price']:.2f}",
                callback_data=f"item:info:{item['name'][:30]}"
            ),
            InlineKeyboardButton(
                "➕", callback_data=f"item:add:{item['name'][:30]}:{item['price']}"
            ),
        ])
    buttons.append([
        InlineKeyboardButton("◀️ Categories", callback_data="order:show_cats"),
        InlineKeyboardButton("🛒 View Cart", callback_data="cart:view"),
    ])
    return InlineKeyboardMarkup(buttons)


def item_quantity_keyboard(item_name: str, current_qty: int):
    """Quantity adjustment for a cart item."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data=f"qty:dec:{item_name[:30]}"),
            InlineKeyboardButton(f" {current_qty} ", callback_data="qty:noop"),
            InlineKeyboardButton("➕", callback_data=f"qty:inc:{item_name[:30]}"),
        ],
        [
            InlineKeyboardButton("🗑️ Remove", callback_data=f"qty:remove:{item_name[:30]}"),
            InlineKeyboardButton("◀️ Back to Cart", callback_data="cart:view"),
        ],
    ])


def cart_keyboard(has_items: bool = True):
    """Cart actions keyboard."""
    if not has_items:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Browse Menu", callback_data="order:show_cats")],
            [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
        ])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Add More", callback_data="order:show_cats"),
            InlineKeyboardButton("🗑️ Clear Cart", callback_data="cart:clear"),
        ],
        [InlineKeyboardButton("✅ Checkout", callback_data="cart:checkout")],
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


def checkout_confirm_keyboard():
    """Final checkout confirmation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Order", callback_data="checkout:confirm"),
            InlineKeyboardButton("◀️ Edit Cart", callback_data="cart:view"),
        ],
    ])


# ─── BANQUET FLOW ─────────────────────────────────────────────

def banquet_event_types_keyboard():
    """Banquet event type selection."""
    events = [
        "Wedding", "Corporate", "Birthday", "Baby/Bridal Shower",
        "Graduation", "Holiday Party", "Bar/Bat Mitzvah", "Sweet 16", "Other"
    ]
    buttons = []
    row = []
    for e in events:
        row.append(InlineKeyboardButton(e, callback_data=f"banquet:event:{e}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")])
    return InlineKeyboardMarkup(buttons)


def banquet_food_keyboard():
    """Banquet food service options."""
    options = [
        ("Full Service", "Multi-course plated dinner"),
        ("Buffet", "Self-serve buffet style"),
        ("Appetizers Only", "Cocktail-style"),
        ("Custom", "Discuss with venue"),
        ("No Food", "Venue only"),
    ]
    buttons = [[InlineKeyboardButton(
        f"{name}", callback_data=f"banquet:food:{name}"
    )] for name, desc in options]
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="banquet:back_event")])
    return InlineKeyboardMarkup(buttons)


def banquet_bar_keyboard():
    """Banquet bar service options."""
    options = ["Open Bar", "Beer & Wine Only", "Cash Bar", "No Bar"]
    buttons = [[InlineKeyboardButton(o, callback_data=f"banquet:bar:{o}")] for o in options]
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="banquet:back_food")])
    return InlineKeyboardMarkup(buttons)


def banquet_room_keyboard():
    """Banquet room setup options."""
    options = ["Banquet Rounds", "Classroom", "Theater", "Cocktail/Standing", "Custom"]
    buttons = [[InlineKeyboardButton(o, callback_data=f"banquet:room:{o}")] for o in options]
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="banquet:back_bar")])
    return InlineKeyboardMarkup(buttons)


def banquet_confirm_keyboard():
    """Submit banquet inquiry."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Submit Banquet Inquiry", callback_data="banquet:submit")],
        [InlineKeyboardButton("✏️ Edit Details", callback_data="banquet:edit")],
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


def banquet_track_keyboard():
    """Track banquet inquiry."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Track My Inquiry", callback_data="banquet:track")],
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


# ─── GIFT CARD FLOW ──────────────────────────────────────────

def gift_card_amounts_keyboard():
    """Gift card amount selection."""
    amounts = ["$25", "$50", "$100", "$200", "$500"]
    buttons = []
    row = []
    for a in amounts:
        row.append(InlineKeyboardButton(a, callback_data=f"gift:amount:{a[1:]}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("💰 Custom Amount", callback_data="gift:amount:custom")])
    buttons.append([InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")])
    return InlineKeyboardMarkup(buttons)


def gift_card_confirm_keyboard():
    """Confirm gift card purchase."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Gift Card", callback_data="gift:confirm")],
        [InlineKeyboardButton("◀️ Edit", callback_data="gift:edit")],
    ])


# ─── RESERVATION FLOW ────────────────────────────────────────

def party_size_keyboard(prefix="res"):
    """Party size selection."""
    buttons = []
    row = []
    for i in range(1, 13):
        row.append(InlineKeyboardButton(str(i), callback_data=f"{prefix}:size:{i}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("13+", callback_data=f"{prefix}:size:13+")])
    buttons.append([InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")])
    return InlineKeyboardMarkup(buttons)


def reservation_time_keyboard():
    """Available reservation times."""
    times = [
        "11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM",
        "1:00 PM", "1:30 PM", "5:00 PM", "5:30 PM",
        "6:00 PM", "6:30 PM", "7:00 PM", "7:30 PM",
        "8:00 PM", "8:30 PM", "9:00 PM", "9:30 PM",
    ]
    buttons = []
    row = []
    for t in times:
        row.append(InlineKeyboardButton(t, callback_data=f"res:time:{t}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="res:back_date")])
    return InlineKeyboardMarkup(buttons)


def reservation_confirm_keyboard():
    """Confirm reservation."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Reservation", callback_data="res:confirm")],
        [InlineKeyboardButton("✏️ Edit", callback_data="res:edit")],
    ])


# ─── WAITLIST FLOW ────────────────────────────────────────────

def waitlist_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Join Waitlist", callback_data="wait:confirm")],
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


# ─── CATERING FLOW ────────────────────────────────────────────

def catering_event_keyboard():
    """Catering event type."""
    events = [
        "Corporate Lunch", "Wedding Reception", "Private Party",
        "Conference", "Holiday Event", "Birthday", "Other"
    ]
    buttons = [[InlineKeyboardButton(e, callback_data=f"cater:event:{e}")] for e in events]
    buttons.append([InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")])
    return InlineKeyboardMarkup(buttons)


def catering_service_keyboard():
    """Catering service style."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚚 Drop-off Only", callback_data="cater:style:Drop-off")],
        [InlineKeyboardButton("👨‍🍳 Full Catering Crew", callback_data="cater:style:Full Crew")],
        [InlineKeyboardButton("◀️ Back", callback_data="cater:back")],
    ])


def catering_cuisine_keyboard():
    """Dietary preferences."""
    prefs = ["No Restrictions", "Vegetarian", "Vegan", "Halal", "Gluten-Free", "Kosher"]
    buttons = [[InlineKeyboardButton(p, callback_data=f"cater:diet:{p}")] for p in prefs]
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="cater:back_style")])
    return InlineKeyboardMarkup(buttons)


def catering_budget_keyboard():
    """Budget range selection."""
    ranges = ["$500-$1000", "$1000-$2500", "$2500-$5000", "$5000-$10000", "$10000+", "Flexible"]
    buttons = [[InlineKeyboardButton(r, callback_data=f"cater:budget:{r}")] for r in ranges]
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="cater:back_diet")])
    return InlineKeyboardMarkup(buttons)


def catering_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Submit Catering Inquiry", callback_data="cater:submit")],
        [InlineKeyboardButton("✏️ Edit", callback_data="cater:edit")],
    ])


# ─── GROUP ORDER FLOW ────────────────────────────────────────

def group_order_start_keyboard():
    """Start or join a group order."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Create Group Order", callback_data="group:create")],
        [InlineKeyboardButton("🔗 Join Group Order", callback_data="group:join")],
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


def group_order_manage_keyboard(code: str):
    """Organizer management keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👀 View Members", callback_data=f"group:members:{code}")],
        [InlineKeyboardButton("🔒 Close & Compile Order", callback_data=f"group:close:{code}")],
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


# ─── COMMON ──────────────────────────────────────────────────

def back_to_main_keyboard():
    """Simple back to main menu button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Main Menu", callback_data="main:back")],
    ])


def yes_no_keyboard(prefix: str):
    """Generic yes/no keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"{prefix}:yes"),
            InlineKeyboardButton("❌ No", callback_data=f"{prefix}:no"),
        ],
    ])
