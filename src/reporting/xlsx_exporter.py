"""XLSX export module."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_metadata_workbook(
    catalog_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    issues_df: pd.DataFrame,
    output_path: str | Path = "exports/metadata_catalog.xlsx",
) -> Path:
    """Write catalog, quality, and governance sheets to an XLSX workbook."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        catalog_df.to_excel(writer, sheet_name="metadata_catalog", index=False)
        quality_df.to_excel(writer, sheet_name="quality_scores", index=False)
        issues_df.to_excel(writer, sheet_name="governance_issues", index=False)

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value or "")) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 2, 48)

    return path


def export_dataframe(
    df: pd.DataFrame,
    output_path: str | Path,
    sheet_name: str = "data",
) -> Path:
    """Export a single DataFrame to XLSX."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path
