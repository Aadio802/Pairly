import aiosqlite
import time

DB = "users.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            rating_total INTEGER DEFAULT 0,
            rating_count INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER,
            partner_id INTEGER,
            last_seen INTEGER
        )
        """)
        await db.commit()

async def ensure_user(user_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()

async def set_gender(user_id, gender):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET gender=? WHERE user_id=?",
            (gender, user_id)
        )
        await db.commit()

async def get_gender(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT gender FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None

async def save_cooldown(user, partner):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO cooldowns VALUES (?, ?, ?)",
            (user, partner, int(time.time()))
        )
        await db.commit()

async def recently_matched(user, partner, seconds=3600):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
        SELECT last_seen FROM cooldowns
        WHERE user_id=? AND partner_id=?
        ORDER BY last_seen DESC LIMIT 1
        """, (user, partner))
        row = await cur.fetchone()
        if not row:
            return False
        return time.time() - row[0] < seconds

async def add_rating(user, partner, rating):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        UPDATE users
        SET rating_total = rating_total + ?, rating_count = rating_count + 1
        WHERE user_id=?
        """, (rating, partner))
        await db.commit()

async def get_rating_stats(user):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT rating_total, rating_count FROM users WHERE user_id=?",
            (user,)
        )
        row = await cur.fetchone()
        if not row or row[1] < 5:
            return None
        avg = round(row[0] / row[1], 1)
        return avg, row[1]
