"""Build and serve linked Plotly and PyVista views of asset data."""
from __future__ import annotations

from html import escape
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, overload

from bokeh.server.server import Server
import pandas as pd
import panel as pn
from panel.io.server import StoppableThread
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from tornado.web import StaticFileHandler

import config
from modules.display import function_legend_entries
from modules.display.display import _function_colors
from modules.snmpdisplay import build_snmp_layout


_VTK_INTERACTION_SCRIPT = Path(__file__).with_name("static") / "z_up_interaction.js"
VTK_INTERACTION_URL = "/ict-digital-twin/z_up_interaction.js"


def _build_function_legend_html(asset_data: pd.DataFrame) -> str:
    """Build a compact HTML legend for the function colors used by the devices."""
    entries = function_legend_entries(asset_data, _function_colors(asset_data))
    return _build_legend_html(entries)


def _build_temperature_legend_html() -> str:
    """Build the SNMP temperature legend."""
    return _build_legend_html(
        [
            (f"Red (>={config.SNMP_TEMPERATURE_RED_MIN_C} C)", "#ff0000"),
            (
                f"Yellow ({config.SNMP_TEMPERATURE_YELLOW_MIN_C}-"
                f"<{config.SNMP_TEMPERATURE_RED_MIN_C} C)",
                "#ffff00",
            ),
            (
                f"Green ({config.SNMP_TEMPERATURE_GREEN_MIN_C}-"
                f"<{config.SNMP_TEMPERATURE_YELLOW_MIN_C} C)",
                "#008000",
            ),
        ]
    )


def _build_legend_html(entries: list[tuple[str, str]]) -> str:
    """Build a compact HTML legend from labels and colors."""
    if not entries:
        return ""

    rows = "".join(
        (
            '<div style="display:flex;align-items:center;gap:7px;'
            'font:12px sans-serif;line-height:18px;color:#f8fafc;">'
            f'<span aria-hidden="true" style="display:inline-block;width:11px;'
            f'height:11px;flex:0 0 11px;background:{escape(color, quote=True)};"></span>'
            f'<span>{escape(label)}</span></div>'
        )
        for label, color in entries
    )
    return (
        '<div style="display:inline-flex;flex-direction:column;gap:3px;'
        'padding:8px 10px;background:transparent;pointer-events:none;">'
        f"{rows}</div>"
    )


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


def _extract_rpdu_capacity(
    room_layout_data: Mapping[str, object] | None,
) -> float | None:
    """Return the configured RPDU capacity when it is a positive number."""
    if not isinstance(room_layout_data, Mapping):
        return None

    power_data = room_layout_data.get("power", {})
    if not isinstance(power_data, Mapping):
        return None

    try:
        capacity = float(power_data.get("rpdu_capacity"))
    except (TypeError, ValueError):
        return None
    return capacity if capacity > 0 else None


def _get_feed_state(
    feeds: tuple[bool, bool] | Mapping[str, tuple[bool, bool]],
    row: object,
) -> tuple[bool, bool]:
    """Return the active feed state for one row."""
    if isinstance(feeds, Mapping):
        return feeds.get(str(row), feeds.get("All rows", (True, True)))
    return feeds


