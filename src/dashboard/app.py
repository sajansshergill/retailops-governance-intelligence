"""Streamlit application entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.catalog.metadata_extractor import build_full_catalog, catalog_summary
from src.dashboard.components.kpi_cards import KPI, render_kpi_row
from src.dashboard.data import build_demo_connection
from src.intelligence.churn_detector import churn_summary
from src.intelligence.revenue_anomaly import revenue_anomaly_summary
from src.intelligence.stockout_risk import stockout_risk_summary
from src.profiling.quality_scorer import score_all_tables


st.set_page_config(
    page_title="RetailOps Governance Intelligence",
    page_icon="RO",
    layout="wide",
)

st.title("RetailOps Data Governance & Intelligence Platform")
st.caption(
    "Synthetic retail data quality, cataloging, governance, and BI workflows "
    "for POS, inventory, and CRM domains."
)

with st.spinner("Generating demo data and scoring governed tables..."):
    conn = build_demo_connection()
    quality = score_all_tables(conn, log_to_mlflow=False)
    catalog = build_full_catalog(conn)
    stockout = stockout_risk_summary(conn)
    churn = churn_summary(conn)
    revenue = revenue_anomaly_summary(conn)
    catalog_stats = catalog_summary(catalog)

avg_quality = round(quality["composite_score"].mean(), 1)

render_kpi_row(
    [
        KPI("Avg Data Quality", f"{avg_quality}/100"),
        KPI("Catalog Assets", catalog_stats["total_assets"]),
        KPI("PII Columns", catalog_stats["pii_columns"]),
        KPI("Stockout Records", stockout["total_at_risk_records"]),
        KPI("Churn Rate", f"{churn['churn_rate_pct']:.1f}%"),
        KPI("Revenue Anomaly Days", revenue["total_anomaly_days"]),
    ],
    columns=6,
)

st.divider()

left, right = st.columns([1.2, 1])
with left:
    st.subheader("Governed Data Domains")
    st.dataframe(
        quality[["table", "completeness", "consistency", "validity", "uniqueness", "composite_score"]],
        use_container_width=True,
        hide_index=True,
    )

with right:
    st.subheader("Platform Capabilities")
    st.markdown(
        """
        - Data health scorecard across completeness, consistency, validity, and uniqueness.
        - Metadata catalog with PII tags, owner assignment, and classifications.
        - Lineage map from source tables through transforms to executive outputs.
        - BI signals for stockout risk, churn, CRM completeness, and revenue anomalies.
        - Export center for stakeholder-ready XLSX, DOCX, and PPTX artifacts.
        """
    )

st.info("Use the pages in the sidebar to inspect each workflow in detail.")
