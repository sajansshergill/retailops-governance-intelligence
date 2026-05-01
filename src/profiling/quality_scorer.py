"""
Multi-dimension data quality scorer.
Computes completeness, consistency, validity, and uniqueness scores
per table and rolls up to a composite 0–100 quality score.
Scores are logged to MLflow for trend tracking across pipeline runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb
import mlflow
import pandas as pd


@dataclass
class QualityDimension:
    completeness: float    # % of non-null values
    consistency: float     # % of values conforming to format/range rules
    validity: float        # % of values passing business rules
    uniqueness: float      # % unique on expected-unique columns
    composite: float       # Weighted average


DIMENSION_WEIGHTS = {
    "completeness": 0.35,
    "consistency": 0.25,
    "validity": 0.25,
    "uniqueness": 0.15,
}


def score_completeness(conn: duckdb.DuckDBPyConnection, table_name: str) -> float:
    """Average non-null rate across all columns."""
    schema = conn.execute(f"DESCRIBE {table_name}").df()
    total_rows = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    if total_rows == 0:
        return 0.0

    null_rates = []
    for col in schema["column_name"]:
        null_count = conn.execute(
            f'SELECT COUNT(*) FROM {table_name} WHERE "{col}" IS NULL'
        ).fetchone()[0]
        null_rates.append(1.0 - null_count / total_rows)

    return round(sum(null_rates) / len(null_rates) * 100, 2)


def score_consistency_pos(conn: duckdb.DuckDBPyConnection) -> float:
    """POS consistency: revenue = unit_price * quantity - discount_amount (within 1 cent)."""
    total = conn.execute("SELECT COUNT(*) FROM pos_transactions").fetchone()[0]
    if total == 0:
        return 0.0
    consistent = conn.execute("""
        SELECT COUNT(*) FROM pos_transactions
        WHERE ABS(revenue - (unit_price * quantity - discount_amount)) <= 0.01
    """).fetchone()[0]
    return round(consistent / total * 100, 2)


def score_consistency_inventory(conn: duckdb.DuckDBPyConnection) -> float:
    """Inventory consistency: stockout_risk label matches stock_level vs reorder_point logic."""
    total = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    if total == 0:
        return 0.0
    consistent = conn.execute("""
        SELECT COUNT(*) FROM inventory
        WHERE
            (stock_level <= reorder_point AND stockout_risk = 'HIGH')
            OR (stock_level > reorder_point AND stock_level <= reorder_point * 1.5 AND stockout_risk = 'MEDIUM')
            OR (stock_level > reorder_point * 1.5 AND stockout_risk = 'LOW')
    """).fetchone()[0]
    return round(consistent / total * 100, 2)


def score_consistency_crm(conn: duckdb.DuckDBPyConnection) -> float:
    """CRM consistency: total_spent ≈ avg_order_value * purchase_frequency (within 5%)."""
    total = conn.execute("SELECT COUNT(*) FROM crm_customers").fetchone()[0]
    if total == 0:
        return 0.0
    consistent = conn.execute("""
        SELECT COUNT(*) FROM crm_customers
        WHERE ABS(total_spent - (avg_order_value * purchase_frequency))
              / NULLIF(total_spent, 0) <= 0.05
    """).fetchone()[0]
    return round(consistent / total * 100, 2)


def score_validity(conn: duckdb.DuckDBPyConnection, table_name: str) -> float:
    """Check business rule validity per table."""
    total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    if total == 0:
        return 0.0

    if table_name == "pos_transactions":
        valid = conn.execute("""
            SELECT COUNT(*) FROM pos_transactions
            WHERE revenue >= 0
              AND unit_price > 0
              AND quantity > 0
              AND discount_pct BETWEEN 0 AND 100
        """).fetchone()[0]
    elif table_name == "inventory":
        valid = conn.execute("""
            SELECT COUNT(*) FROM inventory
            WHERE stock_level >= 0
              AND reorder_point > 0
              AND daily_velocity >= 0
              AND shrinkage_rate BETWEEN 0 AND 1
              AND lead_time_days > 0
        """).fetchone()[0]
    elif table_name == "crm_customers":
        valid = conn.execute("""
            SELECT COUNT(*) FROM crm_customers
            WHERE total_spent >= 0
              AND purchase_frequency >= 0
              AND avg_order_value > 0
              AND rfm_total BETWEEN 3 AND 15
              AND days_since_last_purchase >= 0
        """).fetchone()[0]
    else:
        return 100.0

    return round(valid / total * 100, 2)


def score_uniqueness(conn: duckdb.DuckDBPyConnection, table_name: str) -> float:
    """Check uniqueness on primary key columns."""
    pk_map = {
        "pos_transactions": "transaction_id",
        "inventory": "inventory_id",
        "crm_customers": "customer_id",
    }
    pk = pk_map.get(table_name)
    if not pk:
        return 100.0

    total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    unique = conn.execute(f'SELECT COUNT(DISTINCT "{pk}") FROM {table_name}').fetchone()[0]
    return round(unique / total * 100, 2) if total > 0 else 0.0


def compute_quality_dimensions(
    conn: duckdb.DuckDBPyConnection, table_name: str
) -> QualityDimension:
    """
    Compute all four quality dimensions for a given table.

    Args:
        conn: Active DuckDB connection.
        table_name: Table to score.

    Returns:
        QualityDimension dataclass with individual and composite scores.
    """
    completeness = score_completeness(conn, table_name)
    uniqueness = score_uniqueness(conn, table_name)
    validity = score_validity(conn, table_name)

    consistency_map = {
        "pos_transactions": score_consistency_pos,
        "inventory": score_consistency_inventory,
        "crm_customers": score_consistency_crm,
    }
    consistency_fn = consistency_map.get(table_name)
    consistency = consistency_fn(conn) if consistency_fn else 100.0

    composite = round(
        completeness * DIMENSION_WEIGHTS["completeness"]
        + consistency * DIMENSION_WEIGHTS["consistency"]
        + validity * DIMENSION_WEIGHTS["validity"]
        + uniqueness * DIMENSION_WEIGHTS["uniqueness"],
        2,
    )

    return QualityDimension(
        completeness=completeness,
        consistency=consistency,
        validity=validity,
        uniqueness=uniqueness,
        composite=composite,
    )


def score_all_tables(
    conn: duckdb.DuckDBPyConnection,
    tables: list[str] | None = None,
    log_to_mlflow: bool = True,
    run_name: str | None = None,
) -> pd.DataFrame:
    """
    Score all tables and optionally log to MLflow.

    Args:
        conn: Active DuckDB connection.
        tables: List of table names. Defaults to the three core tables.
        log_to_mlflow: Whether to log scores to MLflow.
        run_name: MLflow run name. Defaults to timestamped name.

    Returns:
        DataFrame with one row per table showing all dimension scores.
    """
    if tables is None:
        tables = ["pos_transactions", "inventory", "crm_customers"]

    results = []
    run_ts = run_name or f"quality_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    mlflow_run = None
    if log_to_mlflow:
        mlflow.set_experiment("retailops_data_quality")
        mlflow_run = mlflow.start_run(run_name=run_ts)

    for table in tables:
        print(f"[Quality Scorer] Scoring: {table}")
        dims = compute_quality_dimensions(conn, table)
        results.append({
            "table": table,
            "completeness": dims.completeness,
            "consistency": dims.consistency,
            "validity": dims.validity,
            "uniqueness": dims.uniqueness,
            "composite_score": dims.composite,
            "run_timestamp": datetime.now().isoformat(),
        })
        print(f"  → Composite: {dims.composite}/100")

        if log_to_mlflow and mlflow_run:
            mlflow.log_metrics({
                f"{table}_completeness": dims.completeness,
                f"{table}_consistency": dims.consistency,
                f"{table}_validity": dims.validity,
                f"{table}_uniqueness": dims.uniqueness,
                f"{table}_composite": dims.composite,
            })

    if log_to_mlflow and mlflow_run:
        mlflow.end_run()

    return pd.DataFrame(results)


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

    scores_df = score_all_tables(conn, log_to_mlflow=False)
    print("\nQuality Scores:")
    print(scores_df.to_string(index=False))