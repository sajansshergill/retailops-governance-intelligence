"""Reusable Streamlit chart components."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def quality_bar(scores: pd.DataFrame) -> go.Figure:
    """Build a grouped quality-dimension bar chart."""
    dims = ["completeness", "consistency", "validity", "uniqueness", "composite_score"]
    chart_df = scores.melt(
        id_vars="table",
        value_vars=[col for col in dims if col in scores.columns],
        var_name="dimension",
        value_name="score",
    )
    fig = px.bar(
        chart_df,
        x="table",
        y="score",
        color="dimension",
        barmode="group",
        range_y=[0, 100],
        title="Quality Scores by Dataset",
    )
    fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="Score")
    return fig


def crm_completeness_heatmap(completeness: pd.DataFrame) -> go.Figure:
    """Build a CRM contact completeness heatmap."""
    fields = [
        "email_completeness",
        "phone_completeness",
        "address_completeness",
        "zip_completeness",
        "dob_completeness",
        "reachability_pct",
    ]
    available = [field for field in fields if field in completeness.columns]
    heatmap = completeness.set_index("segment")[available]
    fig = px.imshow(
        heatmap,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        title="CRM Completeness by Segment",
    )
    fig.update_layout(xaxis_title="", yaxis_title="")
    return fig


def stockout_by_store_bar(stockout: pd.DataFrame) -> go.Figure:
    """Build a top-store stockout risk bar chart."""
    fig = px.bar(
        stockout.head(15),
        x="store_id",
        y="high_risk_skus",
        color="total_value_at_risk",
        title="Stores with Highest Stockout Exposure",
    )
    fig.update_layout(xaxis_title="Store", yaxis_title="High Risk SKUs")
    return fig


def revenue_trend_line(trend: pd.DataFrame, stores: list[str]) -> go.Figure:
    """Build weekly revenue line chart for selected stores."""
    chart_df = trend[trend["store_id"].isin(stores)] if stores else trend.head(0)
    fig = px.line(
        chart_df,
        x="week_start",
        y="weekly_revenue",
        color="store_id",
        title="Weekly Revenue Trend",
    )
    fig.update_layout(xaxis_title="Week", yaxis_title="Revenue")
    return fig
