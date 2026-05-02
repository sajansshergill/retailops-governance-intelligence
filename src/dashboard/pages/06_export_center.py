"""Streamlit page for exports."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.catalog.metadata_extractor import build_full_catalog
from src.dashboard.data import build_demo_connection, table_columns
from src.governance.rules_engine import run_governance_checks
from src.profiling.quality_scorer import score_all_tables
from src.reporting.docx_reporter import build_business_requirements_docx
from src.reporting.pptx_builder import build_executive_summary_pptx
from src.reporting.xlsx_exporter import build_metadata_workbook


st.set_page_config(page_title="Export Center", layout="wide")
st.title("Export Center")

conn = build_demo_connection()
catalog = build_full_catalog(conn)
quality = score_all_tables(conn, log_to_mlflow=False)
quality_scores = dict(zip(quality["table"], quality["composite_score"]))
issues = run_governance_checks(table_columns(conn), quality_scores=quality_scores)

st.write("Generate stakeholder-ready governance and intelligence artifacts.")

col1, col2, col3 = st.columns(3)
with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    xlsx_path = tmp_path / "retailops_metadata_catalog.xlsx"
    build_metadata_workbook(catalog, quality, issues, xlsx_path)
    col1.download_button(
        "Download Metadata XLSX",
        xlsx_path.read_bytes(),
        file_name=xlsx_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    docx_path = tmp_path / "retailops_business_requirements.docx"
    build_business_requirements_docx(catalog, quality, issues, docx_path)
    col2.download_button(
        "Download BRD DOCX",
        docx_path.read_bytes(),
        file_name=docx_path.name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    pptx_path = tmp_path / "retailops_executive_summary.pptx"
    build_executive_summary_pptx(quality, issues, pptx_path)
    col3.download_button(
        "Download Executive PPTX",
        pptx_path.read_bytes(),
        file_name=pptx_path.name,
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

st.subheader("Export Preview")
st.dataframe(catalog.head(25), use_container_width=True, hide_index=True)
