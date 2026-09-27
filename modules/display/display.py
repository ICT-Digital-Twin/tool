"""
display
This will display the loaded data.
"""
from __future__ import annotations

from collections.abc import Mapping
from colorsys import hsv_to_rgb

import pandas as pd
import pyvista as pv
import vtk

from config import (
	AISLE_WIDTH,
	CAMERA_UP,
	DEVICE_COLOR,
	DEVICE_DEPTH_RATIO,
	DEVICE_EDGE_COLOR,
	DEVICE_WIDTH_RATIO,
	ENABLE_TERRAIN_STYLE,
	FUNCTION_COLOR_BRIGHTNESS,
	FUNCTION_COLOR_HUE_STEP,
	FUNCTION_COLOR_SATURATION,
	GRID_AXIS_TITLE,
	GRID_SHOW_AXIS_LABELS,
	HOVER_FONT_SIZE,
	HOVER_TEXT_POSITION,
	RACK_COLOR,
	RACK_DEPTH,
	RACK_GAP,
	RACK_HEIGHT,
	RACK_LINE_WIDTH,
	RACK_RENDER_STYLE,
	RACK_WIDTH,
	ROOM_COLOR,
	ROOM_OPACITY,
	ROOM_RENDER_STYLE,
	RACK_UNIT_HEIGHT,
	SHOW_DEVICE_EDGES,
	TEXT_COLOR,
	create_pyvista_theme,
)


REQUIRED_COLUMNS = {"NAME", "ROW", "RACK", "RACK_UNIT", "SIZE"}


def _number(value: object, default: float = 1.0) -> float:
	"""Return a positive numeric value from CSV data."""
	try:
		number = float(value)
	except (TypeError, ValueError):
		return default
	return number if number > 0 else default


