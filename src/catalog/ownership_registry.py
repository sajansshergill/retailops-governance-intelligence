"""Ownership registry for cataloged data assets."""

from __future__ import annotations

import pandas as pd

from src.governance.rules_engine import TABLE_CLASSIFICATION, TABLE_OWNERS


def get_owner(table_name: str) -> str:
    """Return the registered owner for a table."""
    return TABLE_OWNERS.get(table_name, "data_governance_team")


def get_classification(table_name: str) -> str:
    """Return the registered data classification for a table."""
    return TABLE_CLASSIFICATION.get(table_name, "INTERNAL")


def ownership_registry() -> pd.DataFrame:
    """Return the ownership and classification registry as a DataFrame."""
    tables = sorted(set(TABLE_OWNERS) | set(TABLE_CLASSIFICATION))
    return pd.DataFrame(
        [
            {
                "table_name": table,
                "owner": get_owner(table),
                "classification": get_classification(table),
            }
            for table in tables
        ]
    )
