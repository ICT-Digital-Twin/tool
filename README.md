# ICT Digital Twin tool 
## Running the application

Install the packages listed in `requirements.txt`, then run:

```console
python main.py
```

The application opens in your default browser. Upload the room YAML, asset CSV, and model-details CSV on the main page; the configuration controls and combined 3D and inventory views are available there. Use the selector above the right-hand panel to switch between asset data and the SNMP chart template. The SNMP panel is a placeholder and does not connect to or poll SNMP devices yet.

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

> add notes about the feed logic

```yaml
power:
  feed_a1_capacity: 40000
  feed_a2_capacity: 40000
  feed_b1_capacity: 40000
  feed_b2_capacity: 40000
```

### Asset Data

A CSV file with the following columns:  
```INDEX  NAME  ROW  RACK  RACK_UNIT  MODELNO  SNMP```

This is the asset database arranged into ROWs and RACKs. `SNMP` is the
device's SNMP context selector ID. The imported asset data also includes
`SNMP_COMMUNITY`, populated from the room's `name` in the YAML file.


### Asset details

A CSV file with the following columns:  
```MODELNO  SIZE  POWERLOAD  AIRFLOW  DIRECTION  FUNCTION```

This is the model detail database to provide device charactestics.
