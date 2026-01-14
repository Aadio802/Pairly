import aiosqlite

async def init_db():
    async with aiosqlite.connect("botdata.db") as db:
        # Users table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            preferred_gender TEXT,
            rating_sum INTEGER DEFAULT 0,
            rating_count INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            ghost_ban_until INTEGER DEFAULT 0,
            last_partner INTEGER DEFAULT 0
        );
        """)
        # Reports (optional)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter INTEGER,
            reported INTEGER
        );
        """)
        # Chat logs
        await db.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            partner_id INTEGER,
            timestamp INTEGER,
            message_type TEXT,
            content TEXT
        );
        """)
        await db.commit()
