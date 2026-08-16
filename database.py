"""SQLite helper module for the Subscription Forecasting app.

Initializes the database, creates tables if they don't exist, and seeds
realistic mock data so the UI has something to show on first launch.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "subscriptions.db"

BILLING_CYCLES = ["Monthly", "Annual"]

CHURN_REASONS = [
    "Price sensitivity",
    "Switched to competitor",
    "No longer needed",
    "Poor experience",
    "Low engagement",
    "Payment failure",
]

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    billing_cycle   TEXT NOT NULL,
    price            REAL NOT NULL CHECK (price >= 0),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, name, billing_cycle)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id              INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
    customer_ref             TEXT NOT NULL,
    start_date              TEXT NOT NULL,
    end_date                TEXT,
    status                  TEXT NOT NULL CHECK (status IN ('active', 'churned', 'regraded')),
    churn_reason            TEXT,
    regraded_to_variant_id   INTEGER REFERENCES variants(id) ON DELETE SET NULL,
    mrr                     REAL NOT NULL CHECK (mrr >= 0),
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_variant ON subscriptions(variant_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_dates ON subscriptions(start_date, end_date);
"""

PRODUCT_CATALOG = {
    "StreamPlus": {
        "description": "On-demand video streaming service.",
        "variants": [
            ("Basic", "Monthly", 7.99),
            ("Standard", "Monthly", 13.99),
            ("Premium", "Monthly", 19.99),
            ("Premium", "Annual", 199.99),
        ],
        "monthly_churn": 0.045,
    },
    "MusicWave": {
        "description": "Ad-free music streaming with offline downloads.",
        "variants": [
            ("Individual", "Monthly", 9.99),
            ("Family", "Monthly", 16.99),
            ("Student", "Monthly", 5.99),
        ],
        "monthly_churn": 0.035,
    },
    "CloudVault": {
        "description": "Encrypted cloud storage and backup.",
        "variants": [
            ("100GB", "Monthly", 2.99),
            ("1TB", "Monthly", 9.99),
            ("1TB", "Annual", 99.99),
            ("5TB", "Monthly", 24.99),
        ],
        "monthly_churn": 0.025,
    },
    "FitTrack Pro": {
        "description": "Fitness and nutrition tracking with coaching.",
        "variants": [
            ("Basic", "Monthly", 4.99),
            ("Plus", "Monthly", 12.99),
            ("Coached", "Monthly", 29.99),
        ],
        "monthly_churn": 0.07,
    },
    "NewsDaily": {
        "description": "Digital news and premium journalism access.",
        "variants": [
            ("Digital", "Monthly", 6.99),
            ("Digital", "Annual", 69.99),
            ("All Access", "Monthly", 12.99),
        ],
        "monthly_churn": 0.055,
    },
}

HISTORY_MONTHS = 24
RANDOM_SEED = 42


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
    """Create the data directory and all tables if they don't already exist."""
    with get_connection() as conn:
        conn.executescript(CREATE_TABLES_SQL)


def _month_starts(n_months: int, end_date: date) -> list[date]:
    """Return the first-of-month dates for the trailing n_months, oldest first."""
    anchor = end_date.replace(day=1)
    months = []
    for i in range(n_months - 1, -1, -1):
        year = anchor.year
        month = anchor.month - i
        while month <= 0:
            month += 12
            year -= 1
        months.append(date(year, month, 1))
    return months


