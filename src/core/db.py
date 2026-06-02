import sqlite3
from datetime import datetime

from configs.paths import DB_PATH


# Minimal structured store (SQLite, stdlib). Holds document-level metadata and
# episodic events; the vector chunks live in the document MemoryIndex. Vectors
# in SQLite would be premature — this is the metadata/registry layer.


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT UNIQUE,
                title       TEXT,
                n_chunks    INTEGER,
                ingested_at TEXT
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                agent  TEXT,
                task   TEXT,
                ts     TEXT
            );
            """
        )


def register_document(source, title, n_chunks):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents (source, title, n_chunks, ingested_at) "
            "VALUES (?, ?, ?, ?)",
            (source, title, n_chunks, datetime.now().isoformat()),
        )


def list_documents():
    with _conn() as conn:
        rows = conn.execute(
            "SELECT source, title, n_chunks, ingested_at "
            "FROM documents ORDER BY ingested_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def log_episode(agent, task):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO episodes (agent, task, ts) VALUES (?, ?, ?)",
            (agent, task, datetime.now().isoformat()),
        )
