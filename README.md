# Subscription Forecasting

A Streamlit app for managing and forecasting the subscription base of a
portfolio of products and their plan variants — active subscribers, churn,
and (soon) sales and regrade forecasting.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On first launch, `database.py` creates a local SQLite database at
`data/subscriptions.db` and seeds it with 24 months of simulated
subscriber and churn history across five sample products, so the
dashboard isn't empty on first run.

## Project layout

- `app.py` — Streamlit UI: KPIs, subscriber base & churn charts, a
  trend-based forecast, a raw data browser, and data source controls.
- `database.py` — SQLite schema (`products`, `variants`, `subscriptions`),
  initialization, and mock data seeding.
- `data/` — local SQLite database file (git-ignored, regenerated on first run).

## Data sources

Historic subscription data can come from:
- **SQLite (default)** — seeded automatically on first run.
- **CSV upload** — via the "Data Sources" tab in the app.
- **BigQuery** — placeholder in the app UI; connector not yet implemented.
