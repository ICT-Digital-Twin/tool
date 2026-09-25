"""
display
This will display the loaded data.
"""
from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import pyvista as pv


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

	racks = list(asset_data[["ROW", "RACK"]].drop_duplicates().itertuples(index=False, name=None))
	rack_width = 0.6
	rack_depth = 1.0
	rack_height = 42.0 * 0.04445
	rack_spacing = 1.5

	for rack_index, (row, rack) in enumerate(racks):
		x = rack_index * rack_spacing
		rack_mesh = pv.Box(
			bounds=(
				x - rack_width / 2,
				x + rack_width / 2,
				-rack_depth / 2,
				rack_depth / 2,
				0,
				rack_height,
			)
		)
		plotter.add_mesh(rack_mesh, style="wireframe", color="#8fa3b8", line_width=2)
		plotter.add_text(f"Row {row} / Rack {rack}", position=(x - 0.45, -0.8), font_size=9)

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
					-rack_depth * 0.45,
					rack_depth * 0.45,
					center_z - height / 2,
					center_z + height / 2,
				)
			)
			plotter.add_mesh(device, color="#38bdf8", show_edges=True, edge_color="#d8f3ff")

	if room_layout_data:
		room = room_layout_data.get("room", {})
		if isinstance(room, Mapping):
			room_width = _number(room.get("width"), 0)
			room_length = _number(room.get("length"), 0)
			room_height = _number(room.get("height"), 0)
			if room_width and room_length and room_height:
				room_mesh = pv.Box(
					bounds=(0, room_width, 0, room_length, 0, room_height)
				)
				plotter.add_mesh(room_mesh, style="wireframe", color="#475569", opacity=0.25)

	plotter.add_axes()
	plotter.show_grid()
	plotter.view_isometric()
	return plotter


def display_assets(
	asset_data: pd.DataFrame,
	room_layout_data: Mapping[str, object] | None = None,
) -> None:
	"""Build and display the 3D asset scene."""
	plotter = build_scene(asset_data, room_layout_data)
	plotter.show()
