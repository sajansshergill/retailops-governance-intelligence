"""Streamlit page for governance tracking."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.dashboard.components.kpi_cards import KPI, render_kpi_row
from src.dashboard.data import build_demo_connection, table_columns
from src.governance.rules_engine import build_pii_catalog, run_governance_checks
from src.profiling.quality_scorer import score_all_tables


st.set_page_config(page_title="Governance Tracker", layout="wide")
st.title("Governance Issue Tracker")

conn = build_demo_connection()
scores = score_all_tables(conn, log_to_mlflow=False)
quality_scores = dict(zip(scores["table"], scores["composite_score"]))
issues = run_governance_checks(table_columns(conn), quality_scores=quality_scores)
pii_catalog = build_pii_catalog(table_columns(conn))

if issues.empty:
    issues = pd.DataFrame(
        columns=[
            "issue_id",
            "source_table",
            "column_name",
            "rule_name",
            "description",
            "severity",
            "owner",
            "status",
            "created_at",
            "sla_due",
            "resolved_at",
        ]
    )

render_kpi_row(
    [
        KPI("Open Issues", len(issues)),
        KPI("Critical/High", int(issues["severity"].isin(["CRITICAL", "HIGH"]).sum())),
        KPI("Owners", issues["owner"].nunique() if not issues.empty else 0),
        KPI("PII Columns", len(pii_catalog)),
    ],
    columns=4,
)

severity_options = ["All"] + sorted(issues["severity"].dropna().unique().tolist())
owner_options = ["All"] + sorted(issues["owner"].dropna().unique().tolist())
left, right = st.columns(2)
severity = left.selectbox("Severity", severity_options)
owner = right.selectbox("Owner", owner_options)

filtered = issues.copy()
if severity != "All":
    filtered = filtered[filtered["severity"] == severity]
if owner != "All":
    filtered = filtered[filtered["owner"] == owner]

st.subheader("Issues")
st.dataframe(filtered, use_container_width=True, hide_index=True)

st.subheader("PII Catalog")
st.dataframe(pii_catalog, use_container_width=True, hide_index=True)
