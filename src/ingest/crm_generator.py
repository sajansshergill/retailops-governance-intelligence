"""
Customer CRM synthetic data generator.
Produces customer records with purchase history, contact completeness,
RFM scores, and churn risk signals.
"""

import random
from datetime import datetime, timedelta

import duckdb
import pandas as pd
from faker import Faker

fake = Faker()

SEGMENTS = ["Champion", "Loyal", "Potential Loyalist", "At Risk", "Hibernating", "Lost"]
ACQUISITION_CHANNELS = ["Organic Search", "Paid Search", "Social Media", "Email", "Referral", "Direct", "Affiliate"]
TIERS = ["Bronze", "Silver", "Gold", "Platinum"]


def _rfm_score(recency_days: int, frequency: int, monetary: float) -> dict:
    """Compute simple RFM bucket scores (1–5 scale)."""
    r = 5 if recency_days <= 30 else 4 if recency_days <= 60 else 3 if recency_days <= 120 else 2 if recency_days <= 180 else 1
    f = 5 if frequency >= 20 else 4 if frequency >= 12 else 3 if frequency >= 6 else 2 if frequency >= 2 else 1
    m = 5 if monetary >= 2000 else 4 if monetary >= 1000 else 3 if monetary >= 500 else 2 if monetary >= 100 else 1
    return {"r_score": r, "f_score": f, "m_score": m, "rfm_total": r + f + m}


def generate_crm_data(n_customers: int = 20000, snapshot_date: str = "2024-12-31") -> pd.DataFrame:
    """
    Generate synthetic CRM customer records.

    Args:
        n_customers: Number of customer records to generate.
        snapshot_date: Reference date for recency calculation.

    Returns:
        DataFrame of CRM records.
    """
    snapshot = datetime.strptime(snapshot_date, "%Y-%m-%d")
    records = []

    for _ in range(n_customers):
        first_purchase = snapshot - timedelta(days=random.randint(30, 1825))
        last_purchase_days_ago = random.randint(1, 365)
        last_purchase = snapshot - timedelta(days=last_purchase_days_ago)
        frequency = random.randint(1, 40)
        avg_order_value = round(random.uniform(15.0, 500.0), 2)
        total_spent = round(avg_order_value * frequency, 2)

        rfm = _rfm_score(last_purchase_days_ago, frequency, total_spent)

        # Segment assignment based on RFM
        if rfm["rfm_total"] >= 13:
            segment = "Champion"
        elif rfm["rfm_total"] >= 10:
            segment = "Loyal"
        elif rfm["rfm_total"] >= 7:
            segment = "Potential Loyalist"
        elif rfm["rfm_total"] >= 5:
            segment = "At Risk"
        elif rfm["rfm_total"] >= 3:
            segment = "Hibernating"
        else:
            segment = "Lost"

        # Churn flag: at risk or worse + last purchase > 90 days
        churn_flag = 1 if segment in ["At Risk", "Hibernating", "Lost"] and last_purchase_days_ago > 90 else 0

        # Contact completeness — inject nulls realistically
        email = fake.email() if random.random() > 0.05 else None
        phone = fake.phone_number() if random.random() > 0.12 else None
        address = fake.address().replace("\n", ", ") if random.random() > 0.18 else None
        zip_code = fake.zipcode() if random.random() > 0.08 else None
        date_of_birth = fake.date_of_birth(minimum_age=18, maximum_age=80).strftime("%Y-%m-%d") if random.random() > 0.30 else None

        records.append({
            "customer_id": fake.uuid4(),
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": email,
            "phone": phone,
            "address": address,
            "city": fake.city() if random.random() > 0.10 else None,
            "state": fake.state(),
            "zip_code": zip_code,
            "date_of_birth": date_of_birth,
            "gender": random.choice(["M", "F", "Non-binary", "Prefer not to say"]) if random.random() > 0.15 else None,
            "acquisition_channel": random.choice(ACQUISITION_CHANNELS),
            "first_purchase_date": first_purchase.strftime("%Y-%m-%d"),
            "last_purchase_date": last_purchase.strftime("%Y-%m-%d"),
            "days_since_last_purchase": last_purchase_days_ago,
            "purchase_frequency": frequency,
            "avg_order_value": avg_order_value,
            "total_spent": total_spent,
            "r_score": rfm["r_score"],
            "f_score": rfm["f_score"],
            "m_score": rfm["m_score"],
            "rfm_total": rfm["rfm_total"],
            "segment": segment,
            "tier": random.choice(TIERS),
            "churn_flag": churn_flag,
            "email_opt_in": random.choice([True, False]),
            "sms_opt_in": random.choice([True, False]),
            "loyalty_points": random.randint(0, 5000),
        })

    df = pd.DataFrame(records)
    df["first_purchase_date"] = pd.to_datetime(df["first_purchase_date"])
    df["last_purchase_date"] = pd.to_datetime(df["last_purchase_date"])
    return df


def save_crm_data(df: pd.DataFrame, output_path: str = "data/crm_customers.parquet") -> None:
    """Persist CRM data to parquet."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"[CRM] Saved {len(df):,} records → {output_path}")


def load_crm_to_duckdb(df: pd.DataFrame, conn: duckdb.DuckDBPyConnection) -> None:
    """Register CRM DataFrame as a DuckDB table."""
    conn.register("crm_customers", df)
    conn.execute("CREATE TABLE IF NOT EXISTS crm_customers AS SELECT * FROM crm_customers")
    print(f"[CRM] Loaded {len(df):,} records into DuckDB table 'crm_customers'")


if __name__ == "__main__":
    print("Generating CRM data...")
    df = generate_crm_data(n_customers=20000)
    save_crm_data(df, output_path="data/crm_customers.parquet")
    print(df.head())
    print(f"\nShape: {df.shape}")
    print(f"\nSegment distribution:\n{df['segment'].value_counts()}")
    print(f"\nChurn rate: {df['churn_flag'].mean():.2%}")
    print(f"\nNull counts:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
