"""Panel web interface for loading data and configuring the 3D view."""
from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import panel as pn
from panel.io.server import StoppableThread

import config
from modules.datadisplay import (
	VTK_INTERACTION_URL,
	build_data_layout,
	serve_layout,
)
from modules.display import build_scene
from modules.filemanager import asset_schema_validation_message, loadassets, loadroom


_SCENE_SETTINGS = {
	"RACK_WIDTH",
	"RACK_DEPTH",
	"RACK_UNIT_HEIGHT",
	"RACK_UNIT_COUNT",
	"RACK_GAP",
	"AISLE_WIDTH",
	"DEVICE_WIDTH_RATIO",
	"DEVICE_DEPTH_RATIO",
	"BACKGROUND_COLOR",
	"ROOM_COLOR",
	"RACK_COLOR",
	"DEVICE_COLOR",
	"DEVICE_EDGE_COLOR",
	"TEXT_COLOR",
	"RACK_LINE_WIDTH",
	"SHOW_DEVICE_EDGES",
}


def create_main_layout() -> pn.Column:
	"""Build the upload, configuration, and visualization page."""
	pn.config.respect_explicit_sizing = True
	pn.extension(
		"vtk",
		"plotly",
		"tabulator",
		js_files={"ict-digital-twin-z-up": VTK_INTERACTION_URL},
	)
	state: dict[str, object] = {
		"room_layout": None,
		"asset_data": None,
		"plotter": None,
		"asset_confirmation": None,
	}
	status = pn.pane.Alert(
		"Upload the room layout and both CSV files to build the digital twin.",
		alert_type="info",
		sizing_mode="stretch_width",
	)
	visualization = pn.Column(
		visible=False,
		sizing_mode="stretch_width",
	)
	title = pn.pane.Markdown("# Digital Twin")

	def format_room_title(room_layout: object) -> str:
		room_name = get_room_name(room_layout)
		return f"{room_name} Digital Twin" if room_name else "Digital Twin"

	def get_room_name(room_layout: object) -> str | None:
		if not isinstance(room_layout, Mapping):
			return None
		room = room_layout.get("room")
		if isinstance(room, Mapping):
			room_name = room.get("name") or room.get("room_name")
		else:
			room_name = room_layout.get("room_name") or room_layout.get("name")
		if not isinstance(room_name, str):
			return None
		room_name = room_name.strip()
		return room_name or None

	def update_snmp_community() -> None:
		asset_data = state["asset_data"]
		if isinstance(asset_data, pd.DataFrame):
			asset_data["SNMP_COMMUNITY"] = get_room_name(state["room_layout"])

	def set_title(room_layout: object) -> None:
		title.object = f"# {format_room_title(room_layout)}"

	def set_status(message: str, alert_type: str = "info") -> None:
		state["asset_confirmation"] = None
		status.object = message
		status.alert_type = alert_type
		status.visible = True

	def dismiss_asset_confirmation(message: str) -> None:
		if state["asset_confirmation"] == message:
			state["asset_confirmation"] = None
			status.visible = False

	def update_configuration_visibility() -> None:
		files_loaded = (
			isinstance(state["room_layout"], Mapping)
			and isinstance(state["asset_data"], pd.DataFrame)
		)
		configuration_section.visible = not files_loaded
		input_files_section.visible = not files_loaded

	def clear_visualization() -> None:
		plotter = state["plotter"]
		if plotter is not None:
			plotter.close()
			state["plotter"] = None
		set_title(state["room_layout"])
		visualization.objects = []
		visualization.visible = False

	def render_scene() -> None:
		asset_data = state["asset_data"]
		room_layout = state["room_layout"]
		if not isinstance(asset_data, pd.DataFrame) or not isinstance(room_layout, Mapping):
			return
		new_plotter = None
		try:
			new_plotter = build_scene(asset_data, room_layout)
			data_layout = build_data_layout(asset_data, new_plotter, room_layout)
		except Exception as error:
			if new_plotter is not None:
				new_plotter.close()
			visualization.objects = []
			visualization.visible = False
			set_status(f"Could not build the visualization: {error}", "danger")
			return
		previous_plotter = state["plotter"]
		state["plotter"] = new_plotter
		visualization.objects = [data_layout]
		visualization.visible = True
		confirmation = state["asset_confirmation"]
		if isinstance(confirmation, str):
			dismiss_asset_confirmation(confirmation)
		if previous_plotter is not None:
			previous_plotter.close()

	def update_setting(event: object, setting: str) -> None:
		value = event.new
		if setting == "OUTPUT_DIR":
			config.OUTPUT_DIR = Path(value)
		else:
			setattr(config, setting, value)
		if setting in ("RACK_UNIT_COUNT", "RACK_UNIT_HEIGHT"):
			config.RACK_HEIGHT = config.RACK_UNIT_COUNT * config.RACK_UNIT_HEIGHT
			rack_height.object = f"Rack height: {config.RACK_HEIGHT:.3f} m"
		if setting in _SCENE_SETTINGS:
			render_scene()

	def watch_setting(widget: object, setting: str) -> None:
		widget.param.watch(lambda event: update_setting(event, setting), "value")

	def update_function_color(event: object, category: str) -> None:
		config.FUNCTION_COLORS[category] = event.new
		render_scene()

	room_upload = pn.widgets.FileInput(label="Room layout YAML", accept=".yaml,.yml")
	asset_upload = pn.widgets.FileInput(label="Asset data CSV", accept=".csv")
	model_upload = pn.widgets.FileInput(label="Model details CSV", accept=".csv")

	def load_room(event: object) -> None:
		if not event.new:
			state["room_layout"] = None
			update_snmp_community()
			update_configuration_visibility()
			set_title(state["room_layout"])
			clear_visualization()
			return
		try:
			room_layout = loadroom(event.new)
			if not isinstance(room_layout, Mapping):
				raise ValueError("The selected YAML file must contain a mapping.")
		except Exception as error:
			state["room_layout"] = None
			update_snmp_community()
			update_configuration_visibility()
			set_title(state["room_layout"])
			clear_visualization()
			set_status(f"Could not load room layout: {error}", "danger")
			return
		state["room_layout"] = room_layout
		update_snmp_community()
		update_configuration_visibility()
		set_title(room_layout)
		set_status(f"Loaded room layout: {room_upload.filename}", "success")
		render_scene()

	def load_assets(_event: object) -> None:
		if not asset_upload.value or not model_upload.value:
			state["asset_data"] = None
			update_configuration_visibility()
			clear_visualization()
			if asset_upload.value:
				set_status("Asset CSV loaded. Add the model-details CSV to continue.")
			return
		try:
			asset_data = loadassets(asset_upload.value, model_upload.value)
			if asset_data is None:
				raise ValueError("Asset data was not loaded.")
		except Exception as error:
			state["asset_data"] = None
			update_configuration_visibility()
			clear_visualization()
			set_status(f"Could not load asset data: {error}", "danger")
			return
		validation = asset_schema_validation_message(asset_data)
		state["asset_data"] = asset_data
		update_snmp_community()
		update_configuration_visibility()
		message = (
			f"Loaded {len(asset_data)} assets from {asset_upload.filename} and {model_upload.filename}. "
			f"{validation}"
		)
		alert_type = "success" if validation.endswith("PASSED") else "warning"
		set_status(message, alert_type)
		if alert_type == "success":
			state["asset_confirmation"] = message
			pn.state.add_periodic_callback(
				lambda: dismiss_asset_confirmation(message),
				period=5000,
				count=1,
			)
		render_scene()

	room_upload.param.watch(load_room, "value")
	asset_upload.param.watch(load_assets, "value")
	model_upload.param.watch(load_assets, "value")

	output_directory = pn.widgets.TextInput(
		label="Output directory",
		value=str(config.OUTPUT_DIR),
	)
	watch_setting(output_directory, "OUTPUT_DIR")
	layout_controls = [output_directory]
	for label, setting in (
		("Rack width (m)", "RACK_WIDTH"),
		("Rack depth (m)", "RACK_DEPTH"),
		("Rack-unit height (m)", "RACK_UNIT_HEIGHT"),
		("Rack gap (m)", "RACK_GAP"),
		("Aisle width (m)", "AISLE_WIDTH"),
		("Device width ratio", "DEVICE_WIDTH_RATIO"),
		("Device depth ratio", "DEVICE_DEPTH_RATIO"),
	):
		control = pn.widgets.FloatInput(
			label=label,
			value=getattr(config, setting),
			start=0,
			end=10,
			step=0.01,
		)
		watch_setting(control, setting)
		layout_controls.append(control)

	rack_count = pn.widgets.IntInput(
		label="Rack-unit count",
		value=config.RACK_UNIT_COUNT,
		start=1,
		end=100,
		step=1,
	)
	watch_setting(rack_count, "RACK_UNIT_COUNT")
	layout_controls.append(rack_count)
	rack_height = pn.pane.Markdown(f"Rack height: {config.RACK_HEIGHT:.3f} m")
	layout_controls.append(rack_height)

	color_controls = []
	for label, setting in (
		("Background", "BACKGROUND_COLOR"),
		("Room", "ROOM_COLOR"),
		("Rack", "RACK_COLOR"),
		("Device", "DEVICE_COLOR"),
		("Device edges", "DEVICE_EDGE_COLOR"),
		("Text", "TEXT_COLOR"),
	):
		control = pn.widgets.ColorPicker(label=label, value=getattr(config, setting))
		watch_setting(control, setting)
		color_controls.append(control)

	rack_line_width = pn.widgets.FloatInput(
		label="Rack line width",
		value=config.RACK_LINE_WIDTH,
		start=0,
		end=10,
		step=0.5,
	)
	watch_setting(rack_line_width, "RACK_LINE_WIDTH")
	color_controls.append(rack_line_width)
	for category, color in config.FUNCTION_COLORS.items():
		control = pn.widgets.ColorPicker(label=f"{category} function", value=color)
		control.param.watch(lambda event, key=category: update_function_color(event, key), "value")
		color_controls.append(control)

	show_device_edges = pn.widgets.Checkbox(
		label="Show device edges",
		value=config.SHOW_DEVICE_EDGES,
	)
	watch_setting(show_device_edges, "SHOW_DEVICE_EDGES")
	color_controls.append(show_device_edges)

	configuration = pn.Accordion(
		("Options", pn.Column(*layout_controls, sizing_mode="stretch_width")),
		("Colors", pn.Column(*color_controls, sizing_mode="stretch_width")),
		active=[],
		sizing_mode="stretch_width",
	)
	configuration_section = pn.Column(
		pn.pane.Markdown("## Configuration"),
		configuration,
		sizing_mode="stretch_width",
	)
	uploads = pn.Row(room_upload, asset_upload, model_upload, sizing_mode="stretch_width")
	input_files_section = pn.Column(
		pn.pane.Markdown("## Input files"),
		uploads,
		sizing_mode="stretch_width",
	)
	return pn.Column(
		title,
		configuration_section,
		input_files_section,
		status,
		visualization,
		sizing_mode="stretch_width",
	)


def run_interface() -> None:
	"""Start the single-page web application in the default browser."""
	server_thread: StoppableThread | None = None

	def stop_server(_session_context: object) -> None:
		if server_thread is not None:
			server_thread.stop()

	layout = create_main_layout()
	pn.state.on_session_destroyed(stop_server)
	server_thread = serve_layout(layout, threaded=True)
	server_thread.join()
