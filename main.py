"""
ICT Digital Twin Tool
main.py
PD
2026
"""
from modules.filemanager.filemanager import checkoutputdir, loadroom, loadassets
from modules.display.display import display_assets
from pathlib import Path

output_dir = Path("data/output")


def main():
    checkoutputdir(output_dir)

    room_layout_data = loadroom()
    if not room_layout_data:
        print("No room layout selected. Exiting.")
        return

    room_width = room_layout_data["room"]["width"]
    room_length = room_layout_data["room"]["length"]
    room_height = room_layout_data["room"]["height"]
    power_feed_a_voltage = room_layout_data["power"]["feed_a_voltage"]
    power_feed_a_capacity = room_layout_data["power"]["feed_a_capacity"]
    power_feed_b_voltage = room_layout_data["power"]["feed_b_voltage"]
    power_feed_b_capacity = room_layout_data["power"]["feed_b_capacity"]
    print(f"Room dimensions: {room_width}m x {room_length}m x {room_height}m")
    print(f"Power feed A: {power_feed_a_voltage}V, {power_feed_a_capacity}A, B: {power_feed_b_voltage}V, {power_feed_b_capacity}A")

    asset_data = loadassets()
    if asset_data is None:
        print("No asset data selected. Exiting.")
        return

    expected_columns = [
        "INDEX",
        "NAME",
        "ROW",
        "RACK",
        "RACK_UNIT",
        "SIZE",
        "MODELNO",
    ]

    print(asset_data.columns.tolist())

    if list(asset_data.columns) == expected_columns:
        print("Schema validation PASSED")
    else:
        print("Schema validation FAILED")

    rack_counts = asset_data["RACK"].value_counts().to_dict()
    print(f"Rack counts: {rack_counts}")
    print(f"Unique devices: {asset_data['NAME'].nunique()}")
    print(f"Unique racks: {asset_data['RACK'].nunique()}")

    display_assets(asset_data, room_layout_data)

if __name__ == "__main__":
    main()
