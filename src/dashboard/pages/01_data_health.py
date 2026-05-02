"""Streamlit page for data health monitoring."""

from __future__ import annotations

import streamlit as st

from src.dashboard.components.charts import quality_bar
from src.dashboard.components.kpi_cards import KPI, render_kpi_row
from src.dashboard.data import build_demo_connection
from src.profiling.quality_scorer import score_all_tables


st.set_page_config(page_title="Data Health", layout="wide")
st.title("Data Health Scorecard")

conn = build_demo_connection()
scores = score_all_tables(conn, log_to_mlflow=False)

render_kpi_row(
    [
        KPI("Average Composite", f"{scores['composite_score'].mean():.1f}/100"),
        KPI("Best Dataset", scores.sort_values("composite_score", ascending=False).iloc[0]["table"]),
        KPI("Lowest Completeness", f"{scores['completeness'].min():.1f}%"),
        KPI("Tables Profiled", len(scores)),
    ],
    columns=4,
)

st.plotly_chart(quality_bar(scores), use_container_width=True)
st.dataframe(scores, use_container_width=True, hide_index=True)
