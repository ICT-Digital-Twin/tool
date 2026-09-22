"""
filemanager
This will load
yaml layout files, csv asset data files.
"""
from tkinter import Tk, filedialog
import yaml
from fileinput import filename
from pathlib import Path
from isort import file
import pandas as pd

def checkoutputdir(output_dir):
    output_path = Path(output_dir)
    if not output_path.exists():
        output_path.mkdir(parents=True)
        print(f"Created output directory: {output_dir}")
    else:
        print(f"Output directory exists: {output_dir}")

def loadroom():
    print("Select YAML file for room layout")
    def load(self, filepath):
        file = Path(filepath)

        if file.suffix == ".yaml":
            return pd.read_xml(file)

        raise ValueError(
        f"Unsupported file type: {file.suffix}"
        )

    room_layout_file = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[
            ("YAML files", "*.yaml")
        ]
    )

    with open(room_layout_file, "r") as f:
        room_layout_data = yaml.safe_load(f)

    return room_layout_data

def loadassets():
    print("Select CSVL file for asset data")
    asset_data_file = filedialog.askopenfilename(
        title="Select Asset Data CSV",
        filetypes=[
            ("CSV files", "*.csv"),
            ("All files", "*.*")
        ]
    )

    if not asset_data_file:
        return None # User cancelled

    asset_data = pd.read_csv(asset_data_file)

    return asset_data
