"""
Metadata extractor and asset catalog builder.
Extracts column-level metadata from DuckDB tables and enriches it with
PII tags, ownership, classification, and business descriptions.
Produces the browsable metadata catalog used in the Streamlit dashboard.
"""

from __future__ import annotations

from datetime import datetime

import duckdb
import pandas as pd

from src.governance.rules_engine import (
    PIIType,
    TABLE_CLASSIFICATION,
    TABLE_OWNERS,
    tag_pii,
)

# Human-readable business descriptions for known columns
COLUMN_DESCRIPTIONS = {
    # POS
    "transaction_id": "Unique identifier for each POS transaction.",
    "transaction_date": "Date the transaction occurred.",
    "transaction_time": "Time of day the transaction occurred.",
    "store_id": "Unique identifier for the retail store location.",
    "sku": "Stock Keeping Unit — unique product identifier.",
    "category": "Product category (e.g., Electronics, Apparel).",
    "unit_price": "Listed selling price per unit before discounts.",
    "quantity": "Number of units sold in the transaction.",
    "discount_pct": "Discount percentage applied to the transaction.",
    "discount_amount": "Total dollar value of the discount applied.",
    "revenue": "Net revenue after discounts (unit_price × quantity − discount_amount).",
    "payment_method": "Payment method used (Credit Card, Cash, etc.).",
    "cashier_id": "Employee ID of the cashier who processed the transaction.",
    "region": "Geographic region of the store.",
    # Inventory
    "inventory_id": "Unique identifier for each inventory record.",
    "snapshot_date": "Date of the inventory snapshot.",
    "warehouse_id": "Identifier of the fulfillment warehouse.",
    "supplier": "Name of the product supplier.",
    "stock_level": "Current on-hand stock quantity.",
    "reorder_point": "Minimum stock level triggering a reorder.",
    "daily_velocity": "Average units sold per day.",
    "days_to_stockout": "Estimated days until stock reaches zero at current velocity.",
    "stockout_risk": "Risk classification: HIGH / MEDIUM / LOW.",
    "lead_time_days": "Supplier lead time in days for replenishment.",
    "shrinkage_rate": "Rate of inventory loss due to theft, damage, or error.",
    "unit_cost": "Cost per unit paid to the supplier.",
    "last_replenished": "Date of the most recent inventory replenishment.",
    # CRM
    "customer_id": "Unique identifier for the customer.",
    "first_name": "Customer's first name (PII).",
    "last_name": "Customer's last name (PII).",
    "email": "Customer's email address (PII).",
    "phone": "Customer's phone number (PII).",
    "address": "Customer's street address (PII).",
    "city": "Customer's city of residence.",
    "state": "Customer's state of residence.",
    "zip_code": "Customer's ZIP code (PII).",
    "date_of_birth": "Customer's date of birth (PII).",
    "gender": "Customer's self-identified gender.",
    "acquisition_channel": "Marketing channel through which customer was acquired.",
    "first_purchase_date": "Date of the customer's first purchase.",
    "last_purchase_date": "Date of the customer's most recent purchase.",
    "days_since_last_purchase": "Number of days since last purchase (recency).",
    "purchase_frequency": "Total number of purchases made.",
    "avg_order_value": "Average spend per order.",
    "total_spent": "Cumulative lifetime spend.",
    "r_score": "RFM Recency score (1–5, higher = more recent).",
    "f_score": "RFM Frequency score (1–5, higher = more frequent).",
    "m_score": "RFM Monetary score (1–5, higher = higher spend).",
    "rfm_total": "Combined RFM score (3–15).",
    "segment": "Customer segment based on RFM (e.g., Champion, At Risk).",
    "tier": "Loyalty tier (Bronze / Silver / Gold / Platinum).",
    "churn_flag": "1 if customer is flagged as at-risk of churning, else 0.",
    "email_opt_in": "Whether customer has opted into email marketing.",
    "sms_opt_in": "Whether customer has opted into SMS marketing.",
    "loyalty_points": "Current loyalty points balance.",
}


