"""
Statistical anomaly detector.
Identifies outliers in numeric columns using z-score and IQR methods via DuckDB SQL.
Flags anomalous rows for downstream business intelligence and governance review.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def detect_zscore_outliers(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column: str,
    threshold: float = 3.0,
    group_by: str | None = None,
) -> pd.DataFrame:
    """
    Detect outliers using z-score method.

    Args:
        conn: Active DuckDB connection.
        table_name: Table to scan.
        column: Numeric column to analyze.
        threshold: Z-score threshold for flagging (default: 3.0).
        group_by: Optional grouping column (e.g., 'store_id') for per-group z-scores.

    Returns:
        DataFrame of flagged rows with z-score column appended.
    """
    if group_by:
        query = f"""
            SELECT *,
                ({column} - AVG({column}) OVER (PARTITION BY {group_by}))
                / NULLIF(STDDEV({column}) OVER (PARTITION BY {group_by}), 0) AS z_score
            FROM {table_name}
        """
    else:
        query = f"""
            SELECT *,
                ({column} - AVG({column}) OVER ())
                / NULLIF(STDDEV({column}) OVER (), 0) AS z_score
            FROM {table_name}
        """

    outlier_query = f"""
        SELECT * FROM ({query}) t
        WHERE ABS(z_score) >= {threshold}
        ORDER BY ABS(z_score) DESC
    """
    result = conn.execute(outlier_query).df()
    result["anomaly_method"] = "z_score"
    result["flagged_column"] = column
    return result


def detect_iqr_outliers(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column: str,
    multiplier: float = 1.5,
) -> pd.DataFrame:
    """
    Detect outliers using IQR (interquartile range) method.

    Args:
        conn: Active DuckDB connection.
        table_name: Table to scan.
        column: Numeric column to analyze.
        multiplier: IQR multiplier for fence calculation (default: 1.5).

    Returns:
        DataFrame of flagged rows outside IQR fences.
    """
    bounds = conn.execute(f"""
        SELECT
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {column}) AS q1,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {column}) AS q3
        FROM {table_name}
        WHERE {column} IS NOT NULL
    """).fetchone()

    q1, q3 = bounds
    iqr = q3 - q1
    lower_fence = q1 - multiplier * iqr
    upper_fence = q3 + multiplier * iqr

    result = conn.execute(f"""
        SELECT *, {column} AS flagged_value
        FROM {table_name}
        WHERE {column} < {lower_fence} OR {column} > {upper_fence}
        ORDER BY {column} DESC
    """).df()
    result["anomaly_method"] = "iqr"
    result["flagged_column"] = column
    result["iqr_lower_fence"] = lower_fence
    result["iqr_upper_fence"] = upper_fence
    return result


def revenue_anomaly_by_store(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Detect stores with anomalous daily revenue using z-score grouped by store.

    Returns:
        DataFrame of store-day pairs flagged as revenue anomalies.
    """
    query = """
        WITH daily_revenue AS (
            SELECT
                store_id,
                transaction_date,
                SUM(revenue) AS daily_revenue,
                COUNT(*) AS transaction_count
            FROM pos_transactions
            WHERE store_id IS NOT NULL
            GROUP BY store_id, transaction_date
        ),
        scored AS (
            SELECT *,
                (daily_revenue - AVG(daily_revenue) OVER (PARTITION BY store_id))
                / NULLIF(STDDEV(daily_revenue) OVER (PARTITION BY store_id), 0) AS z_score
            FROM daily_revenue
        )
        SELECT *,
            CASE
                WHEN z_score >= 3.0 THEN 'SPIKE'
                WHEN z_score <= -3.0 THEN 'DROP'
                ELSE 'NORMAL'
            END AS anomaly_type
        FROM scored
        WHERE ABS(z_score) >= 2.5
        ORDER BY ABS(z_score) DESC
    """
    return conn.execute(query).df()


