"""
Inventory synthetic data generator.
Produces SKU-level stock records with reorder points, supplier lead times,
shrinkage rates, and stockout risk signals.
"""

import random
from datetime import datetime, timedelta

import duckdb
import pandas as pd
from faker import Faker

fake = Faker()

SKUS = [f"SKU_{str(i).zfill(5)}" for i in range(1, 501)]
STORES = [f"STORE_{str(i).zfill(3)}" for i in range(1, 51)]
SUPPLIERS = [fake.company() for _ in range(30)]
WAREHOUSES = [f"WH_{str(i).zfill(2)}" for i in range(1, 11)]


def generate_inventory_data(snapshot_date: str = "2024-12-31") -> pd.DataFrame:
    """
    Generate synthetic inventory snapshot — one record per SKU per store.

    Args:
        snapshot_date: Date of inventory snapshot.

    Returns:
        DataFrame of inventory records.
    """
    snapshot = datetime.strptime(snapshot_date, "%Y-%m-%d")
    records = []

    for sku in SKUS:
        for store_id in random.sample(STORES, k=random.randint(10, 50)):
            reorder_point = random.randint(10, 100)
            stock_level = random.randint(0, 300)
            daily_velocity = round(random.uniform(0.5, 20.0), 2)
            lead_time_days = random.randint(1, 21)
            shrinkage_rate = round(random.uniform(0.0, 0.05), 4)

            # Business logic: days-to-stockout
            if daily_velocity > 0:
                days_to_stockout = round(stock_level / daily_velocity, 1)
            else:
                days_to_stockout = 999.0

            # Stockout risk flag
            if stock_level <= reorder_point:
                stockout_risk = "HIGH"
            elif stock_level <= reorder_point * 1.5:
                stockout_risk = "MEDIUM"
            else:
                stockout_risk = "LOW"

            # Inject ~3% nulls in supplier and warehouse fields
            supplier = random.choice(SUPPLIERS) if random.random() > 0.03 else None
            warehouse_id = random.choice(WAREHOUSES) if random.random() > 0.03 else None
            last_replenished = (
                (snapshot - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
                if random.random() > 0.05 else None
            )

            records.append({
                "inventory_id": fake.uuid4(),
                "snapshot_date": snapshot_date,
                "sku": sku,
                "store_id": store_id,
                "warehouse_id": warehouse_id,
                "supplier": supplier,
                "stock_level": stock_level,
                "reorder_point": reorder_point,
                "daily_velocity": daily_velocity,
                "days_to_stockout": days_to_stockout,
                "stockout_risk": stockout_risk,
                "lead_time_days": lead_time_days,
                "shrinkage_rate": shrinkage_rate,
                "unit_cost": round(random.uniform(1.50, 250.00), 2),
                "last_replenished": last_replenished,
            })

    df = pd.DataFrame(records)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    return df


def save_inventory_data(df: pd.DataFrame, output_path: str = "data/inventory.parquet") -> None:
    """Persist inventory data to parquet."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"[Inventory] Saved {len(df):,} records → {output_path}")


def load_inventory_to_duckdb(df: pd.DataFrame, conn: duckdb.DuckDBPyConnection) -> None:
    """Register inventory DataFrame as a DuckDB table."""
    conn.register("inventory", df)
    conn.execute("CREATE TABLE IF NOT EXISTS inventory AS SELECT * FROM inventory")
    print(f"[Inventory] Loaded {len(df):,} records into DuckDB table 'inventory'")


if __name__ == "__main__":
    print("Generating Inventory data...")
    df = generate_inventory_data()
    save_inventory_data(df, output_path="data/inventory.parquet")
    print(df.head())
    print(f"\nShape: {df.shape}")
    print(f"\nStockout risk distribution:\n{df['stockout_risk'].value_counts()}")
    print(f"\nNull counts:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
