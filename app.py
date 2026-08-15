"""Streamlit UI for the Product Planning & Forecasting app."""

from datetime import date, timedelta

import streamlit as st

import database as db

st.set_page_config(
    page_title="Product Planning & Forecasting",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()
db.seed_if_empty()

st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
    }
    h1 {
        padding-bottom: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📦 Product Planning & Forecasting")
st.caption("Plan, track, and forecast product volumes across categories.")

metrics = db.get_summary_metrics()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Planned Volume", f"{metrics['total_volume']:,}")
m2.metric("Total Plans", metrics["row_count"])
m3.metric("Approved Plans", metrics["approved_count"])
m4.metric("Categories Covered", metrics["category_count"])

st.divider()

st.subheader("Add a New Product Plan")
with st.form("new_plan_form", clear_on_submit=True):
    left, right = st.columns(2)
    with left:
        product_name = st.text_input("Product Name")
        category = st.selectbox("Category", db.CATEGORIES)
        planned_volume = st.number_input(
            "Planned Volume", min_value=0, step=100, value=1000
        )
    with right:
        forecast_date = st.date_input(
            "Forecast Date", value=date.today() + timedelta(days=30)
        )
        status = st.selectbox("Status", db.STATUSES)
        notes = st.text_area("Notes", height=100)

    submitted = st.form_submit_button("Add Plan", type="primary")
    if submitted:
        if not product_name.strip():
            st.error("Product Name is required.")
        else:
            db.insert_plan(
                product_name=product_name.strip(),
                category=category,
                planned_volume=int(planned_volume),
                forecast_date=forecast_date.isoformat(),
                status=status,
                notes=notes.strip(),
            )
            st.success(f"Added '{product_name}' to the plan.")
            st.rerun()

st.divider()

st.subheader("Current Plans")

df = db.fetch_all_plans()

if not df.empty:
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        selected_categories = st.multiselect(
            "Filter by Category", options=db.CATEGORIES, default=[]
        )
    with filter_col2:
        selected_statuses = st.multiselect(
            "Filter by Status", options=db.STATUSES, default=[]
        )

    filtered_df = df.copy()
    if selected_categories:
        filtered_df = filtered_df[filtered_df["category"].isin(selected_categories)]
    if selected_statuses:
        filtered_df = filtered_df[filtered_df["status"].isin(selected_statuses)]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "product_name": st.column_config.TextColumn("Product Name"),
            "category": st.column_config.TextColumn("Category"),
            "planned_volume": st.column_config.NumberColumn(
                "Planned Volume", format="%d"
            ),
            "forecast_date": st.column_config.DateColumn("Forecast Date"),
            "status": st.column_config.TextColumn("Status"),
            "notes": st.column_config.TextColumn("Notes", width="large"),
            "created_at": st.column_config.DatetimeColumn("Created At"),
        },
    )

    with st.expander("Manage existing plans"):
        plan_options = {
            f"#{row.id} — {row.product_name}": row.id for row in df.itertuples()
        }
        selected_label = st.selectbox("Select a plan", options=list(plan_options.keys()))
        if st.button("Delete selected plan"):
            db.delete_plan(plan_options[selected_label])
            st.success("Plan deleted.")
            st.rerun()
else:
    st.info("No product plans yet. Add one above to get started.")
