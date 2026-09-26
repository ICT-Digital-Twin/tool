# Project Structure

## Modules

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
