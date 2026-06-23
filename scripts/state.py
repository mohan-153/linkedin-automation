"""
state.py
Tiny SQLite-backed state store for tracking generated LinkedIn drafts.

Each draft has:
  request_id   - unique id (used to match email replies back to a draft)
  created_at   - timestamp
  news_summary - the source news text used as input
  post_text    - generated LinkedIn post text
  image_path   - local path to generated image
  image_prompt - prompt used to generate the image
  status       - 'pending' | 'posted' | 'skipped' | 'regenerating'
  message_id   - the Message-ID header of the review email we sent
                 (used to match IMAP replies via In-Reply-To/References)
"""
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "state.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS drafts (
            request_id TEXT PRIMARY KEY,
            created_at INTEGER,
            news_summary TEXT,
            post_text TEXT,
            image_path TEXT,
            image_prompt TEXT,
            status TEXT DEFAULT 'pending',
            message_id TEXT,
            regenerate_count INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def create_draft(request_id, news_summary, post_text, image_path, image_prompt, message_id):
    conn = _connect()
    conn.execute(
        """
        INSERT INTO drafts (request_id, created_at, news_summary, post_text,
                             image_path, image_prompt, status, message_id)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (request_id, int(time.time()), news_summary, post_text, image_path, image_prompt, message_id),
    )
    conn.commit()
    conn.close()


def get_draft(request_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM drafts WHERE request_id = ?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_draft_by_message_id(message_id):
    """Find a pending draft whose review email Message-ID matches (for reply parsing)."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM drafts WHERE message_id = ? ORDER BY created_at DESC LIMIT 1",
        (message_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_status(request_id, status):
    conn = _connect()
    conn.execute("UPDATE drafts SET status = ? WHERE request_id = ?", (status, request_id))
    conn.commit()
    conn.close()


def update_message_id(request_id, message_id):
    conn = _connect()
    conn.execute("UPDATE drafts SET message_id = ? WHERE request_id = ?", (message_id, request_id))
    conn.commit()
    conn.close()


def increment_regenerate(request_id):
    conn = _connect()
    conn.execute(
        "UPDATE drafts SET regenerate_count = regenerate_count + 1 WHERE request_id = ?",
        (request_id,),
    )
    conn.commit()
    conn.close()


def get_pending_drafts():
    conn = _connect()
    rows = conn.execute("SELECT * FROM drafts WHERE status = 'pending'").fetchall()
    conn.close()
    return [dict(r) for r in rows]
