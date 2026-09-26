"""
filemanager
This will load
yaml layout files, csv asset data files.
"""
from pathlib import Path

import pandas as pd
import yaml
from tkinter import filedialog


def checkoutputdir(output_dir):
    output_path = Path(output_dir)
    if not output_path.exists():
        output_path.mkdir(parents=True)
        print(f"Created output directory: {output_dir}")
    else:
        print(f"Output directory exists: {output_dir}")
    return output_path


def loadroom():
    print("Select YAML file for room layout")
    room_layout_file = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[("YAML files", "*.yaml"), ("YAML files", "*.yml")],
    )

    if not room_layout_file:
        return None

    with open(room_layout_file, "r", encoding="utf-8") as file:
        room_layout_data = yaml.safe_load(file)

    return room_layout_data


def loadassets():
    print("Select CSV file for asset data")
    asset_data_file = filedialog.askopenfilename(
        title="Select Asset Data CSV",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )

    if not asset_data_file:
        return None

    asset_data = pd.read_csv(asset_data_file)
    return asset_data.sort_values(
        by=["ROW", "RACK", "RACK_UNIT"],
        ascending=[True, True, False],
    )
