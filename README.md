# ICT Digital Twin tool 
## Input file requirements
### Room Layout (YAML)

Specifies room dimensions and power details

```yaml
room:
  width: width in metres
  length: length in metres
  height: height in metres

power:
  feed_a_voltage: Feed Voltage in volts
  feed_a_capacity: Feed Voltage in amps
  feed_b_voltage: Feed Voltage in volts
  feed_b_capacity: Feed Voltage in amps
```

### Asset Data

A CSV file with the following columns: ```INDEX  NAME  ROW  RACK  RACK_UNIT  MODELNO```

This is the asset database arranged into ROWs and RACKs.


### Asset details

A CSV file with the following columns: ```MODELNO  SIZE  POWERLOAD  AIRFLOW  DIRECTION  FUNCTION```

This is the model detail database to provide device charactestics.



