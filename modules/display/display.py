"""
display
This will display the loaded data.
"""
from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import pyvista as pv
import vtk


REQUIRED_COLUMNS = {"NAME", "ROW", "RACK", "RACK_UNIT", "SIZE"}


def _number(value: object, default: float = 1.0) -> float:
	"""Return a positive numeric value from CSV data."""
	try:
		number = float(value)
	except (TypeError, ValueError):
		return default
	return number if number > 0 else default


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

	plotter = pv.Plotter()
	plotter.set_background("#17202a")
	interactor = plotter.iren
	if interactor is None:
		raise RuntimeError("The PyVista plotter has no render-window interactor")
	device_details = {}
	room_width = room_length = room_height = 0
	if room_layout_data:
		room = room_layout_data.get("room", {})
		if isinstance(room, Mapping):
			room_width = _number(room.get("width"), 0)
			room_length = _number(room.get("length"), 0)
			room_height = _number(room.get("height"), 0)
	has_room_dimensions = room_width and room_length and room_height

	racks = list(asset_data[["ROW", "RACK"]].drop_duplicates().itertuples(index=False, name=None))
	rack_width = 0.8
	rack_depth = 1.0
	rack_height = 42.0 * 0.04445
	rack_gap = 0.003
	rack_spacing = rack_width + rack_gap
	aisle_width = 1.0
	row_values = list(asset_data["ROW"].drop_duplicates())
	row_racks = {
		row: list(asset_data.loc[asset_data["ROW"] == row, "RACK"].drop_duplicates())
		for row in row_values
	}
	max_racks_per_row = max((len(racks_in_row) for racks_in_row in row_racks.values()), default=0)
	rack_x_offset = room_width / 2 - (max_racks_per_row - 1) * rack_spacing / 2 if has_room_dimensions else 0
	row_y_offset = room_length / 2 - (len(row_values) - 1) * (rack_depth + aisle_width) / 2 if has_room_dimensions else 0
	# Adjacent rack rows leave a one-meter aisle between their one-meter-deep racks.
	row_positions = {
		row: row_index * (rack_depth + aisle_width) + row_y_offset
		for row_index, row in enumerate(row_values)
	}
	rack_positions = {}
	for row_index, row in enumerate(row_values):
		for rack_index, rack in enumerate(row_racks[row]):
			rack_positions[(row, rack)] = (rack_index * rack_spacing + rack_x_offset, row_positions[row])

	if has_room_dimensions:
		room_mesh = pv.Box(bounds=(0, room_width, 0, room_length, 0, room_height))
		plotter.add_mesh(room_mesh, style="wireframe", color="#475569", opacity=0.25)

	for row, rack in racks:
		x, y = rack_positions[(row, rack)]
		rack_mesh = pv.Box(
			bounds=(
				x - rack_width / 2,
				x + rack_width / 2,
				y - rack_depth / 2,
				y + rack_depth / 2,
				0,
				rack_height,
			)
		)
		plotter.add_mesh(rack_mesh, style="wireframe", color="#8fa3b8", line_width=2)

		rack_assets = asset_data[(asset_data["ROW"] == row) & (asset_data["RACK"] == rack)]
		for asset in rack_assets.itertuples(index=False):
			rack_unit = _number(getattr(asset, "RACK_UNIT"), 1.0)
			unit_size = _number(getattr(asset, "SIZE"), 1.0)
			height = unit_size * 0.04445
			center_z = (rack_unit - 1) * 0.04445 + height / 2
			device = pv.Box(
				bounds=(
					x - rack_width * 0.45,
					x + rack_width * 0.45,
					y - rack_depth * 0.45,
					y + rack_depth * 0.45,
					center_z - height / 2,
					center_z + height / 2,
				)
			)
			device_actor = plotter.add_mesh(
				device,
				color="#38bdf8",
				show_edges=True,
				edge_color="#d8f3ff",
			)
			device_details[device_actor] = "\n".join(
				f"{column}: {value}"
				for column, value in zip(asset_data.columns, asset)
			)

	hover_label = plotter.add_text(
		"",
		position="upper_left",
		font_size=12,
		color="#f8fafc",
		name="asset_hover",
		render=False,
	)
	picker = vtk.vtkCellPicker()
	picker.PickFromListOn()
	for device_actor in device_details:
		picker.AddPickList(device_actor)
	last_details = None

	def update_hover(_caller: object, _event: str) -> None:
		nonlocal last_details
		x, y = interactor.get_event_position()
		picker.Pick(x, y, 0, plotter.renderer)
		picked_actor = picker.GetActor()
		details = device_details.get(picked_actor)
		if details != last_details:
			hover_label.set_text("upper_left", details or "")
			last_details = details

	interactor.add_observer("MouseMoveEvent", update_hover)

	plotter.show_grid(
		show_xlabels=False,
		show_ylabels=False,
		show_zlabels=False,
		xtitle="",
		ytitle="",
		ztitle="",
	)
	plotter.enable_terrain_style()
	plotter.camera.up = (0, 0, 1)
	plotter.view_isometric()
	return plotter


def display_assets(
	asset_data: pd.DataFrame,
	room_layout_data: Mapping[str, object] | None = None,
) -> None:
	"""Build and display the 3D asset scene."""
	plotter = build_scene(asset_data, room_layout_data)
	plotter.show()
