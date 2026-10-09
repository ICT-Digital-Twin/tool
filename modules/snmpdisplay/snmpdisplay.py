"""Plotly panel for SNMP feed data."""
from __future__ import annotations

import panel as pn
import plotly.graph_objects as go


def build_snmp_figure() -> go.Figure:
    """Build the empty time-series chart template for future SNMP samples."""
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[],
            y=[],
            mode="lines",
            name="SNMP feed",
        )
    )
    figure.add_annotation(
        text="SNMP polling is not connected yet",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
    )
    figure.update_layout(
        title="SNMP Feed Data",
        template="plotly_white",
        autosize=True,
        height=500,
        xaxis_title="Time",
        yaxis_title="Value",
        margin={"l": 55, "r": 30, "t": 75, "b": 50},
    )
    return figure


def build_snmp_layout() -> pn.Column:
    """Build the right-side panel template for future SNMP feed data."""
    pn.extension("plotly")
    return pn.Column(
        pn.pane.Markdown("## SNMP feed data"),
        pn.pane.Plotly(
            build_snmp_figure(),
            config={"responsive": True},
            sizing_mode="stretch_width",
            height=500,
        ),
        pn.pane.Markdown("SNMP polling and feed-to-device mapping are not configured yet."),
        sizing_mode="stretch_both",
        min_height=800,
    )
