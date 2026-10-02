"""Dear PyGui interface for loading data and opening the 3D view."""
from collections.abc import Mapping
from pathlib import Path
from tkinter import filedialog
from typing import Any, TypedDict

import dearpygui.dearpygui as dpg
import pandas as pd

import config
from modules.datadisplay import display_data
from modules.display import build_scene
from modules.filemanager import asset_schema_validation_message, loadassets, loadroom


class InterfaceState(TypedDict):
	"""Loaded room and asset inputs used by the interface callbacks."""
	room_layout: Mapping[str, object] | None
	asset_path: str | None
	model_path: str | None
	asset_data: pd.DataFrame | None


def _stop_web_servers(servers: list[Any]) -> None:
	"""Stop and clear the threaded visualization servers."""
	for server in servers:
		server.stop()
		server.join()
	servers.clear()


def _shutdown_interface(servers: list[Any]) -> None:
	"""Stop any active web servers and close the Dear PyGui context safely."""
	_stop_web_servers(servers)
	try:
		if dpg.is_dearpygui_running():
			dpg.stop_dearpygui()
	except Exception:
		pass
	try:
		dpg.destroy_context()
	except Exception:
		pass


def run_interface() -> None:
	"""Create and run the application interface."""
	web_servers: list[Any] = []
	state: InterfaceState = {
		"room_layout": None,
		"asset_path": None,
		"model_path": None,
		"asset_data": None,
	}

	def select_file(title: str, filetypes: list[tuple[str, str]]) -> str:
		"""Open a native Tkinter file chooser and return the selected path."""
		return filedialog.askopenfilename(title=title, filetypes=filetypes)

	def set_status(message: str) -> None:
		dpg.set_value("status_label", message)

	def update_view_button() -> None:
		ready = state["room_layout"] is not None and state["asset_data"] is not None
		dpg.configure_item("view_button", enabled=ready)

	def load_room_callback(_sender: int = 0, _app_data: object = None, _user_data: object = None) -> None:
		file_path = select_file(
			"Select room layout",
			[("YAML files", "*.yaml"), ("YAML files", "*.yml")],
		)
		if not file_path:
			return
		try:
			room_layout = loadroom(file_path)
			if room_layout is None:
				raise ValueError("The selected YAML file is empty.")
		except Exception as error:
			set_status(f"Could not load room layout: {error}")
			return
		state["room_layout"] = room_layout
		dpg.set_value("room_file_label", Path(file_path).name)
		set_status("Room layout loaded.")
		update_view_button()

	def load_asset_callback(_sender: int = 0, _app_data: object = None, _user_data: object = None) -> None:
		file_path = select_file(
			"Select asset data CSV",
			[("CSV files", "*.csv"), ("All files", "*.*")],
		)
		if not file_path:
			return
		state["asset_path"] = file_path
		state["model_path"] = None
		state["asset_data"] = None
		dpg.set_value("asset_file_label", Path(file_path).name)
		dpg.set_value("model_file_label", "Not selected")
		dpg.configure_item("model_button", enabled=True)
		set_status("Asset CSV selected. Select the model-details CSV to continue.")
		update_view_button()

	def load_model_callback(_sender: int = 0, _app_data: object = None, _user_data: object = None) -> None:
		file_path = select_file(
			"Select model details CSV",
			[("CSV files", "*.csv"), ("All files", "*.*")],
		)
		if not file_path:
			return
		if state["asset_path"] is None:
			set_status("Select the asset CSV first.")
			return
		state["model_path"] = file_path
		try:
			asset_data = loadassets(state["asset_path"], file_path)
		except Exception as error:
			state["asset_data"] = None
			set_status(f"Could not load asset data: {error}")
			update_view_button()
			return
		if asset_data is None:
			set_status("Asset data was not loaded.")
			return
		state["asset_data"] = asset_data
		dpg.set_value("model_file_label", Path(file_path).name)
		set_status(f"Loaded {len(asset_data)} assets.\n{asset_schema_validation_message(asset_data)}")
		update_view_button()

	def update_config_value(_sender: int, value: object, setting: str) -> None:
		if setting == "OUTPUT_DIR":
			if isinstance(value, str):
				config.OUTPUT_DIR = Path(value)
		elif setting == "CAMERA_UP":
			if isinstance(value, (tuple, list)):
				setattr(config, setting, tuple(float(component) for component in value))
		else:
			setattr(config, setting, value)
		if setting in ("RACK_UNIT_COUNT", "RACK_UNIT_HEIGHT"):
			config.RACK_HEIGHT = config.RACK_UNIT_COUNT * config.RACK_UNIT_HEIGHT
			dpg.set_value("rack_height_value", f"{config.RACK_HEIGHT:.3f} m")

	def update_theme(_sender: int, value: str, _user_data: object = None) -> None:
		import pyvista as pv
		config.PYVISTA_THEME = getattr(pv.themes, value)

	def update_color(_sender: int, value: list[int], setting: str | tuple[str, str]) -> None:
		color = "#" + "".join(f"{round(channel):02x}" for channel in value[:3])
		if isinstance(setting, tuple):
			config.FUNCTION_COLORS[setting[1]] = color
		else:
			setattr(config, setting, color)

	def color_value(color: str) -> tuple[int, int, int, int]:
		return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5)) + (255,)

	def add_float_option(
		label: str,
		setting: str,
		minimum: float = 0.0,
		maximum: float = 100.0,
		step: float = 0.01,
	) -> None:
		dpg.add_input_float(
			label=label,
			default_value=getattr(config, setting),
			min_value=minimum,
			max_value=maximum,
			min_clamped=True,
			max_clamped=True,
			step=step,
			callback=update_config_value,
			user_data=setting,
		)

	def add_color_option(label: str, setting: str | tuple[str, str], color: str) -> None:
		dpg.add_color_edit(
			label=label,
			default_value=color_value(color),
			no_alpha=True,
			callback=update_color,
			user_data=setting,
		)

	def open_view(_sender: int, _app_data: object, _user_data: object = None) -> None:
		asset_data = state["asset_data"]
		room_layout = state["room_layout"]
		if asset_data is None or room_layout is None:
			return
		try:
			plotter = build_scene(asset_data, room_layout)
			web_servers.append(display_data(asset_data, plotter, room_layout))
		except Exception as error:
			set_status(f"Could not open combined view: {error}")

	def close_viewport(_sender: int = 0, _app_data: object = None, _user_data: object = None) -> None:
		_shutdown_interface(web_servers)

	try:
		dpg.create_context()
		dpg.configure_app(manual_callback_management=True)
		with dpg.window(label="ICT Digital Twin", tag="main_window", width=640, height=640):
			dpg.add_text("Load the room layout and both data files")
			dpg.add_separator()
			dpg.add_button(label="Load room layout YAML", callback=load_room_callback, width=220)
			dpg.add_text("Not selected", tag="room_file_label")
			dpg.add_spacer(height=6)
			dpg.add_button(label="Load asset data CSV", callback=load_asset_callback, width=220)
			dpg.add_text("Not selected", tag="asset_file_label")
			dpg.add_spacer(height=6)
			dpg.add_button(label="Load model details CSV", tag="model_button", enabled=False, callback=load_model_callback, width=220)
			dpg.add_text("Not selected", tag="model_file_label")
			dpg.add_separator()
			dpg.add_button(label="Open 3D view", tag="view_button", enabled=False, callback=open_view, width=220)
			dpg.add_button(label="Configuration", callback=lambda: dpg.show_item("config_window"), width=220)
			dpg.add_text("Select all three files to enable the 3D view.", tag="status_label", wrap=490)

		with dpg.window(label="Configuration", tag="config_window", width=620, height=720, show=False, modal=True):
			with dpg.collapsing_header(label="Files and layout", default_open=True):
				dpg.add_input_text(
					label="Output directory",
					default_value=str(config.OUTPUT_DIR),
					callback=update_config_value,
					user_data="OUTPUT_DIR",
				)
				for label, setting in (
					("Rack width (m)", "RACK_WIDTH"),
					("Rack depth (m)", "RACK_DEPTH"),
					("Rack-unit height (m)", "RACK_UNIT_HEIGHT"),
					("Rack gap (m)", "RACK_GAP"),
					("Aisle width (m)", "AISLE_WIDTH"),
					("Device width ratio", "DEVICE_WIDTH_RATIO"),
					("Device depth ratio", "DEVICE_DEPTH_RATIO"),
				):
					add_float_option(label, setting, maximum=10.0)
				dpg.add_input_int(
					label="Rack-unit count",
					default_value=config.RACK_UNIT_COUNT,
					min_value=1,
					max_value=100,
					min_clamped=True,
					max_clamped=True,
					callback=update_config_value,
					user_data="RACK_UNIT_COUNT",
				)
				dpg.add_text(f"Rack height: {config.RACK_HEIGHT:.3f} m", tag="rack_height_value")

			with dpg.collapsing_header(label="Colors", default_open=True):
				for label, setting in (
					("Background", "BACKGROUND_COLOR"),
					("Room", "ROOM_COLOR"),
					("Rack", "RACK_COLOR"),
					("Device", "DEVICE_COLOR"),
					("Device edges", "DEVICE_EDGE_COLOR"),
					("Text", "TEXT_COLOR"),
				):
					add_color_option(label, setting, getattr(config, setting))
				add_float_option("Rack line width", "RACK_LINE_WIDTH", maximum=10.0)
				for category, color in config.FUNCTION_COLORS.items():
					add_color_option(category, ("FUNCTION_COLORS", category), color)
				dpg.add_checkbox(
					label="Show device edges",
					default_value=config.SHOW_DEVICE_EDGES,
					callback=update_config_value,
					user_data="SHOW_DEVICE_EDGES",
				)

			dpg.add_button(label="Close", callback=lambda: dpg.hide_item("config_window"), width=100)

		dpg.create_viewport(title="ICT Digital Twin", width=640, height=640)
		dpg.set_exit_callback(close_viewport)
		dpg.setup_dearpygui()
		dpg.show_viewport()
		dpg.set_primary_window("main_window", True)
		while dpg.is_dearpygui_running():
			callbacks = dpg.get_callback_queue()
			dpg.run_callbacks(callbacks)
			dpg.render_dearpygui_frame()
	finally:
		_shutdown_interface(web_servers)