def extract_metadata(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> pd.DataFrame:
    """
    Extract column-level metadata from a DuckDB table.

    Args:
        conn: Active DuckDB connection.
        table_name: Table to catalog.

    Returns:
        DataFrame with one row per column containing full metadata.
    """
    schema_df = conn.execute(f"DESCRIBE {table_name}").df()
    total_rows = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    owner = TABLE_OWNERS.get(table_name, "data_governance_team")
    classification = TABLE_CLASSIFICATION.get(table_name, "INTERNAL")

    records = []
    for _, row in schema_df.iterrows():
        col = row["column_name"]
        dtype = row["column_type"]
        nullable = row.get("null", "YES")

        null_count = conn.execute(
            f'SELECT COUNT(*) FROM {table_name} WHERE "{col}" IS NULL'
        ).fetchone()[0]
        null_rate = round(null_count / total_rows, 4) if total_rows > 0 else 0.0
        completeness = round(1.0 - null_rate, 4)

        unique_count = conn.execute(
            f'SELECT COUNT(DISTINCT "{col}") FROM {table_name}'
        ).fetchone()[0]

        pii_type = tag_pii(col)

        records.append({
            "asset_id": f"{table_name}.{col}",
            "table_name": table_name,
            "column_name": col,
            "data_type": dtype,
            "nullable": nullable,
            "total_rows": total_rows,
            "null_count": null_count,
            "null_rate": null_rate,
            "completeness": completeness,
            "unique_count": unique_count,
            "pii_type": pii_type.value,
            "is_pii": pii_type != PIIType.NONE,
            "classification": classification,
            "owner": owner,
            "business_description": COLUMN_DESCRIPTIONS.get(col, "No description available."),
            "last_profiled": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    return pd.DataFrame(records)


def build_full_catalog(
    conn: duckdb.DuckDBPyConnection,
    tables: list[str] | None = None,
) -> pd.DataFrame:
    """
    Build the complete metadata catalog across all registered tables.

    Args:
        conn: Active DuckDB connection.
        tables: Tables to catalog. Defaults to the three core tables.

    Returns:
        Combined metadata catalog DataFrame.
    """
    if tables is None:
        tables = ["pos_transactions", "inventory", "crm_customers"]

    frames = []
    for table in tables:
        print(f"[Catalog] Extracting metadata: {table}")
        df = extract_metadata(conn, table)
        frames.append(df)
        print(f"  → {len(df)} columns cataloged")

    catalog = pd.concat(frames, ignore_index=True)
    print(f"[Catalog] Total catalog entries: {len(catalog)}")
    return catalog


def catalog_summary(catalog_df: pd.DataFrame) -> dict:
    """
    Return high-level summary statistics from the metadata catalog.

    Args:
        catalog_df: Output of build_full_catalog().

    Returns:
        Dict of summary metrics.
    """
    confidential_tables = catalog_df.loc[
        catalog_df["classification"] == "CONFIDENTIAL", "table_name"
    ].nunique()

    return {
        "total_assets": len(catalog_df),
        "tables": catalog_df["table_name"].nunique(),
        "pii_columns": int(catalog_df["is_pii"].sum()),
        "avg_completeness": round(catalog_df["completeness"].mean() * 100, 2),
        "columns_with_nulls": int((catalog_df["null_count"] > 0).sum()),
        "confidential_tables": int(confidential_tables),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.ingest.pos_generator import generate_pos_data, load_pos_to_duckdb
    from src.ingest.inventory_generator import generate_inventory_data, load_inventory_to_duckdb
    from src.ingest.crm_generator import generate_crm_data, load_crm_to_duckdb

    conn = duckdb.connect()
    load_pos_to_duckdb(generate_pos_data(2000), conn)
    load_inventory_to_duckdb(generate_inventory_data(), conn)
    load_crm_to_duckdb(generate_crm_data(1000), conn)

    catalog = build_full_catalog(conn)
    print("\nSample catalog entries:")
    print(catalog[["table_name", "column_name", "data_type", "completeness", "pii_type", "owner"]].to_string())

    summary = catalog_summary(catalog)
    print(f"\nCatalog Summary: {summary}")