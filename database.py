"""SQLite helper module for the Product Planning & Forecasting app."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "product_planning.db"

CATEGORIES = [
    "Electronics",
    "Apparel",
    "Home Goods",
    "Food & Beverage",
    "Automotive",
    "Industrial",
    "Health & Beauty",
    "Toys & Games",
]

STATUSES = [
    "Draft",
    "Under Review",
    "Approved",
    "In Production",
    "Shipped",
    "Cancelled",
]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product_plans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    planned_volume  INTEGER NOT NULL CHECK (planned_volume >= 0),
    forecast_date   TEXT NOT NULL,
    status          TEXT NOT NULL,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

SEED_ROWS = [
    ("Aurora Wireless Earbuds", "Electronics", 25000, "2026-09-15", "Approved",
     "Q3 launch, strong pre-order signal from retail partners."),
    ("TrailBlaze Hiking Boots", "Apparel", 8000, "2026-10-01", "Under Review",
     "Awaiting confirmation on leather supplier lead times."),
    ("HomeBrew Coffee Maker", "Home Goods", 12000, "2026-09-01", "In Production",
     "Line running at 80% capacity, on track for target date."),
    ("Zesty Citrus Sparkling Water", "Food & Beverage", 60000, "2026-08-20", "Shipped",
     "First batch shipped to distribution centers on schedule."),
    ("VoltDrive EV Charging Cable", "Automotive", 15000, "2026-11-10", "Draft",
     "Initial volume estimate pending engineering sign-off."),
    ("SteelCore Warehouse Shelving", "Industrial", 4000, "2026-12-05", "Approved",
     "Bulk order from three regional distribution centers."),
    ("GlowSkin Vitamin C Serum", "Health & Beauty", 30000, "2026-09-25", "Under Review",
     "Formulation finalized, packaging design in progress."),
    ("BuildBlocks Mega Set", "Toys & Games", 18000, "2026-11-20", "Draft",
     "Targeting holiday season restock."),
]


@contextmanager
def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the data directory and product_plans table if they don't exist."""
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)


def seed_if_empty() -> None:
    """Insert mock rows only if the table currently has zero rows."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM product_plans").fetchone()[0]
        if count == 0:
            conn.executemany(
                """INSERT INTO product_plans
                   (product_name, category, planned_volume, forecast_date, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                SEED_ROWS,
            )


def insert_plan(
    product_name: str,
    category: str,
    planned_volume: int,
    forecast_date: str,
    status: str,
    notes: str = "",
) -> int:
    """Insert a new product plan row and return its new id."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO product_plans
               (product_name, category, planned_volume, forecast_date, status, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (product_name, category, planned_volume, forecast_date, status, notes),
        )
        return cur.lastrowid


def fetch_all_plans() -> pd.DataFrame:
    """Return all product plans as a DataFrame, most recent forecast date first."""
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM product_plans ORDER BY forecast_date DESC, id DESC", conn
        )


def delete_plan(plan_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM product_plans WHERE id = ?", (plan_id,))


def get_summary_metrics() -> dict:
    """Return aggregate metrics used for the dashboard's summary row."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(planned_volume), 0) AS total_volume,
                 COUNT(*) AS row_count,
                 COALESCE(SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END), 0) AS approved_count,
                 COUNT(DISTINCT category) AS category_count
               FROM product_plans"""
        ).fetchone()
        return dict(row)
