"""
POS / Sales synthetic data generator.
Produces realistic transaction-level retail sales data across stores and SKUs.
"""

import random
from datetime import datetime, timedelta

import duckdb
import pandas as pd
from faker import Faker

fake = Faker()

STORES = [f"STORE_{str(i).zfill(3)}" for i in range(1, 51)]
SKUS = [f"SKU_{str(i).zfill(5)}" for i in range(1, 501)]
CATEGORIES = ["Electronics", "Apparel", "Home & Garden", "Grocery", "Sports", "Beauty", "Toys"]
PAYMENT_METHODS = ["Credit Card", "Debit Card", "Cash", "Mobile Pay", "Gift Card"]


def generate_pos_data(n_records: int = 50000, start_date: str = "2024-01-01", end_date: str = "2024-12-31") -> pd.DataFrame:
    """
    Generate synthetic POS transaction records.

    Args:
        n_records: Number of transactions to generate.
        start_date: Start date for transaction range (YYYY-MM-DD).
        end_date: End date for transaction range (YYYY-MM-DD).

    Returns:
        DataFrame of POS transactions.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    date_range = (end - start).days

    records = []
    for _ in range(n_records):
        sku = random.choice(SKUS)
        category = random.choice(CATEGORIES)
        unit_price = round(random.uniform(2.99, 499.99), 2)
        quantity = random.randint(1, 10)
        discount_pct = random.choice([0, 0, 0, 5, 10, 15, 20, 25])
        discount_amount = round(unit_price * quantity * discount_pct / 100, 2)
        revenue = round(unit_price * quantity - discount_amount, 2)

        # Inject ~2% nulls in non-critical fields to simulate real-world dirtiness
        store_id = random.choice(STORES) if random.random() > 0.01 else None
        payment_method = random.choice(PAYMENT_METHODS) if random.random() > 0.02 else None

        records.append({
            "transaction_id": fake.uuid4(),
            "transaction_date": (start + timedelta(days=random.randint(0, date_range))).strftime("%Y-%m-%d"),
            "transaction_time": fake.time(),
            "store_id": store_id,
            "sku": sku,
            "category": category,
            "unit_price": unit_price,
            "quantity": quantity,
            "discount_pct": discount_pct,
            "discount_amount": discount_amount,
            "revenue": revenue,
            "payment_method": payment_method,
            "cashier_id": fake.numerify("EMP####"),
            "region": fake.state(),
        })

    df = pd.DataFrame(records)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def save_pos_data(df: pd.DataFrame, output_path: str = "data/pos_transactions.parquet") -> None:
    """Persist POS data to parquet."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"[POS] Saved {len(df):,} records → {output_path}")


def load_pos_to_duckdb(df: pd.DataFrame, conn: duckdb.DuckDBPyConnection) -> None:
    """Register POS DataFrame as a DuckDB table."""
    conn.register("pos_transactions", df)
    conn.execute("CREATE TABLE IF NOT EXISTS pos_transactions AS SELECT * FROM pos_transactions")
    print(f"[POS] Loaded {len(df):,} records into DuckDB table 'pos_transactions'")


if __name__ == "__main__":
    print("Generating POS data...")
    df = generate_pos_data(n_records=50000)
    save_pos_data(df, output_path="data/pos_transactions.parquet")
    print(df.head())
    print(f"\nShape: {df.shape}")
    print(f"Date range: {df['transaction_date'].min()} → {df['transaction_date'].max()}")
    print(f"Null counts:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
