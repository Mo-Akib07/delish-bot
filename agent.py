"""
agent.py — Multi-provider AI Agent brain for Delish Bot.
Fallback chain: Gemini → Groq → Mistral → NVIDIA → Local.
Supports conversational ordering via text commands.
"""

import os, json, logging, re, asyncio
from typing import Optional
import google.generativeai as genai

from scraper import (
    scrape_live_menu, scrape_time_slots, search_menu_items,
    get_categories, get_items_by_category, FALLBACK_MENU
)
from utils.formatters import format_cart, format_menu_items

logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

genai.configure(api_key=GEMINI_API_KEY)

# ─── SESSION STORE ────────────────────────────────────────────
user_sessions = {}

def get_session(user_id: int) -> dict:
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "cart": [], "flow": None, "flow_state": None,
            "flow_data": {}, "chat": None, "history": [],
        }
    return user_sessions[user_id]

def clear_session_flow(user_id: int):
    s = get_session(user_id)
    s["flow"] = None; s["flow_state"] = None; s["flow_data"] = {}

def clear_cart(user_id: int):
    get_session(user_id)["cart"] = []

def add_to_cart(user_id: int, item_name: str, price: float, qty: int = 1, category: str = ""):
    session = get_session(user_id)
    for item in session["cart"]:
        if item["name"] == item_name:
            item["qty"] += qty
            return session["cart"]
    session["cart"].append({"name": item_name, "price": price, "qty": qty, "category": category})
    return session["cart"]

def remove_from_cart(user_id: int, item_name: str):
    s = get_session(user_id)
    s["cart"] = [i for i in s["cart"] if i["name"] != item_name]
    return s["cart"]

def update_cart_qty(user_id: int, item_name: str, delta: int):
    s = get_session(user_id)
    for item in s["cart"]:
        if item["name"] == item_name:
            item["qty"] = max(0, item["qty"] + delta)
            if item["qty"] == 0: s["cart"].remove(item)
            break
    return s["cart"]

def get_cart(user_id: int) -> list:
    return get_session(user_id)["cart"]

def get_cart_total(user_id: int) -> float:
    return sum(i["price"] * i["qty"] for i in get_cart(user_id))


# ─── SYSTEM PROMPT ────────────────────────────────────────────
SYSTEM_PROMPT = """You are the AI concierge for Delish, a popular American restaurant in New York, NY.
Be warm, helpful, concise. Use emojis tastefully. Format prices in USD.

Restaurant: Delish | American + Indian cuisine | New York, NY | Open 24/7 | ⭐ 4.2
Delivery: 25-40 min | Pickup: ~20-30 min

You can help with: ordering food, gift cards, banquet hall bookings, table reservations,
order ahead, group orders, catering, and waitlist. When users ask about food, search the
menu and recommend items. Be conversational and proactive."""


# ─── GROQ / MISTRAL / NVIDIA FALLBACK ────────────────────────

async def _call_groq(message: str, context: str = "") -> str:
    """Call Groq API (OpenAI-compatible) as fallback."""
    if not GROQ_API_KEY: return ""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\n" + context},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 800, "temperature": 0.7,
                }
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            logger.warning(f"Groq API {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"Groq fallback error: {e}")
    return ""

async def _call_mistral(message: str, context: str = "") -> str:
    """Call Mistral API as fallback."""
    if not MISTRAL_API_KEY: return ""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "mistral-small-latest",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\n" + context},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 800, "temperature": 0.7,
                }
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            logger.warning(f"Mistral API {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"Mistral fallback error: {e}")
    return ""

async def _call_nvidia(message: str, context: str = "") -> str:
    """Call NVIDIA NIM API as fallback."""
    if not NVIDIA_API_KEY: return ""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "meta/llama-3.1-8b-instruct",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\n" + context},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 800, "temperature": 0.7,
                }
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            logger.warning(f"NVIDIA API {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"NVIDIA fallback error: {e}")
    return ""


# ─── GEMINI TOOL DECLARATIONS ────────────────────────────────

TOOL_DECLARATIONS = [
    genai.protos.FunctionDeclaration(
        name="get_menu_categories",
        description="Get all available menu categories",
        parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
    ),
    genai.protos.FunctionDeclaration(
        name="get_menu_items",
        description="Get menu items for a specific category",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={"category": genai.protos.Schema(type=genai.protos.Type.STRING, description="Category name")},
            required=["category"],
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="search_menu",
        description="Search menu items by keyword",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={"query": genai.protos.Schema(type=genai.protos.Type.STRING, description="Search query")},
            required=["query"],
        ),
    ),
]