def build_data_figure(
    asset_data: pd.DataFrame,
    room_layout_data: Mapping[str, object] | None = None,
    row_feeds: tuple[bool, bool] | Mapping[str, tuple[bool, bool]] = (True, True),
    rack_feeds: tuple[bool, bool] | Mapping[str, tuple[bool, bool]] = (True, True),
) -> go.Figure:
    """Build the row and rack charts used by the inventory dashboard."""
    if not isinstance(asset_data, pd.DataFrame):
        raise TypeError("asset_data must be a pandas DataFrame")

    row_column = "ROW" if "ROW" in asset_data else None
    rack_column = "RACK" if "RACK" in asset_data else None
    power_column = "POWERLOAD" if "POWERLOAD" in asset_data else None
    row_title = "Load by row" if row_column and power_column else "Assets by Row"
    rack_metric = "Load" if power_column else "Asset count"

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
        if power_column:
            row_feed_states = [
                _get_feed_state(row_feeds, row_name) for row_name in row_values.index
            ]
            for feed_index, (feed_name, color) in enumerate(
                (
                    ("Feed 1 powerload", "#1f77b4"),
                    ("Feed 2 powerload", "#d62728"),
                )
            ):
                visible = (
                    any(state[feed_index] for state in row_feed_states)
                    if isinstance(row_feeds, Mapping)
                    else row_feeds[feed_index]
                )
                figure.add_trace(
                    go.Bar(
                        x=row_x,
                        y=[
                            powerload / sum(state)
                            if state[feed_index] and sum(state)
                            else 0
                            for powerload, state in zip(row_y, row_feed_states)
                        ],
                        customdata=[["ROW", value] for value in row_x],
                        name=feed_name,
                        marker_color=color,
                        visible=visible,
                        hovertemplate=(
                            f"{feed_name} for row %{{x}}: %{{y}}<extra></extra>"
                        ),
                    ),
                    row=1,
                    col=1,
                )
        else:
            figure.add_trace(
                go.Bar(
                    x=row_x,
                    y=row_y,
                    customdata=[["ROW", value] for value in row_x],
                    name="Assets by row",
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
            powerload_counts = pd.to_numeric(
                row_data[power_column], errors="coerce"
            ).groupby(row_data[row_column], dropna=False).count()
            dual_feed_rows = powerload_counts.reindex(
                row_values.index, fill_value=0
            ).eq(2).tolist()
            row_feed_traces: dict[str, dict[str, object]] = {}
            for row_name, capacities in zip(row_values.index, row_feed_capacities):
                if not capacities:
                    continue
                row_position = row_x.index(str(row_name))
                for feed_number in sorted(
                    capacities,
                    key=lambda value: (0 if value.isdigit() else 1, int(value) if value.isdigit() else 0, value),
                ):
                    if not feed_number:
                        continue
                    trace_name = f"{row_name}{feed_number} capacity"
                    row_feed_traces.setdefault(
                        trace_name,
                        {
                            "row_label": str(row_name),
                            "capacity": capacities[feed_number],
                            "values": [None] * len(row_x),
                        },
                    )
                    if dual_feed_rows[row_position]:
                        row_feed_traces[trace_name]["values"][row_position] = capacities[feed_number]
            if any(dual_feed_rows) and row_feed_traces:
                first_dual_row = next((index for index, is_dual in enumerate(dual_feed_rows) if is_dual), 0)
                for trace_name, trace_info in row_feed_traces.items():
                    row_label = str(trace_info["row_label"])
                    row_prefix = row_label.upper()
                    color = (
                        "#1f77b4"
                        if row_prefix.startswith("A")
                        else "#d62728" if row_prefix.startswith("B") else "#1f77b4"
                    )
                    trace_values = [None] * len(row_x)
                    row_position = row_x.index(str(row_label)) if str(row_label) in row_x else -1
                    if row_position >= 0 and dual_feed_rows[row_position]:
                        trace_values[row_position] = trace_info["capacity"]
                    elif any(dual_feed_rows):
                        trace_values[first_dual_row] = trace_info["capacity"]
                    figure.add_trace(
                        go.Scatter(
                            x=row_x,
                            y=trace_values,
                            mode="lines+markers",
                            line={"color": color, "width": 2},
                            marker={"color": color},
                            name=trace_name,
                            hovertemplate=f"{trace_name} for row %{{x}}: %{{y}}<extra></extra>",
                        ),
                        row=1,
                        col=1,
                    )
            elif any(
                    feed_number
                    for capacities in row_feed_capacities
                    for feed_number in capacities
            ):
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
                                line={"color": "#d62728", "width": 2, "dash": "dot"},
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
        if power_column:
            rack_feed_values: list[list[float]] = [[], []]
            rack_feed_active = [False, False]
            for rack_name in rack_values.index:
                rack_assets = rack_data[rack_data[rack_column].eq(rack_name)]
                if row_column:
                    rack_rows = rack_assets.groupby(row_column, dropna=False)
                    row_loads = (
                        (row_name, float(row_assets[power_column].sum()))
                        for row_name, row_assets in rack_rows
                    )
                else:
                    row_loads = [(None, float(rack_values.loc[rack_name]))]
                feed_loads = [0.0, 0.0]
                for row_name, powerload in row_loads:
                    feed_state = _get_feed_state(rack_feeds, row_name)
                    active_feed_count = sum(feed_state)
                    for feed_index, enabled in enumerate(feed_state):
                        if enabled and active_feed_count:
                            feed_loads[feed_index] += powerload / active_feed_count
                            rack_feed_active[feed_index] = True
                for feed_index in range(2):
                    rack_feed_values[feed_index].append(feed_loads[feed_index])

            for feed_index, (feed_name, color) in enumerate(
                (
                    ("Feed 1 powerload", "#1f77b4"),
                    ("Feed 2 powerload", "#d62728"),
                )
            ):
                figure.add_trace(
                    go.Bar(
                        x=rack_x,
                        y=rack_feed_values[feed_index],
                        customdata=[["RACK", value] for value in rack_x],
                        name=feed_name,
                        marker_color=color,
                        visible=rack_feed_active[feed_index],
                        hovertemplate=(
                            f"{feed_name} for rack %{{x}}: %{{y}}<extra></extra>"
                        ),
                    ),
                    row=1,
                    col=2,
                )
            rpdu_capacity = _extract_rpdu_capacity(room_layout_data)
            if (
                rpdu_capacity is not None
                and any(
                    feed_active and powerload > rpdu_capacity
                    for feed_values, feed_active in zip(
                        rack_feed_values, rack_feed_active
                    )
                    for powerload in feed_values
                )
            ):
                figure.add_trace(
                    go.Scatter(
                        x=rack_x,
                        y=[rpdu_capacity] * len(rack_x),
                        mode="lines",
                        line={"color": "#d62728", "width": 2, "dash": "dot"},
                        name="RPDU limit",
                        hovertemplate="RPDU limit: %{y}<extra></extra>",
                    ),
                    row=1,
                    col=2,
                )
        else:
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
    else:
        figure.add_trace(go.Bar(x=[], y=[]), row=1, col=2)

    figure.update_xaxes(title_text="Row", row=1, col=1)
    figure.update_yaxes(
        title_text="Power load" if power_column else "Assets",
        rangemode="tozero",
        autorange=True,
        row=1,
        col=1,
    )
    figure.update_xaxes(title_text="Rack", row=1, col=2)
    figure.update_yaxes(
        title_text="" if power_column else rack_metric,
        rangemode="tozero",
        autorange=True,
        row=1,
        col=2,
    )
    figure.update_layout(
        title="Asset inventory and capacity",
        template="plotly_white",
        autosize=True,
        height=500,
        barmode="group",
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
        "tabulator",
        js_files={"ict-digital-twin-z-up": VTK_INTERACTION_URL},
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
    snmp_device_colors: dict[int, str] = {}
    snmp_mode_active = False
    rack_styles = {
        index: (actor.prop.color, actor.prop.line_width)
        for index, actor in rack_actors.items()
    }

    display_columns = [
        column
        for column in assets.columns
        if str(column).strip().upper()
        not in {"INDEX", "AIRFLOW DIRECTION", "ROW", "SIZE", "SNMP_COMMUNITY"}
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
    legend_pane = pn.pane.HTML(
        _build_function_legend_html(assets),
        styles={
            "position": "absolute",
            "left": "12px",
            "bottom": "48px",
            "z-index": "10",
        },
        margin=0,
    )
    vtk_view = pn.Column(
        vtk_pane,
        legend_pane,
        sizing_mode="stretch_both",
        min_height=800,
        styles={"position": "relative", "flex": "1.2 1 0px", "min-width": "0"},
    )
    plotly_pane = pn.pane.Plotly(
        build_data_figure(assets, room_layout_data),
        config={"responsive": True},
        sizing_mode="stretch_width",
        height=500,
    )
    row_labels = (
        assets.groupby("ROW", dropna=False).size().index.astype(str).tolist()
        if "ROW" in assets
        else ["All rows"]
    )
    row_feed_controls = {
        row_label: (
            pn.widgets.Checkbox(
                name="Feed 1",
                value=True,
                styles={"color": "#1f77b4"},
            ),
            pn.widgets.Checkbox(
                name="Feed 2",
                value=True,
                styles={"color": "#d62728"},
            ),
        )
        for row_label in row_labels
    }

    def update_feed_load(_event: object) -> None:
        enabled_feeds = {
            row_label: (feed_1.value, feed_2.value)
            for row_label, (feed_1, feed_2) in row_feed_controls.items()
        }
        plotly_pane.object = build_data_figure(
            assets,
            room_layout_data,
            row_feeds=enabled_feeds,
            rack_feeds=enabled_feeds,
        )

    for controls in row_feed_controls.values():
        for feed_control in controls:
            feed_control.param.watch(update_feed_load, "value")

    feed_controls = pn.Column(
        pn.pane.Markdown("Power feed toggle", margin=0),
        *(
            pn.Row(
                pn.pane.Markdown(f"**Row {row_label}**", margin=0, width=90),
                *controls,
                sizing_mode="stretch_width",
            )
            for row_label, controls in row_feed_controls.items()
        ),
        sizing_mode="stretch_width",
    )
    selected_asset_indices: set[int] = set()

    def apply_device_colors() -> None:
        for index, actor in device_actors.items():
            base_color, _ = device_styles[index]
            if index in selected_asset_indices:
                actor.prop.color = "#fff176"
            elif snmp_mode_active:
                actor.prop.color = snmp_device_colors.get(index, base_color)
            else:
                actor.prop.color = base_color

    def update_snmp_colors(rows: list[dict[str, object]]) -> None:
        snmp_device_colors.clear()
        for index in device_actors:
            row = rows[index] if index < len(rows) else {}
            temperature = row.get("Temperature (°C)")
            if temperature is None:
                temperature = row.get("Temperature")
            if (
                isinstance(temperature, (int, float))
                and not isinstance(temperature, bool)
                and config.SNMP_TEMPERATURE_GREEN_MIN_C
                <= temperature
                < config.SNMP_TEMPERATURE_YELLOW_MIN_C
            ):
                color = "#008000"
            elif (
                isinstance(temperature, (int, float))
                and not isinstance(temperature, bool)
                and config.SNMP_TEMPERATURE_YELLOW_MIN_C
                <= temperature
                < config.SNMP_TEMPERATURE_RED_MIN_C
            ):
                color = "#ffff00"
            else:
                color = "#ff0000"
            snmp_device_colors[index] = color

        if snmp_mode_active:
            apply_device_colors()
            plotter.render()
            vtk_pane.param.trigger("object")

    def set_snmp_mode(active: bool) -> None:
        nonlocal snmp_mode_active
        snmp_mode_active = active
        legend_pane.object = (
            _build_temperature_legend_html()
            if active
            else _build_function_legend_html(assets)
        )
        apply_device_colors()
        plotter.render()
        vtk_pane.param.trigger("object")

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
                _, base_width = device_styles[index]
                selected = index in selected_asset_indices
                actor.prop.line_width = max(base_width, 2.5) if selected else base_width
            apply_device_colors()
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
        color="primary",
        width=120,
        height=32,
        margin=(8, 0, 0, 0),
        styles={
            "background": "#2563eb",
            "border": "none",
            "border-radius": "6px",
            "box-shadow": "0 2px 5px rgba(0, 0, 0, 0.18)",
            "color": "#ffffff",
            "font-weight": "600",
        },
    )

    def clear_dashboard_selection(_event: object) -> None:
        for controls in row_feed_controls.values():
            for feed_control in controls:
                feed_control.value = True
        update_feed_load(None)
        update_selection(set(), sync_inventory=True)

    clear_selection.on_click(clear_dashboard_selection)
    plotly_pane.param.watch(on_plotly_click, "click_data")
    inventory.param.watch(on_inventory_selection, "selection")
    dashboard = pn.Column(
        plotly_pane,
        pn.Row(
            feed_controls,
            clear_selection,
            align="end",
            sizing_mode="stretch_width",
        ),
        inventory,
        sizing_mode="stretch_both",
        min_height=800,
    )
    right_panel_content = pn.Column(
        dashboard,
        sizing_mode="stretch_both",
        min_height=800,
    )
    right_panel_selector = pn.widgets.Select(
        label="",
        options={
            "Asset data": "assets",
            "SNMP data": "snmp",
        },
        value="assets",
        width=180,
        height=32,
        margin=(8, 0, 0, 0),
    )
    snmp_panel = build_snmp_layout(assets, on_results=update_snmp_colors)

    def select_right_panel(event: object) -> None:
        is_snmp = event.new == "snmp"
        right_panel_content.objects = (
            [snmp_panel] if is_snmp else [dashboard]
        )
        set_snmp_mode(is_snmp)
        snmp_panel.visible = is_snmp

    right_panel_selector.param.watch(select_right_panel, "value")
    right_panel = pn.Column(
        right_panel_selector,
        right_panel_content,
        sizing_mode="stretch_both",
        min_height=800,
        styles={"flex": "1 1 0px", "min-width": "0"},
    )
    return pn.Row(
        vtk_view,
        right_panel,
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
    return serve_layout(layout, threaded=True)


@overload
def serve_layout(layout: object, threaded: Literal[True]) -> StoppableThread: ...


@overload
def serve_layout(layout: object, threaded: Literal[False] = False) -> Server: ...


def serve_layout(layout: object, threaded: bool = False) -> StoppableThread | Server:
    """Serve a Panel layout with the static assets required by the VTK view."""
    return pn.serve(
        layout,
        port=0,
        show=True,
        threaded=threaded,
        title="ICT Digital Twin",
        extra_patterns=[
            (
                r"/ict-digital-twin/(.*)",
                StaticFileHandler,
                {"path": str(_VTK_INTERACTION_SCRIPT.parent)},
            )
        ],
    )