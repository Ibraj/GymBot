import aiosqlite
import json
from datetime import date
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    split        TEXT    DEFAULT 'ppl',
    intensity    TEXT    DEFAULT 'moderate',
    week_number  INTEGER DEFAULT 1,
    is_deload    INTEGER DEFAULT 0,
    last_used    TEXT    DEFAULT '{}',
    pinned       TEXT    DEFAULT '{}',
    setup_done   INTEGER DEFAULT 0,
    created_at   TEXT    DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT    PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    date         TEXT    NOT NULL,
    split        TEXT    NOT NULL,
    day          TEXT    NOT NULL,
    intensity    TEXT    NOT NULL,
    week_number  INTEGER NOT NULL,
    is_deload    INTEGER DEFAULT 0,
    completed    INTEGER DEFAULT 0,
    exercises    TEXT    DEFAULT '[]',
    note         TEXT    DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS exercise_history (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL,
    exercise_id          TEXT    NOT NULL,
    current_weight_kg    REAL    DEFAULT 20.0,
    consecutive_failures INTEGER DEFAULT 0,
    history              TEXT    DEFAULT '[]',
    UNIQUE(user_id, exercise_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS active_sessions (
    user_id     INTEGER PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    message_id  INTEGER DEFAULT NULL,
    chat_id     INTEGER DEFAULT NULL,
    state       TEXT    DEFAULT '{}'
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        for table, col, definition in [
            ("users",           "setup_done", "INTEGER DEFAULT 0"),
            ("sessions",        "note",       "TEXT DEFAULT ''"),
            ("active_sessions", "message_id", "INTEGER DEFAULT NULL"),
            ("active_sessions", "chat_id",    "INTEGER DEFAULT NULL"),
        ]:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            except Exception:
                pass
        await db.commit()


# ── User ─────────────────────────────────────────────────────────────────────

async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            r = dict(row)
            r["last_used"] = json.loads(r["last_used"])
            r["pinned"]    = json.loads(r["pinned"])
            return r


async def upsert_user(user_id: int, **kwargs) -> dict:
    user = await get_user(user_id)
    if not user:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
        user = await get_user(user_id)

    if kwargs:
        for key in ("last_used", "pinned"):
            if key in kwargs and isinstance(kwargs[key], dict):
                kwargs[key] = json.dumps(kwargs[key])
        sets   = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [user_id]
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", values)
            await db.commit()

    return await get_user(user_id)


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(session_id: str, user_id: int, split: str, day: str,
                         intensity: str, week_number: int, is_deload: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO sessions
               (session_id, user_id, date, split, day, intensity, week_number, is_deload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, str(date.today()), split, day,
             intensity, week_number, int(is_deload))
        )
        await db.execute(
            "INSERT OR REPLACE INTO active_sessions (user_id, session_id) VALUES (?, ?)",
            (user_id, session_id)
        )
        await db.commit()


async def store_workout_message(user_id: int, message_id: int, chat_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE active_sessions SET message_id = ?, chat_id = ? WHERE user_id = ?",
            (message_id, chat_id, user_id)
        )
        await db.commit()


async def get_workout_message(user_id: int) -> tuple[int, int] | tuple[None, None]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT message_id, chat_id FROM active_sessions WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row or not row["message_id"]:
                return None, None
            return row["message_id"], row["chat_id"]


async def get_active_session(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT s.* FROM sessions s
               JOIN active_sessions a ON s.session_id = a.session_id
               WHERE a.user_id = ?""", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            r = dict(row)
            r["exercises"] = json.loads(r["exercises"])
            return r


async def update_session_exercises(session_id: str, exercises: list) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET exercises = ? WHERE session_id = ?",
            (json.dumps(exercises), session_id)
        )
        await db.commit()


async def complete_session(session_id: str, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sessions SET completed = 1 WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM active_sessions WHERE user_id = ?", (user_id,))
        await db.commit()


async def add_session_note(session_id: str, note: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET note = ? WHERE session_id = ?", (note, session_id)
        )
        await db.commit()


async def get_recent_sessions(user_id: int, limit: int = 7) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT session_id, date, split, day, intensity, week_number, is_deload, note
               FROM sessions
               WHERE user_id = ? AND completed = 1
               ORDER BY date DESC, session_id DESC
               LIMIT ?""",
            (user_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_last_session(user_id: int) -> dict | None:
    sessions = await get_recent_sessions(user_id, limit=1)
    return sessions[0] if sessions else None


# ── Exercise History ──────────────────────────────────────────────────────────

async def get_exercise_history(user_id: int, exercise_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM exercise_history WHERE user_id = ? AND exercise_id = ?",
            (user_id, exercise_id)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "exercise_id": exercise_id,
                    "current_weight_kg": 20.0,
                    "consecutive_failures": 0,
                    "history": []
                }
            r = dict(row)
            r["history"] = json.loads(r["history"])
            return r


async def update_exercise_history(user_id: int, exercise_id: str,
                                   current_weight_kg: float,
                                   consecutive_failures: int,
                                   new_entry: dict) -> None:
    existing = await get_exercise_history(user_id, exercise_id)
    history  = existing["history"]
    history.append(new_entry)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO exercise_history
               (user_id, exercise_id, current_weight_kg, consecutive_failures, history)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, exercise_id) DO UPDATE SET
               current_weight_kg = excluded.current_weight_kg,
               consecutive_failures = excluded.consecutive_failures,
               history = excluded.history""",
            (user_id, exercise_id, current_weight_kg,
             consecutive_failures, json.dumps(history))
        )
        await db.commit()