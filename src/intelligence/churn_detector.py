"""
Customer churn detector and retention targeting engine.
Identifies at-risk customers by RFM segment and recency thresholds,
computes revenue-at-risk from churn, and surfaces targeted retention cohorts.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def churn_risk_cohorts(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Return all churn-flagged customers with retention priority scoring.

    Returns:
        DataFrame of at-risk customers sorted by revenue_at_risk descending.
    """
    return conn.execute("""
        SELECT
            customer_id,
            segment,
            tier,
            days_since_last_purchase,
            purchase_frequency,
            avg_order_value,
            total_spent,
            rfm_total,
            r_score,
            f_score,
            m_score,
            churn_flag,
            email_opt_in,
            sms_opt_in,
            loyalty_points,
            -- Revenue at risk: estimated 12-month value if customer churns
            ROUND(avg_order_value * (purchase_frequency / NULLIF(
                DATEDIFF('day',
                    first_purchase_date::DATE,
                    last_purchase_date::DATE
                ) / 365.0, 0)
            ), 2) AS annual_revenue_estimate,
            -- Retention priority: high spenders with email opt-in are highest priority
            CASE
                WHEN total_spent >= 1000 AND email_opt_in = TRUE THEN 'P1_HIGH'
                WHEN total_spent >= 500 THEN 'P2_MEDIUM'
                WHEN email_opt_in = TRUE OR sms_opt_in = TRUE THEN 'P3_REACHABLE'
                ELSE 'P4_LOW'
            END AS retention_priority
        FROM crm_customers
        WHERE churn_flag = 1
        ORDER BY total_spent DESC
    """).df()


def churn_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """
    KPI summary for churn risk landscape.

    Returns:
        Dict with churn count, rate, revenue at risk, and reachability.
    """
    result = conn.execute("""
        SELECT
            COUNT(*) AS total_customers,
            SUM(churn_flag) AS churned_customers,
            ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct,
            ROUND(SUM(CASE WHEN churn_flag = 1 THEN total_spent ELSE 0 END), 2) AS revenue_at_risk,
            SUM(CASE WHEN churn_flag = 1 AND email_opt_in = TRUE THEN 1 ELSE 0 END) AS email_reachable,
            SUM(CASE WHEN churn_flag = 1 AND sms_opt_in = TRUE THEN 1 ELSE 0 END) AS sms_reachable
        FROM crm_customers
    """).fetchone()

    return {
        "total_customers": result[0],
        "churned_customers": result[1],
        "churn_rate_pct": result[2],
        "revenue_at_risk": result[3],
        "email_reachable": result[4],
        "sms_reachable": result[5],
    }


def churn_by_segment(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Aggregate churn metrics by RFM segment for heatmap visualization."""
    return conn.execute("""
        SELECT
            segment,
            COUNT(*) AS total_in_segment,
            SUM(churn_flag) AS churned,
            ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct,
            ROUND(AVG(total_spent), 2) AS avg_total_spent,
            ROUND(AVG(days_since_last_purchase), 1) AS avg_days_since_purchase
        FROM crm_customers
        GROUP BY segment
        ORDER BY churn_rate_pct DESC
    """).df()


def crm_completeness_by_segment(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    CRM field completeness rates broken down by customer segment.
    Used to identify data gaps that prevent effective outreach.
    """
    return conn.execute("""
        SELECT
            segment,
            COUNT(*) AS customer_count,
            ROUND(AVG(CASE WHEN email IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 1) AS email_completeness,
            ROUND(AVG(CASE WHEN phone IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 1) AS phone_completeness,
            ROUND(AVG(CASE WHEN address IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 1) AS address_completeness,
            ROUND(AVG(CASE WHEN zip_code IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 1) AS zip_completeness,
            ROUND(AVG(CASE WHEN date_of_birth IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 1) AS dob_completeness,
            -- Overall contact score: can we reach this customer at all?
            ROUND(AVG(CASE WHEN email IS NOT NULL OR phone IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 1) AS reachability_pct
        FROM crm_customers
        GROUP BY segment
        ORDER BY reachability_pct ASC
    """).df()


def retention_campaign_targets(
    conn: duckdb.DuckDBPyConnection,
    priority: str = "P1_HIGH",
    channel: str = "email",
) -> pd.DataFrame:
    """
    Pull a targeted customer list for a retention campaign.

    Args:
        conn: Active DuckDB connection.
        priority: Retention priority tier (P1_HIGH, P2_MEDIUM, P3_REACHABLE, P4_LOW).
        channel: Outreach channel filter ('email' or 'sms').

    Returns:
        DataFrame of targetable customers with contact info fields.
    """
    channel_filter = "email_opt_in = TRUE" if channel == "email" else "sms_opt_in = TRUE"

    return conn.execute(f"""
        SELECT
            customer_id,
            segment,
            tier,
            days_since_last_purchase,
            total_spent,
            avg_order_value,
            loyalty_points,
            email_opt_in,
            sms_opt_in,
            CASE
                WHEN total_spent >= 1000 AND {channel_filter} THEN 'P1_HIGH'
                WHEN total_spent >= 500 THEN 'P2_MEDIUM'
                WHEN {channel_filter} THEN 'P3_REACHABLE'
                ELSE 'P4_LOW'
            END AS retention_priority
        FROM crm_customers
        WHERE churn_flag = 1
          AND {channel_filter}
        HAVING retention_priority = '{priority}'
        ORDER BY total_spent DESC
    """).df()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.ingest.crm_generator import generate_crm_data, load_crm_to_duckdb

    conn = duckdb.connect()
    load_crm_to_duckdb(generate_crm_data(5000), conn)

    summary = churn_summary(conn)
    print("Churn Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    print(f"\nChurn by Segment:")
    print(churn_by_segment(conn).to_string(index=False))

    print(f"\nCRM Completeness by Segment:")
    print(crm_completeness_by_segment(conn).to_string(index=False))