def _function_colors(asset_data: pd.DataFrame) -> dict[str, str]:
	"""Return a distinct, stable color for each non-empty function."""
	if "FUNCTION" not in asset_data:
		return {}

	functions = sorted(
		{
			str(value).strip()
			for value in asset_data["FUNCTION"]
			if not pd.isna(value) and str(value).strip()
		}
	)
	return {
		function: "#" + "".join(
			f"{round(channel * 255):02x}"
			for channel in hsv_to_rgb(
				index * FUNCTION_COLOR_HUE_STEP % 1,
				FUNCTION_COLOR_SATURATION,
				FUNCTION_COLOR_BRIGHTNESS,
			)
		)
		for index, function in enumerate(functions)
	}


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

	plotter = pv.Plotter(theme=create_pyvista_theme())
	interactor = plotter.iren
	if interactor is None:
		raise RuntimeError("The PyVista plotter has no render-window interactor")
	device_details = {}
	device_racks = {}
	function_colors = _function_colors(asset_data)
	room_width = room_length = room_height = 0
	if room_layout_data:
		room = room_layout_data.get("room", {})
		if isinstance(room, Mapping):
			room_width = _number(room.get("width"), 0)
			room_length = _number(room.get("length"), 0)
			room_height = _number(room.get("height"), 0)
	has_room_dimensions = room_width and room_length and room_height

	racks = list(asset_data[["ROW", "RACK"]].drop_duplicates().itertuples(index=False, name=None))
	rack_spacing = RACK_WIDTH + RACK_GAP
	row_values = list(asset_data["ROW"].drop_duplicates())
	row_racks = {
		row: list(asset_data.loc[asset_data["ROW"] == row, "RACK"].drop_duplicates())
		for row in row_values
	}
	max_racks_per_row = max((len(racks_in_row) for racks_in_row in row_racks.values()), default=0)
	rack_x_offset = room_width / 2 - (max_racks_per_row - 1) * rack_spacing / 2 if has_room_dimensions else 0
	row_y_offset = room_length / 2 - (len(row_values) - 1) * (RACK_DEPTH + AISLE_WIDTH) / 2 if has_room_dimensions else 0
	# Adjacent rack rows leave a one-meter aisle between their one-meter-deep racks.
	row_positions = {
		row: row_index * (RACK_DEPTH + AISLE_WIDTH) + row_y_offset
		for row_index, row in enumerate(row_values)
	}
	rack_positions = {}
	for row_index, row in enumerate(row_values):
		for rack_index, rack in enumerate(row_racks[row]):
			rack_positions[(row, rack)] = (rack_index * rack_spacing + rack_x_offset, row_positions[row])

	if has_room_dimensions:
		room_mesh = pv.Box(bounds=(0, room_width, 0, room_length, 0, room_height))
		plotter.add_mesh(room_mesh, style=ROOM_RENDER_STYLE, color=ROOM_COLOR, opacity=ROOM_OPACITY)

	for row, rack in racks:
		x, y = rack_positions[(row, rack)]
		rack_mesh = pv.Box(
			bounds=(
				x - RACK_WIDTH / 2,
				x + RACK_WIDTH / 2,
				y - RACK_DEPTH / 2,
				y + RACK_DEPTH / 2,
				0,
				RACK_HEIGHT,
			)
		)
		plotter.add_mesh(rack_mesh, style=RACK_RENDER_STYLE, color=RACK_COLOR, line_width=RACK_LINE_WIDTH)

		rack_assets = asset_data[(asset_data["ROW"] == row) & (asset_data["RACK"] == rack)]
		powerloads = rack_assets["POWERLOAD"] if "POWERLOAD" in rack_assets else pd.Series(0, index=rack_assets.index)
		rack_powerload = pd.to_numeric(powerloads, errors="coerce").fillna(0).sum()
		for asset in rack_assets.itertuples(index=False):
			rack_unit = _number(getattr(asset, "RACK_UNIT"), 1.0)
			unit_size = _number(getattr(asset, "SIZE"), 1.0)
			height = unit_size * RACK_UNIT_HEIGHT
			center_z = (rack_unit - 1) * RACK_UNIT_HEIGHT + height / 2
			device = pv.Box(
				bounds=(
					x - RACK_WIDTH * DEVICE_WIDTH_RATIO / 2,
					x + RACK_WIDTH * DEVICE_WIDTH_RATIO / 2,
					y - RACK_DEPTH * DEVICE_DEPTH_RATIO / 2,
					y + RACK_DEPTH * DEVICE_DEPTH_RATIO / 2,
					center_z - height / 2,
					center_z + height / 2,
				)
			)
			device_actor = plotter.add_mesh(
				device,
				color=function_colors.get(str(getattr(asset, "FUNCTION", "")).strip(), DEVICE_COLOR),
				show_edges=SHOW_DEVICE_EDGES,
				edge_color=DEVICE_EDGE_COLOR,
			)
			device_details[device_actor] = "\n".join(
				f"{column}: {value}"
				for column, value in zip(asset_data.columns, asset)
			)
			device_racks[device_actor] = (row, rack, rack_powerload)

	hover_label = plotter.add_text(
		"",
		position=HOVER_TEXT_POSITION,
		font_size=HOVER_FONT_SIZE,
		color=TEXT_COLOR,
		name="asset_hover",
		viewport=True,
		render=False,
	)
	hover_label.GetTextProperty().SetVerticalJustificationToTop()
	rack_power_label = plotter.add_text(
		"",
		position=(0.02, 0.02),
		font_size=HOVER_FONT_SIZE,
		color=TEXT_COLOR,
		name="rack_powerload",
		viewport=True,
		render=False,
	)
	picker = vtk.vtkCellPicker()
	picker.PickFromListOn()
	for device_actor in device_details:
		picker.AddPickList(device_actor)
	last_details = None
	last_rack_powerload = None

	def update_hover(_caller: object, _event: str) -> None:
		nonlocal last_details, last_rack_powerload
		x, y = interactor.get_event_position()
		picker.Pick(x, y, 0, plotter.renderer)
		picked_actor = picker.GetActor()
		details = device_details.get(picked_actor)
		rack_info = device_racks.get(picked_actor)
		if details != last_details:
			hover_label.SetInput(details or "")
			last_details = details
		rack_powerload = rack_info[2] if rack_info else None
		if rack_powerload != last_rack_powerload:
			text = f"Rack powerload: {rack_powerload:g} W" if rack_powerload is not None else ""
			rack_power_label.SetInput(text)
			last_rack_powerload = rack_powerload

	interactor.add_observer("MouseMoveEvent", update_hover)

	plotter.show_grid(
		show_xlabels=GRID_SHOW_AXIS_LABELS,
		show_ylabels=GRID_SHOW_AXIS_LABELS,
		show_zlabels=GRID_SHOW_AXIS_LABELS,
		xtitle=GRID_AXIS_TITLE,
		ytitle=GRID_AXIS_TITLE,
		ztitle=GRID_AXIS_TITLE,
	)
	if ENABLE_TERRAIN_STYLE:
		plotter.enable_terrain_style()
	plotter.camera.up = CAMERA_UP
	plotter.view_isometric()
	return plotter


def display_assets(
	asset_data: pd.DataFrame,
	room_layout_data: Mapping[str, object] | None = None,
) -> None:
	"""Build and display the 3D asset scene."""
	plotter = build_scene(asset_data, room_layout_data)
	plotter.show()
