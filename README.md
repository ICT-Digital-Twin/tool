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
  feed_a_capacity: Feed capacity in watts
  feed_b_voltage: Feed Voltage in volts
  feed_b_capacity: Feed capacity in watts
```

For multiple feeds serving the same row, put the feed number in the row name.
The row's total feed capacity is the sum of its feeds.  
Individual feed capacities are shown as green dotted lines in the row powerload chart.

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


