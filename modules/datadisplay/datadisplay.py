"""Build and open interactive Plotly views of asset data."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import panel as pn
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tornado.web import StaticFileHandler


_VTK_INTERACTION_SCRIPT = Path(__file__).with_name("static") / "z_up_interaction.js"
_VTK_INTERACTION_URL = "/ict-digital-twin/z_up_interaction.js"


def _extract_rpdu_capacity(room_layout_data: Mapping[str, object] | None) -> float | None:
    """Return the configured RPDU capacity from the room layout, if present."""
    if not isinstance(room_layout_data, Mapping):
        return None

    power_data = room_layout_data.get("power", {})
    if not isinstance(power_data, Mapping):
        return None

    value = power_data.get("rpdu_capacity")
    try:
        capacity = float(value)
    except (TypeError, ValueError):
        return None
    return capacity if capacity > 0 else None


def _extract_feed_capacity(
    room_layout_data: Mapping[str, object] | None,
    row: object,
) -> float | None:
    """Return the configured feed capacity for a row, if present."""
    if not isinstance(room_layout_data, Mapping):
        return None

    power_data = room_layout_data.get("power", {})
    if not isinstance(power_data, Mapping):
        return None

    value = power_data.get(f"feed_{str(row).strip().casefold()}_capacity")
    try:
        capacity = float(value)
    except (TypeError, ValueError):
        return None
    return capacity if capacity > 0 else None


def build_data_figure(
    asset_data: pd.DataFrame,
    room_layout_data: Mapping[str, object] | None = None,
) -> go.Figure:
    """Build an inventory table with function and rack visualizations."""
    if not isinstance(asset_data, pd.DataFrame):
        raise TypeError("asset_data must be a pandas DataFrame")

    row_column = "ROW" if "ROW" in asset_data else None
    rack_column = "RACK" if "RACK" in asset_data else None
    power_column = "POWERLOAD" if "POWERLOAD" in asset_data else None
    row_title = "Powerload by Row" if row_column and power_column else "Assets by Row"
    rack_metric = "Power load" if power_column else "Asset count"

    figure = make_subplots(
        rows=2,
        cols=2,
        specs=[[{"type": "table", "colspan": 2}, None], [{"type": "bar"}, {"type": "bar"}]],
        subplot_titles=("Asset inventory", row_title, f"{rack_metric} by rack"),
        row_heights=(0.64, 0.36),
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    display_columns = [
        column
        for column in asset_data.columns
        if str(column).strip().upper() not in {"INDEX", "AIRFLOW DIRECTION"}
    ]
    header_labels = {
        "NAME": "NAME",
        "ROW": "ROW",
        "RACK": "RACK",
        "RACK_UNIT": "Unit",
        "MODELNO": "Model",
        "SIZE": "Size",
        "POWERLOAD": "Power",
        "FUNCTION": "Funct",
    }
    columns = [
        header_labels.get(str(column).strip().upper(), str(column))
        for column in display_columns
    ]
    cell_values = [
        asset_data[column].fillna("").astype(str).tolist()
        for column in display_columns
    ]
    row_colors = ["#ffffff" if index % 2 == 0 else "#f1f5f4" for index in range(len(asset_data))]
    figure.add_trace(
        go.Table(
            columnwidth=[max(80, min(180, len(column) * 11)) for column in columns],
            header={
                "values": columns,
                "fill_color": "#254b4a",
                "font": {"color": "white", "size": 10},
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

    if row_column:
        row_data = asset_data.copy()
        if power_column:
            row_data[power_column] = pd.to_numeric(row_data[power_column], errors="coerce").fillna(0)
            row_values = row_data.groupby(row_column, dropna=False)[power_column].sum()
        else:
            row_values = row_data.groupby(row_column, dropna=False).size()
        row_x = row_values.index.astype(str).tolist()
        row_y = row_values.values.tolist()
        figure.add_trace(
            go.Bar(
                x=row_x,
                y=row_y,
                name="watts" if power_column else "assets",
                marker_color="#d18a46",
            ),
            row=2,
            col=1,
        )
        if power_column:
            row_capacities = [
                _extract_feed_capacity(room_layout_data, row)
                for row in row_values.index
            ]
            if any(capacity is not None for capacity in row_capacities):
                figure.add_trace(
                    go.Scatter(
                        x=row_x,
                        y=row_capacities,
                        mode="lines",
                        line={"color": "#b42318", "width": 2, "dash": "dash"},
                        name="Feed capacity",
                        hovertemplate="Feed %{x} capacity: %{y}<extra></extra>",
                    ),
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
        rack_x = rack_values.index.astype(str).tolist()
        rack_y = rack_values.values.tolist()
        figure.add_trace(
            go.Bar(
                x=rack_x,
                y=rack_y,
                name="watts" if power_column else "assets",
                marker_color="#d18a46",
            ),
            row=2,
            col=2,
        )
        rpdu_capacity = _extract_rpdu_capacity(room_layout_data)
        if rpdu_capacity is not None:
            figure.add_trace(
                go.Scatter(
                    x=rack_x,
                    y=[rpdu_capacity] * len(rack_x),
                    mode="lines",
                    line={"color": "#b42318", "width": 2, "dash": "dash"},
                    name="RPDU capacity",
                    hovertemplate="RPDU capacity: %{y}<extra></extra>",
                ),
                row=2,
                col=2,
            )
    else:
        figure.add_trace(go.Bar(x=[], y=[]), row=2, col=2)

    figure.update_xaxes(title_text="Row", row=2, col=1)
    figure.update_yaxes(title_text="Power load" if power_column else "Assets", rangemode="tozero", row=2, col=1)
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


def build_data_layout(
    asset_data: pd.DataFrame,
    plotter: object,
    room_layout_data: Mapping[str, object] | None = None,
) -> pn.Row:
    """Build a shared browser layout for the 3D scene and asset dashboard."""
    pn.extension(
        "vtk",
        "plotly",
        js_files={"ict-digital-twin-z-up": _VTK_INTERACTION_URL},
    )
    return pn.Row(
        pn.pane.VTK(plotter.ren_win, sizing_mode="stretch_both", min_height=800),
        pn.pane.Plotly(
            build_data_figure(asset_data, room_layout_data),
            config={"responsive": True},
            sizing_mode="stretch_both",
            min_height=800,
        ),
        sizing_mode="stretch_both",
        min_height=800,
    )


def display_data(
    asset_data: pd.DataFrame,
    plotter: object,
    room_layout_data: Mapping[str, object] | None = None,
) -> object:
    """Serve the shared visualization page and open it in the default browser."""
    layout = build_data_layout(asset_data, plotter, room_layout_data)
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