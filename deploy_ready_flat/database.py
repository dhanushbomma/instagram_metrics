"""SQLite database management for Instagram metrics caching and API usage logging."""

import sqlite3
import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH, CACHE_EXPIRY_HOURS


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Creates a database connection with dict-like row access."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes tables for post metrics cache and API usage tracking."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Table for cached Instagram post metrics with accurate shares column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instagram_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            shortcode TEXT,
            post_type TEXT,
            username TEXT,
            views INTEGER,
            likes INTEGER,
            comments INTEGER,
            shares INTEGER,
            thumbnail TEXT,
            posted_at TEXT,
            status TEXT,
            fetched_at TEXT NOT NULL,
            error_message TEXT
        )
    """)

    # Migration check: Ensure 'shares' column exists if db was created earlier
    cursor.execute("PRAGMA table_info(instagram_posts)")
    columns = [col[1] for col in cursor.fetchall()]
    if "shares" not in columns:
        cursor.execute("ALTER TABLE instagram_posts ADD COLUMN shares INTEGER")

    # Table for API usage tracking and cost auditing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            provider TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL,
            estimated_cost REAL DEFAULT 0.0
        )
    """)

    conn.commit()
    conn.close()


def get_cached_post(url: str, max_age_hours: int = CACHE_EXPIRY_HOURS, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """
    Retrieves a cached post record if it exists and was fetched within max_age_hours.
    Returns None if cache is expired or post was a failed fetch (so failed ones can retry).
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM instagram_posts WHERE url = ?
    """, (url,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    row_dict = dict(row)

    # Failed rows are not considered fresh hits to allow automatic retries
    if row_dict.get("status") in ["Failed", "Private/Not found", "API Key Required"]:
        return None

    # Check cache freshness
    fetched_at_str = row_dict.get("fetched_at")
    if not fetched_at_str:
        return None

    try:
        fetched_at = datetime.datetime.fromisoformat(fetched_at_str)
        now = datetime.datetime.now(datetime.timezone.utc if fetched_at.tzinfo else None)
        age = now - fetched_at
        if age.total_seconds() > (max_age_hours * 3600):
            return None  # Cache expired
    except Exception:
        return None

    return row_dict


def save_post(data: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Inserts or updates an Instagram post record in SQLite."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO instagram_posts (
            url, shortcode, post_type, username, views, likes,
            comments, shares, thumbnail, posted_at, status, fetched_at, error_message
        ) VALUES (
            :url, :shortcode, :post_type, :username, :views, :likes,
            :comments, :shares, :thumbnail, :posted_at, :status, :fetched_at, :error_message
        )
        ON CONFLICT(url) DO UPDATE SET
            shortcode=excluded.shortcode,
            post_type=excluded.post_type,
            username=excluded.username,
            views=excluded.views,
            likes=excluded.likes,
            comments=excluded.comments,
            shares=excluded.shares,
            thumbnail=excluded.thumbnail,
            posted_at=excluded.posted_at,
            status=excluded.status,
            fetched_at=excluded.fetched_at,
            error_message=excluded.error_message
    """, {
        "url": data.get("url"),
        "shortcode": data.get("shortcode", ""),
        "post_type": data.get("post_type", "Unknown"),
        "username": data.get("username"),
        "views": data.get("views"),
        "likes": data.get("likes"),
        "comments": data.get("comments"),
        "shares": data.get("shares"),
        "thumbnail": data.get("thumbnail"),
        "posted_at": data.get("posted_at"),
        "status": data.get("status", "Success"),
        "fetched_at": data.get("fetched_at", datetime.datetime.utcnow().isoformat()),
        "error_message": data.get("error_message", "")
    })

    conn.commit()
    conn.close()


def get_all_posts(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Returns all cached posts sorted by fetched_at in descending order."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM instagram_posts ORDER BY fetched_at DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def log_api_call(provider: str, url: str, status: str, cost: float = 0.0, db_path: str = DB_PATH) -> None:
    """Logs an external API request for auditing and cost tracking."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO api_usage_logs (timestamp, provider, url, status, estimated_cost)
        VALUES (?, ?, ?, ?, ?)
    """, (now_str, provider, url, status, cost))
    conn.commit()
    conn.close()


def get_api_usage_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Calculates cumulative and today's API call counts and estimated cost."""
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), SUM(estimated_cost) FROM api_usage_logs")
    total_calls, total_cost = cursor.fetchone()

    today_str = datetime.date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*), SUM(estimated_cost) FROM api_usage_logs WHERE timestamp LIKE ?",
        (f"{today_str}%",)
    )
    today_calls, today_cost = cursor.fetchone()

    conn.close()
    return {
        "total_calls": total_calls or 0,
        "total_cost": total_cost or 0.0,
        "today_calls": today_calls or 0,
        "today_cost": today_cost or 0.0,
    }


def clear_all_posts(db_path: str = DB_PATH) -> None:
    """Clears all records in the posts table (cache reset)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM instagram_posts")
    conn.commit()
    conn.close()