TOOL_FUNCTIONS = {
    "get_menu_categories": lambda: json.dumps({"categories": get_categories()}),
    "get_menu_items": lambda category: json.dumps({"category": category, "items": get_items_by_category(category)}),
    "search_menu": lambda query: json.dumps({"query": query, "results": search_menu_items(query)}),
}

_model = None
def _get_model():
    global _model
    if _model is None:
        _model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            tools=[genai.protos.Tool(function_declarations=TOOL_DECLARATIONS)],
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=1024),
        )
    return _model

def _get_or_create_chat(user_id: int):
    session = get_session(user_id)
    if session["chat"] is None:
        session["chat"] = _get_model().start_chat(history=[])
    return session["chat"]


# ─── CONVERSATIONAL ORDERING ─────────────────────────────────

_ORDER_PATTERNS = [
    r"(?:order|add|get|i(?:'ll| will) (?:have|take)|give me|i want|i'd like)\s+(\d+)?\s*(.+)",
]

def _detect_order_intent(msg: str) -> tuple:
    """Detect if user wants to order something by text. Returns (qty, search_term) or (None, None)."""
    lower = msg.lower().strip()
    for pattern in _ORDER_PATTERNS:
        m = re.match(pattern, lower)
        if m:
            qty_str = m.group(1)
            item_text = m.group(2).strip().rstrip("?!.,")
            # Clean up common suffixes
            for suffix in ["please", "pls", "plz", "thanks", "thx", "to my cart", "to cart", "for me"]:
                item_text = item_text.replace(suffix, "").strip()
            if len(item_text) > 2:
                return (int(qty_str) if qty_str else 1, item_text)
    return (None, None)

def _find_best_match(search_term: str) -> dict:
    """Find the best matching menu item for a search term."""
    results = search_menu_items(search_term)
    if not results:
        return None
    # Prefer exact name match
    for r in results:
        if search_term.lower() in r["name"].lower():
            return r
    return results[0]


# ─── SMART LOCAL HANDLER ─────────────────────────────────────

_FOOD_KW = [
    "food", "eat", "hungry", "menu", "dish", "meal", "chicken", "burger",
    "fries", "pizza", "salad", "soup", "steak", "vegan", "vegetarian",
    "spicy", "dessert", "drink", "coffee", "lassi", "samosa", "tikka",
    "masala", "naan", "paneer", "cheese", "nachos", "wings", "calamari",
    "shrimp", "salmon", "kids", "what do you have", "what's good",
    "recommend", "popular", "best", "breakfast", "lunch", "dinner",
]

