"""
Data lineage mapper.
Defines source → transform → report lineage for all data assets
and produces a lineage graph exportable to the Streamlit dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LineageNode:
    node_id: str
    label: str
    node_type: str          # source | transform | report
    description: str
    owner: str
    tags: list[str] = field(default_factory=list)


@dataclass
class LineageEdge:
    source_id: str
    target_id: str
    transformation: str     # e.g., "aggregation", "filter", "join", "enrichment"
    description: str


# ── Node registry ──────────────────────────────────────────────────────────────

NODES: list[LineageNode] = [
    # Sources
    LineageNode("src_pos", "POS Transactions (Raw)", "source",
                "Raw point-of-sale transaction records from all store locations.",
                "sales_ops_team", ["retail", "transactions"]),
    LineageNode("src_inv", "Inventory Snapshot (Raw)", "source",
                "Daily inventory snapshot per SKU per store.",
                "supply_chain_team", ["retail", "inventory"]),
    LineageNode("src_crm", "Customer CRM (Raw)", "source",
                "Customer master records with purchase history and contact info.",
                "marketing_data_team", ["retail", "crm", "pii"]),

    # Transforms
    LineageNode("xf_pos_daily", "Daily Revenue Aggregation", "transform",
                "Aggregates POS transactions to store-day level revenue totals.",
                "sales_ops_team", ["aggregation"]),
    LineageNode("xf_inv_risk", "Stockout Risk Scoring", "transform",
                "Computes days-to-stockout and assigns HIGH/MEDIUM/LOW risk labels.",
                "supply_chain_team", ["scoring", "risk"]),
    LineageNode("xf_crm_rfm", "RFM Segmentation", "transform",
                "Computes recency, frequency, monetary scores and assigns customer segments.",
                "marketing_data_team", ["scoring", "segmentation"]),
    LineageNode("xf_pos_anomaly", "Revenue Anomaly Detection", "transform",
                "Applies z-score analysis to daily revenue per store to flag anomalies.",
                "sales_ops_team", ["anomaly", "statistics"]),
    LineageNode("xf_crm_churn", "Churn Risk Flagging", "transform",
                "Flags customers as churn risk based on RFM segment and recency thresholds.",
                "marketing_data_team", ["churn", "risk"]),
    LineageNode("xf_catalog", "Metadata Catalog Build", "transform",
                "Extracts column-level metadata, PII tags, and quality scores from all sources.",
                "data_governance_team", ["governance", "metadata"]),
    LineageNode("xf_quality", "Quality Scoring", "transform",
                "Computes completeness, consistency, validity, uniqueness scores per table.",
                "data_governance_team", ["governance", "quality"]),

    # Reports / Outputs
    LineageNode("rpt_health", "Data Health Scorecard", "report",
                "Per-table quality score dashboard with trend tracking via MLflow.",
                "data_governance_team", ["dashboard"]),
    LineageNode("rpt_catalog", "Metadata Catalog Export", "report",
                "Browsable asset registry exported to .xlsx for stakeholder distribution.",
                "data_governance_team", ["catalog", "export"]),
    LineageNode("rpt_bi", "Business Intelligence Panel", "report",
                "Streamlit BI view: stockout risk table, CRM heatmap, revenue anomaly flags.",
                "analytics_team", ["dashboard", "bi"]),
    LineageNode("rpt_governance", "Governance Issue Tracker", "report",
                "Open violation log with owner, severity, SLA countdown.",
                "data_governance_team", ["governance", "dashboard"]),
    LineageNode("rpt_docx", "Business Requirement Document (.docx)", "report",
                "Auto-generated Word document with data interface specs and lineage summary.",
                "data_governance_team", ["export", "documentation"]),
    LineageNode("rpt_pptx", "Executive Summary Deck (.pptx)", "report",
                "5-slide PowerPoint deck with KPIs, health scores, and recommendations.",
                "data_governance_team", ["export", "executive"]),
]

# ── Edge registry ───────────────────────────────────────────────────────────────

EDGES: list[LineageEdge] = [
    # POS lineage
    LineageEdge("src_pos", "xf_pos_daily", "aggregation",
                "Sum revenue and count transactions by store_id and transaction_date."),
    LineageEdge("src_pos", "xf_pos_anomaly", "statistical_analysis",
                "Apply z-score per store on daily revenue to detect anomalies."),
    LineageEdge("xf_pos_daily", "rpt_bi", "read",
                "Revenue trend data feeds the BI panel."),
    LineageEdge("xf_pos_anomaly", "rpt_bi", "read",
                "Anomaly flags displayed in BI panel anomaly table."),

    # Inventory lineage
    LineageEdge("src_inv", "xf_inv_risk", "scoring",
                "Compute days_to_stockout = stock_level / daily_velocity; assign risk label."),
    LineageEdge("xf_inv_risk", "rpt_bi", "read",
                "Stockout risk table feeds the BI panel."),

    # CRM lineage
    LineageEdge("src_crm", "xf_crm_rfm", "scoring",
                "Compute RFM scores and assign customer segments."),
    LineageEdge("src_crm", "xf_crm_churn", "filter",
                "Flag customers where segment IN (At Risk, Hibernating, Lost) AND recency > 90 days."),
    LineageEdge("xf_crm_rfm", "rpt_bi", "read",
                "CRM completeness heatmap and RFM distribution feeds BI panel."),
    LineageEdge("xf_crm_churn", "rpt_bi", "read",
                "Churn risk customer count feeds BI panel retention widget."),

    # Governance lineage
    LineageEdge("src_pos", "xf_catalog", "metadata_extraction",
                "Extract column names, types, null rates from POS table."),
    LineageEdge("src_inv", "xf_catalog", "metadata_extraction",
                "Extract column names, types, null rates from Inventory table."),
    LineageEdge("src_crm", "xf_catalog", "metadata_extraction",
                "Extract column names, types, null rates, PII tags from CRM table."),
    LineageEdge("xf_catalog", "rpt_catalog", "export",
                "Full metadata catalog written to .xlsx for distribution."),
    LineageEdge("xf_catalog", "rpt_docx", "documentation",
                "Column metadata used to populate data interface section of Word doc."),

    LineageEdge("src_pos", "xf_quality", "profiling",
                "Completeness, consistency, validity, uniqueness scored for POS."),
    LineageEdge("src_inv", "xf_quality", "profiling",
                "Completeness, consistency, validity, uniqueness scored for Inventory."),
    LineageEdge("src_crm", "xf_quality", "profiling",
                "Completeness, consistency, validity, uniqueness scored for CRM."),
    LineageEdge("xf_quality", "rpt_health", "read",
                "Quality scores feed the Data Health Scorecard dashboard."),
    LineageEdge("xf_quality", "rpt_pptx", "export",
                "Quality scores included in executive summary deck."),
    LineageEdge("xf_quality", "rpt_governance", "read",
                "Tables below quality threshold trigger governance issues."),
    LineageEdge("rpt_health", "rpt_pptx", "aggregation",
                "Health scorecard KPIs included in executive deck."),
    LineageEdge("rpt_governance", "rpt_docx", "documentation",
                "Open governance violations included in Word requirement doc."),
]


def get_lineage_dict() -> dict:
    """
    Return full lineage as a JSON-serializable dict for Streamlit visualization.

    Returns:
        Dict with 'nodes' and 'edges' lists.
    """
    node_types_color = {"source": "#2196F3", "transform": "#FF9800", "report": "#4CAF50"}

    return {
        "nodes": [
            {
                "id": n.node_id,
                "label": n.label,
                "type": n.node_type,
                "description": n.description,
                "owner": n.owner,
                "tags": n.tags,
                "color": node_types_color.get(n.node_type, "#9E9E9E"),
            }
            for n in NODES
        ],
        "edges": [
            {
                "source": e.source_id,
                "target": e.target_id,
                "transformation": e.transformation,
                "description": e.description,
            }
            for e in EDGES
        ],
    }


def get_downstream_nodes(node_id: str) -> list[str]:
    """Return all node IDs downstream of a given node (BFS traversal)."""
    downstream = []
    queue = [node_id]
    visited = {node_id}
    while queue:
        current = queue.pop(0)
        for edge in EDGES:
            if edge.source_id == current and edge.target_id not in visited:
                visited.add(edge.target_id)
                downstream.append(edge.target_id)
                queue.append(edge.target_id)
    return downstream


def get_upstream_nodes(node_id: str) -> list[str]:
    """Return all node IDs upstream of a given node (BFS traversal)."""
    upstream = []
    queue = [node_id]
    visited = {node_id}
    while queue:
        current = queue.pop(0)
        for edge in EDGES:
            if edge.target_id == current and edge.source_id not in visited:
                visited.add(edge.source_id)
                upstream.append(edge.source_id)
                queue.append(edge.source_id)
    return upstream


if __name__ == "__main__":
    lineage = get_lineage_dict()
    print(f"Nodes: {len(lineage['nodes'])}")
    print(f"Edges: {len(lineage['edges'])}")
    print("\nDownstream of src_crm:", get_downstream_nodes("src_crm"))
    print("Upstream of rpt_pptx:", get_upstream_nodes("rpt_pptx"))