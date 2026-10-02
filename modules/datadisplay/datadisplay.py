"""Build and open interactive Plotly views of asset data."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import panel as pn
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tornado.web import StaticFileHandler


_VTK_INTERACTION_SCRIPT = Path(__file__).with_name("static") / "z_up_interaction.js"
_VTK_INTERACTION_URL = "/ict-digital-twin/z_up_interaction.js"


def build_data_figure(asset_data: pd.DataFrame) -> go.Figure:
    """Build an inventory table with function and rack visualizations."""
    if not isinstance(asset_data, pd.DataFrame):
        raise TypeError("asset_data must be a pandas DataFrame")

    category_column = next(
        (column for column in ("FUNCTION", "MODELNO", "ROW") if column in asset_data),
        None,
    )
    rack_column = "RACK" if "RACK" in asset_data else None
    power_column = "POWERLOAD" if "POWERLOAD" in asset_data else None
    category_title = f"Assets by {category_column}" if category_column else "Asset count"
    rack_metric = "Power load" if power_column else "Asset count"

    figure = make_subplots(
        rows=2,
        cols=2,
        specs=[[{"type": "table", "colspan": 2}, None], [{"type": "bar"}, {"type": "bar"}]],
        subplot_titles=("Asset inventory", category_title, f"{rack_metric} by rack"),
        row_heights=(0.64, 0.36),
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    columns = [str(column) for column in asset_data.columns]
    cell_values = [
        asset_data[column].fillna("").astype(str).tolist()
        for column in asset_data.columns
    ]
    row_colors = ["#ffffff" if index % 2 == 0 else "#f1f5f4" for index in range(len(asset_data))]
    figure.add_trace(
        go.Table(
            columnwidth=[max(80, min(180, len(column) * 11)) for column in columns],
            header={
                "values": columns,
                "fill_color": "#254b4a",
                "font": {"color": "white", "size": 12},
                "align": "left",
                "height": 30,
            },
            cells={
                "values": cell_values,
                "fill_color": [row_colors] * len(columns),
                "font": {"color": "#203332", "size": 11},
                "align": "left",
                "height": 25,
            },
        ),
        row=1,
        col=1,
    )

    if category_column:
        categories = (
            asset_data[category_column]
            .fillna("Unspecified")
            .astype(str)
            .str.strip()
            .replace("", "Unspecified")
            .value_counts()
        )
        figure.add_trace(
            go.Bar(x=categories.index.tolist(), y=categories.values.tolist(), marker_color="#4d8b78"),
            row=2,
            col=1,
        )
    else:
        figure.add_trace(go.Bar(x=[], y=[]), row=2, col=1)

    if rack_column:
        rack_data = asset_data.copy()
        if power_column:
            rack_data[power_column] = pd.to_numeric(rack_data[power_column], errors="coerce").fillna(0)
            rack_values = rack_data.groupby(rack_column, dropna=False)[power_column].sum()
        else:
            rack_values = rack_data.groupby(rack_column, dropna=False).size()
        figure.add_trace(
            go.Bar(x=rack_values.index.astype(str).tolist(), y=rack_values.values.tolist(), marker_color="#d18a46"),
            row=2,
            col=2,
        )
    else:
        figure.add_trace(go.Bar(x=[], y=[]), row=2, col=2)

    figure.update_xaxes(title_text=category_column or "Category", row=2, col=1)
    figure.update_yaxes(title_text="Assets", rangemode="tozero", row=2, col=1)
    figure.update_xaxes(title_text="Rack", row=2, col=2)
    figure.update_yaxes(title_text=rack_metric, rangemode="tozero", row=2, col=2)
    figure.update_layout(
        title="Asset inventory and capacity",
        template="plotly_white",
        autosize=True,
        height=max(900, min(1800, 700 + len(asset_data) * 20)),
        showlegend=False,
        margin={"l": 45, "r": 35, "t": 90, "b": 45},
    )
    return figure


def build_data_layout(asset_data: pd.DataFrame, plotter: object) -> pn.Row:
    """Build a shared browser layout for the 3D scene and asset dashboard."""
    pn.extension(
        "vtk",
        "plotly",
        js_files={"ict-digital-twin-z-up": _VTK_INTERACTION_URL},
    )
    return pn.Row(
        pn.pane.VTK(plotter.ren_win, sizing_mode="stretch_both", min_height=800),
        pn.pane.Plotly(
            build_data_figure(asset_data),
            config={"responsive": True},
            sizing_mode="stretch_both",
            min_height=800,
        ),
        sizing_mode="stretch_both",
        min_height=800,
    )


def display_data(asset_data: pd.DataFrame, plotter: object) -> object:
    """Serve the shared visualization page and open it in the default browser."""
    layout = build_data_layout(asset_data, plotter)
    return pn.serve(
        layout,
        port=0,
        show=True,
        threaded=True,
        title="ICT Digital Twin",
        extra_patterns=[
            (
                r"/ict-digital-twin/(.*)",
                StaticFileHandler,
                {"path": str(_VTK_INTERACTION_SCRIPT.parent)},
            )
        ],
    )