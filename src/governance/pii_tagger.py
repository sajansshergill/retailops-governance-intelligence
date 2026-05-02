"""PII tagging helpers for governed retail datasets."""

from __future__ import annotations

import pandas as pd

from src.governance.rules_engine import PIIType, tag_pii


def tag_columns(columns: list[str]) -> pd.DataFrame:
    """Tag a list of columns with detected PII type."""
    return pd.DataFrame(
        [
            {
                "column_name": column,
                "pii_type": tag_pii(column).value,
                "is_pii": tag_pii(column) != PIIType.NONE,
            }
            for column in columns
        ]
    )


def pii_columns(columns: list[str]) -> list[str]:
    """Return only columns that are classified as PII."""
    return [column for column in columns if tag_pii(column) != PIIType.NONE]
