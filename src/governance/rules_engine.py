"""
Governance rules engine.
Enforces naming standards, PII tagging, ownership assignment, and
data classification across all registered data assets.
Produces a governance issue log with severity, owner, and SLA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import pandas as pd


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class PIIType(str, Enum):
    NAME = "NAME"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    FINANCIAL = "FINANCIAL"
    ID = "ID"
    NONE = "NONE"


# SLA in days by severity
SLA_DAYS = {
    Severity.CRITICAL: 1,
    Severity.HIGH: 3,
    Severity.MEDIUM: 7,
    Severity.LOW: 14,
    Severity.INFO: 30,
}

# Column name → PII type mapping
PII_PATTERNS = {
    PIIType.EMAIL: re.compile(r"email", re.I),
    PIIType.PHONE: re.compile(r"phone|mobile|cell", re.I),
    PIIType.NAME: re.compile(r"^(first|last|full|customer)_?name$", re.I),
    PIIType.ADDRESS: re.compile(r"address|street|zip|postal", re.I),
    PIIType.DATE_OF_BIRTH: re.compile(r"dob|date_of_birth|birth_date", re.I),
    PIIType.FINANCIAL: re.compile(r"revenue|spent|payment|credit|card|bank|account", re.I),
    PIIType.ID: re.compile(r"customer_id|ssn|national_id|passport", re.I),
}

# Naming convention: snake_case, no reserved words, length 2–64
NAMING_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
RESERVED_WORDS = {"select", "from", "where", "table", "index", "order", "group", "join", "null"}

# Table → default owner
TABLE_OWNERS = {
    "pos_transactions": "sales_ops_team",
    "inventory": "supply_chain_team",
    "crm_customers": "marketing_data_team",
}

# Table → data classification
TABLE_CLASSIFICATION = {
    "pos_transactions": "INTERNAL",
    "inventory": "INTERNAL",
    "crm_customers": "CONFIDENTIAL",
}


@dataclass
class GovernanceIssue:
    issue_id: str
    source_table: str
    column_name: str | None
    rule_name: str
    description: str
    severity: Severity
    owner: str
    status: str = "OPEN"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sla_due: str = field(default="")
    resolved_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.sla_due:
            due = datetime.now() + timedelta(days=SLA_DAYS[self.severity])
            self.sla_due = due.strftime("%Y-%m-%d")


def tag_pii(column_name: str) -> PIIType:
    """Identify PII type for a given column name."""
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(column_name):
            return pii_type
    return PIIType.NONE


def check_naming_standards(table_name: str, columns: list[str]) -> list[GovernanceIssue]:
    """
    Enforce snake_case naming, length constraints, and reserved word avoidance.

    Args:
        table_name: Table being checked.
        columns: List of column names.

    Returns:
        List of GovernanceIssue objects for violations.
    """
    issues = []
    owner = TABLE_OWNERS.get(table_name, "data_governance_team")

    # Check table name
    if not NAMING_PATTERN.match(table_name):
        issues.append(GovernanceIssue(
            issue_id=f"NAMING_{table_name}_TABLE",
            source_table=table_name,
            column_name=None,
            rule_name="TABLE_NAMING_STANDARD",
            description=f"Table name '{table_name}' violates snake_case naming convention.",
            severity=Severity.MEDIUM,
            owner=owner,
        ))

    for col in columns:
        if not NAMING_PATTERN.match(col):
            issues.append(GovernanceIssue(
                issue_id=f"NAMING_{table_name}_{col}",
                source_table=table_name,
                column_name=col,
                rule_name="COLUMN_NAMING_STANDARD",
                description=f"Column '{col}' in '{table_name}' violates snake_case naming convention.",
                severity=Severity.LOW,
                owner=owner,
            ))
        if col.lower() in RESERVED_WORDS:
            issues.append(GovernanceIssue(
                issue_id=f"RESERVED_{table_name}_{col}",
                source_table=table_name,
                column_name=col,
                rule_name="RESERVED_WORD_COLLISION",
                description=f"Column '{col}' is a SQL reserved word.",
                severity=Severity.HIGH,
                owner=owner,
            ))

    return issues


def check_pii_exposure(table_name: str, columns: list[str]) -> list[GovernanceIssue]:
    """
    Flag columns containing PII in tables not classified as CONFIDENTIAL.

    Args:
        table_name: Table being checked.
        columns: List of column names.

    Returns:
        List of GovernanceIssue objects for PII exposure violations.
    """
    issues = []
    classification = TABLE_CLASSIFICATION.get(table_name, "INTERNAL")
    owner = TABLE_OWNERS.get(table_name, "data_governance_team")

    for col in columns:
        pii_type = tag_pii(col)
        if pii_type != PIIType.NONE:
            if classification != "CONFIDENTIAL":
                issues.append(GovernanceIssue(
                    issue_id=f"PII_{table_name}_{col}",
                    source_table=table_name,
                    column_name=col,
                    rule_name="PII_EXPOSURE_RISK",
                    description=(
                        f"Column '{col}' contains {pii_type.value} PII but table "
                        f"'{table_name}' is classified as {classification}, not CONFIDENTIAL."
                    ),
                    severity=Severity.HIGH,
                    owner=owner,
                    metadata={"pii_type": pii_type.value, "classification": classification},
                ))

    return issues


def check_ownership_assignment(table_name: str) -> list[GovernanceIssue]:
    """Flag tables with no registered owner."""
    issues = []
    if table_name not in TABLE_OWNERS:
        issues.append(GovernanceIssue(
            issue_id=f"OWNERSHIP_{table_name}",
            source_table=table_name,
            column_name=None,
            rule_name="MISSING_OWNER",
            description=f"Table '{table_name}' has no registered data owner.",
            severity=Severity.HIGH,
            owner="data_governance_team",
        ))
    return issues


def check_quality_threshold(
    table_name: str, composite_score: float, threshold: float = 85.0
) -> list[GovernanceIssue]:
    """Flag tables falling below quality score threshold."""
    issues = []
    if composite_score < threshold:
        severity = Severity.CRITICAL if composite_score < 70 else Severity.HIGH
        issues.append(GovernanceIssue(
            issue_id=f"QUALITY_{table_name}",
            source_table=table_name,
            column_name=None,
            rule_name="QUALITY_THRESHOLD_BREACH",
            description=(
                f"Table '{table_name}' composite quality score is {composite_score}/100, "
                f"below threshold of {threshold}/100."
            ),
            severity=severity,
            owner=TABLE_OWNERS.get(table_name, "data_governance_team"),
            metadata={"score": composite_score, "threshold": threshold},
        ))
    return issues


def run_governance_checks(
    tables: dict[str, list[str]],
    quality_scores: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Run all governance checks across all tables.

    Args:
        tables: Dict of {table_name: [column_names]}.
        quality_scores: Optional dict of {table_name: composite_score}.

    Returns:
        DataFrame of all governance issues.
    """
    all_issues: list[GovernanceIssue] = []

    for table_name, columns in tables.items():
        print(f"[Governance] Checking: {table_name}")
        all_issues.extend(check_naming_standards(table_name, columns))
        all_issues.extend(check_pii_exposure(table_name, columns))
        all_issues.extend(check_ownership_assignment(table_name))

        if quality_scores and table_name in quality_scores:
            all_issues.extend(
                check_quality_threshold(table_name, quality_scores[table_name])
            )

    print(f"[Governance] Total issues found: {len(all_issues)}")

    return pd.DataFrame([{
        "issue_id": i.issue_id,
        "source_table": i.source_table,
        "column_name": i.column_name,
        "rule_name": i.rule_name,
        "description": i.description,
        "severity": i.severity.value,
        "owner": i.owner,
        "status": i.status,
        "created_at": i.created_at,
        "sla_due": i.sla_due,
        "resolved_at": i.resolved_at,
    } for i in all_issues])


