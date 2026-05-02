"""Reusable Streamlit KPI card components."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class KPI:
    """A small metric displayed in a Streamlit column."""

    label: str
    value: str | int | float
    delta: str | int | float | None = None
    help_text: str | None = None


def render_kpi_row(kpis: Iterable[KPI], columns: int | None = None) -> None:
    """Render KPI cards across the page."""
    kpi_list = list(kpis)
    if not kpi_list:
        return

    cols = st.columns(columns or len(kpi_list))
    for col, kpi in zip(cols, kpi_list):
        col.metric(
            label=kpi.label,
            value=kpi.value,
            delta=kpi.delta,
            help=kpi.help_text,
        )


def money(value: float | int | None) -> str:
    """Format a value as compact USD."""
    value = value or 0
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def percent(value: float | int | None) -> str:
    """Format a value as a percent."""
    return f"{value or 0:.1f}%"