def _generate_mock_subscriptions(variant_rows: list[sqlite3.Row]) -> list[tuple]:
    """Simulate 24 months of subscriber acquisition and churn per variant.

    Each variant grows its active base gradually while shedding a random
    share of subscribers every month at roughly the product's target churn
    rate, so the resulting history has a realistic base + churn curve.
    """
    rng = np.random.default_rng(RANDOM_SEED)
    today = date.today()
    months = _month_starts(HISTORY_MONTHS, today)

    rows = []
    customer_seq = 1

    for variant in variant_rows:
        product_churn = variant["monthly_churn"]
        base_new_per_month = rng.integers(25, 90)
        active_customers: list[dict] = []

        for month_idx, month_start in enumerate(months):
            is_current_month = month_idx == len(months) - 1
            days_in_month = (
                (months[month_idx + 1] - month_start).days
                if month_idx + 1 < len(months)
                else (today - month_start).days + 1
            )

            growth_factor = 1.0 + (month_idx / HISTORY_MONTHS) * 0.6
            new_count = max(0, int(rng.poisson(base_new_per_month * growth_factor)))
            for _ in range(new_count):
                offset = int(rng.integers(0, max(days_in_month, 1)))
                start = month_start + timedelta(days=offset)
                if start > today:
                    continue
                active_customers.append(
                    {
                        "customer_ref": f"CUST-{customer_seq:05d}",
                        "start_date": start,
                    }
                )
                customer_seq += 1

            noisy_churn_rate = float(np.clip(rng.normal(product_churn, product_churn * 0.35), 0.005, 0.25))
            still_active = []
            for cust in active_customers:
                if cust["start_date"] > month_start + timedelta(days=days_in_month - 1):
                    still_active.append(cust)
                    continue
                if not is_current_month and rng.random() < noisy_churn_rate:
                    churn_offset = int(rng.integers(0, max(days_in_month, 1)))
                    churn_date = month_start + timedelta(days=churn_offset)
                    if churn_date < cust["start_date"]:
                        churn_date = cust["start_date"]
                    if churn_date > today:
                        still_active.append(cust)
                        continue
                    reason = CHURN_REASONS[int(rng.integers(0, len(CHURN_REASONS)))]
                    rows.append(
                        (
                            variant["id"],
                            cust["customer_ref"],
                            cust["start_date"].isoformat(),
                            churn_date.isoformat(),
                            "churned",
                            reason,
                            None,
                            variant["price"],
                        )
                    )
                else:
                    still_active.append(cust)
            active_customers = still_active

        for cust in active_customers:
            rows.append(
                (
                    variant["id"],
                    cust["customer_ref"],
                    cust["start_date"].isoformat(),
                    None,
                    "active",
                    None,
                    None,
                    variant["price"],
                )
            )

    return rows


def seed_if_empty() -> None:
    """Populate products, variants, and simulated subscription history once."""
    with get_connection() as conn:
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count > 0:
            return

        variant_rows = []
        for product_name, info in PRODUCT_CATALOG.items():
            cur = conn.execute(
                "INSERT INTO products (name, description) VALUES (?, ?)",
                (product_name, info["description"]),
            )
            product_id = cur.lastrowid
            for variant_name, cycle, price in info["variants"]:
                vcur = conn.execute(
                    "INSERT INTO variants (product_id, name, billing_cycle, price) VALUES (?, ?, ?, ?)",
                    (product_id, variant_name, cycle, price),
                )
                variant_rows.append(
                    {
                        "id": vcur.lastrowid,
                        "product_id": product_id,
                        "price": price,
                        "monthly_churn": info["monthly_churn"],
                    }
                )

        subscription_rows = _generate_mock_subscriptions(variant_rows)
        conn.executemany(
            """INSERT INTO subscriptions
               (variant_id, customer_ref, start_date, end_date, status,
                churn_reason, regraded_to_variant_id, mrr)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            subscription_rows,
        )


def fetch_products() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM products ORDER BY name", conn)


def fetch_variants() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """SELECT v.*, p.name AS product_name
               FROM variants v JOIN products p ON p.id = v.product_id
               ORDER BY p.name, v.name""",
            conn,
        )


def fetch_subscriptions() -> pd.DataFrame:
    """Return every subscription row joined with product/variant labels."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            """SELECT s.*, v.name AS variant_name, v.billing_cycle, p.name AS product_name
               FROM subscriptions s
               JOIN variants v ON v.id = s.variant_id
               JOIN products p ON p.id = v.product_id""",
            conn,
        )
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df


def insert_csv_subscriptions(df: pd.DataFrame) -> int:
    """Append externally-sourced subscription rows (e.g. from an uploaded CSV).

    Expects columns: variant_id, customer_ref, start_date, end_date, status,
    churn_reason, mrr. Returns the number of rows inserted.
    """
    required = {"variant_id", "customer_ref", "start_date", "status", "mrr"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    with get_connection() as conn:
        for _, row in df.iterrows():
            conn.execute(
                """INSERT INTO subscriptions
                   (variant_id, customer_ref, start_date, end_date, status,
                    churn_reason, regraded_to_variant_id, mrr)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(row["variant_id"]),
                    str(row["customer_ref"]),
                    str(row["start_date"]),
                    row.get("end_date") or None,
                    str(row["status"]),
                    row.get("churn_reason") or None,
                    row.get("regraded_to_variant_id") or None,
                    float(row["mrr"]),
                ),
            )
    return len(df)


def get_summary_metrics() -> dict:
    """Aggregate metrics for the dashboard's headline KPI row."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN status = 'active' THEN mrr ELSE 0 END), 0) AS mrr,
                 COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0) AS active_subscribers,
                 COALESCE(SUM(CASE WHEN status = 'churned' THEN 1 ELSE 0 END), 0) AS total_churned,
                 (SELECT COUNT(*) FROM products) AS product_count,
                 (SELECT COUNT(*) FROM variants) AS variant_count
               FROM subscriptions"""
        ).fetchone()
        return dict(row)
