# ICT Digital Twin tool 
## Running the application

Install the packages listed in `requirements.txt`, then run:

```console
python main.py
```

The application opens in your default browser. Upload the room YAML, asset CSV, and model-details CSV on the main page; the configuration controls and combined 3D and inventory views are available there.

## Input file requirements
### Room Layout (YAML)

Specifies room dimensions and power details

```yaml
room:
  name: room name
  width: width in metres
  length: length in metres
  height: height in metres

power:
  feed_a_voltage: Feed Voltage in volts
  feed_a_capacity: Feed capacity in watts
  feed_b_voltage: Feed Voltage in volts
  feed_b_capacity: Feed capacity in watts
```

For multiple feeds serving the same row, put the feed number in the row name.
The row's total feed capacity is the sum of its feeds.  
Individual feed capacities are shown as green dotted lines in the row powerload chart.
The row powerload chart shows two grouped bars per row, and the rack chart shows two grouped bars per rack: half of the total powerload on Feed 1 (blue) and half on Feed 2 (red).

```yaml
power:
  feed_a1_capacity: 40000
  feed_a2_capacity: 40000
  feed_b1_capacity: 40000
  feed_b2_capacity: 40000
```

### Asset Data

A CSV file with the following columns:  
```INDEX  NAME  ROW  RACK  RACK_UNIT  MODELNO```

This is the asset database arranged into ROWs and RACKs.


### Asset details

A CSV file with the following columns:  
```MODELNO  SIZE  POWERLOAD  AIRFLOW  DIRECTION  FUNCTION```

This is the model detail database to provide device charactestics.