def build_pii_catalog(tables: dict[str, list[str]]) -> pd.DataFrame:
    """
    Build a PII catalog — all PII-tagged columns across all tables.

    Args:
        tables: Dict of {table_name: [column_names]}.

    Returns:
        DataFrame of PII-tagged columns with type and classification.
    """
    rows = []
    for table_name, columns in tables.items():
        classification = TABLE_CLASSIFICATION.get(table_name, "INTERNAL")
        owner = TABLE_OWNERS.get(table_name, "data_governance_team")
        for col in columns:
            pii_type = tag_pii(col)
            if pii_type != PIIType.NONE:
                rows.append({
                    "table": table_name,
                    "column": col,
                    "pii_type": pii_type.value,
                    "classification": classification,
                    "owner": owner,
                    "masked": False,  # future: hook into masking layer
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sample_tables = {
        "pos_transactions": [
            "transaction_id", "transaction_date", "transaction_time", "store_id",
            "sku", "category", "unit_price", "quantity", "discount_pct",
            "discount_amount", "revenue", "payment_method", "cashier_id", "region"
        ],
        "inventory": [
            "inventory_id", "snapshot_date", "sku", "store_id", "warehouse_id",
            "supplier", "stock_level", "reorder_point", "daily_velocity",
            "days_to_stockout", "stockout_risk", "lead_time_days",
            "shrinkage_rate", "unit_cost", "last_replenished"
        ],
        "crm_customers": [
            "customer_id", "first_name", "last_name", "email", "phone",
            "address", "city", "state", "zip_code", "date_of_birth", "gender",
            "acquisition_channel", "first_purchase_date", "last_purchase_date",
            "days_since_last_purchase", "purchase_frequency", "avg_order_value",
            "total_spent", "r_score", "f_score", "m_score", "rfm_total",
            "segment", "tier", "churn_flag", "email_opt_in", "sms_opt_in", "loyalty_points"
        ],
    }

    issues_df = run_governance_checks(sample_tables, quality_scores={"pos_transactions": 92, "inventory": 78, "crm_customers": 88})
    print(f"\nGovernance Issues ({len(issues_df)}):")
    print(issues_df[["source_table", "rule_name", "severity", "sla_due"]].to_string())

    pii_df = build_pii_catalog(sample_tables)
    print(f"\nPII Catalog ({len(pii_df)} columns):")
    print(pii_df.to_string())