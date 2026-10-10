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
  feed_a1_capacity: 20000
  feed_a2_capacity: 20000
  feed_b1_capacity: 20000
  feed_b2_capacity: 20000
  feed_c1_capacity: 20000
  feed_c2_capacity: 20000
  feed_d1_capacity: 20000
  feed_d2_capacity: 20000
  rpdu_capacity: 14000
```

#### loadassets

Takes a CSV file as an input with the asset database, one device per row, with the following headers:  
```INDEX  NAME  ROW  RACK  RACK_UNIT  MODELNO  SNMP```

`SNMP` contains the device hostname used by the SNMP poller. Imported assets
receive an `SNMP_COMMUNITY` value from the room `name` in the layout YAML.

The SNMP panel polls the local simulator at `127.0.0.1:1161` immediately when
the SNMP view is selected, then every `SNMP_REFRESH_SECONDS` seconds (30 by
default, configured in `config.py`). Polling stops when the Asset data view is
selected. The poll button can request an immediate update. It uses SNMP v2c,
each asset's `SNMP` name, lowercased, and the room name as the community string
prefix (for example, `DemoColo-01/tora01a`). The PyVista view uses green for
successful (`OK`) polls, yellow for an explicit `Warning` status, and red for
other statuses; switching back to Asset data restores the asset-function
colors. It queries system metadata and plots the device's reported temperature
trend in the SNMP panel, plus the vendor-specific serial OID selected by the
device-name prefix, matching `sweep.py`. Temperature readings use the Dell
PowerEdge sensor OID `1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1` for server
families, the Cisco entity-sensor OID
`1.3.6.1.4.1.9.9.91.1.1.1.1.4.1` for ToR switches, the PowerStore scalar
`1.3.6.1.4.1.674.11000.1.5.1.1.0` for SAN controllers, the Dell core-switch
scalar `1.3.6.1.4.1.6027.3.1.1.1.5.0`, and the Brocade SAN-switch scalar
`1.3.6.1.4.1.1588.2.1.1.1.5.0`. Temperature values are already in degrees
Celsius and are displayed without unit conversion. The simulator returned
`35` for both devices in each of these families during validation. The standard
`sysUpTime.0` value is TimeTicks (hundredths of a second), so the poller
divides it by 100 to report seconds. A missing sensor reading stays missing
instead of being replaced with system uptime.

### Display

Uses ```pyvista``` to display data.

Use left click to rotate the view.  Use mouse wheel/right click to zoom.

Use shift-left click to pan.

The row and rack powerload charts have separate Feed 1 and Feed 2 toggles for
each displayed row, grouped under "Power feed toggle". Feed 1 is blue and
Feed 2 is red. Disabling one feed moves that row's full load to its remaining
feed on both charts. Capacity reference lines in the row chart are red and
dotted; the rack chart shows the configured RPDU capacity as a red dotted line
when an active feed exceeds it.

Mouseover any device to view asset data.


#### Display logic

The ROW field is used to distribute racks per row.  Rows are rendered in pairs...


## Running on a VM

[ document the fix for the omesa.dll problem on VMs here ]

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
