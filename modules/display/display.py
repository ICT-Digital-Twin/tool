""" This will display the room and asset data with PyVista."""
from __future__ import annotations

from collections.abc import Mapping
from colorsys import hsv_to_rgb

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

    asset_data = asset_data.reset_index(drop=True)
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

    label_meshes = []
    for row_index, row in enumerate(row_values):
        rack_x_positions = [rack_positions[(row, rack)][0] for rack in row_racks[row]]
        row_label = pv.Text3D(f"Row {row}", height=0.18, depth=0)
        row_label.rotate_z(180, point=row_label.center, inplace=True)
        row_label.translate(
            (
                max(rack_x_positions) + config.RACK_WIDTH * 1.75,
                row_positions[row],
                0.02,
            ),
            inplace=True,
        )
        label_meshes.append((row_label, f"_ict_row_label_{row_index}"))

    if has_room_dimensions:
        room_mesh = pv.Box(bounds=(0, room_width, 0, room_length, 0, room_height))
        plotter.add_mesh(
            room_mesh,
            style=config.ROOM_RENDER_STYLE,
            color=config.ROOM_COLOR,
            opacity=config.ROOM_OPACITY,
            line_width=config.ROOM_LINE_WIDTH,
        )

    for rack_index, (row, rack) in enumerate(racks):
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
            name=f"_ict_rack_{rack_index}",
        )
        rack_label = pv.Text3D(str(rack), height=0.14, depth=0)
        rack_label.rotate_z(180, point=rack_label.center, inplace=True)
        rack_label.translate(
            (x, y, config.RACK_HEIGHT + 0.02),
            inplace=True,
        )
        label_meshes.append((rack_label, f"_ict_rack_label_{rack_index}"))

        rack_assets = asset_data[(asset_data["ROW"] == row) & (asset_data["RACK"] == rack)]
        for asset in rack_assets.itertuples(index=True):
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
                name=f"_ict_device_{asset.Index}",
            )

    for label_mesh, label_name in label_meshes:
        plotter.add_mesh(
            label_mesh,
            color=config.TEXT_COLOR,
            lighting=False,
            name=label_name,
            reset_camera=False,
            render=False,
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


def display_assets(
    asset_data: pd.DataFrame,
    room_layout_data: Mapping[str, object] | None = None,
) -> None:
    """Build and display the 3D asset scene."""
    plotter = build_scene(asset_data, room_layout_data)
    plotter.show(window_size=[1024, 768])
