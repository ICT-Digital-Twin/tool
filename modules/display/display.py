"""
This will display the room and asset data with PyVista.
"""
from __future__ import annotations

from collections.abc import Mapping
from colorsys import hsv_to_rgb
from pathlib import Path

import pandas as pd
import pyvista as pv

import config

REQUIRED_COLUMNS = {"NAME", "ROW", "RACK", "RACK_UNIT", "SIZE"}


def _number(value: object, default: float = 1.0) -> float:
    """Return a positive numeric value from CSV data."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _function_colors(asset_data: pd.DataFrame) -> dict[str, str]:
    """Map function values to the configured function-category colors."""
    if "FUNCTION" not in asset_data:
        return {}

    category_names = {
        "compute": "Compute",
        "storage": "Storage",
        "network": "Network",
        "other": "Other",
    }
    colors = {}
    unknown_functions = {}
    for value in asset_data["FUNCTION"]:
        if pd.isna(value):
            continue
        function = str(value).strip()
        category = category_names.get(function.casefold())
        if category is not None:
            colors[function] = config.FUNCTION_COLORS[category]
            continue
        color_index = unknown_functions.setdefault(function, len(unknown_functions))
        hue = (color_index * config.FUNCTION_COLOR_HUE_STEP) % 1.0
        rgb = hsv_to_rgb(
            hue,
            config.FUNCTION_COLOR_SATURATION,
            config.FUNCTION_COLOR_BRIGHTNESS,
        )
        colors[function] = "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)
    return colors


def build_scene(
    asset_data: pd.DataFrame,
    room_layout_data: Mapping[str, object] | None = None,
) -> pv.Plotter:
    """Build a PyVista scene from the asset DataFrame without opening a window."""
    if not isinstance(asset_data, pd.DataFrame):
        raise TypeError("asset_data must be a pandas DataFrame")

    missing_columns = REQUIRED_COLUMNS - set(asset_data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"asset_data is missing required columns: {missing}")

    plotter = pv.Plotter(theme=config.create_pyvista_theme())

    function_colors = _function_colors(asset_data)
    room_width = room_length = room_height = 0
    if room_layout_data:
        room = room_layout_data.get("room", {})
        if isinstance(room, Mapping):
            room_width = _number(room.get("width"), 0)
            room_length = _number(room.get("length"), 0)
            room_height = _number(room.get("height"), 0)
    has_room_dimensions = room_width and room_length and room_height

    racks = list(
        asset_data[["ROW", "RACK"]].drop_duplicates().itertuples(index=False, name=None)
    )
    rack_spacing = config.RACK_WIDTH + config.RACK_GAP
    row_values = list(asset_data["ROW"].drop_duplicates())
    row_racks = {
        row: list(asset_data.loc[asset_data["ROW"] == row, "RACK"].drop_duplicates())
        for row in row_values
    }
    max_racks_per_row = max(
        (len(racks_in_row) for racks_in_row in row_racks.values()), default=0
    )
    rack_x_offset = (
        room_width / 2 - (max_racks_per_row - 1) * rack_spacing / 2
        if has_room_dimensions
        else 0
    )
    row_y_offset = (
        room_length / 2 - (len(row_values) - 1) * (config.RACK_DEPTH + config.AISLE_WIDTH) / 2
        if has_room_dimensions
        else 0
    )
    # Adjacent rack rows leave the configured aisle between their racks.
    row_positions = {
        row: row_index * (config.RACK_DEPTH + config.AISLE_WIDTH) + row_y_offset
        for row_index, row in enumerate(row_values)
    }
    rack_positions = {}
    for row_index, row in enumerate(row_values):
        for rack_index, rack in enumerate(row_racks[row]):
            rack_positions[(row, rack)] = (
                rack_index * rack_spacing + rack_x_offset,
                row_positions[row],
            )

    if has_room_dimensions:
        room_mesh = pv.Box(bounds=(0, room_width, 0, room_length, 0, room_height))
        plotter.add_mesh(
            room_mesh,
            style=config.ROOM_RENDER_STYLE,
            color=config.ROOM_COLOR,
            opacity=config.ROOM_OPACITY,
        )

    for row, rack in racks:
        x, y = rack_positions[(row, rack)]
        rack_mesh = pv.Box(
            bounds=(
                x - config.RACK_WIDTH / 2,
                x + config.RACK_WIDTH / 2,
                y - config.RACK_DEPTH / 2,
                y + config.RACK_DEPTH / 2,
                0,
                config.RACK_HEIGHT,
            )
        )
        plotter.add_mesh(
            rack_mesh,
            style=config.RACK_RENDER_STYLE,
            color=config.RACK_COLOR,
            line_width=config.RACK_LINE_WIDTH,
        )

        rack_assets = asset_data[(asset_data["ROW"] == row) & (asset_data["RACK"] == rack)]
        for asset in rack_assets.itertuples(index=False):
            rack_unit = _number(getattr(asset, "RACK_UNIT"), 1.0)
            unit_size = _number(getattr(asset, "SIZE"), 1.0)
            height = unit_size * config.RACK_UNIT_HEIGHT
            center_z = (rack_unit - 1) * config.RACK_UNIT_HEIGHT + height / 2
            device = pv.Box(
                bounds=(
                    x - config.RACK_WIDTH * config.DEVICE_WIDTH_RATIO / 2,
                    x + config.RACK_WIDTH * config.DEVICE_WIDTH_RATIO / 2,
                    y - config.RACK_DEPTH * config.DEVICE_DEPTH_RATIO / 2,
                    y + config.RACK_DEPTH * config.DEVICE_DEPTH_RATIO / 2,
                    center_z - height / 2,
                    center_z + height / 2,
                )
            )
            plotter.add_mesh(
                device,
                color=function_colors.get(
                    str(getattr(asset, "FUNCTION", "")).strip(),
                    config.DEVICE_COLOR,
                ),
                show_edges=config.SHOW_DEVICE_EDGES,
                edge_color=config.DEVICE_EDGE_COLOR,
            )

    if config.GRID_SHOW_AXIS_LABELS:
        plotter.show_grid(
            show_xlabels=True,
            show_ylabels=True,
            show_zlabels=True,
            xtitle=config.GRID_AXIS_TITLE,
            ytitle=config.GRID_AXIS_TITLE,
            ztitle=config.GRID_AXIS_TITLE,
        )
    if config.ENABLE_TERRAIN_STYLE:
        plotter.enable_terrain_style()
    plotter.camera.up = config.CAMERA_UP
    plotter.view_isometric()
    return plotter


def _add_export_button(plotter: pv.Plotter) -> None:
    """Add a button that exports the current camera view as a PNG."""
    output_path = Path(config.OUTPUT_DIR) / "pyvista_view.png"
    export_status = plotter.add_text(
        "",
        position=(10, 55),
        font_size=config.HOVER_FONT_SIZE,
        color=config.TEXT_COLOR,
    )

    def export_view(_value: bool) -> None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plotter.screenshot(output_path, return_img=False)
        except Exception as error:
            export_status.SetInput(f"PNG export failed: {error}")
            return
        export_status.SetInput("PNG exported")

    button = plotter.add_checkbox_button_widget(
        export_view,
        value=False,
        position=(10, 10),
        size=140,
        border_size=2,
        color_on=config.DEVICE_COLOR,
        color_off=config.RACK_COLOR,
        background_color=config.BACKGROUND_COLOR,
    )
    representation = button.GetRepresentation()
    button_texture = representation.GetButtonTexture(0)
    representation.SetButtonTexture(1, button_texture)
    representation.PlaceWidget((10, 150, 10, 46, 0, 0))
    plotter.add_text(
        "Export PNG",
        position=(60, 19),
        font_size=config.HOVER_FONT_SIZE,
        color=config.TEXT_COLOR,
    )


def display_assets(
    asset_data: pd.DataFrame,
    room_layout_data: Mapping[str, object] | None = None,
) -> None:
    """Build and display the 3D asset scene."""
    plotter = build_scene(asset_data, room_layout_data)
    _add_export_button(plotter)
    plotter.show(window_size=[1024, 768])
