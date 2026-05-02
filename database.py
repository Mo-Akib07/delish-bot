"""
database.py — Async SQLite database for Delish Bot.
Stores orders, banquet inquiries, reservations, waitlist, catering, gift cards, group orders.
"""

import aiosqlite
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "delish.db")


async def init_db():
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                total REAL NOT NULL,
                order_type TEXT NOT NULL DEFAULT 'pickup',
                delivery_address TEXT,
                delivery_phone TEXT,
                pickup_time TEXT,
                customer_name TEXT,
                customer_phone TEXT,
                customer_email TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS banquet_inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT,
                event_date TEXT,
                guest_count INTEGER,
                start_time TEXT,
                end_time TEXT,
                food_service TEXT,
                bar_service TEXT,
                room_setup TEXT,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                company TEXT,
                special_requests TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                party_size INTEGER,
                reservation_date TEXT,
                reservation_time TEXT,
                name TEXT,
                phone TEXT,
                special_requests TEXT,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                party_size INTEGER,
                name TEXT,
                phone TEXT,
                estimated_wait INTEGER DEFAULT 5,
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS catering_inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT,
                event_date TEXT,
                headcount INTEGER,
                cuisine_prefs TEXT,
                service_style TEXT,
                event_location TEXT,
                budget_range TEXT,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                special_requests TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gift_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT UNIQUE NOT NULL,
                amount REAL NOT NULL,
                recipient_name TEXT,
                recipient_contact TEXT,
                personal_message TEXT,
                redeemed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS group_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                organizer_id INTEGER NOT NULL,
                party_size INTEGER DEFAULT 2,
                items_json TEXT DEFAULT '[]',
                is_open INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS group_order_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                items_json TEXT DEFAULT '[]',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_code) REFERENCES group_orders(code)
            );
        """)
        await db.commit()


# ─── ORDER CRUD ───────────────────────────────────────────────

async def create_order(user_id, items, total, order_type="pickup",
                       delivery_address=None, delivery_phone=None,
                       pickup_time=None, name=None, phone=None, email=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO orders (user_id, items_json, total, order_type,
               delivery_address, delivery_phone, pickup_time,
               customer_name, customer_phone, customer_email)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, json.dumps(items), total, order_type,
             delivery_address, delivery_phone, pickup_time, name, phone, email)
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_orders(user_id, limit=5):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ─── BANQUET CRUD ─────────────────────────────────────────────

async def create_banquet_inquiry(user_id, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO banquet_inquiries
               (user_id, event_type, event_date, guest_count, start_time, end_time,
                food_service, bar_service, room_setup, contact_name, contact_phone,
                contact_email, company, special_requests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, data.get("event_type"), data.get("event_date"),
             data.get("guest_count"), data.get("start_time"), data.get("end_time"),
             data.get("food_service"), data.get("bar_service"), data.get("room_setup"),
             data.get("contact_name"), data.get("contact_phone"),
             data.get("contact_email"), data.get("company"),
             data.get("special_requests"))
        )
        await db.commit()
        return cursor.lastrowid


async def get_banquet_inquiry(inquiry_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM banquet_inquiries WHERE id = ?", (inquiry_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def search_banquet_by_contact(name=None, phone=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if phone:
            cursor = await db.execute(
                "SELECT * FROM banquet_inquiries WHERE contact_phone = ? ORDER BY created_at DESC",
                (phone,))
        elif name:
            cursor = await db.execute(
                "SELECT * FROM banquet_inquiries WHERE contact_name LIKE ? ORDER BY created_at DESC",
                (f"%{name}%",))
        else:
            return []
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ─── RESERVATION CRUD ────────────────────────────────────────

async def create_reservation(user_id, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO reservations
               (user_id, party_size, reservation_date, reservation_time,
                name, phone, special_requests)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, data.get("party_size"), data.get("date"),
             data.get("time"), data.get("name"), data.get("phone"),
             data.get("special_requests"))
        )
        await db.commit()
        return cursor.lastrowid


async def get_reservation(res_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reservations WHERE id = ?", (res_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ─── WAITLIST CRUD ────────────────────────────────────────────

async def add_to_waitlist(user_id, party_size, name, phone, estimated_wait=5):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO waitlist (user_id, party_size, name, phone, estimated_wait)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, party_size, name, phone, estimated_wait)
        )
        await db.commit()
        return cursor.lastrowid


async def notify_waitlist(waitlist_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE waitlist SET notified = 1 WHERE id = ?", (waitlist_id,))
        await db.commit()


async def get_waitlist_entry(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM waitlist WHERE user_id = ? AND notified = 0 ORDER BY created_at DESC LIMIT 1",
            (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ─── CATERING CRUD ────────────────────────────────────────────

async def create_catering_inquiry(user_id, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO catering_inquiries
               (user_id, event_type, event_date, headcount, cuisine_prefs,
                service_style, event_location, budget_range,
                contact_name, contact_phone, contact_email, special_requests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, data.get("event_type"), data.get("event_date"),
             data.get("headcount"), data.get("cuisine_prefs"),
             data.get("service_style"), data.get("event_location"),
             data.get("budget_range"), data.get("contact_name"),
             data.get("contact_phone"), data.get("contact_email"),
             data.get("special_requests"))
        )
        await db.commit()
        return cursor.lastrowid


# ─── GIFT CARD CRUD ──────────────────────────────────────────

async def create_gift_card(user_id, code, amount, recipient_name,
                           recipient_contact, message=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO gift_cards
               (user_id, code, amount, recipient_name, recipient_contact, personal_message)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, code, amount, recipient_name, recipient_contact, message)
        )
        await db.commit()
        return cursor.lastrowid


async def get_gift_card(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM gift_cards WHERE code = ?", (code,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ─── GROUP ORDER CRUD ────────────────────────────────────────

async def create_group_order(organizer_id, code, party_size=2):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO group_orders (code, organizer_id, party_size)
               VALUES (?, ?, ?)""",
            (code, organizer_id, party_size)
        )
        await db.commit()


async def get_group_order(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM group_orders WHERE code = ?", (code,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def join_group_order(group_code, user_id, user_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO group_order_members (group_code, user_id, user_name)
               VALUES (?, ?, ?)""",
            (group_code, user_id, user_name)
        )
        await db.commit()


async def add_member_items(group_code, user_id, items):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE group_order_members SET items_json = ?
               WHERE group_code = ? AND user_id = ?""",
            (json.dumps(items), group_code, user_id)
        )
        await db.commit()


async def close_group_order(code):
    async with aiosqlite.connect(DB_PATH) as db:
        # Compile all member items
        cursor = await db.execute(
            "SELECT items_json FROM group_order_members WHERE group_code = ?",
            (code,))
        rows = await cursor.fetchall()
        all_items = []
        for row in rows:
            all_items.extend(json.loads(row[0]))
        await db.execute(
            "UPDATE group_orders SET is_open = 0, items_json = ? WHERE code = ?",
            (json.dumps(all_items), code)
        )
        await db.commit()
        return all_items


async def get_group_members(code):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM group_order_members WHERE group_code = ?", (code,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