def _smart_local_response(message_text: str, user_id: int) -> str:
    msg = message_text.lower().strip()

    # Greetings
    if any(msg.startswith(g) or msg == g for g in ["hi", "hello", "hey", "hola", "sup", "yo", "good morning", "good evening"]):
        cart = get_cart(user_id)
        cart_note = f"\n\n🛒 You have {len(cart)} items (${get_cart_total(user_id):.2f})" if cart else ""
        return (
            "Hey there! 👋 Welcome to *Delish*!\n\n"
            "I'm your AI concierge. Try:\n"
            "• _\"order chicken tikka masala\"_ — I'll add it to your cart\n"
            "• _\"do you have vegan food?\"_ — I'll search the menu\n"
            "• Or use the buttons below!\n\n"
            f"What sounds good today?{cart_note}"
        )

    # Help
    if any(k in msg for k in ["help", "what can you do", "options", "features"]):
        return (
            "Here's what I can do! 🎯\n\n"
            "🛍️ *Order by chat* — _\"order 2 chicken kabobs\"_\n"
            "🔍 *Search menu* — _\"do you have burgers?\"_\n"
            "📋 *Browse menu* — /menu\n🛒 *View cart* — /cart\n"
            "📅 *Reserve table* — tap button below\n"
            "🎁 *Gift cards* — tap button below\n\n"
            "💡 _Just tell me what you want!_"
        )

    # Hours
    if any(k in msg for k in ["hours", "open", "close", "timing"]):
        return "🕐 *Delish* is open *24/7*!\n📍 New York, NY\n🚗 Delivery: 25-40 min\n📍 Pickup: ~20-30 min"

    # Location
    if any(k in msg for k in ["location", "address", "where", "directions"]):
        return "📍 *Delish* — New York, NY\n⭐ 4.2 stars\n🚗 Delivery & Pickup available"

    # Feature-specific redirects
    if any(k in msg for k in ["reserve", "reservation", "book a table"]):
        return "📅 Tap *📅 Reserve Table* below, or /start to see all options!"
    if any(k in msg for k in ["gift card", "voucher", "present"]):
        return "🎁 Tap *🎁 Gift Card* below to buy one! ($25-$500)"
    if any(k in msg for k in ["banquet", "wedding", "corporate event"]):
        return "🏛️ Tap *🏛️ Banquet Hall* below to submit an inquiry!"
    if any(k in msg for k in ["cater", "catering"]):
        return "🍱 Tap *🍱 Catering* below to get started!"
    if any(k in msg for k in ["waitlist", "queue"]):
        return "⏳ Tap *⏳ Join Waitlist* below!"
    if any(k in msg for k in ["group order", "order together", "with friends"]):
        return "👥 Tap *👥 Group Order* below to create or join!"

    # Conversational ordering — "order chicken kabob", "add 2 samosas"
    qty, search_term = _detect_order_intent(msg)
    if search_term:
        match = _find_best_match(search_term)
        if match:
            add_to_cart(user_id, match["name"], match["price"], qty, match.get("category", ""))
            total = get_cart_total(user_id)
            cart_count = len(get_cart(user_id))
            return (
                f"✅ Added to cart!\n\n"
                f"*{match['name']}* × {qty}  —  ${match['price'] * qty:.2f}\n"
                f"_{match.get('desc', '')[:80]}_\n\n"
                f"🛒 Cart: *{cart_count} items* • *${total:.2f}*\n\n"
                f"Want anything else? Try:\n"
                f"• _\"add nachos\"_ or _\"order mango lassi\"_\n"
                f"• _\"that's all\"_ or _\"checkout\"_ when ready\n"
                f"• /cart to see your full cart"
            )
        else:
            return (
                f"🔍 Couldn't find *\"{search_term}\"* on our menu.\n\n"
                f"Try: _\"order chicken tikka\"_ or _\"add samosa\"_\n"
                f"Or /menu to browse categories!"
            )

    # Checkout trigger
    if any(k in msg for k in ["that's all", "thats all", "checkout", "check out", "place order", "done ordering", "finish"]):
        cart = get_cart(user_id)
        if not cart:
            return "🛒 Your cart is empty! Try _\"order chicken tikka masala\"_ or tap *🛍️ Order Food*."
        session = get_session(user_id)
        session["flow"] = "text_checkout"
        session["flow_state"] = "order_type"
        session["flow_data"] = {}
        total = get_cart_total(user_id)
        text = "📋 *Your Order:*\n━━━━━━━━━━━━━━━━━━━━\n"
        for item in cart:
            text += f"  • {item['name']} ×{item['qty']}  —  ${item['price'] * item['qty']:.2f}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n💰 *Total: ${total:.2f}*\n\n"
        text += "📍 *Pickup* or 🚗 *Delivery*?\n_(Type \"pickup\" or \"delivery\")_"
        return text

    # Cart check
    if msg in ["cart", "my cart", "show cart", "view cart", "what's in my cart"]:
        cart = get_cart(user_id)
        if not cart:
            return "🛒 Cart is empty! Try _\"order chicken tikka masala\"_ to add items."
        text = format_cart(cart)
        text += f"\n\n💰 *Total: ${get_cart_total(user_id):.2f}*"
        text += "\n\n_Type \"checkout\" when ready, or add more items!_"
        return text

    # Food search (non-ordering)
    search_terms = []
    for pattern in ["do you have ", "show me ", "looking for ", "got any ", "find me ", "search for ", "any ", "what about "]:
        if pattern in msg:
            term = msg.split(pattern, 1)[1].strip().rstrip("?!.,")
            if term: search_terms.append(term)

    food_matches = [k for k in _FOOD_KW if k in msg and len(k) > 3]
    all_search = search_terms + food_matches

    if all_search:
        all_results, seen = [], set()
        for term in all_search:
            for r in search_menu_items(term):
                if r["name"] not in seen:
                    seen.add(r["name"]); all_results.append(r)
        if all_results:
            query_str = ", ".join(all_search[:2])
            text = f"🔍 Found *{len(all_results)} items* for *\"{query_str}\"*:\n\n"
            for i, item in enumerate(all_results[:6], 1):
                text += f"*{i}. {item['name']}*  —  ${item['price']:.2f}\n"
                if item.get("desc"): text += f"   _{item['desc'][:60]}_\n"
            text += f"\n👉 To order, type: _\"order {all_results[0]['name'].lower()}\"_\n"
            text += "_Or use the 🛍️ Order Food button!_"
            return text
        else:
            return f"🔍 No items found for *\"{all_search[0]}\"*. Try /menu to browse!"

    return ""


