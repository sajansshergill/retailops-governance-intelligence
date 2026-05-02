"""Streamlit page for lineage mapping."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from src.catalog.lineage_mapper import (
    get_downstream_nodes,
    get_lineage_dict,
    get_upstream_nodes,
)


st.set_page_config(page_title="Lineage Map", layout="wide")
st.title("Lineage Map")

lineage = get_lineage_dict()
node_lookup = {node["id"]: node for node in lineage["nodes"]}

net = Network(height="650px", width="100%", directed=True, bgcolor="#ffffff")
for node in lineage["nodes"]:
    net.add_node(
        node["id"],
        label=node["label"],
        title=f"{node['description']}<br>Owner: {node['owner']}",
        color=node["color"],
    )
for edge in lineage["edges"]:
    net.add_edge(
        edge["source"],
        edge["target"],
        title=edge["description"],
        label=edge["transformation"],
    )
net.toggle_physics(True)
components.html(net.generate_html(), height=680, scrolling=True)

selected = st.selectbox(
    "Inspect upstream/downstream impact",
    options=[node["id"] for node in lineage["nodes"]],
    format_func=lambda node_id: node_lookup[node_id]["label"],
)

left, right = st.columns(2)
left.subheader("Upstream Dependencies")
left.write([node_lookup[node_id]["label"] for node_id in get_upstream_nodes(selected)] or "None")
right.subheader("Downstream Consumers")
right.write([node_lookup[node_id]["label"] for node_id in get_downstream_nodes(selected)] or "None")

st.subheader("Lineage Edges")
st.dataframe(lineage["edges"], use_container_width=True, hide_index=True)
