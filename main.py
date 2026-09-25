"""
ICT Digital Twin Tool
main.py
PD
2026
"""
from modules.filemanager.filemanager import checkoutputdir, loadroom, loadassets
import pandas as pd
from pathlib import Path
# for testing: from pprint import pprint

output_dir = Path("data/output")

def main():
    # check if the output directory exists, if not create it
    checkoutputdir(output_dir)

    # select a room layout file in YAML format
    room_layout_data = loadroom()

    # just display the details for now
    room_width = room_layout_data["room"]["width"]
    room_length = room_layout_data["room"]["length"]
    room_height = room_layout_data["room"]["height"]
    power_feed_a_voltage = room_layout_data["power"]["feed_a_voltage"]
    power_feed_a_capacity = room_layout_data["power"]["feed_a_capacity"]
    power_feed_b_voltage = room_layout_data["power"]["feed_b_voltage"]
    power_feed_b_capacity = room_layout_data["power"]["feed_b_capacity"]
    print(f"Room dimensions: {room_width}m x {room_length}m x {room_height}m")
    print(f"Power feed A: {power_feed_a_voltage}V, {power_feed_a_capacity}A, B: {power_feed_b_voltage}V, {power_feed_b_capacity}A")

    # load asset data
    asset_data = loadassets()

    # validate the file structure
    expected_columns = [
    "INDEX",
    "NAME",
    "ROW",
    "RACK",
    "RACK_UNIT",
    "SIZE",
    "MODELNO"
    ]
     
    print(asset_data.columns.tolist())
    
    if list(asset_data.columns) == expected_columns:
        print("Schema validation PASSED")
    else:
        print("Schema validation FAILED")

    # print rack and device summary
    rack_counts = asset_data["RACK"].value_counts().to_dict()
    print(f"Rack counts: {rack_counts}")
    print(f"Unique devices: {asset_data['NAME'].nunique()}")
    print(f"Unique racks: {asset_data['RACK'].nunique()}")

    # print("\nDevices per rack:")
    # print(asset_data['RACK'].value_counts().sort_index())

    # this will display the room layout and asset data


    

if __name__ == "__main__":
    main()