# ─── TEXT CHECKOUT FLOW ──────────────────────────────────────

async def handle_text_checkout(user_id: int, message: str) -> str:
    """Handle the text-based checkout flow step by step."""
    session = get_session(user_id)
    msg = message.strip().lower()
    state = session["flow_state"]

    if state == "order_type":
        if "pickup" in msg:
            session["flow_data"]["order_type"] = "pickup"
            session["flow_state"] = "name"
            return "📍 *Pickup* selected!\n\nWhat's your *name*?"
        elif "delivery" in msg:
            session["flow_data"]["order_type"] = "delivery"
            session["flow_state"] = "delivery_address"
            return "🚗 *Delivery* selected!\n\nWhat's your *delivery address*?"
        else:
            return "Please type *pickup* or *delivery*:"

    if state == "delivery_address":
        session["flow_data"]["delivery_address"] = message.strip()
        session["flow_state"] = "name"
        return f"📍 Delivering to: *{message.strip()}*\n\nWhat's your *name*?"

    if state == "name":
        session["flow_data"]["customer_name"] = message.strip()
        session["flow_state"] = "phone"
        return f"👤 Hi *{message.strip()}*!\n\nYour *phone number*?"

    if state == "phone":
        phone = message.strip().replace(" ", "").replace("-", "")
        if len(phone) < 7:
            return "❌ Please enter a valid phone number:"
        session["flow_data"]["customer_phone"] = message.strip()
        session["flow_state"] = "confirm"
        # Show final summary
        cart = get_cart(user_id)
        total = get_cart_total(user_id)
        fd = session["flow_data"]
        text = "📋 *Final Order Summary*\n━━━━━━━━━━━━━━━━━━━━\n"
        for item in cart:
            text += f"  • {item['name']} ×{item['qty']}  —  ${item['price'] * item['qty']:.2f}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n💰 *Total: ${total:.2f}*\n\n"
        text += f"👤 {fd.get('customer_name')} • 📱 {fd.get('customer_phone')}\n"
        if fd.get("order_type") == "pickup":
            text += "📍 Pickup at Delish, New York\n"
        else:
            text += f"🚗 Delivery to: {fd.get('delivery_address', '—')}\n"
        text += "\n✅ Type *confirm* to place your order, or *cancel* to go back."
        return text

    if state == "confirm":
        if "confirm" in msg or "yes" in msg:
            from database import create_order
            from utils.formatters import format_order_confirmation
            cart = get_cart(user_id)
            total = get_cart_total(user_id)
            fd = session["flow_data"]
            order_id = await create_order(
                user_id=user_id, items=cart, total=total,
                order_type=fd.get("order_type", "pickup"),
                delivery_address=fd.get("delivery_address"),
                pickup_time="ASAP", name=fd.get("customer_name"),
                phone=fd.get("customer_phone"),
            )
            text = format_order_confirmation(
                order_id=order_id, items=cart, total=total,
                order_type=fd.get("order_type", "pickup"), pickup_time="ASAP",
                delivery_address=fd.get("delivery_address"),
            )
            clear_cart(user_id)
            clear_session_flow(user_id)
            return text
        elif "cancel" in msg:
            clear_session_flow(user_id)
            return "❌ Order cancelled. Your cart is still saved.\nType _\"checkout\"_ when ready!"
        else:
            return "Type *confirm* to place order or *cancel* to go back."

    return ""


