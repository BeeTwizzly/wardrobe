"""SQLite database schema, migrations, and CRUD operations for DRIP."""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path


def get_connection(db_path: Path = Path("drip.db")) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and seed default settings if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wardrobe_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_filename TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL DEFAULT '',
            colors TEXT NOT NULL DEFAULT '[]',
            pattern TEXT NOT NULL DEFAULT 'solid',
            material TEXT NOT NULL DEFAULT '',
            formality INTEGER NOT NULL DEFAULT 3,
            seasons TEXT NOT NULL DEFAULT '["spring","summer","fall","winter"]',
            notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS outfits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            occasion TEXT NOT NULL,
            weather_summary TEXT NOT NULL DEFAULT '',
            item_ids TEXT NOT NULL DEFAULT '[]',
            reasoning TEXT NOT NULL DEFAULT '',
            rating INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wear_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL REFERENCES wardrobe_items(id),
            outfit_id INTEGER REFERENCES outfits(id),
            date_worn TEXT NOT NULL DEFAULT (date('now')),
            UNIQUE(item_id, date_worn)
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outfit_a_ids TEXT NOT NULL,
            outfit_b_ids TEXT NOT NULL,
            outfit_a_name TEXT NOT NULL,
            outfit_b_name TEXT NOT NULL,
            winner TEXT NOT NULL,
            occasion TEXT NOT NULL,
            weather_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed default settings if not present
    defaults = {
        "location_lat": "39.89",
        "location_lon": "-86.16",
        "location_name": "Indianapolis, IN",
        "no_repeat_days": "7",
        "style_vibe": "smart casual",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()


# --- Settings CRUD ---


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    """Get a user setting value."""
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set a user setting value."""
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_all_settings(conn: sqlite3.Connection) -> dict[str, str]:
    """Get all user settings as a dict."""
    rows = conn.execute("SELECT key, value FROM user_settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


# --- Wardrobe Items CRUD ---


def add_item(
    conn: sqlite3.Connection,
    image_filename: str,
    name: str,
    category: str,
    subcategory: str = "",
    colors: list[str] | None = None,
    pattern: str = "solid",
    material: str = "",
    formality: int = 3,
    seasons: list[str] | None = None,
    notes: str = "",
) -> int:
    """Add a wardrobe item. Returns the new item ID."""
    colors_json = json.dumps(colors or [])
    seasons_json = json.dumps(seasons or ["spring", "summer", "fall", "winter"])
    cursor = conn.execute(
        """INSERT INTO wardrobe_items
           (image_filename, name, category, subcategory, colors, pattern,
            material, formality, seasons, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            image_filename,
            name,
            category,
            subcategory,
            colors_json,
            pattern,
            material,
            formality,
            seasons_json,
            notes,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_item(conn: sqlite3.Connection, item_id: int) -> dict | None:
    """Get a single wardrobe item by ID."""
    row = conn.execute(
        "SELECT * FROM wardrobe_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_item(row)


def get_all_items(
    conn: sqlite3.Connection,
    active_only: bool = True,
    category: str | None = None,
    seasons: list[str] | None = None,
    formality_min: int = 1,
    formality_max: int = 5,
) -> list[dict]:
    """Get wardrobe items with optional filters."""
    query = "SELECT * FROM wardrobe_items WHERE 1=1"
    params: list = []

    if active_only:
        query += " AND active = 1"

    if category:
        query += " AND category = ?"
        params.append(category)

    if formality_min > 1 or formality_max < 5:
        query += " AND formality >= ? AND formality <= ?"
        params.append(formality_min)
        params.append(formality_max)

    query += " ORDER BY created_at DESC"

    rows = conn.execute(query, params).fetchall()
    items = [_row_to_item(row) for row in rows]

    # Filter by season in Python (JSON array in SQLite)
    if seasons:
        items = [
            item
            for item in items
            if any(s in item["seasons"] for s in seasons)
        ]

    return items


def update_item(conn: sqlite3.Connection, item_id: int, **kwargs) -> bool:
    """Update a wardrobe item. Pass only fields to change."""
    if not kwargs:
        return False

    # Serialize lists to JSON
    if "colors" in kwargs and isinstance(kwargs["colors"], list):
        kwargs["colors"] = json.dumps(kwargs["colors"])
    if "seasons" in kwargs and isinstance(kwargs["seasons"], list):
        kwargs["seasons"] = json.dumps(kwargs["seasons"])

    set_parts = [f"{key} = ?" for key in kwargs]
    set_parts.append("updated_at = datetime('now')")
    values = list(kwargs.values()) + [item_id]

    query = f"UPDATE wardrobe_items SET {', '.join(set_parts)} WHERE id = ?"
    cursor = conn.execute(query, values)
    conn.commit()
    return cursor.rowcount > 0


def delete_item(conn: sqlite3.Connection, item_id: int) -> bool:
    """Delete a wardrobe item and its wear log entries."""
    conn.execute("DELETE FROM wear_log WHERE item_id = ?", (item_id,))
    cursor = conn.execute("DELETE FROM wardrobe_items WHERE id = ?", (item_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_item_count_by_category(conn: sqlite3.Connection) -> dict[str, int]:
    """Get count of active items per category."""
    rows = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM wardrobe_items WHERE active = 1 GROUP BY category"
    ).fetchall()
    return {row["category"]: row["cnt"] for row in rows}


# --- Outfits CRUD ---


def save_outfit(
    conn: sqlite3.Connection,
    name: str,
    occasion: str,
    weather_summary: str,
    item_ids: list[int],
    reasoning: str,
) -> int:
    """Save an outfit. Returns the new outfit ID."""
    cursor = conn.execute(
        """INSERT INTO outfits (name, occasion, weather_summary, item_ids, reasoning)
           VALUES (?, ?, ?, ?, ?)""",
        (name, occasion, weather_summary, json.dumps(item_ids), reasoning),
    )
    conn.commit()
    return cursor.lastrowid


def get_outfit(conn: sqlite3.Connection, outfit_id: int) -> dict | None:
    """Get a single outfit by ID."""
    row = conn.execute(
        "SELECT * FROM outfits WHERE id = ?", (outfit_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_outfit(row)


def rate_outfit(conn: sqlite3.Connection, outfit_id: int, rating: int) -> bool:
    """Rate an outfit (1-5)."""
    cursor = conn.execute(
        "UPDATE outfits SET rating = ? WHERE id = ?", (rating, outfit_id)
    )
    conn.commit()
    return cursor.rowcount > 0


# --- Wear Log CRUD ---


def log_wear(
    conn: sqlite3.Connection,
    item_id: int,
    date_worn: str | None = None,
    outfit_id: int | None = None,
) -> bool:
    """Log an item as worn. Returns False if already logged for that date."""
    if date_worn is None:
        date_worn = date.today().isoformat()
    try:
        conn.execute(
            "INSERT INTO wear_log (item_id, outfit_id, date_worn) VALUES (?, ?, ?)",
            (item_id, outfit_id, date_worn),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_wear_log(
    conn: sqlite3.Connection,
    item_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Get wear log entries with optional filters."""
    query = """
        SELECT wl.*, wi.name as item_name, wi.category as item_category,
               wi.image_filename as item_image
        FROM wear_log wl
        JOIN wardrobe_items wi ON wl.item_id = wi.id
        WHERE 1=1
    """
    params: list = []

    if item_id is not None:
        query += " AND wl.item_id = ?"
        params.append(item_id)
    if start_date:
        query += " AND wl.date_worn >= ?"
        params.append(start_date)
    if end_date:
        query += " AND wl.date_worn <= ?"
        params.append(end_date)

    query += " ORDER BY wl.date_worn DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_last_worn_date(conn: sqlite3.Connection, item_id: int) -> str | None:
    """Get the most recent date an item was worn."""
    row = conn.execute(
        "SELECT MAX(date_worn) as last_worn FROM wear_log WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    return row["last_worn"] if row and row["last_worn"] else None


def get_items_worn_recently(
    conn: sqlite3.Connection, days: int = 7
) -> set[int]:
    """Get IDs of items worn within the last N days."""
    rows = conn.execute(
        "SELECT DISTINCT item_id FROM wear_log WHERE date_worn >= date('now', ?)",
        (f"-{days} days",),
    ).fetchall()
    return {row["item_id"] for row in rows}


def get_most_worn_items(
    conn: sqlite3.Connection, limit: int = 10
) -> list[dict]:
    """Get the most frequently worn items."""
    rows = conn.execute(
        """SELECT wi.*, COUNT(wl.id) as wear_count
           FROM wardrobe_items wi
           JOIN wear_log wl ON wi.id = wl.item_id
           WHERE wi.active = 1
           GROUP BY wi.id
           ORDER BY wear_count DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) | {"wear_count": row["wear_count"]} for row in rows]


def get_least_worn_items(
    conn: sqlite3.Connection, limit: int = 10
) -> list[dict]:
    """Get active items with fewest wears (including zero)."""
    rows = conn.execute(
        """SELECT wi.*, COALESCE(COUNT(wl.id), 0) as wear_count,
                  MAX(wl.date_worn) as last_worn
           FROM wardrobe_items wi
           LEFT JOIN wear_log wl ON wi.id = wl.item_id
           WHERE wi.active = 1
           GROUP BY wi.id
           ORDER BY wear_count ASC, wi.created_at ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_forgotten_items(
    conn: sqlite3.Connection, days: int = 30
) -> list[dict]:
    """Get active items not worn in the last N days."""
    rows = conn.execute(
        """SELECT wi.*, MAX(wl.date_worn) as last_worn
           FROM wardrobe_items wi
           LEFT JOIN wear_log wl ON wi.id = wl.item_id
           WHERE wi.active = 1
           GROUP BY wi.id
           HAVING last_worn IS NULL OR last_worn < date('now', ?)
           ORDER BY last_worn ASC""",
        (f"-{days} days",),
    ).fetchall()
    return [dict(row) for row in rows]


def save_battle(
    conn: sqlite3.Connection,
    outfit_a_ids: list[int],
    outfit_b_ids: list[int],
    outfit_a_name: str,
    outfit_b_name: str,
    winner: str,
    occasion: str,
    weather_summary: str | None = None,
) -> int:
    """Save a battle result. winner must be 'a' or 'b'. Returns the battle ID."""
    cursor = conn.execute(
        """INSERT INTO battles
           (outfit_a_ids, outfit_b_ids, outfit_a_name, outfit_b_name,
            winner, occasion, weather_summary)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            json.dumps(outfit_a_ids),
            json.dumps(outfit_b_ids),
            outfit_a_name,
            outfit_b_name,
            winner,
            occasion,
            weather_summary,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_battle_history(
    conn: sqlite3.Connection, limit: int = 20
) -> list[dict]:
    """Get recent battle history."""
    rows = conn.execute(
        "SELECT * FROM battles ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["outfit_a_ids"] = json.loads(d["outfit_a_ids"])
        d["outfit_b_ids"] = json.loads(d["outfit_b_ids"])
        results.append(d)
    return results


def get_battle_item_stats(conn: sqlite3.Connection) -> dict:
    """Compute per-item win/loss counts from battles.

    Returns {"wins": {item_id: count}, "losses": {item_id: count}}.
    """
    battles = get_battle_history(conn, limit=1000)
    wins: dict[int, int] = {}
    losses: dict[int, int] = {}
    for b in battles:
        if b["winner"] == "a":
            winner_ids, loser_ids = b["outfit_a_ids"], b["outfit_b_ids"]
        else:
            winner_ids, loser_ids = b["outfit_b_ids"], b["outfit_a_ids"]
        for iid in winner_ids:
            wins[iid] = wins.get(iid, 0) + 1
        for iid in loser_ids:
            losses[iid] = losses.get(iid, 0) + 1
    return {"wins": wins, "losses": losses}


def clear_all_data(conn: sqlite3.Connection) -> None:
    """Delete all data from all tables."""
    conn.executescript("""
        DELETE FROM wear_log;
        DELETE FROM outfits;
        DELETE FROM battles;
        DELETE FROM wardrobe_items;
        DELETE FROM user_settings;
    """)
    conn.commit()


# --- Helpers ---


def _row_to_item(row: sqlite3.Row) -> dict:
    """Convert a database row to an item dict with parsed JSON fields."""
    item = dict(row)
    item["colors"] = json.loads(item.get("colors", "[]"))
    item["seasons"] = json.loads(item.get("seasons", '["spring","summer","fall","winter"]'))
    return item


def _row_to_outfit(row: sqlite3.Row) -> dict:
    """Convert a database row to an outfit dict with parsed JSON fields."""
    outfit = dict(row)
    outfit["item_ids"] = json.loads(outfit.get("item_ids", "[]"))
    return outfit
