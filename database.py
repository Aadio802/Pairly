import aiosqlite
import time

DB_NAME = "bot.db"

# =========================
# DATABASE INIT
# =========================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            first_start INTEGER DEFAULT 1,
            sunflowers INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_active INTEGER,
            premium_until INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rater_id INTEGER,
            rated_id INTEGER,
            rating INTEGER
        );

        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            banned_until INTEGER,
            ghost INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS spam (
            user_id INTEGER PRIMARY KEY,
            link_count INTEGER DEFAULT 0,
            warned INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER,
            last_partner INTEGER,
            timestamp INTEGER
        );

        CREATE TABLE IF NOT EXISTS pets (
            user_id INTEGER,
            pet_name TEXT,
            used INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS garden (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 0
        );
        """)
        await db.commit()

# =========================
# USER
# =========================

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

async def ensure_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, last_active) VALUES (?, ?)",
            (user_id, int(time.time()))
        )
        await db.commit()

async def set_gender(user_id, gender):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET gender=? WHERE user_id=?",
            (gender, user_id)
        )
        await db.commit()

# =========================
# RATINGS
# =========================

async def add_rating(rater, rated, value):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO ratings (rater_id, rated_id, rating) VALUES (?, ?, ?)",
            (rater, rated, value)
        )
        await db.commit()

async def get_rating_stats(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT COUNT(*), AVG(rating) FROM ratings WHERE rated_id=?",
            (user_id,)
        )
        count, avg = await cur.fetchone()
        if count < 5:
            return None
        return round(avg, 2), count

# =========================
# PREMIUM
# =========================

async def is_premium(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT premium_until FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row and row[0] > int(time.time())

# =========================
# BANS
# =========================

async def is_banned(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT banned_until FROM bans WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row and row[0] > int(time.time())

async def ban_user(user_id, reason, duration_days, ghost=False):
    until = int(time.time()) + duration_days * 86400
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT INTO bans (user_id, reason, banned_until, ghost)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
        reason=?, banned_until=?, ghost=?
        """, (user_id, reason, until, ghost, reason, until, ghost))
        await db.commit()

# =========================
# COOLDOWN
# =========================

async def save_cooldown(user, partner):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO cooldowns VALUES (?, ?, ?)",
            (user, partner, int(time.time()))
        )
        await db.commit()

async def recent_partner(user, partner, seconds=600):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
        SELECT 1 FROM cooldowns
        WHERE user_id=? AND last_partner=? AND timestamp > ?
        """, (user, partner, int(time.time()) - seconds))
        return await cur.fetchone() is not None

