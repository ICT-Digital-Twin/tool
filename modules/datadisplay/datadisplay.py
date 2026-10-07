"""Build and serve linked Plotly and PyVista views of asset data."""
from __future__ import annotations

import re
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


def _extract_feed_capacities(
    room_layout_data: Mapping[str, object] | None,
    row: object,
) -> dict[str, float]:
    """Return configured feed capacities for a row, keyed by feed number."""
    if not isinstance(room_layout_data, Mapping):
        return {}

    power_data = room_layout_data.get("power", {})
    if not isinstance(power_data, Mapping):
        return {}

    row_name = re.escape(str(row).strip().casefold())
    key_pattern = re.compile(rf"^feed_{row_name}(\d*)_capacity$", re.IGNORECASE)
    capacities = {}
    for key, value in power_data.items():
        if not isinstance(key, str):
            continue
        match = key_pattern.fullmatch(key)
        if match is None:
            continue
        try:
            capacity = float(value)
        except (TypeError, ValueError):
            continue
        if capacity > 0:
            capacities[match.group(1)] = capacity
    return capacities


def build_data_figure(
    asset_data: pd.DataFrame,
    room_layout_data: Mapping[str, object] | None = None,
) -> go.Figure:
    """Build the row and rack charts used by the inventory dashboard."""
    if not isinstance(asset_data, pd.DataFrame):
        raise TypeError("asset_data must be a pandas DataFrame")

    row_column = "ROW" if "ROW" in asset_data else None
    rack_column = "RACK" if "RACK" in asset_data else None
    power_column = "POWERLOAD" if "POWERLOAD" in asset_data else None
    row_title = "Powerload by row" if row_column and power_column else "Assets by Row"
    rack_metric = "Power load" if power_column else "Asset count"

    figure = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "bar"}, {"type": "bar"}]],
        subplot_titles=(row_title, f"{rack_metric} by rack"),
        horizontal_spacing=0.08,
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
                customdata=[["ROW", value] for value in row_x],
                name="Power load by row" if power_column else "Assets by row",
                marker_color="#d18a46",
            ),
            row=1,
            col=1,
        )
        if power_column:
            row_feed_capacities = [
                _extract_feed_capacities(room_layout_data, row)
                for row in row_values.index
            ]
            row_capacities = [
                sum(capacities.values()) if capacities else None
                for capacities in row_feed_capacities
            ]
            if any(capacity is not None for capacity in row_capacities):
                has_numbered_feeds = any(
                    feed_number
                    for capacities in row_feed_capacities
                    for feed_number in capacities
                )
                figure.add_trace(
                    go.Scatter(
                        x=row_x,
                        y=row_capacities,
                        mode="lines",
                        line={"color": "#b42318", "width": 2, "dash": "dash"},
                        name="Total feed capacity" if has_numbered_feeds else "Feed capacity",
                        hovertemplate=(
                            "Total feed capacity for row %{x}: %{y}<extra></extra>"
                            if has_numbered_feeds
                            else "Feed %{x} capacity: %{y}<extra></extra>"
                        ),
                    ),
                    row=1,
                    col=1,
                )
                feed_numbers = sorted(
                    {
                        feed_number
                        for capacities in row_feed_capacities
                        for feed_number in capacities
                        if feed_number
                    },
                    key=int,
                )
                for feed_number in feed_numbers:
                    feed_capacities = [
                        capacities.get(feed_number)
                        for capacities in row_feed_capacities
                    ]
                    if any(capacity is not None for capacity in feed_capacities):
                        figure.add_trace(
                            go.Scatter(
                                x=row_x,
                                y=feed_capacities,
                                mode="lines",
                                line={"color": "#16803c", "width": 2, "dash": "dot"},
                                name=f"Feed {feed_number} capacity",
                                hovertemplate=(
                                    f"Feed {feed_number} capacity for row "
                                    "%{x}: %{y}<extra></extra>"
                                ),
                            ),
                            row=1,
                            col=1,
                        )
    else:
        figure.add_trace(go.Bar(x=[], y=[]), row=1, col=1)

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
                customdata=[["RACK", value] for value in rack_x],
                name=f"{rack_metric} by rack",
                marker_color="#d18a46",
            ),
            row=1,
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
                row=1,
                col=2,
            )
    else:
        figure.add_trace(go.Bar(x=[], y=[]), row=1, col=2)

    figure.update_xaxes(title_text="Row", row=1, col=1)
    figure.update_yaxes(title_text="Power load" if power_column else "Assets", rangemode="tozero", row=1, col=1)
    figure.update_xaxes(title_text="Rack", row=1, col=2)
    figure.update_yaxes(title_text=rack_metric, rangemode="tozero", row=1, col=2)
    figure.update_layout(
        title="Asset inventory and capacity",
        template="plotly_white",
        autosize=True,
        height=500,
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
    assets = asset_data.reset_index(drop=True)
    rack_keys = list(
        assets[["ROW", "RACK"]].drop_duplicates().itertuples(index=False, name=None)
    )
    rack_asset_indices = {
        rack_index: set(
            assets.index[
                assets["ROW"].astype(str).eq(str(row))
                & assets["RACK"].astype(str).eq(str(rack))
            ].tolist()
        )
        for rack_index, (row, rack) in enumerate(rack_keys)
    }
    device_actors = {
        index: plotter.actors[f"_ict_device_{index}"]
        for index in range(len(assets))
    }
    rack_actors = {
        index: plotter.actors[f"_ict_rack_{index}"]
        for index in range(len(rack_keys))
    }
    device_styles = {
        index: (actor.prop.color, actor.prop.line_width)
        for index, actor in device_actors.items()
    }
    rack_styles = {
        index: (actor.prop.color, actor.prop.line_width)
        for index, actor in rack_actors.items()
    }

    display_columns = [
        column
        for column in assets.columns
        if str(column).strip().upper() not in {"INDEX", "AIRFLOW DIRECTION", "ROW", "SIZE"}
    ]
    header_labels = {
        "INDEX": "Index",
        "NAME": "NAME",
        "RACK": "RACK",
        "RACK_UNIT": "Unit",
        "MODELNO": "Model",
        "POWERLOAD": "Power",
        "FUNCTION": "Function",
    }
    inventory = pn.widgets.Tabulator(
        assets[display_columns],
        titles={
            column: header_labels.get(str(column).strip().upper(), str(column))
            for column in display_columns
        },
        selectable=True,
        height=350,
        sizing_mode="stretch_width",
        row_height=22,
        stylesheets=[
            """
            .tabulator {
                font-size: 11px;
            }
            .tabulator-cell,
            .tabulator-col-title,
            .tabulator-header {
                font-size: 11px;
            }
            """
        ],
    )
    vtk_pane = pn.pane.VTK(
        plotter.ren_win,
        sizing_mode="stretch_both",
        min_height=800,
    )
    plotly_pane = pn.pane.Plotly(
        build_data_figure(assets, room_layout_data),
        config={"responsive": True},
        sizing_mode="stretch_width",
        height=500,
    )
    selected_asset_indices: set[int] = set()

    def update_selection(asset_indices: set[int], sync_inventory: bool = False) -> None:
        next_selection = {
            index for index in asset_indices if 0 <= index < len(assets)
        }
        selection_changed = next_selection != selected_asset_indices
        if selection_changed:
            selected_asset_indices.clear()
            selected_asset_indices.update(next_selection)
            selected_rack_indices = {
                rack_index
                for rack_index, rack_indices in rack_asset_indices.items()
                if selected_asset_indices.intersection(rack_indices)
            }
            for index, actor in device_actors.items():
                base_color, base_width = device_styles[index]
                selected = index in selected_asset_indices
                actor.prop.color = "#fff176" if selected else base_color
                actor.prop.line_width = max(base_width, 2.5) if selected else base_width
            for index, actor in rack_actors.items():
                base_color, base_width = rack_styles[index]
                selected = index in selected_rack_indices
                actor.prop.color = "#26c6da" if selected else base_color
                actor.prop.line_width = max(base_width, 4) if selected else base_width
            plotter.render()
            vtk_pane.param.trigger("object")
        if sync_inventory:
            selection = sorted(selected_asset_indices)
            if inventory.selection != selection:
                inventory.selection = selection

    def on_plotly_click(event: object) -> None:
        click_data = event.new
        if not isinstance(click_data, Mapping):
            return
        points = click_data.get("points", [])
        if not isinstance(points, list):
            return
        for point in points:
            if not isinstance(point, Mapping):
                continue
            custom_data = point.get("customdata")
            if (
                not isinstance(custom_data, (list, tuple))
                or len(custom_data) != 2
            ):
                continue
            category, value = custom_data
            if category == "ROW":
                indices = set(
                    assets.index[assets["ROW"].astype(str).eq(str(value))].tolist()
                )
            elif category == "RACK":
                indices = set(
                    assets.index[assets["RACK"].astype(str).eq(str(value))].tolist()
                )
            else:
                continue
            update_selection(indices, sync_inventory=True)
            return

    def on_inventory_selection(event: object) -> None:
        update_selection(set(event.new))

    clear_selection = pn.widgets.Button(
        label="Clear selection",
        width=130,
    )
    clear_selection.on_click(lambda _event: update_selection(set(), sync_inventory=True))
    plotly_pane.param.watch(on_plotly_click, "click_data")
    inventory.param.watch(on_inventory_selection, "selection")
    dashboard = pn.Column(
        plotly_pane,
        pn.Row(
            pn.pane.Markdown("Select a chart bar or inventory row to highlight it in 3D."),
            clear_selection,
            sizing_mode="stretch_width",
        ),
        inventory,
        sizing_mode="stretch_both",
        min_height=800,
    )
    return pn.Row(
        vtk_pane,
        dashboard,
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