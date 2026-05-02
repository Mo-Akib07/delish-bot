"""
scraper.py — Firecrawl-powered live menu scraper with hardcoded fallback.
Scrapes the DirectTap Delish menu (React SPA) using Firecrawl's JS rendering.
"""

import os
import re
import json
import logging
from firecrawl import FirecrawlApp

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
RESTAURANT_URL = os.getenv("RESTAURANT_URL", "https://sandbox.directtap.ai/menu/delish")

# ─── FALLBACK MENU (scraped from live site) ───────────────────

FALLBACK_MENU = {
    "Appetizer": [
        {"name": "Vegetable Samosa", "price": 8.49, "desc": "Turnovers stuffed with red bliss potatoes, peas, herbs, and spices. Served with tamarind chutney. Baked. Vegan."},
        {"name": "Chicken Kabob Appetizer", "price": 10.99, "desc": "Tender marinated chicken skewers with mint chutney"},
        {"name": "Nachos", "price": 9.49, "desc": "Tortilla chips with salsa and cheese"},
        {"name": "Crispy Wings", "price": 13.99, "desc": "8 wings, choice of buffalo, BBQ, or garlic parm"},
        {"name": "Calamari Fritti", "price": 12.99, "desc": "Lightly breaded, spicy marinara dipping sauce"},
        {"name": "Soup of the Day", "price": 7.99, "desc": "Chef's rotating daily soup — ask your server"},
        {"name": "Shrimp Cocktail", "price": 14.99, "desc": "6 jumbo shrimp, house cocktail sauce, lemon"},
    ],
    "Appetizers": [
        {"name": "Bruschetta", "price": 9.99, "desc": "Toasted bread with fresh tomatoes, basil, and balsamic glaze"},
        {"name": "Spring Rolls", "price": 8.99, "desc": "Crispy vegetable spring rolls with sweet chili sauce"},
        {"name": "Stuffed Mushrooms", "price": 10.49, "desc": "Portobello caps stuffed with herbed cream cheese"},
        {"name": "Hummus Platter", "price": 9.49, "desc": "House-made hummus with warm pita and vegetables"},
    ],
    "Beverages": [
        {"name": "Mango Lassi", "price": 4.99, "desc": "Traditional yogurt-based mango smoothie"},
        {"name": "Masala Chai", "price": 3.49, "desc": "Spiced Indian tea with steamed milk"},
        {"name": "Fresh Lime Soda", "price": 3.99, "desc": "Fresh squeezed lime with soda water"},
        {"name": "Iced Tea", "price": 2.99, "desc": "House-brewed with lemon"},
        {"name": "Strawberry Shake", "price": 5.99, "desc": "Creamy strawberry milkshake"},
    ],
    "Breads": [
        {"name": "Garlic Naan", "price": 3.99, "desc": "Fresh baked with roasted garlic butter"},
        {"name": "Butter Naan", "price": 3.49, "desc": "Classic buttery naan bread"},
        {"name": "Tandoori Roti", "price": 2.99, "desc": "Whole wheat bread from the tandoor"},
        {"name": "Cheese Naan", "price": 4.49, "desc": "Stuffed with melted mozzarella and cheddar"},
        {"name": "Peshawari Naan", "price": 4.99, "desc": "Stuffed with coconut, raisins, and nuts"},
    ],
    "Burger": [
        {"name": "Classic Burger", "price": 12.99, "desc": "Angus beef patty, lettuce, tomato, house sauce"},
        {"name": "Cheese Burger", "price": 14.99, "desc": "Double patty with American cheese and pickles"},
        {"name": "Spicy Burger", "price": 15.99, "desc": "Jalapeño-infused patty with pepper jack cheese and sriracha mayo"},
        {"name": "Veggie Burger", "price": 11.99, "desc": "House-made black bean patty with avocado"},
        {"name": "BBQ Bacon Burger", "price": 16.99, "desc": "Smoked bacon, onion rings, BBQ sauce"},
    ],
    "Cheese": [
        {"name": "Cheese Platter", "price": 18.99, "desc": "Artisan cheese selection with crackers, nuts, and honey"},
        {"name": "Mozzarella Sticks", "price": 9.99, "desc": "Breaded and fried with marinara sauce"},
        {"name": "Cheese Fondue", "price": 22.99, "desc": "Swiss and gruyère blend with bread and vegetables for dipping"},
        {"name": "Mac & Cheese Bites", "price": 8.99, "desc": "Crispy fried mac and cheese balls"},
    ],
    "Desserts": [
        {"name": "Gulab Jamun", "price": 6.99, "desc": "Warm milk-solid dumplings in rose-scented syrup"},
        {"name": "Chocolate Lava Cake", "price": 9.99, "desc": "Warm chocolate cake with molten center and vanilla ice cream"},
        {"name": "Tiramisu", "price": 8.99, "desc": "Classic Italian coffee-flavored dessert"},
        {"name": "New York Cheesecake", "price": 7.99, "desc": "Creamy cheesecake with berry compote"},
        {"name": "Kheer", "price": 5.99, "desc": "Indian rice pudding with cardamom and pistachios"},
    ],
    "Drink": [
        {"name": "Coca Cola", "price": 2.49, "desc": "Classic Coca Cola"},
        {"name": "Sprite", "price": 2.49, "desc": "Lemon-lime soda"},
        {"name": "Orange Juice", "price": 3.99, "desc": "Freshly squeezed"},
        {"name": "Sparkling Water", "price": 2.99, "desc": "San Pellegrino"},
        {"name": "Ginger Ale", "price": 2.49, "desc": "Canada Dry"},
    ],
    "Drinks": [
        {"name": "Craft Beer", "price": 7.99, "desc": "Ask about today's rotating selection"},
        {"name": "House Wine", "price": 9.99, "desc": "Red or white, by the glass"},
        {"name": "Cocktail Special", "price": 12.99, "desc": "Bartender's featured cocktail of the day"},
        {"name": "Mocktail", "price": 6.99, "desc": "Virgin mojito or passion fruit fizz"},
        {"name": "Sangria", "price": 10.99, "desc": "House-made red sangria with fresh fruit"},
    ],
    "Entrées": [
        {"name": "Chicken Tikka Masala", "price": 16.99, "desc": "Tender chicken in creamy tomato-spice sauce with basmati rice"},
        {"name": "Grilled Salmon", "price": 22.99, "desc": "Atlantic salmon with lemon-dill sauce, roasted vegetables"},
        {"name": "Lamb Biryani", "price": 18.99, "desc": "Fragrant basmati rice with tender lamb and aromatic spices"},
        {"name": "Pasta Primavera", "price": 14.99, "desc": "Penne with seasonal vegetables in garlic cream sauce"},
        {"name": "Ribeye Steak", "price": 28.99, "desc": "12oz USDA prime ribeye with mashed potatoes and asparagus"},
    ],
    "Kids Menu": [
        {"name": "Chicken Tenders", "price": 8.99, "desc": "Crispy chicken tenders with fries and honey mustard"},
        {"name": "Mac & Cheese", "price": 7.99, "desc": "Creamy three-cheese macaroni"},
        {"name": "Mini Burger", "price": 9.99, "desc": "Small beef patty with fries"},
        {"name": "Grilled Cheese", "price": 6.99, "desc": "Classic grilled cheese with tomato soup"},
    ],
    "Main Course": [
        {"name": "Butter Chicken", "price": 15.99, "desc": "Creamy tomato-butter sauce with tender chicken"},
        {"name": "Paneer Tikka", "price": 13.99, "desc": "Marinated cottage cheese grilled in tandoor"},
        {"name": "Fish & Chips", "price": 16.99, "desc": "Beer-battered cod with crispy fries and tartar sauce"},
        {"name": "Roast Chicken", "price": 19.99, "desc": "Herb-roasted half chicken with root vegetables"},
        {"name": "Dal Makhani", "price": 12.99, "desc": "Slow-cooked black lentils in creamy tomato sauce"},
        {"name": "Palak Paneer", "price": 13.49, "desc": "Cottage cheese cubes in smooth spinach gravy"},
    ],
    "Random": [
        {"name": "Chef's Special", "price": 24.99, "desc": "Daily rotating special — ask your server for today's creation"},
        {"name": "Mystery Box", "price": 29.99, "desc": "A surprise 3-course meal curated by our head chef"},
    ],
}

