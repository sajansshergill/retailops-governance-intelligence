"""Shared dashboard data bootstrap helpers."""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from src.ingest.crm_generator import generate_crm_data
from src.ingest.inventory_generator import generate_inventory_data
from src.ingest.pos_generator import generate_pos_data


CORE_TABLES = ["pos_transactions", "inventory", "crm_customers"]


@st.cache_data(show_spinner=False)
def generate_sample_data(
    pos_records: int = 8_000,
    crm_customers: int = 3_000,
) -> dict[str, pd.DataFrame]:
    """Generate deterministic-enough in-memory data for dashboard demos."""
    return {
        "pos_transactions": generate_pos_data(pos_records),
        "inventory": generate_inventory_data(),
        "crm_customers": generate_crm_data(crm_customers),
    }


@st.cache_resource(show_spinner=False)
def build_demo_connection(
    pos_records: int = 8_000,
    crm_customers: int = 3_000,
) -> duckdb.DuckDBPyConnection:
    """Create a cached DuckDB connection with the core retail tables loaded."""
    conn = duckdb.connect(database=":memory:")
    for table_name, df in generate_sample_data(pos_records, crm_customers).items():
        conn.register(f"{table_name}_df", df)
        conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS "
            f"SELECT * FROM {table_name}_df"
        )
    return conn


def table_columns(conn: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Return table-to-column mapping for the governed core tables."""
    return {
        table: conn.execute(f"DESCRIBE {table}").df()["column_name"].tolist()
        for table in CORE_TABLES
    }
