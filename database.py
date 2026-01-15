import aiosqlite
import asyncio
import time
from typing import Optional, List, Tuple


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # ===============================
    # INIT
    # ===============================
    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    gender TEXT NOT NULL,
                    joined_at INTEGER NOT NULL,
                    premium_until INTEGER DEFAULT 0,
                    rating_sum INTEGER DEFAULT 0,
                    rating_count INTEGER DEFAULT 0,
                    visible_rating REAL DEFAULT 0.0,
                    streak INTEGER DEFAULT 0,
                    last_active_day INTEGER DEFAULT 0,
                    banned_until INTEGER DEFAULT 0,
                    ban_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS matches (
                    user_id INTEGER,
                    partner_id INTEGER,
                    active INTEGER DEFAULT 1,
                    started_at INTEGER,
                    PRIMARY KEY (user_id, partner_id)
                );

                CREATE TABLE IF NOT EXISTS ratings (
                    rater_id INTEGER,
                    target_id INTEGER,
                    rating INTEGER,
                    created_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS sunflowers (
                    user_id INTEGER PRIMARY KEY,
                    from_streaks INTEGER DEFAULT 0,
                    from_games INTEGER DEFAULT 0,
                    from_gifts INTEGER DEFAULT 0
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
                    last_generated INTEGER
                );

                CREATE TABLE IF NOT EXISTS temp_premium (
                    user_id INTEGER PRIMARY KEY,
                    expires_at INTEGER,
                    last_purchase INTEGER
                );

                CREATE TABLE IF NOT EXISTS games (
                    chat_id INTEGER PRIMARY KEY,
                    game_type TEXT,
                    state TEXT,
                    bet INTEGER,
                    started_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS moderation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    reason TEXT,
                    expires_at INTEGER,
                    created_at INTEGER
                );
                """
            )
            await db.commit()

    # ===============================
    # USERS
    # ===============================
    async def add_user(self, user_id: int, gender: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO users
                (user_id, gender, joined_at, last_active_day)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, gender, int(time.time()), self._today()),
            )
            await db.execute(
                "INSERT OR IGNORE INTO sunflowers (user_id) VALUES (?)",
                (user_id,),
            )
            await db.commit()

    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            return await cur.fetchone()

    # ===============================
    # MATCHMAKING
    # ===============================
    async def start_match(self, user_id: int, partner_id: int):
        now = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO matches VALUES (?, ?, 1, ?)",
                (user_id, partner_id, now),
            )
            await db.execute(
                "INSERT OR REPLACE INTO matches VALUES (?, ?, 1, ?)",
                (partner_id, user_id, now),
            )
            await db.commit()

    async def end_match(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE matches SET active = 0 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()

    async def get_partner(self, user_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT partner_id FROM matches
                WHERE user_id = ? AND active = 1
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    # ===============================
    # RATINGS
    # ===============================
    async def add_rating(self, rater: int, target: int, rating: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO ratings VALUES (?, ?, ?, ?)",
                (rater, target, rating, int(time.time())),
            )
            await db.execute(
                """
                UPDATE users
                SET rating_sum = rating_sum + ?,
                    rating_count = rating_count + 1
                WHERE user_id = ?
                """,
                (rating, target),
            )
            await db.commit()
        await self._update_visible_rating(target)

    async def _update_visible_rating(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT rating_sum, rating_count FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row and row[1] >= 5:
                avg = round(row[0] / row[1], 2)
                await db.execute(
                    "UPDATE users SET visible_rating = ? WHERE user_id = ?",
                    (avg, user_id),
                )
                await db.commit()

    # ===============================
    # PREMIUM
    # ===============================
    async def set_premium(self, user_id: int, seconds: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE users
                SET premium_until = MAX(premium_until, ?) + ?
                WHERE user_id = ?
                """,
                (int(time.time()), seconds, user_id),
            )
            await db.commit()

    async def is_premium(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT premium_until FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            return bool(row and row[0] > time.time())

    # ===============================
    # SUNFLOWERS
    # ===============================
    async def add_sunflowers(self, user_id: int, amount: int, source: str):
        column = {
            "streak": "from_streaks",
            "game": "from_games",
            "gift": "from_gifts",
        }[source]

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"""
                UPDATE sunflowers
                SET {column} = {column} + ?
                WHERE user_id = ?
                """,
                (amount, user_id),
            )
            await db.commit()

    async def get_total_sunflowers(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT from_streaks + from_games + from_gifts
                FROM sunflowers WHERE user_id = ?
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0

    # ===============================
    # STREAKS
    # ===============================
    async def update_streak(self, user_id: int):
        today = self._today()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT streak, last_active_day FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row:
                return

            streak, last_day = row
            if last_day == today:
                return
            if last_day == today - 1:
                streak += 1
            else:
                streak = 0
                await db.execute(
                    "UPDATE sunflowers SET from_streaks = 0 WHERE user_id = ?",
                    (user_id,),
                )

            await db.execute(
                """
                UPDATE users
                SET streak = ?, last_active_day = ?
                WHERE user_id = ?
                """,
                (streak, today, user_id),
            )
            await db.commit()

    # ===============================
    # PETS
    # ===============================
    async def add_pet(self, user_id: int, pet_type: str, uses: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO pets (user_id, pet_type, uses_left)
                VALUES (?, ?, ?)
                """,
                (user_id, pet_type, uses),
            )
            await db.commit()

    async def get_pets(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT pet_type, uses_left FROM pets WHERE user_id = ?",
                (user_id,),
            )
            return await cur.fetchall()

    # ===============================
    # MODERATION
    # ===============================
    async def ban_user(self, user_id: int, reason: str, seconds: int):
        expires = int(time.time()) + seconds
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE users
                SET banned_until = ?, ban_reason = ?
                WHERE user_id = ?
                """,
                (expires, reason, user_id),
            )
            await db.execute(
                """
                INSERT INTO moderation_logs
                (user_id, reason, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, reason, expires, int(time.time())),
            )
            await db.commit()

    async def is_banned(self, user_id: int) -> Optional[Tuple[str, int]]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT banned_until, ban_reason FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row and row[0] > time.time():
                return row[1], row[0]
            return None

    # ===============================
    # HELPERS
    # ===============================
    def _today(self) -> int:
        return int(time.time() // 86400)
