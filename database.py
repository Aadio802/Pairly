import aiosqlite
import asyncio
from datetime import datetime, timedelta

DB_PATH = "pairly.db"


# -------------------- DATABASE INIT --------------------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                gender TEXT NOT NULL,
                rating REAL DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                premium_until TEXT,
                temp_premium_until TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS matchmaking (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER,
                searching INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rater_id INTEGER,
                rated_id INTEGER,
                stars INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sunflowers (
                user_id INTEGER PRIMARY KEY,
                from_streaks INTEGER DEFAULT 0,
                from_games INTEGER DEFAULT 0,
                from_gifts INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS streaks (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                last_active_date TEXT
            );

            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                pet_type TEXT,
                uses_left INTEGER
            );

            CREATE TABLE IF NOT EXISTS gardens (
                user_id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 1,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_until TEXT
            );

            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_users TEXT,
                game_type TEXT,
                bet INTEGER,
                started_at TEXT
            );
            """
        )
        await db.commit()


# -------------------- USERS --------------------

async def create_user(user_id: int, gender: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO users 
            (user_id, gender, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, gender, datetime.utcnow().isoformat())
        )
        await db.execute(
            "INSERT OR IGNORE INTO sunflowers (user_id) VALUES (?)",
            (user_id,)
        )
        await db.execute(
            "INSERT OR IGNORE INTO streaks (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone()


# -------------------- PREMIUM --------------------

async def is_premium(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT premium_until, temp_premium_until FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return False

        now = datetime.utcnow()
        for date_str in row:
            if date_str:
                if datetime.fromisoformat(date_str) > now:
                    return True
        return False


async def add_premium(user_id: int, days: int, temporary=False):
    until = (datetime.utcnow() + timedelta(days=days)).isoformat()
    field = "temp_premium_until" if temporary else "premium_until"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {field} = ? WHERE user_id = ?",
            (until, user_id)
        )
        await db.commit()


# -------------------- MATCHMAKING --------------------

async def set_searching(user_id: int, searching: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO matchmaking
            (user_id, searching)
            VALUES (?, ?)
            """,
            (user_id, int(searching))
        )
        await db.commit()


async def set_partner(user_id: int, partner_id: int | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE matchmaking SET partner_id = ? WHERE user_id = ?",
            (partner_id, user_id)
        )
        await db.commit()


async def get_partner(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT partner_id FROM matchmaking WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None


# -------------------- RATINGS --------------------

async def add_rating(rater_id: int, rated_id: int, stars: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO ratings
            (rater_id, rated_id, stars, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (rater_id, rated_id, stars, datetime.utcnow().isoformat())
        )

        cur = await db.execute(
            "SELECT AVG(stars), COUNT(*) FROM ratings WHERE rated_id = ?",
            (rated_id,)
        )
        avg, count = await cur.fetchone()

        await db.execute(
            """
            UPDATE users
            SET rating = ?, rating_count = ?
            WHERE user_id = ?
            """,
            (round(avg, 2), count, rated_id)
        )
        await db.commit()


# -------------------- SUNFLOWERS --------------------

async def add_sunflowers(user_id: int, amount: int, source: str):
    field = {
        "streak": "from_streaks",
        "game": "from_games",
        "gift": "from_gifts"
    }[source]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE sunflowers SET {field} = {field} + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def get_sunflowers(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT from_streaks, from_games, from_gifts FROM sunflowers WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return 0
        return sum(row)


# -------------------- STREAKS --------------------

async def update_streak(user_id: int):
    today = datetime.utcnow().date()

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT current_streak, last_active_date FROM streaks WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return

        streak, last_date = row
        if last_date:
            last = datetime.fromisoformat(last_date).date()
            if today == last:
                return
            if today == last + timedelta(days=1):
                streak += 1
            else:
                streak = 1
                await db.execute(
                    "UPDATE sunflowers SET from_streaks = 0 WHERE user_id = ?",
                    (user_id,)
                )
        else:
            streak = 1

        await db.execute(
            """
            UPDATE streaks
            SET current_streak = ?, last_active_date = ?
            WHERE user_id = ?
            """,
            (streak, today.isoformat(), user_id)
        )
        await db.commit()


# -------------------- PETS --------------------

async def add_pet(user_id: int, pet_type: str, uses: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO pets (user_id, pet_type, uses_left)
            VALUES (?, ?, ?)
            """,
            (user_id, pet_type, uses)
        )
        await db.commit()


async def get_pets(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT pet_type, uses_left FROM pets WHERE user_id = ?",
            (user_id,)
        )
        return await cur.fetchall()


# -------------------- GARDEN --------------------

async def create_garden(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO gardens
            (user_id, level, created_at)
            VALUES (?, 1, ?)
            """,
            (user_id, datetime.utcnow().isoformat())
        )
        await db.commit()


# -------------------- BANS --------------------

async def ban_user(user_id: int, reason: str, minutes: int):
    until = (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO bans
            (user_id, reason, banned_until)
            VALUES (?, ?, ?)
            """,
            (user_id, reason, until)
        )
        await db.commit()


async def check_ban(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT reason, banned_until FROM bans WHERE user_id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None

        reason, until = row
        if datetime.fromisoformat(until) > datetime.utcnow():
            return reason, until

        await db.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        await db.commit()
        return None
