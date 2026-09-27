# Project Structure

## Modules

### config.py

Contains default configuration values with dimensions in metres.

```pyton
RACK_WIDTH = 0.8
RACK_DEPTH = 1.0
RACK_UNIT_HEIGHT = 0.04445
RACK_UNIT_COUNT = 42
RACK_HEIGHT = RACK_UNIT_COUNT * RACK_UNIT_HEIGHT
RACK_GAP = 0.003
AISLE_WIDTH = 1.0
DEVICE_WIDTH_RATIO = 0.9
DEVICE_DEPTH_RATIO = 0.9
```

and Pyvista and colour default settings

```python
BACKGROUND_COLOR = "#17202a"
ROOM_COLOR = "#475569"
ROOM_OPACITY = 0.25
RACK_COLOR = "#8fa3b8"
RACK_LINE_WIDTH = 2
DEVICE_COLOR = "#3b38f8"
FUNCTION_COLORS = {
    "Compute": "#3a7fc9",
    "Storage": "#9b6e32",
    "Network": "#389a7e",
    "Other": "#865cb0",
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
```

### filemanager.py

This modules contains ```loadroom``` and ```loadassets``` functions.

#### loadroom

Takes a YAML file as an input and expects the following blocks, keys and values:

```yaml
room:
  width: width in metres
  length: length in metres
  height: height in metres

power:
  feed_a_voltage: Feed Voltage in volts
  feed_a_capacity: Feed Voltage in volts
  feed_b_voltage: Feed Voltage in volts
  feed_b_capacity: Feed Voltage in volts
```

#### loadassets

Takes a CSV file as an input with the asset database, one device per row, with the following headers:  
```INDEX  NAME  ROW  RACK  RACK_UNIT  SIZE  MODELNO```

### Display

Uses ```pyvista``` to display data.

Use left click to rotate the view.  Use mouse wheel/right click to zoom.

Use shift-left click to pan.

Mouseover any device to view asset data.


#### Display logic

The ROW field is used to distribute racks per row.  Rows are rendered in pairs...




## Files

```console
C:\_Github Repositories\tool\.gitignore
C:\_Github Repositories\tool\data
C:\_Github Repositories\tool\docs
C:\_Github Repositories\tool\LICENSE
C:\_Github Repositories\tool\main.py
C:\_Github Repositories\tool\modules
C:\_Github Repositories\tool\README.md
C:\_Github Repositories\tool\requirements.txt
C:\_Github Repositories\tool\tests
C:\_Github Repositories\tool\data\output
C:\_Github Repositories\tool\data\sample_input
C:\_Github Repositories\tool\data\output\testoutput.html
C:\_Github Repositories\tool\data\output\testoutput.png
C:\_Github Repositories\tool\data\sample_input\generated_asset_data.csv
C:\_Github Repositories\tool\data\sample_input\generated_asset_data_II.csv
C:\_Github Repositories\tool\data\sample_input\model_data.csv
C:\_Github Repositories\tool\data\sample_input\yaml_test.yaml
C:\_Github Repositories\tool\docs\design.md
C:\_Github Repositories\tool\modules\display
C:\_Github Repositories\tool\modules\filemanager
C:\_Github Repositories\tool\modules\__init__.py
C:\_Github Repositories\tool\modules\display\display.py
C:\_Github Repositories\tool\modules\display\__init__.py
C:\_Github Repositories\tool\modules\filemanager\filemanager.py
C:\_Github Repositories\tool\modules\filemanager\__init__.py
C:\_Github Repositories\tool\tests\test_project_validation.py
```
