"""
Column-level data profiler using DuckDB.
Computes completeness, cardinality, type distribution, min/max/mean,
and flags anomalous columns across all registered datasets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import duckdb
import pandas as pd


@dataclass
class ColumnProfile:
    source: str
    column_name: str
    data_type: str
    total_rows: int
    null_count: int
    null_rate: float
    unique_count: int
    cardinality_rate: float
    min_value: Any = None
    max_value: Any = None
    mean_value: float | None = None
    std_value: float | None = None
    sample_values: list = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def completeness_score(self) -> float:
        return round(1.0 - self.null_rate, 4)


def profile_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> list[ColumnProfile]:
    """
    Profile all columns in a DuckDB table.

    Args:
        conn: Active DuckDB connection.
        table_name: Name of table to profile.

    Returns:
        List of ColumnProfile objects, one per column.
    """
    schema_df = conn.execute(f"DESCRIBE {table_name}").df()
    total_rows = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    profiles = []
    for _, row in schema_df.iterrows():
        col = row["column_name"]
        dtype = row["column_type"]

        null_count = conn.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE \"{col}\" IS NULL"
        ).fetchone()[0]
        null_rate = round(null_count / total_rows, 4) if total_rows > 0 else 0.0

        unique_count = conn.execute(
            f"SELECT COUNT(DISTINCT \"{col}\") FROM {table_name}"
        ).fetchone()[0]
        cardinality_rate = round(unique_count / total_rows, 4) if total_rows > 0 else 0.0

        # Numeric stats
        mean_val = std_val = min_val = max_val = None
        numeric_types = ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT")
        if any(t in dtype.upper() for t in numeric_types):
            stats = conn.execute(
                f'SELECT MIN("{col}"), MAX("{col}"), AVG("{col}"), STDDEV("{col}") FROM {table_name}'
            ).fetchone()
            min_val, max_val, mean_val, std_val = stats
            if mean_val is not None:
                mean_val = round(float(mean_val), 4)
            if std_val is not None:
                std_val = round(float(std_val), 4)
        else:
            min_max = conn.execute(
                f'SELECT MIN(CAST("{col}" AS VARCHAR)), MAX(CAST("{col}" AS VARCHAR)) FROM {table_name}'
            ).fetchone()
            min_val, max_val = min_max

        # Sample values (top 5 most frequent)
        samples = conn.execute(
            f'SELECT CAST("{col}" AS VARCHAR) as v FROM {table_name} '
            f'WHERE "{col}" IS NOT NULL GROUP BY v ORDER BY COUNT(*) DESC LIMIT 5'
        ).df()["v"].tolist()

        # Flag rules
        flags = []
        if null_rate > 0.20:
            flags.append("HIGH_NULL_RATE")
        if null_rate > 0.0:
            flags.append("HAS_NULLS")
        if cardinality_rate == 1.0 and total_rows > 1:
            flags.append("LIKELY_ID_COLUMN")
        if cardinality_rate < 0.01 and unique_count > 1:
            flags.append("LOW_CARDINALITY")
        if unique_count == 1:
            flags.append("SINGLE_VALUE_COLUMN")
        if "ID" in col.upper() and null_count > 0:
            flags.append("NULLABLE_ID")

        profiles.append(ColumnProfile(
            source=table_name,
            column_name=col,
            data_type=dtype,
            total_rows=total_rows,
            null_count=null_count,
            null_rate=null_rate,
            unique_count=unique_count,
            cardinality_rate=cardinality_rate,
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            std_value=std_val,
            sample_values=samples,
            flags=flags,
        ))

    return profiles


def profiles_to_dataframe(profiles: list[ColumnProfile]) -> pd.DataFrame:
    """Convert list of ColumnProfile objects to a flat DataFrame."""
    return pd.DataFrame([{
        "source": p.source,
        "column_name": p.column_name,
        "data_type": p.data_type,
        "total_rows": p.total_rows,
        "null_count": p.null_count,
        "null_rate": p.null_rate,
        "completeness_score": p.completeness_score,
        "unique_count": p.unique_count,
        "cardinality_rate": p.cardinality_rate,
        "min_value": str(p.min_value) if p.min_value is not None else None,
        "max_value": str(p.max_value) if p.max_value is not None else None,
        "mean_value": p.mean_value,
        "std_value": p.std_value,
        "sample_values": ", ".join(str(s) for s in p.sample_values),
        "flags": ", ".join(p.flags) if p.flags else "CLEAN",
    } for p in profiles])


def profile_all_tables(conn: duckdb.DuckDBPyConnection, tables: list[str]) -> pd.DataFrame:
    """
    Profile multiple tables and return a combined DataFrame.

    Args:
        conn: Active DuckDB connection.
        tables: List of table names to profile.

    Returns:
        Combined profile DataFrame across all tables.
    """
    all_profiles = []
    for table in tables:
        print(f"[Profiler] Profiling table: {table}")
        profiles = profile_table(conn, table)
        all_profiles.extend(profiles)
        print(f"  → {len(profiles)} columns profiled")

    return profiles_to_dataframe(all_profiles)


def compute_table_quality_score(profile_df: pd.DataFrame, table_name: str) -> float:
    """
    Compute a 0–100 quality score for a table based on completeness.

    Args:
        profile_df: Output of profiles_to_dataframe().
        table_name: Table to score.

    Returns:
        Float quality score between 0 and 100.
    """
    tbl = profile_df[profile_df["source"] == table_name]
    if tbl.empty:
        return 0.0
    avg_completeness = tbl["completeness_score"].mean()
    high_null_penalty = tbl["flags"].str.contains("HIGH_NULL_RATE").sum() * 2
    nullable_id_penalty = tbl["flags"].str.contains("NULLABLE_ID").sum() * 5
    score = avg_completeness * 100 - high_null_penalty - nullable_id_penalty
    return round(max(0.0, min(100.0, score)), 2)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.ingest.pos_generator import generate_pos_data, load_pos_to_duckdb
    from src.ingest.inventory_generator import generate_inventory_data, load_inventory_to_duckdb
    from src.ingest.crm_generator import generate_crm_data, load_crm_to_duckdb

    conn = duckdb.connect()
    load_pos_to_duckdb(generate_pos_data(5000), conn)
    load_inventory_to_duckdb(generate_inventory_data(), conn)
    load_crm_to_duckdb(generate_crm_data(2000), conn)

    profile_df = profile_all_tables(conn, ["pos_transactions", "inventory", "crm_customers"])
    print(f"\nProfile shape: {profile_df.shape}")
    print(profile_df[["source", "column_name", "null_rate", "completeness_score", "flags"]].to_string())

    for table in ["pos_transactions", "inventory", "crm_customers"]:
        score = compute_table_quality_score(profile_df, table)
        print(f"\n[Quality Score] {table}: {score}/100")
