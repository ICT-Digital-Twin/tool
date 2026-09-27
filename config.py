"""Application paths, scene dimensions, and PyVista appearance settings."""
from pathlib import Path

import pyvista as pv


OUTPUT_DIR = Path("data/output")

RACK_WIDTH = 0.8
RACK_DEPTH = 1.0
RACK_UNIT_HEIGHT = 0.04445
RACK_UNIT_COUNT = 42
RACK_HEIGHT = RACK_UNIT_COUNT * RACK_UNIT_HEIGHT
RACK_GAP = 0.003
AISLE_WIDTH = 1.0
DEVICE_WIDTH_RATIO = 0.9
DEVICE_DEPTH_RATIO = 0.9

PYVISTA_THEME = pv.themes.DarkTheme
BACKGROUND_COLOR = "#17202a"
ROOM_COLOR = "#475569"
ROOM_OPACITY = 0.25
RACK_COLOR = "#8fa3b8"
RACK_LINE_WIDTH = 2
DEVICE_COLOR = "#3b38f8"
FUNCTION_COLORS = {
    "Compute": "#4ea5ff",
    "Storage": "#ffb454",
    "Network": "#50d6b0",
    "Other": "#c084fc",
}
FUNCTION_COLOR_HUE_STEP = 0.4
FUNCTION_COLOR_SATURATION = 0.72
FUNCTION_COLOR_BRIGHTNESS = 0.95
DEVICE_EDGE_COLOR = "#d8f3ff"
SHOW_DEVICE_EDGES = True
TEXT_COLOR = "#f8fafc"
HOVER_FONT_SIZE = 10
HOVER_TEXT_POSITION = (0.02, 0.98)
ROOM_RENDER_STYLE = "wireframe"
RACK_RENDER_STYLE = "wireframe"
GRID_SHOW_AXIS_LABELS = False
GRID_AXIS_TITLE = ""
ENABLE_TERRAIN_STYLE = True
CAMERA_UP = (0, 0, 1)


def create_pyvista_theme() -> pv.themes.Theme:
    """Create a PyVista theme using the configured base and scene colors."""
    theme = PYVISTA_THEME()
    theme.background = BACKGROUND_COLOR
    theme.font.color = TEXT_COLOR
    theme.edge_color = DEVICE_EDGE_COLOR
    return theme