# All categories
MENU_CATEGORIES = list(FALLBACK_MENU.keys())

# Flatten for search
ALL_ITEMS = []
for cat, items in FALLBACK_MENU.items():
    for item in items:
        ALL_ITEMS.append({**item, "category": cat})


# ─── FALLBACK TIME SLOTS ─────────────────────────────────────

FALLBACK_TIME_SLOTS = {
    "Late Night": [
        {"time": "12:00 AM - 2:00 AM", "slots_left": 8},
        {"time": "2:00 AM - 4:00 AM", "slots_left": 12},
    ],
    "Breakfast": [
        {"time": "7:00 AM - 8:00 AM", "slots_left": 5},
        {"time": "8:00 AM - 9:00 AM", "slots_left": 3},
        {"time": "9:00 AM - 10:00 AM", "slots_left": 7},
    ],
    "Lunch": [
        {"time": "11:00 AM - 12:00 PM", "slots_left": 4},
        {"time": "12:00 PM - 1:00 PM", "slots_left": 2},
        {"time": "1:00 PM - 2:00 PM", "slots_left": 6},
        {"time": "2:00 PM - 3:00 PM", "slots_left": 9},
    ],
    "Dinner": [
        {"time": "5:00 PM - 6:00 PM", "slots_left": 3},
        {"time": "6:00 PM - 7:00 PM", "slots_left": 1},
        {"time": "7:00 PM - 8:00 PM", "slots_left": 2},
        {"time": "8:00 PM - 9:00 PM", "slots_left": 5},
        {"time": "9:00 PM - 10:00 PM", "slots_left": 8},
    ],
}


# ─── FIRECRAWL SCRAPER ────────────────────────────────────────

def _init_firecrawl():
    """Initialize Firecrawl client."""
    if not FIRECRAWL_API_KEY:
        return None
    try:
        return FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    except Exception as e:
        logger.error(f"Failed to init Firecrawl: {e}")
        return None