def inventory_anomaly_flags(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Flag inventory records with extreme shrinkage, zero velocity, or implausible stock levels.

    Returns:
        DataFrame of flagged inventory records with reason column.
    """
    query = """
        SELECT *,
            CASE
                WHEN shrinkage_rate > 0.04 THEN 'HIGH_SHRINKAGE'
                WHEN daily_velocity = 0 AND stock_level > 0 THEN 'ZERO_VELOCITY_WITH_STOCK'
                WHEN stock_level = 0 AND stockout_risk != 'HIGH' THEN 'STOCKOUT_MISLABELED'
                WHEN days_to_stockout < lead_time_days THEN 'REORDER_BREACH'
                ELSE 'REVIEW'
            END AS anomaly_reason
        FROM inventory
        WHERE
            shrinkage_rate > 0.04
            OR (daily_velocity = 0 AND stock_level > 0)
            OR (stock_level = 0 AND stockout_risk != 'HIGH')
            OR days_to_stockout < lead_time_days
        ORDER BY shrinkage_rate DESC
    """
    return conn.execute(query).df()


def crm_anomaly_flags(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Flag CRM records with suspicious data patterns (extreme spenders, impossible dates, etc.).

    Returns:
        DataFrame of anomalous CRM records.
    """
    query = """
        WITH stats AS (
            SELECT
                AVG(total_spent) AS avg_spent,
                STDDEV(total_spent) AS std_spent,
                AVG(purchase_frequency) AS avg_freq,
                STDDEV(purchase_frequency) AS std_freq
            FROM crm_customers
        )
        SELECT c.*,
            CASE
                WHEN (c.total_spent - s.avg_spent) / NULLIF(s.std_spent, 0) > 3 THEN 'HIGH_SPEND_OUTLIER'
                WHEN (c.purchase_frequency - s.avg_freq) / NULLIF(s.std_freq, 0) > 3 THEN 'HIGH_FREQ_OUTLIER'
                WHEN c.days_since_last_purchase > 365 AND c.segment = 'Champion' THEN 'SEGMENT_MISMATCH'
                WHEN c.total_spent < c.avg_order_value THEN 'SPEND_FREQ_INCONSISTENCY'
                ELSE 'REVIEW'
            END AS anomaly_reason
        FROM crm_customers c, stats s
        WHERE
            (c.total_spent - s.avg_spent) / NULLIF(s.std_spent, 0) > 3
            OR (c.purchase_frequency - s.avg_freq) / NULLIF(s.std_freq, 0) > 3
            OR (c.days_since_last_purchase > 365 AND c.segment = 'Champion')
            OR c.total_spent < c.avg_order_value
    """
    return conn.execute(query).df()


def run_all_anomaly_checks(conn: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """
    Run all anomaly detection routines and return results by category.

    Returns:
        Dict with keys: 'revenue', 'inventory', 'crm'
    """
    print("[Anomaly Detector] Running revenue anomaly check...")
    revenue = revenue_anomaly_by_store(conn)
    print(f"  → {len(revenue)} store-day anomalies flagged")

    print("[Anomaly Detector] Running inventory anomaly check...")
    inventory = inventory_anomaly_flags(conn)
    print(f"  → {len(inventory)} inventory records flagged")

    print("[Anomaly Detector] Running CRM anomaly check...")
    crm = crm_anomaly_flags(conn)
    print(f"  → {len(crm)} CRM records flagged")

    return {"revenue": revenue, "inventory": inventory, "crm": crm}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.ingest.pos_generator import generate_pos_data, load_pos_to_duckdb
    from src.ingest.inventory_generator import generate_inventory_data, load_inventory_to_duckdb
    from src.ingest.crm_generator import generate_crm_data, load_crm_to_duckdb

    conn = duckdb.connect()
    load_pos_to_duckdb(generate_pos_data(10000), conn)
    load_inventory_to_duckdb(generate_inventory_data(), conn)
    load_crm_to_duckdb(generate_crm_data(5000), conn)

    results = run_all_anomaly_checks(conn)
    for k, df in results.items():
        print(f"\n[{k.upper()}] Sample anomalies:")
        print(df.head(3).to_string())
