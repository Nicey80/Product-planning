"""Streamlit UI for the Subscription Forecasting app."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import database as db

st.set_page_config(
    page_title="Subscription Forecasting",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()
db.seed_if_empty()

# ---------------------------------------------------------------------------
# Palette (validated categorical + chrome tokens, dark chart surface)
# ---------------------------------------------------------------------------
SURFACE = "#1a1a19"
INK_PRIMARY = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRIDLINE = "#2c2c2a"
BASELINE = "#383835"

CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]
SEQUENTIAL_BLUE = "#3987e5"
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#e66767"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def style_fig(fig: go.Figure, yaxis_title: str, legend: bool = True) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK_SECONDARY, size=12),
        margin=dict(l=10, r=10, t=40 if legend else 15, b=10),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=INK_SECONDARY)),
        xaxis=dict(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BASELINE, tickfont=dict(color=INK_MUTED)),
        yaxis=dict(title=yaxis_title, gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BASELINE, tickfont=dict(color=INK_MUTED)),
        hoverlabel=dict(bgcolor=SURFACE, font_color=INK_PRIMARY, bordercolor=BASELINE),
        height=360,
    )
    return fig


def render_chart(container, title: str, fig: go.Figure, yaxis_title: str, legend: bool = True) -> None:
    container.markdown(f"**{title}**")
    container.plotly_chart(style_fig(fig, yaxis_title, legend=legend), use_container_width=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
if "data_version" not in st.session_state:
    st.session_state.data_version = 0


@st.cache_data
def load_subscriptions(_version: int) -> pd.DataFrame:
    return db.fetch_subscriptions()


@st.cache_data
def load_products(_version: int) -> pd.DataFrame:
    return db.fetch_products()


@st.cache_data
def load_variants(_version: int) -> pd.DataFrame:
    return db.fetch_variants()


def compute_monthly_metrics(df: pd.DataFrame, months: int = 24, group_col: str | None = None) -> pd.DataFrame:
    """Roll subscription-level rows up into per-month active/new/churned/mrr totals."""
    periods = pd.period_range(end=pd.Timestamp(date.today()).to_period("M"), periods=months, freq="M")
    groups = [None] if group_col is None else list(df[group_col].unique())
    records = []
    for period in periods:
        month_end = period.end_time.normalize()
        for g in groups:
            sub = df if g is None else df[df[group_col] == g]
            active_mask = (sub["start_date"] <= month_end) & (sub["end_date"].isna() | (sub["end_date"] > month_end))
            new_mask = sub["start_date"].dt.to_period("M") == period
            churned_mask = (sub["status"] == "churned") & (sub["end_date"].dt.to_period("M") == period)
            records.append(
                {
                    "month": period.to_timestamp(),
                    "group": g if g is not None else "Total",
                    "active": int(active_mask.sum()),
                    "new": int(new_mask.sum()),
                    "churned": int(churned_mask.sum()),
                    "mrr": float(sub.loc[active_mask, "mrr"].sum()),
                }
            )
    return pd.DataFrame(records)


def trailing_churn_rate(df: pd.DataFrame, as_of: pd.Timestamp, window_days: int) -> float:
    window_start = as_of - pd.Timedelta(days=window_days)
    churned = df[(df["status"] == "churned") & (df["end_date"] > window_start) & (df["end_date"] <= as_of)].shape[0]
    active_at_start = ((df["start_date"] <= window_start) & (df["end_date"].isna() | (df["end_date"] > window_start))).sum()
    return churned / active_at_start if active_at_start else 0.0


# ---------------------------------------------------------------------------
# Global styling
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    .hero {{
        background: linear-gradient(135deg, #1c2f4d 0%, #142138 45%, #0d0d0d 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 2.25rem 2.5rem;
        margin-bottom: 1.5rem;
    }}
    .hero h1 {{
        font-size: 2.15rem;
        margin: 0 0 0.5rem 0;
        background: linear-gradient(90deg, #ffffff 0%, #9ec5f4 55%, #3987e5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .hero p {{
        color: {INK_SECONDARY};
        font-size: 1.02rem;
        margin: 0;
        max-width: 62ch;
    }}
    .kpi-card {{
        background: {SURFACE};
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 1.15rem 1.35rem;
    }}
    .kpi-label {{
        color: {INK_MUTED};
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-bottom: 0.4rem;
    }}
    .kpi-value {{
        color: {INK_PRIMARY};
        font-size: 1.9rem;
        font-weight: 700;
        line-height: 1.1;
    }}
    .kpi-delta-good {{ color: {STATUS_GOOD}; font-size: 0.85rem; margin-top: 0.4rem; }}
    .kpi-delta-bad {{ color: {STATUS_CRITICAL}; font-size: 0.85rem; margin-top: 0.4rem; }}
    .kpi-delta-flat {{ color: {INK_MUTED}; font-size: 0.85rem; margin-top: 0.4rem; }}
    section[data-testid="stSidebar"] {{ background: #121212; }}
    </style>
    <div class="hero">
        <h1>📡 Subscription Forecasting</h1>
        <p>Track the active subscriber base and churn across every product and plan variant, with a
        simple trend-based forecast. Sales and regrade forecasting are next on the roadmap.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — filters + forecast horizon
# ---------------------------------------------------------------------------
products_df = load_products(st.session_state.data_version)
variants_df = load_variants(st.session_state.data_version)
all_product_names = products_df["name"].tolist()
color_map = {name: CATEGORICAL[i % len(CATEGORICAL)] for i, name in enumerate(all_product_names)}

with st.sidebar:
    st.markdown("### Filters")
    selected_products = st.multiselect("Products", options=all_product_names, default=all_product_names)
    horizon = st.slider("Forecast horizon (months)", min_value=1, max_value=12, value=6)
    st.divider()
    st.caption("Data source, filters, and forecast horizon apply across every tab.")

subs_df_all = load_subscriptions(st.session_state.data_version)

if not selected_products:
    st.warning("Select at least one product in the sidebar to see data.")
    st.stop()

subs_df = subs_df_all[subs_df_all["product_name"].isin(selected_products)]

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
today = pd.Timestamp(date.today())
active_mask = subs_df["status"] == "active"
active_count = int(active_mask.sum())
mrr = float(subs_df.loc[active_mask, "mrr"].sum())

active_30d_ago = int(
    ((subs_df["start_date"] <= today - pd.Timedelta(days=30))
     & (subs_df["end_date"].isna() | (subs_df["end_date"] > today - pd.Timedelta(days=30)))).sum()
)
subscriber_delta = active_count - active_30d_ago

churn_rate_30 = trailing_churn_rate(subs_df, today, 30)
churn_rate_prev30 = trailing_churn_rate(subs_df, today - pd.Timedelta(days=30), 30)
churn_delta = churn_rate_30 - churn_rate_prev30


def kpi_card(col, label: str, value: str, delta_text: str | None = None, delta_class: str = "kpi-delta-flat"):
    delta_html = f'<div class="{delta_class}">{delta_text}</div>' if delta_text else ""
    col.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


k1, k2, k3, k4 = st.columns(4)
kpi_card(
    k1, "Active Subscribers", f"{active_count:,}",
    f"{'▲' if subscriber_delta >= 0 else '▼'} {abs(subscriber_delta):,} vs. 30 days ago",
    "kpi-delta-good" if subscriber_delta >= 0 else "kpi-delta-bad",
)
kpi_card(k2, "Monthly Recurring Revenue", f"${mrr:,.0f}")
kpi_card(
    k3, "30-Day Churn Rate", f"{churn_rate_30:.1%}",
    f"{'▲' if churn_delta >= 0 else '▼'} {abs(churn_delta):.1%} vs. prior 30 days",
    "kpi-delta-bad" if churn_delta >= 0 else "kpi-delta-good",
)
kpi_card(k4, "Products / Variants", f"{len(selected_products)} / {variants_df[variants_df['product_name'].isin(selected_products)].shape[0]}")

st.write("")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_forecast, tab_raw, tab_sources = st.tabs(
    ["📊 Overview", "🔮 Forecast", "🗂️ Raw Data", "🔌 Data Sources"]
)

with tab_overview:
    by_product = compute_monthly_metrics(subs_df, months=24, group_col="product_name")
    total = compute_monthly_metrics(subs_df, months=24, group_col=None).sort_values("month").reset_index(drop=True)
    total["prior_active"] = total["active"].shift(1)
    total["churn_rate"] = np.where(total["prior_active"] > 0, total["churned"] / total["prior_active"], 0.0)

    c1, c2 = st.columns(2)

    with c1:
        fig_base = go.Figure()
        for product in selected_products:
            d = by_product[by_product["group"] == product].sort_values("month")
            color = color_map[product]
            fig_base.add_trace(
                go.Scatter(
                    x=d["month"], y=d["active"], name=product, mode="lines",
                    stackgroup="active", line=dict(width=2, color=color),
                    fillcolor=hex_to_rgba(color, 0.55),
                    hovertemplate="%{y:,} active<extra>" + product + "</extra>",
                )
            )
        render_chart(st, "Active subscriber base by product", fig_base, "Active subscribers")

    with c2:
        fig_net = go.Figure()
        fig_net.add_trace(go.Bar(x=total["month"], y=total["new"], name="New", marker_color=SEQUENTIAL_BLUE))
        fig_net.add_trace(go.Bar(x=total["month"], y=-total["churned"], name="Churned", marker_color=STATUS_CRITICAL))
        fig_net.update_layout(barmode="relative")
        render_chart(st, "New vs. churned subscribers", fig_net, "Subscribers")

    c3, c4 = st.columns(2)

    with c3:
        fig_churn = go.Figure()
        fig_churn.add_trace(
            go.Scatter(
                x=total["month"], y=total["churn_rate"], mode="lines+markers", name="Churn rate",
                line=dict(width=2, color=SEQUENTIAL_BLUE), marker=dict(size=8, color=SEQUENTIAL_BLUE),
            )
        )
        fig_churn.update_yaxes(tickformat=".1%")
        render_chart(st, "Monthly churn rate", fig_churn, "Churn rate", legend=False)

    with c4:
        rows = []
        for product in selected_products:
            rate = trailing_churn_rate(subs_df[subs_df["product_name"] == product], today, 90)
            rows.append({"product": product, "churn_rate": rate})
        cbdf = pd.DataFrame(rows).sort_values("churn_rate")
        fig_bar = go.Figure(
            go.Bar(
                x=cbdf["churn_rate"], y=cbdf["product"], orientation="h",
                marker_color=[color_map[p] for p in cbdf["product"]],
            )
        )
        fig_bar.update_xaxes(tickformat=".1%")
        render_chart(st, "90-day churn rate by product", fig_bar, "Churn rate", legend=False)

    reason_counts = subs_df.loc[subs_df["status"] == "churned", "churn_reason"].value_counts()
    if not reason_counts.empty:
        top = reason_counts.head(5)
        other = reason_counts.iloc[5:].sum()
        labels, values, colors = list(top.index), list(top.values), CATEGORICAL[: len(top)]
        if other > 0:
            labels.append("Other")
            values.append(int(other))
            colors.append(INK_MUTED)
        fig_reason = go.Figure(go.Pie(labels=labels, values=values, hole=0.55, marker=dict(colors=colors)))
        render_chart(st, "Churn reasons", fig_reason, "", legend=True)

with tab_forecast:
    st.caption(
        "Baseline forecast: a linear trend fit to the last 12 months of active subscribers, "
        "with churn held at the trailing 3-month average. Treat this as a starting point, not a "
        "cohort or survival model."
    )

    recent = total.tail(12).reset_index(drop=True)
    x = np.arange(len(recent))
    slope, intercept = np.polyfit(x, recent["active"].values, 1)
    future_x = np.arange(len(recent), len(recent) + horizon)
    future_active = np.clip(slope * future_x + intercept, 0, None)
    future_months = pd.date_range(recent["month"].iloc[-1] + pd.DateOffset(months=1), periods=horizon, freq="MS")

    avg_churn_rate = recent["churn_rate"].tail(3).mean()
    active_series = np.r_[total["active"].iloc[-1], future_active]
    projected_churned = np.round(active_series[:-1] * avg_churn_rate).astype(int)

    avg_price = subs_df.loc[active_mask, "mrr"].mean() if active_count else 0.0
    projected_mrr = future_active[-1] * avg_price if len(future_active) else 0.0

    f1, f2, f3 = st.columns(3)
    kpi_card(f1, f"Projected Active Subscribers (+{horizon}mo)", f"{int(future_active[-1]):,}")
    kpi_card(f2, f"Projected Churn (next {horizon}mo)", f"{int(projected_churned.sum()):,}")
    kpi_card(f3, f"Projected MRR (+{horizon}mo)", f"${projected_mrr:,.0f}")

    st.write("")

    g1, g2 = st.columns(2)
    with g1:
        fig_fc = go.Figure()
        fig_fc.add_trace(
            go.Scatter(x=total["month"], y=total["active"], mode="lines", name="Historical",
                       line=dict(width=2, color=SEQUENTIAL_BLUE))
        )
        fig_fc.add_trace(
            go.Scatter(
                x=[total["month"].iloc[-1], *future_months], y=[total["active"].iloc[-1], *future_active],
                mode="lines", name=f"Forecast (+{horizon}mo)", line=dict(width=2, color=SEQUENTIAL_BLUE, dash="dash"),
            )
        )
        fig_fc.add_vline(x=total["month"].iloc[-1], line_width=1, line_dash="dot", line_color=BASELINE)
        render_chart(st, "Active subscriber forecast", fig_fc, "Active subscribers")

    with g2:
        fig_fc_churn = go.Figure(
            go.Bar(x=future_months, y=projected_churned, marker_color=STATUS_CRITICAL, name="Projected churn")
        )
        render_chart(st, "Projected monthly churn", fig_fc_churn, "Subscribers", legend=False)

with tab_raw:
    st.subheader("Subscription records")
    status_filter = st.multiselect("Status", options=sorted(subs_df["status"].unique()), default=list(subs_df["status"].unique()))
    display_df = subs_df[subs_df["status"].isin(status_filter)].sort_values("start_date", ascending=False)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "product_name": st.column_config.TextColumn("Product"),
            "variant_name": st.column_config.TextColumn("Variant"),
            "billing_cycle": st.column_config.TextColumn("Billing"),
            "customer_ref": st.column_config.TextColumn("Customer"),
            "start_date": st.column_config.DateColumn("Start Date"),
            "end_date": st.column_config.DateColumn("End Date"),
            "status": st.column_config.TextColumn("Status"),
            "churn_reason": st.column_config.TextColumn("Churn Reason"),
            "mrr": st.column_config.NumberColumn("MRR", format="$%.2f"),
        },
        column_order=[
            "id", "product_name", "variant_name", "billing_cycle", "customer_ref",
            "start_date", "end_date", "status", "churn_reason", "mrr",
        ],
    )
    st.download_button(
        "Download filtered data as CSV",
        data=display_df.to_csv(index=False).encode("utf-8"),
        file_name="subscriptions_export.csv",
        mime="text/csv",
    )

with tab_sources:
    st.subheader("Historic data sources")
    st.caption("Subscription history can be loaded from the local SQLite database, an uploaded CSV, or (soon) BigQuery.")

    s1, s2 = st.columns(2)

    with s1:
        st.markdown("#### Upload a CSV")
        st.caption(
            "Expected columns: `variant_id`, `customer_ref`, `start_date`, `end_date`, `status`, "
            "`churn_reason`, `mrr`. Rows are appended to the existing subscription history."
        )
        with st.expander("Variant ID reference"):
            st.dataframe(
                variants_df[["id", "product_name", "name", "billing_cycle", "price"]],
                use_container_width=True,
                hide_index=True,
            )
        uploaded = st.file_uploader("Subscription history CSV", type=["csv"])
        if uploaded is not None:
            preview_df = pd.read_csv(uploaded)
            st.dataframe(preview_df.head(10), use_container_width=True, hide_index=True)
            if st.button("Import rows into the database", type="primary"):
                try:
                    inserted = db.insert_csv_subscriptions(preview_df)
                    st.session_state.data_version += 1
                    st.success(f"Imported {inserted} rows.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with s2:
        st.markdown("#### BigQuery (coming soon)")
        st.caption("Point the app at a BigQuery table of historic subscription snapshots.")
        st.text_input("Project", placeholder="my-gcp-project", disabled=True)
        st.text_input("Dataset.table", placeholder="subscriptions.history", disabled=True)
        st.button("Connect to BigQuery", disabled=True)
        st.info("BigQuery connectivity is planned. This panel is a placeholder until the connector ships.")
