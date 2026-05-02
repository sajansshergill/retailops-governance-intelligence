"""Streamlit page for business intelligence insights."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.dashboard.components.charts import (
    crm_completeness_heatmap,
    revenue_trend_line,
    stockout_by_store_bar,
)
from src.dashboard.components.kpi_cards import KPI, money, render_kpi_row
from src.dashboard.data import build_demo_connection
from src.intelligence.churn_detector import (
    churn_by_segment,
    churn_risk_cohorts,
    churn_summary,
    crm_completeness_by_segment,
)
from src.intelligence.revenue_anomaly import (
    daily_revenue_anomalies,
    revenue_anomaly_summary,
    revenue_trend_by_store,
    sku_revenue_anomalies,
)
from src.intelligence.stockout_risk import (
    compute_stockout_risk_table,
    stockout_by_store,
    stockout_risk_summary,
    top_stockout_skus,
)


st.set_page_config(page_title="Business Intelligence", layout="wide")
st.title("Business Intelligence")

conn = build_demo_connection()
stockout_summary = stockout_risk_summary(conn)
churn_stats = churn_summary(conn)
revenue_stats = revenue_anomaly_summary(conn)

render_kpi_row(
    [
        KPI("Stockout Exposure", money(stockout_summary["total_stock_value_at_risk"])),
        KPI("Reorder Breaches", stockout_summary["reorder_breach_count"]),
        KPI("Churn Rate", f"{churn_stats['churn_rate_pct']:.1f}%"),
        KPI("Revenue at Risk", money(churn_stats["revenue_at_risk"])),
        KPI("Revenue Anomaly Days", revenue_stats["total_anomaly_days"]),
    ],
    columns=5,
)

stockout_tab, crm_tab, revenue_tab = st.tabs(
    ["Stockout Risk", "CRM & Churn", "Revenue Anomalies"]
)

with stockout_tab:
    by_store = stockout_by_store(conn)
    st.plotly_chart(stockout_by_store_bar(by_store), use_container_width=True)
    st.subheader("Top At-Risk SKUs")
    st.dataframe(top_stockout_skus(conn), use_container_width=True, hide_index=True)
    st.subheader("Detailed Risk Table")
    st.dataframe(compute_stockout_risk_table(conn).head(100), use_container_width=True, hide_index=True)

with crm_tab:
    completeness = crm_completeness_by_segment(conn)
    st.plotly_chart(crm_completeness_heatmap(completeness), use_container_width=True)
    left, right = st.columns(2)
    left.subheader("Churn by Segment")
    left.dataframe(churn_by_segment(conn), use_container_width=True, hide_index=True)
    right.subheader("Top Retention Cohorts")
    right.dataframe(churn_risk_cohorts(conn).head(50), use_container_width=True, hide_index=True)

with revenue_tab:
    trend = revenue_trend_by_store(conn)
    stores = sorted(trend["store_id"].dropna().unique().tolist())[:5]
    selected_stores = st.multiselect("Stores", sorted(trend["store_id"].dropna().unique()), default=stores)
    st.plotly_chart(revenue_trend_line(trend, selected_stores), use_container_width=True)
    left, right = st.columns(2)
    left.subheader("Store-Day Anomalies")
    left.dataframe(daily_revenue_anomalies(conn).head(50), use_container_width=True, hide_index=True)
    right.subheader("SKU Revenue Outliers")
    right.dataframe(sku_revenue_anomalies(conn).head(50), use_container_width=True, hide_index=True)
