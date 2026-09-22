"""
ICT Digital Twin Tool
main.py
PD
2026
"""
from modules.filemanager.filemanager import loadroom, loadassets
# for testing: from pprint import pprint

def main():
    # select a room layout file
    room_layout_data = loadroom()
    
    room_width = room_layout_data["room"]["width"]
    room_length = room_layout_data["room"]["length"]
    room_height = room_layout_data["room"]["height"]
    power_feed_a_voltage = room_layout_data["power"]["feed_a_voltage"]
    power_feed_a_capacity = room_layout_data["power"]["feed_a_capacity"]
    power_feed_b_voltage = room_layout_data["power"]["feed_b_voltage"]
    power_feed_b_capacity = room_layout_data["power"]["feed_b_capacity"]
    print(f"Room dimensions: {room_width}m x {room_length}m x {room_height}m")
    print(f"Power feed A: {power_feed_a_voltage}V, {power_feed_a_capacity}A")
    print(f"Power feed B: {power_feed_b_voltage}V, {power_feed_b_capacity}A")

    # load asset data
    asset_data = loadassets()
    print(asset_data)


if __name__ == "__main__":
    main()