# ─── MAIN AGENT FUNCTION ─────────────────────────────────────

async def process_message(user_id: int, message_text: str) -> str:
    """Process message with multi-provider fallback chain."""

    # Step 0: Check if in text checkout flow
    session = get_session(user_id)
    if session.get("flow") == "text_checkout":
        result = await handle_text_checkout(user_id, message_text)
        if result: return result

    # Step 1: Smart local handler (instant)
    local_response = _smart_local_response(message_text, user_id)

    # Step 2: Try Gemini
    try:
        chat = _get_or_create_chat(user_id)
        cart = get_cart(user_id)
        ctx = ""
        if cart:
            cart_items = ", ".join(f"{i['name']}x{i['qty']}" for i in cart)
            ctx = f"[Cart: {cart_items}, ${get_cart_total(user_id):.2f}] "
        response = await chat.send_message_async(ctx + message_text)

        # Handle tool calls
        for _ in range(3):
            fn_calls = [p.function_call for p in response.parts if hasattr(p, 'function_call') and p.function_call and p.function_call.name]
            if not fn_calls: break
            fn_responses = []
            for fc in fn_calls:
                args = dict(fc.args) if fc.args else {}
                try: result = TOOL_FUNCTIONS[fc.name](**args)
                except Exception as e: result = json.dumps({"error": str(e)})
                fn_responses.append(genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(name=fc.name, response={"result": result})
                ))
            response = await chat.send_message_async(genai.protos.Content(parts=fn_responses))

        text = "\n".join(p.text for p in response.parts if hasattr(p, 'text') and p.text)
        if text: return text
    except Exception as e:
        logger.warning(f"Gemini error: {e}")
        session["chat"] = None

    # Step 3: Try Groq fallback
    menu_ctx = f"Menu categories: {', '.join(get_categories()[:8])}"
    cart = get_cart(user_id)
    if cart:
        cart_str = ", ".join(f"{i['name']}x{i['qty']}" for i in cart)
        menu_ctx += f"\nUser's cart: {cart_str}"
    groq_resp = await _call_groq(message_text, menu_ctx)
    if groq_resp: return groq_resp

    # Step 4: Try Mistral fallback
    mistral_resp = await _call_mistral(message_text, menu_ctx)
    if mistral_resp: return mistral_resp

    # Step 5: Try NVIDIA fallback
    nvidia_resp = await _call_nvidia(message_text, menu_ctx)
    if nvidia_resp: return nvidia_resp

    # Step 6: Local response
    if local_response: return local_response

    return (
        "👋 I'm your Delish AI concierge!\n\n"
        "Try:\n• _\"order chicken tikka masala\"_\n• _\"do you have burgers?\"_\n"
        "• /menu to browse\n• /cart to check your cart\n\n"
        "💡 _Or use the buttons below!_"
    )

async def get_ai_response(user_id: int, context: str) -> str:
    try:
        model = _get_model()
        r = await model.generate_content_async(
            f"{SYSTEM_PROMPT}\n\nContext: {context}\n\nGenerate a brief, friendly response.",
            generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=256),
        )
        return r.text
    except: return ""
