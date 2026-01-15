import aiosqlite
import time
from typing import Optional

DB_PATH = "pairly.db"


# ─────────────────────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────────────────────

async def get_db():
    conn = await aiosqlite.connect(DB_PATH)
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ─────────────────────────────────────────────
# DATABASE INITIALIZATION
# ─────────────────────────────────────────────

async def init_db():
    async with await get_db() as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT NOT NULL,
            is_premium INTEGER DEFAULT 0,
            premium_until INTEGER DEFAULT 0,
            rating_sum INTEGER DEFAULT 0,
            rating_count INTEGER DEFAULT 0,
            ban_until INTEGER,
            ban_reason TEXT,
            created_at INTEGER,
            last_active INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_users_premium ON users(is_premium);

        CREATE TABLE IF NOT EXISTS matchmaking (
            user_id INTEGER PRIMARY KEY,
            status TEXT,
            partner_id INTEGER,
            chat_started INTEGER
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rater_id INTEGER,
            rated_id INTEGER,
            stars INTEGER,
            created_at INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_ratings_rated ON ratings(rated_id);

        CREATE TABLE IF NOT EXISTS premium_history (
            user_id INTEGER,
            source TEXT,
            duration_days INTEGER,
            started_at INTEGER,
            expires_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS sunflowers (
            user_id INTEGER PRIMARY KEY,
            from_streak INTEGER DEFAULT 0,
            from_games INTEGER DEFAULT 0,
            from_gifts INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS streaks (
            user_id INTEGER PRIMARY KEY,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_day INTEGER
        );

        CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pet_type TEXT,
            remaining_uses INTEGER
        );

        CREATE TABLE IF NOT EXISTS gardens (
            user_id INTEGER PRIMARY KEY,
            level INTEGER,
            last_generated INTEGER
        );

        CREATE TABLE IF NOT EXISTS games (
            chat_id TEXT PRIMARY KEY,
            game_type TEXT,
            state TEXT,
            bet INTEGER,
            started_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS moderation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            reason TEXT,
            expires_at INTEGER,
            created_at INTEGER
        );
        """)
        await db.commit()


# ─────────────────────────────────────────────
# USER HELPERS
# ─────────────────────────────────────────────

async def create_user(user_id: int, gender: str):
    async with await get_db() as db:
        await db.execute("""
            INSERT OR IGNORE INTO users 
            (user_id, gender, created_at, last_active)
            VALUES (?, ?, ?, ?)
        """, (user_id, gender, int(time.time()), int(time.time())))
        await db.execute("""
            INSERT OR IGNORE INTO sunflowers (user_id)
            VALUES (?)
        """, (user_id,))
        await db.execute("""
            INSERT OR IGNORE INTO streaks (user_id)
            VALUES (?)
        """, (user_id,))
        await db.commit()


async def update_last_active(user_id: int):
    async with await get_db() as db:
        await db.execute(
            "UPDATE users SET last_active=? WHERE user_id=?",
            (int(time.time()), user_id)
        )
        await db.commit()


# ─────────────────────────────────────────────
# PREMIUM HELPERS
# ─────────────────────────────────────────────

async def is_premium(user_id: int) -> bool:
    async with await get_db() as db:
        cur = await db.execute(
            "SELECT premium_until FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return bool(row and row[0] > int(time.time()))


async def grant_premium(user_id: int, days: int, source: str):
    now = int(time.time())
    expires = now + days * 86400

    async with await get_db() as db:
        await db.execute("""
            UPDATE users 
            SET is_premium=1, premium_until=?
            WHERE user_id=?
        """, (expires, user_id))

        await db.execute("""
            INSERT INTO premium_history 
            (user_id, source, duration_days, started_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, source, days, now, expires))

        await db.commit()


# ─────────────────────────────────────────────
# SUNFLOWER WALLET
# ─────────────────────────────────────────────

async def get_sunflowers(user_id: int) -> int:
    async with await get_db() as db:
        cur = await db.execute("""
            SELECT from_streak + from_games + from_gifts 
            FROM sunflowers WHERE user_id=?
        """, (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


async def add_sunflowers(user_id: int, source: str, amount: int):
    assert source in ("from_streak", "from_games", "from_gifts")
    async with await get_db() as db:
        await db.execute(
            f"UPDATE sunflowers SET {source} = {source} + ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()


async def remove_streak_sunflowers(user_id: int):
    async with await get_db() as db:
        await db.execute(
            "UPDATE sunflowers SET from_streak=0 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()


# ─────────────────────────────────────────────
# STREAK SYSTEM
# ─────────────────────────────────────────────

async def update_streak(user_id: int, new_streak: int):
    async with await get_db() as db:
        await db.execute("""
            UPDATE streaks 
            SET current_streak=?, 
                best_streak=MAX(best_streak, ?),
                last_day=?
            WHERE user_id=?
        """, (new_streak, new_streak, int(time.time()), user_id))
        await db.commit()


# ─────────────────────────────────────────────
# PET SYSTEM
# ─────────────────────────────────────────────

async def get_pet_count(user_id: int) -> int:
    async with await get_db() as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM pets WHERE user_id=?",
            (user_id,)
        )
        return (await cur.fetchone())[0]


async def add_pet(user_id: int, pet_type: str, uses: int):
    async with await get_db() as db:
        await db.execute("""
            INSERT INTO pets (user_id, pet_type, remaining_uses)
            VALUES (?, ?, ?)
        """, (user_id, pet_type, uses))
        await db.commit()


async def consume_pet(user_id: int) -> bool:
    async with await get_db() as db:
        cur = await db.execute("""
            SELECT id, remaining_uses FROM pets 
            WHERE user_id=? ORDER BY id LIMIT 1
        """, (user_id,))
        row = await cur.fetchone()

        if not row:
            return False

        pet_id, uses = row
        if uses <= 1:
            await db.execute("DELETE FROM pets WHERE id=?", (pet_id,))
        else:
            await db.execute("""
                UPDATE pets SET remaining_uses=? WHERE id=?
            """, (uses - 1, pet_id))

        await db.commit()
        return True


# ─────────────────────────────────────────────
# GARDEN SYSTEM
# ─────────────────────────────────────────────

async def create_garden(user_id: int):
    async with await get_db() as db:
        await db.execute("""
            INSERT OR IGNORE INTO gardens 
            (user_id, level, last_generated)
            VALUES (?, 1, ?)
        """, (user_id, int(time.time())))
        await db.commit()


async def destroy_garden(user_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM gardens WHERE user_id=?", (user_id,))
        await db.commit()


# ─────────────────────────────────────────────
# MODERATION
# ─────────────────────────────────────────────

async def ban_user(user_id: int, reason: str, duration_seconds: int):
    expires = int(time.time()) + duration_seconds
    async with await get_db() as db:
        await db.execute("""
            UPDATE users SET ban_until=?, ban_reason=? WHERE user_id=?
        """, (expires, reason, user_id))
        await db.execute("""
            INSERT INTO moderation_logs 
            (user_id, action, reason, expires_at, created_at)
            VALUES (?, 'ban', ?, ?, ?)
        """, (user_id, reason, expires, int(time.time())))
        await db.commit()


async def is_banned(user_id: int) -> Optional[str]:
    async with await get_db() as db:
        cur = await db.execute("""
            SELECT ban_until, ban_reason FROM users WHERE user_id=?
        """, (user_id,))
        row = await cur.fetchone()

        if not row:
            return None

        ban_until, reason = row
        if ban_until and ban_until > int(time.time()):
            return reason

        return None
