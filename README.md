# RetailOps Data Governance & Intelligence Platform

A production-grade data governance and business intelligence platform for mid-size retail operations —— enforcing data quality, cataloging cross-functional data assets, and surfacing actionable intelligence across Sales, Inventory, and Customer CRM to drive measurable business outcomes.

## Business Problem
Mid-size retail chains (50-200 stores) typically opearte across three disconnectes systems —— Point-of-Sale, Inventory Management, and Customer CRM —— with no unified view of data quality, ownership, or lineage. The result:
- **Overstock and stockout losses** from untruets inventory signals
- **Missed churn** because CRM completeness is never measured
- **Leadership decisions made on bad data** with no audit trail
- **Analyst bottlenecks** from manual reporting across siloed sources

This platfrom eliminates those gaps by governing the data before it reaches decisions.

## Business Value Delivered
<img width="1298" height="974" alt="image" src="https://github.com/user-attachments/assets/f371fadb-6485-4eb1-9f55-c299b0cedb9e" />

## Platform Architecture
<img width="626" height="1314" alt="image" src="https://github.com/user-attachments/assets/63ed3de3-8341-4911-ac7e-2accb5b1aad6" />

## Data Sources
All data is synthetic, generated via Faker and modeled to reflect realistic retail operations.
<img width="1278" height="440" alt="image" src="https://github.com/user-attachments/assets/f99b0b75-d2cc-4f14-beea-e167609cd14c" />

## Tech Stack
<img width="1278" height="1102" alt="image" src="https://github.com/user-attachments/assets/2931ffb6-752c-4644-a161-8a4afeff3278" />

## Repository Structure
<img width="728" height="1442" alt="image" src="https://github.com/user-attachments/assets/b9df5421-501d-451b-8ae6-608c4cc7e5b0" />
<img width="732" height="936" alt="image" src="https://github.com/user-attachments/assets/b9b0e61b-cef2-4e87-8826-2f7f4e6dd4d5" />

## Dashboard Views
**1. Data Health Scorecard**
Per-source quality score (0-100) across completeness, consistency, validity, and uniqueness dimensions. Trend cahrt across pipeline runs tracked via MLflow.

**2. Metadata Catalog**
Browsable, filterable registry of all data assets —— column name, data type, PII flag, business owner, last updated, quality score. Exportable to .xslx.

**3. Lineage Map**
Visual graph of source -> transform -> report lineage per dataset. Shows which reports depend on which source tables and which transformations apply.

**4. Business Intelligence Panel**
**- Stickout Risk Table ——** SKUs flagged as at-risk by store location
**- CRM Completeness Heatmap ——** missing fields by customer segment
**- Revenue Anomaly Flags ——** stores or SKUs with statistically significant deviation

**5. Governance Issue Tracker**
Open violations log: rule name, dataset, severity, assigned owner, resolution status, and SLA countdown. Mirrors a lightweight project management view for data stewards.

**6. Export Center**
One-click generation of:
- .docx —— Business requirement document with data interface specs
- .xslx —— Full metadata catalog with quality scorecard
- .pptx —— Executive summary deck (KPIs, data health score, top recommendations)

## Key Business Metrics Produced
<img width="1316" height="732" alt="image" src="https://github.com/user-attachments/assets/fe7ad8e3-6b3a-4223-b44d-baece3c3adba" />

## Getting Started
**Prerequisites**
bashPython 3.10+
Docker (optional)

**Installation**
bashgit clone https://github.com/sajansshergill/retailops-governance-platform.git
cd retailops-governance-platform
pip install -r requirements.txt

**Generate Synthetic Data**
bashpython src/ingest/pos_generator.py
python src/ingest/inventory_generator.py
python src/ingest/crm_generator.py

**Run Profiling & Governance Pipeline**
bashpython src/profiling/column_profiler.py
python src/governance/rules_engine.py
python src/intelligence/stockout_risk.py
python src/intelligence/churn_detector.py

**Launch Dashboard**
bashstreamlit run src/dashboard/app.py

**Run with Docker**
bashdocker-compose up --build

**Run Tests**
bashpytest tests/ -v

## MLflow Tracking
Each pipeline run is logged to MLflow with:
- Data quality scores per source
- Governance rule violation counts
- Stockout and churn flag counts
- Run timestamp and data snapshot hash

mlflow ui
#### Open http://localhost:5000

## Sample Outputs
<img width="1258" height="388" alt="image" src="https://github.com/user-attachments/assets/9cf14156-ee52-4300-a3d0-60389982cf8f" />

## Roadmap
- Airflow DAG for scheduled pipeline orchestration
- dbt integration for SQL transformation layer
- Slack alerting on governance violations above threshold
- Role-based access control in Streamlit (admin vs viewer)
- Historical trend analysis across 6-month data snapshots
