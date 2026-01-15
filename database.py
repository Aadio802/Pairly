import sqlite3
from datetime import datetime, date

DB_NAME = "bot.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def setup_database():
    conn = get_connection()
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        sunflowers INTEGER DEFAULT 0,
        premium INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        last_daily TEXT
    )
    """)

    # Pets table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pets (
        user_id INTEGER,
        pet_name TEXT,
        pet_level INTEGER DEFAULT 1,
        PRIMARY KEY (user_id)
    )
    """)

    # Games stats
    cur.execute("""
    CREATE TABLE IF NOT EXISTS games (
        user_id INTEGER PRIMARY KEY,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


# ---------- USER ----------
def add_user(user_id, username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR IGNORE INTO users (user_id, username)
    VALUES (?, ?)
    """, (user_id, username))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user


# ---------- SUNFLOWERS ----------
def add_sunflowers(user_id, amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE users SET sunflowers = sunflowers + ?
    WHERE user_id=?
    """, (amount, user_id))
    conn.commit()
    conn.close()


# ---------- DAILY STREAK ----------
def claim_daily(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT streak, last_daily FROM users WHERE user_id=?", (user_id,))
    streak, last_daily = cur.fetchone()

    today = date.today().isoformat()

    if last_daily == today:
        conn.close()
        return False, streak

    new_streak = streak + 1
    reward = 50 + (new_streak * 10)

    cur.execute("""
    UPDATE users
    SET streak=?, last_daily=?, sunflowers = sunflowers + ?
    WHERE user_id=?
    """, (new_streak, today, reward, user_id))

    conn.commit()
    conn.close()
    return True, reward


# ---------- PETS ----------
def adopt_pet(user_id, pet_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO pets (user_id, pet_name, pet_level)
    VALUES (?, ?, 1)
    """, (user_id, pet_name))
    conn.commit()
    conn.close()


def get_pet(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT pet_name, pet_level FROM pets WHERE user_id=?", (user_id,))
    pet = cur.fetchone()
    conn.close()
    return pet


# ---------- PREMIUM ----------
def set_premium(user_id, value: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE users SET premium=?
    WHERE user_id=?
    """, (1 if value else 0, user_id))
    conn.commit()
    conn.close()


# ---------- GAMES ----------
def record_game(user_id, win: bool):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("INSERT OR IGNORE INTO games (user_id) VALUES (?)", (user_id,))

    if win:
        cur.execute("UPDATE games SET wins = wins + 1 WHERE user_id=?", (user_id,))
    else:
        cur.execute("UPDATE games SET losses = losses + 1 WHERE user_id=?", (user_id,))

    conn.commit()
    conn.close()
