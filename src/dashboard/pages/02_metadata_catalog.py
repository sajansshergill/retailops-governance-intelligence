"""Streamlit page for the metadata catalog."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.catalog.metadata_extractor import build_full_catalog, catalog_summary
from src.dashboard.components.kpi_cards import KPI, render_kpi_row
from src.dashboard.data import build_demo_connection


st.set_page_config(page_title="Metadata Catalog", layout="wide")
st.title("Metadata Catalog")

conn = build_demo_connection()
catalog = build_full_catalog(conn)
summary = catalog_summary(catalog)

render_kpi_row(
    [
        KPI("Catalog Assets", summary["total_assets"]),
        KPI("Tables", summary["tables"]),
        KPI("PII Columns", summary["pii_columns"]),
        KPI("Average Completeness", f"{summary['avg_completeness']:.1f}%"),
        KPI("Columns with Nulls", summary["columns_with_nulls"]),
    ],
    columns=5,
)

tables = sorted(catalog["table_name"].unique())
classifications = sorted(catalog["classification"].unique())

left, right, pii_col = st.columns(3)
selected_tables = left.multiselect("Tables", tables, default=tables)
selected_classifications = right.multiselect(
    "Classifications", classifications, default=classifications
)
pii_filter = pii_col.selectbox("PII filter", ["All", "PII only", "Non-PII only"])

filtered = catalog[
    catalog["table_name"].isin(selected_tables)
    & catalog["classification"].isin(selected_classifications)
]
if pii_filter == "PII only":
    filtered = filtered[filtered["is_pii"]]
elif pii_filter == "Non-PII only":
    filtered = filtered[~filtered["is_pii"]]

st.dataframe(
    filtered[
        [
            "asset_id",
            "data_type",
            "completeness",
            "pii_type",
            "classification",
            "owner",
            "business_description",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)
