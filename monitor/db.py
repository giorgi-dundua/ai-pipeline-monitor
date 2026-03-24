"""
Postgres connection management and all database queries.
Uses psycopg3 directly — no ORM.
"""
import uuid
from datetime import datetime
from decimal import Decimal 
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from monitor.config import settings


def get_connection() -> psycopg.Connection:
    return psycopg.connect(settings.postgres_dsn, row_factory=dict_row)


@contextmanager
def transaction():
    """Yield a connection with automatic commit/rollback."""
    with get_connection() as conn:
        with conn.transaction():
            yield conn


def apply_migrations(migrations_dir: Path = Path("migrations")) -> None:
    """Apply all .sql migration files in order. Idempotent via tracking table."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        conn.commit()

        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM _migrations").fetchall()
        }

        for sql_file in sorted(migrations_dir.glob("*.sql")):
            if sql_file.name in applied:
                continue
            print(f"Applying migration: {sql_file.name}")
            conn.execute(sql_file.read_text())
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (%s)", (sql_file.name,)
            )
            conn.commit()
            print(f"  ✓ {sql_file.name}")


# --- Insert functions ---

def insert_request(
    conn: psycopg.Connection,
    *,
    model: str,
    prompt_hash: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: Decimal,
    pricing_version: datetime,
    success: bool,
    error_type: Optional[str] = None,
) -> uuid.UUID:
    row = conn.execute(
        """
        INSERT INTO requests
            (model, prompt_hash, input_tokens, output_tokens,
             latency_ms, cost_usd, pricing_version, success, error_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (model, prompt_hash, input_tokens, output_tokens,
         latency_ms, cost_usd, pricing_version, success, error_type),
    ).fetchone()
    return row["id"]


def insert_eval_result(
    conn: psycopg.Connection,
    *,
    request_id: uuid.UUID,
    eval_name: str,
    passed: bool,
    score: Optional[float] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO eval_results (request_id, eval_name, passed, score)
        VALUES (%s, %s, %s, %s)
        """,
        (str(request_id), eval_name, passed, score),
    )


# --- Query functions ---

def get_recent_requests(conn: psycopg.Connection, limit: int = 100) -> list[dict]:
    return conn.execute(
        "SELECT * FROM requests ORDER BY created_at DESC LIMIT %s", (limit,)
    ).fetchall()


def get_eval_results_for_request(
    conn: psycopg.Connection, request_id: uuid.UUID
) -> list[dict]:
    return conn.execute(
        "SELECT * FROM eval_results WHERE request_id = %s", (str(request_id),)
    ).fetchall()