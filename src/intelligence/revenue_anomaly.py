"""
Revenue anomaly detection.
Identifies stores and SKUs with statistically significant revenue deviations
using z-score and rolling baseline methods via DuckDB SQL.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def daily_revenue_anomalies(
    conn: duckdb.DuckDBPyConnection, z_threshold: float = 2.5
) -> pd.DataFrame:
    """
    Detect store-day revenue anomalies using per-store z-score.

    Args:
        conn: Active DuckDB connection.
        z_threshold: Z-score cutoff for anomaly flagging.

    Returns:
        DataFrame of flagged store-day records with anomaly type and z-score.
    """
    return conn.execute(f"""
        WITH daily AS (
            SELECT
                store_id,
                transaction_date,
                SUM(revenue) AS daily_revenue,
                COUNT(*) AS transaction_count,
                AVG(revenue) AS avg_transaction_value
            FROM pos_transactions
            WHERE store_id IS NOT NULL
            GROUP BY store_id, transaction_date
        ),
        scored AS (
            SELECT *,
                AVG(daily_revenue) OVER (PARTITION BY store_id) AS store_avg_revenue,
                STDDEV(daily_revenue) OVER (PARTITION BY store_id) AS store_std_revenue
            FROM daily
        )
        SELECT *,
            ROUND(
                (daily_revenue - store_avg_revenue) / NULLIF(store_std_revenue, 0),
                3
            ) AS z_score,
            CASE
                WHEN (daily_revenue - store_avg_revenue) / NULLIF(store_std_revenue, 0) >= {z_threshold}
                    THEN 'REVENUE_SPIKE'
                WHEN (daily_revenue - store_avg_revenue) / NULLIF(store_std_revenue, 0) <= -{z_threshold}
                    THEN 'REVENUE_DROP'
            END AS anomaly_type
        FROM scored
        WHERE ABS((daily_revenue - store_avg_revenue) / NULLIF(store_std_revenue, 0)) >= {z_threshold}
        ORDER BY ABS((daily_revenue - store_avg_revenue) / NULLIF(store_std_revenue, 0)) DESC
    """).df()


def sku_revenue_anomalies(
    conn: duckdb.DuckDBPyConnection, z_threshold: float = 3.0
) -> pd.DataFrame:
    """
    Detect SKU-level revenue outliers across all stores.

    Returns:
        DataFrame of SKUs with anomalous total revenue contribution.
    """
    return conn.execute(f"""
        WITH sku_totals AS (
            SELECT
                sku,
                category,
                SUM(revenue) AS total_revenue,
                SUM(quantity) AS total_units_sold,
                AVG(unit_price) AS avg_price,
                COUNT(DISTINCT store_id) AS stores_sold_in
            FROM pos_transactions
            GROUP BY sku, category
        ),
        scored AS (
            SELECT *,
                AVG(total_revenue) OVER (PARTITION BY category) AS cat_avg_revenue,
                STDDEV(total_revenue) OVER (PARTITION BY category) AS cat_std_revenue
            FROM sku_totals
        )
        SELECT *,
            ROUND(
                (total_revenue - cat_avg_revenue) / NULLIF(cat_std_revenue, 0),
                3
            ) AS z_score,
            CASE
                WHEN (total_revenue - cat_avg_revenue) / NULLIF(cat_std_revenue, 0) >= {z_threshold}
                    THEN 'TOP_PERFORMER'
                WHEN (total_revenue - cat_avg_revenue) / NULLIF(cat_std_revenue, 0) <= -{z_threshold}
                    THEN 'UNDERPERFORMER'
            END AS anomaly_type
        FROM scored
        WHERE ABS((total_revenue - cat_avg_revenue) / NULLIF(cat_std_revenue, 0)) >= {z_threshold}
        ORDER BY z_score DESC
    """).df()


def revenue_trend_by_store(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Weekly revenue trend per store — used for sparkline charts in dashboard.

    Returns:
        DataFrame with week, store_id, weekly_revenue columns.
    """
    return conn.execute("""
        SELECT
            store_id,
            DATE_TRUNC('week', transaction_date) AS week_start,
            ROUND(SUM(revenue), 2) AS weekly_revenue,
            COUNT(*) AS transaction_count
        FROM pos_transactions
        WHERE store_id IS NOT NULL
        GROUP BY store_id, week_start
        ORDER BY store_id, week_start
    """).df()


def revenue_anomaly_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """
    High-level KPIs for the revenue anomaly landscape.

    Returns:
        Dict with spike count, drop count, total anomalous revenue.
    """
    anomalies = daily_revenue_anomalies(conn)
    spikes = anomalies[anomalies["anomaly_type"] == "REVENUE_SPIKE"]
    drops = anomalies[anomalies["anomaly_type"] == "REVENUE_DROP"]

    total_revenue = conn.execute("SELECT SUM(revenue) FROM pos_transactions").fetchone()[0] or 0

    return {
        "total_anomaly_days": len(anomalies),
        "spike_days": len(spikes),
        "drop_days": len(drops),
        "stores_with_anomalies": anomalies["store_id"].nunique() if not anomalies.empty else 0,
        "avg_spike_revenue": round(spikes["daily_revenue"].mean(), 2) if not spikes.empty else 0,
        "avg_drop_revenue": round(drops["daily_revenue"].mean(), 2) if not drops.empty else 0,
        "total_revenue": round(total_revenue, 2),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.ingest.pos_generator import generate_pos_data, load_pos_to_duckdb

    conn = duckdb.connect()
    load_pos_to_duckdb(generate_pos_data(20000), conn)

    summary = revenue_anomaly_summary(conn)
    print("Revenue Anomaly Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    anomalies = daily_revenue_anomalies(conn)
    print(f"\nTop anomalies:\n{anomalies[['store_id', 'transaction_date', 'daily_revenue', 'z_score', 'anomaly_type']].head(10).to_string(index=False)}")