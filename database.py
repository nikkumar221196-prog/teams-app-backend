import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_connection_params():
    """Parse DATABASE_URL or use individual env vars."""
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

@contextmanager
def get_db():
    conn = psycopg2.connect(get_connection_params())
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                organization TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen TEXT,
                UNIQUE(name, organization)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                organization TEXT NOT NULL,
                text TEXT,
                attachment TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        print("PostgreSQL database initialized successfully")

def add_user(name: str, organization: str):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, organization, created_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (name, organization, datetime.utcnow().isoformat())
            )
            return True
        except Exception:
            return False

def get_users_by_org(organization: str):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT name, organization, created_at, last_seen FROM users WHERE organization = %s",
            (organization,)
        )
        return [dict(row) for row in cursor.fetchall()]

def update_last_seen(name: str, organization: str, last_seen: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_seen = %s WHERE name = %s AND organization = %s",
            (last_seen, name, organization)
        )
        return cursor.rowcount > 0

def add_message(from_user: str, to_user: str, organization: str, text: str, attachment: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (from_user, to_user, organization, text, attachment, timestamp) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (from_user, to_user, organization, text, attachment, datetime.utcnow().isoformat())
        )
        return cursor.fetchone()[0]

def get_messages_by_org(organization: str):
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT id, from_user, to_user, organization, text, attachment, timestamp FROM messages WHERE organization = %s ORDER BY id",
            (organization,)
        )
        return [
            {
                "id": row["id"],
                "from": row["from_user"],
                "to": row["to_user"],
                "organization": row["organization"],
                "text": row["text"],
                "attachment": row["attachment"],
                "timestamp": row["timestamp"]
            }
            for row in cursor.fetchall()
        ]

def delete_message(message_id: int, organization: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM messages WHERE id = %s AND organization = %s",
            (message_id, organization)
        )
        return cursor.rowcount > 0

def delete_all_messages(organization: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM messages WHERE organization = %s",
            (organization,)
        )
        return cursor.rowcount
