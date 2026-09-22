"""
ICT Digital Twin Tool
main.py
PD
2026
"""

from modules.filemanager.filemanager import filemanager as fm, filename
from tkinter import Tk, filedialog
import yaml
# for testing
# from pprint import pprint

def main():
    # select a room layout file
    room_layout_file = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[
            ("YAML files", "*.yaml")
        ]
    )

    with open(room_layout_file, "r") as f:
        room_layout_data = yaml.safe_load(f)
    
    room_width = room_layout_data["room"]["width"]
    room_length = room_layout_data["room"]["length"]
    room_height = room_layout_data["room"]["height"]
    power_feed_a_voltage = room_layout_data["power"]["feed_a_voltage"]
    power_feed_a_capacity = room_layout_data["power"]["feed_a_capacity"]
    power_feed_b_voltage = room_layout_data["power"]["feed_b_voltage"]
    power_feed_b_capacity = room_layout_data["power"]["feed_b_capacity"]

if __name__ == "__main__":
    main()