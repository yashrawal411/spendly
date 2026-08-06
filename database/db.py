"""SQLite helpers for Spendly.

Exposes:
    get_db()   -- open a connection to expense_tracker.db in the project
                  root, with row_factory = sqlite3.Row and foreign keys ON
    init_db()  -- CREATE TABLE IF NOT EXISTS for users and expenses
    seed_db()  -- insert one demo user (password = "demo123") and 8 sample
                 expenses; safe to call repeatedly

The DB file is gitignored.
"""

import os
import sqlite3

from werkzeug.security import generate_password_hash

# Project root = parent of the database/ package.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "expense_tracker.db")


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection to the project database.

    - row_factory = sqlite3.Row so callers can use dict-like access
    - PRAGMA foreign_keys = ON so FK constraints are enforced
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create users and expenses tables if they don't already exist."""
    conn = get_db()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,           -- YYYY-MM-DD
                description TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


def seed_db() -> None:
    """Insert demo data. Idempotent — no-op once the demo user exists."""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Idempotency guard: bail out if users table is already populated.
        if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        # --- demo user (password = "demo123", hashed via werkzeug) -------
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (
                "Demo User",
                "demo@spendly.com",
                generate_password_hash("demo123"),
            ),
        )
        demo_id = cur.lastrowid

        # --- 8 sample expenses, one per category (7) + one extra Food ----
        samples = [
            (250.00,  "Food",          "2026-08-01", "Chai and samosa"),
            (1200.00, "Transport",     "2026-08-02", "Auto to office"),
            (3499.00, "Shopping",      "2026-08-03", "T-shirt online"),
            (1850.00, "Bills",         "2026-08-04", "Electricity bill"),
            (599.00,  "Entertainment", "2026-08-05", "Movie ticket"),
            (450.00,  "Health",        "2026-08-06", "Pharmacy"),
            (320.00,  "Other",         "2026-08-07", "Misc household"),
            (780.00,  "Food",          "2026-08-08", "Groceries"),
        ]
        for amount, category, date, description in samples:
            cur.execute(
                """
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (demo_id, amount, category, date, description),
            )

        conn.commit()
    finally:
        conn.close()
