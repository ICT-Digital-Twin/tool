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
```INDEX  NAME  RACK  RACK_UNIT  SIZE  MODELNO```

### Display

Uses ```plotly``` to display data.


## Files

```console
c:\_Github Repositories\tool\.gitignore
c:\_Github Repositories\tool\data
c:\_Github Repositories\tool\docs
c:\_Github Repositories\tool\LICENSE
c:\_Github Repositories\tool\main.py
c:\_Github Repositories\tool\modules
c:\_Github Repositories\tool\README.md
c:\_Github Repositories\tool\docs\design.md
c:\_Github Repositories\tool\modules\display
c:\_Github Repositories\tool\modules\filemanager
c:\_Github Repositories\tool\modules\__init__.py
c:\_Github Repositories\tool\modules\display\display.py
c:\_Github Repositories\tool\modules\display\__init__.py
c:\_Github Repositories\tool\modules\filemanager\filemanager.py
c:\_Github Repositories\tool\modules\filemanager\__init__.py
c:\_Github Repositories\tool\output
```
