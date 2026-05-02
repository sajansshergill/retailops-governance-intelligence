"""
Stockout risk scoring engine.
Computes days-to-stockout, reorder urgency, and financial exposure
per SKU per store. Surfaces top at-risk items for operations teams.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def compute_stockout_risk_table(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Full stockout risk table with urgency tiering and financial exposure estimate.

    Returns:
        DataFrame sorted by days_to_stockout ascending (most urgent first).
    """
    query = """
        SELECT
            sku,
            store_id,
            stock_level,
            reorder_point,
            daily_velocity,
            days_to_stockout,
            lead_time_days,
            stockout_risk,
            shrinkage_rate,
            unit_cost,
            -- Financial exposure: value of stock at risk of being lost to stockout
            ROUND(stock_level * unit_cost, 2) AS stock_value,
            -- Reorder breach flag: will we run out before supplier delivers?
            CASE
                WHEN days_to_stockout <= lead_time_days THEN TRUE
                ELSE FALSE
            END AS reorder_breach,
            -- Urgency score 0–100 (lower days_to_stockout = higher urgency)
            CASE
                WHEN days_to_stockout <= 0 THEN 100
                WHEN days_to_stockout <= lead_time_days THEN
                    ROUND(100 - (days_to_stockout / NULLIF(lead_time_days, 0)) * 30, 1)
                WHEN days_to_stockout <= reorder_point THEN
                    ROUND(60 - (days_to_stockout / NULLIF(reorder_point, 0)) * 20, 1)
                ELSE ROUND(GREATEST(0, 40 - days_to_stockout / 10.0), 1)
            END AS urgency_score,
            supplier,
            last_replenished
        FROM inventory
        WHERE stockout_risk IN ('HIGH', 'MEDIUM')
        ORDER BY urgency_score DESC, days_to_stockout ASC
    """
    return conn.execute(query).df()


def top_stockout_skus(conn: duckdb.DuckDBPyConnection, top_n: int = 20) -> pd.DataFrame:
    """
    Top N SKUs at highest combined stockout risk across all stores.

    Args:
        conn: Active DuckDB connection.
        top_n: Number of SKUs to return.

    Returns:
        Aggregated DataFrame at SKU level with risk exposure metrics.
    """
    query = f"""
        SELECT
            sku,
            COUNT(DISTINCT store_id) AS stores_at_risk,
            AVG(days_to_stockout) AS avg_days_to_stockout,
            MIN(days_to_stockout) AS min_days_to_stockout,
            SUM(stock_value) AS total_stock_value_at_risk,
            SUM(CASE WHEN reorder_breach THEN 1 ELSE 0 END) AS reorder_breach_count,
            AVG(urgency_score) AS avg_urgency_score
        FROM (
            SELECT
                sku,
                store_id,
                days_to_stockout,
                lead_time_days,
                unit_cost,
                stock_level,
                ROUND(stock_level * unit_cost, 2) AS stock_value,
                CASE WHEN days_to_stockout <= lead_time_days THEN TRUE ELSE FALSE END AS reorder_breach,
                CASE
                    WHEN days_to_stockout <= 0 THEN 100
                    WHEN days_to_stockout <= lead_time_days THEN
                        ROUND(100 - (days_to_stockout / NULLIF(lead_time_days, 0)) * 30, 1)
                    ELSE ROUND(GREATEST(0, 40 - days_to_stockout / 10.0), 1)
                END AS urgency_score
            FROM inventory
            WHERE stockout_risk IN ('HIGH', 'MEDIUM')
        ) t
        GROUP BY sku
        ORDER BY avg_urgency_score DESC, min_days_to_stockout ASC
        LIMIT {top_n}
    """
    return conn.execute(query).df()


def stockout_risk_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """
    High-level KPI summary for the stockout risk landscape.

    Returns:
        Dict with total at-risk items, breach count, and financial exposure.
    """
    result = conn.execute("""
        SELECT
            COUNT(*) AS total_at_risk_records,
            COUNT(DISTINCT sku) AS unique_skus_at_risk,
            COUNT(DISTINCT store_id) AS stores_affected,
            SUM(CASE WHEN days_to_stockout <= lead_time_days THEN 1 ELSE 0 END) AS reorder_breach_count,
            ROUND(SUM(stock_level * unit_cost), 2) AS total_stock_value_at_risk,
            ROUND(AVG(days_to_stockout), 1) AS avg_days_to_stockout
        FROM inventory
        WHERE stockout_risk IN ('HIGH', 'MEDIUM')
    """).fetchone()

    return {
        "total_at_risk_records": result[0],
        "unique_skus_at_risk": result[1],
        "stores_affected": result[2],
        "reorder_breach_count": result[3],
        "total_stock_value_at_risk": result[4],
        "avg_days_to_stockout": result[5],
    }


def stockout_by_store(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Aggregate stockout risk by store for heatmap visualization."""
    return conn.execute("""
        SELECT
            store_id,
            COUNT(*) AS at_risk_skus,
            SUM(CASE WHEN stockout_risk = 'HIGH' THEN 1 ELSE 0 END) AS high_risk_skus,
            ROUND(AVG(days_to_stockout), 1) AS avg_days_to_stockout,
            ROUND(SUM(stock_level * unit_cost), 2) AS total_value_at_risk
        FROM inventory
        WHERE stockout_risk IN ('HIGH', 'MEDIUM')
        GROUP BY store_id
        ORDER BY high_risk_skus DESC
    """).df()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.ingest.inventory_generator import generate_inventory_data, load_inventory_to_duckdb

    conn = duckdb.connect()
    load_inventory_to_duckdb(generate_inventory_data(), conn)

    summary = stockout_risk_summary(conn)
    print("Stockout Risk Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    top = top_stockout_skus(conn, top_n=10)
    print(f"\nTop 10 at-risk SKUs:\n{top.to_string(index=False)}")