def scrape_live_menu(category: str = None) -> dict:
    """
    Scrape the live menu from DirectTap using Firecrawl.
    Falls back to hardcoded menu on failure.
    Returns: {category: [{name, price, desc}]}
    """
    app = _init_firecrawl()
    if not app:
        logger.info("Firecrawl not available, using fallback menu")
        if category:
            return {category: FALLBACK_MENU.get(category, [])}
        return FALLBACK_MENU

    try:
        result = app.scrape(
            RESTAURANT_URL,
            formats=["markdown"],
            wait_for=5000,
            actions=[
                {"type": "wait", "milliseconds": 3000},
                {"type": "scroll", "direction": "down", "amount": 3},
            ]
        )

        markdown = result.get("markdown", "") if isinstance(result, dict) else ""
        if not markdown:
            logger.warning("Empty scrape result, using fallback")
            if category:
                return {category: FALLBACK_MENU.get(category, [])}
            return FALLBACK_MENU

        parsed = _parse_menu_markdown(markdown)
        if not parsed:
            logger.warning("Parse returned empty, using fallback")
            if category:
                return {category: FALLBACK_MENU.get(category, [])}
            return FALLBACK_MENU

        if category:
            return {category: parsed.get(category, FALLBACK_MENU.get(category, []))}
        return parsed

    except Exception as e:
        logger.error(f"Firecrawl scrape failed: {e}")
        if category:
            return {category: FALLBACK_MENU.get(category, [])}
        return FALLBACK_MENU


def _parse_menu_markdown(markdown: str) -> dict:
    """Parse scraped markdown into structured menu data."""
    menu = {}
    current_category = None

    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect category headers (## Category or **Category**)
        cat_match = re.match(r'^#{1,3}\s+(.+)$', line)
        if not cat_match:
            cat_match = re.match(r'^\*\*(.+)\*\*$', line)

        if cat_match:
            potential_cat = cat_match.group(1).strip()
            if potential_cat in MENU_CATEGORIES:
                current_category = potential_cat
                if current_category not in menu:
                    menu[current_category] = []
                i += 1
                continue

        # Detect items with prices ($X.XX pattern)
        if current_category:
            price_match = re.search(r'\$(\d+\.?\d*)', line)
            if price_match:
                price = float(price_match.group(1))
                name = re.sub(r'\$\d+\.?\d*', '', line).strip()
                name = re.sub(r'^[-*•]\s*', '', name).strip()
                name = re.sub(r'\*\*(.+)\*\*', r'\1', name).strip()

                desc = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.search(r'\$\d+\.?\d*', next_line) and not re.match(r'^#{1,3}', next_line):
                        desc = next_line.strip("*- ")
                        i += 1

                if name:
                    menu[current_category].append({
                        "name": name,
                        "price": price,
                        "desc": desc
                    })
        i += 1

    return menu


def scrape_time_slots() -> dict:
    """Scrape available time slots. Returns fallback on failure."""
    app = _init_firecrawl()
    if not app:
        return FALLBACK_TIME_SLOTS

    try:
        result = app.scrape(
            RESTAURANT_URL.replace("/menu/", "/order-ahead/"),
            formats=["markdown"],
            wait_for=5000,
        )
        markdown = result.get("markdown", "") if isinstance(result, dict) else ""
        if not markdown:
            return FALLBACK_TIME_SLOTS

        # Try to parse time slots from markdown
        slots = _parse_time_slots(markdown)
        return slots if slots else FALLBACK_TIME_SLOTS

    except Exception as e:
        logger.error(f"Time slot scrape failed: {e}")
        return FALLBACK_TIME_SLOTS


def _parse_time_slots(markdown: str) -> dict:
    """Parse time slot information from scraped content."""
    slots = {}
    lines = markdown.split("\n")
    current_period = None

    for line in lines:
        line = line.strip()
        for period in ["Late Night", "Breakfast", "Lunch", "Dinner"]:
            if period.lower() in line.lower():
                current_period = period
                if current_period not in slots:
                    slots[current_period] = []
                break

        if current_period:
            time_match = re.search(
                r'(\d{1,2}:\d{2}\s*(?:AM|PM)\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM))',
                line, re.IGNORECASE
            )
            left_match = re.search(r'(\d+)\s*left', line, re.IGNORECASE)

            if time_match:
                slot = {"time": time_match.group(1)}
                slot["slots_left"] = int(left_match.group(1)) if left_match else 5
                slots[current_period].append(slot)

    return slots


def search_menu_items(query: str) -> list:
    """Search menu items by name or description."""
    query_lower = query.lower()
    results = []
    for item in ALL_ITEMS:
        if (query_lower in item["name"].lower() or
                query_lower in item.get("desc", "").lower()):
            results.append(item)
    return results[:10]  # Limit results


def get_categories() -> list:
    """Return all menu categories."""
    return MENU_CATEGORIES


def get_items_by_category(category: str) -> list:
    """Get items for a specific category."""
    return FALLBACK_MENU.get(category, [])
