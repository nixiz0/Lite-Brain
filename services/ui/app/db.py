import json
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from CONFIG import DATABASE_URL


# =========== Helper Functions ===========
def _ensure_sqlite_dir(url: str):
    """
    Ensure the directory for a SQLite database URL exists.
    Only applied to file-based sqlite URLs. Creates parent directories if needed.
    """
    if url.startswith("sqlite:///") or url.startswith("sqlite+pysqlite:///"):
        path_part = url.split(":///")[1]
        p = Path(path_part)
        if not p.is_absolute():
            p = Path.cwd() / path_part
        p.parent.mkdir(parents=True, exist_ok=True)


# =========== DB Initialization ===========
# Creates the folder if we are on SQLite
_ensure_sqlite_dir(DATABASE_URL)

# connect_args are only relevant for SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,  # allow usage from multiple threads
        "timeout": 60,               # increase timeout before "database is locked"
    }

# Global SQLAlchemy engine and session factory
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # validate connections before using them
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    FastAPI-style dependency that yields a database session.
    The session is always closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========== DB Migrations ===========
def run_light_migrations(engine):
    """
    Apply lightweight, in-place migrations using raw SQL.
    - Tunes SQLite pragmas for better concurrency.
    - Ensures conversation metadata columns exist and backfills them.
    - Creates folders/documents tables if missing and keeps them in sync.
    """
    with engine.connect() as conn:
        insp = inspect(conn)

        # --- SQLite concurrency tuning ---
        if DATABASE_URL.startswith("sqlite"):
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))

        # --- Conversation metadata and messages migration ---
        if insp.has_table("conversations"):
            cols = {c["name"] for c in insp.get_columns("conversations")}

            if "updated_at" not in cols:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN updated_at DATETIME")
                )
            if "summary" not in cols:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN summary VARCHAR")
                )
            if "msg_count" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE conversations "
                        "ADD COLUMN msg_count INTEGER DEFAULT 0"
                    )
                )
            if "messages" not in cols:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN messages TEXT")
                )

            if "llm_tier" not in cols:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN llm_tier VARCHAR")
                )

            has_messages_table = insp.has_table("messages")

            if has_messages_table:
                # Select conversations that do not yet have bundled messages
                res = conn.execute(
                    text(
                        """
                    SELECT c.id
                    FROM conversations c
                    WHERE c.messages IS NULL OR c.messages = ''
                """
                    )
                ).fetchall()

                # For each conversation, bundle legacy rows from messages into a JSON list
                for (conv_id,) in res:
                    rows = conn.execute(
                        text(
                            """
                            SELECT role, content, ts FROM messages
                            WHERE conversation_id = :cid
                            ORDER BY ts ASC
                        """
                        ),
                        {"cid": conv_id},
                    ).fetchall()

                    bundled = [
                        {
                            "role": r[0],
                            "content": r[1],
                            "ts": (r[2].isoformat() if r[2] else None),
                        }
                        for r in rows
                    ]

                    conn.execute(
                        text(
                            """
                            UPDATE conversations
                            SET messages = :messages,
                                msg_count = COALESCE(:cnt, 0),
                                updated_at = COALESCE(
                                    (SELECT MAX(ts) FROM messages WHERE conversation_id = :cid),
                                    created_at
                                ),
                                summary = COALESCE(summary, title)
                            WHERE id = :cid
                        """
                        ),
                        {
                            "cid": conv_id,
                            "messages": json.dumps(
                                bundled, ensure_ascii=False
                            ),
                            "cnt": len(bundled),
                        },
                    )
            else:
                # No messages table: normalize existing conversation metadata in-place
                conn.execute(
                    text(
                        """
                    UPDATE conversations
                    SET updated_at = COALESCE(updated_at, created_at),
                        msg_count = COALESCE(msg_count, 0),
                        summary = COALESCE(summary, title),
                        messages = COALESCE(messages, '[]')
                """
                    )
                )

        # --- Folders table creation ---
        if not insp.has_table("folders"):
            conn.execute(
                text(
                    """
                CREATE TABLE folders (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    created_at DATETIME NOT NULL
                )
            """
                )
            )

        # --- Documents table creation / migration ---
        if not insp.has_table("documents"):
            conn.execute(
                text(
                    """
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    path VARCHAR NOT NULL,
                    added_at DATETIME NOT NULL,
                    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE
                )
            """
                )
            )
        else:
            cols_doc = {c["name"] for c in insp.get_columns("documents")}
            if "folder_id" not in cols_doc:
                conn.execute(
                    text(
                        "ALTER TABLE documents "
                        "ADD COLUMN folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE"
                    )
                )

        conn.commit()
