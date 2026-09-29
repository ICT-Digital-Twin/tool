"""
This will load a yaml layout file and csv asset data files.
"""
from pathlib import Path

from tkinter import filedialog
import pandas as pd
import yaml

def checkoutputdir(output_dir):
    """Function checking if the output directory exists."""
    output_path = Path(output_dir)
    if not output_path.exists():
        output_path.mkdir(parents=True)
        print(f"Created output directory: {output_dir}")
    else:
        print(f"Output directory exists: {output_dir}")
    return output_path


def asset_schema_validation_message(asset_data):
    """Return the validation status for the merged asset data columns."""
    expected_columns = [
        "INDEX", "NAME", "ROW", "RACK", "RACK_UNIT", "MODELNO",
        "SIZE", "POWERLOAD", "AIRFLOW DIRECTION", "FUNCTION"
    ]
    if list(asset_data.columns) == expected_columns:
        return "Schema validation PASSED"
    return "Schema validation FAILED"


def loadroom(file_path=None):
    """Function to load a yaml file for room layout."""
    room_layout_file = file_path
    if room_layout_file is None:
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


def loadassets(asset_data_file=None, model_data_file=None):
    """Function to load asset data from CSV files."""
    if asset_data_file is None:
        print("Select CSV file for asset data")
        asset_data_file = filedialog.askopenfilename(
            title="Select Asset Data CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )

    if not asset_data_file:
        return None

    asset_data = pd.read_csv(asset_data_file)

    if model_data_file is None:
        print("Select CSV file for model details")
        model_data_file = filedialog.askopenfilename(
            title="Select Model Details CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )

    if not model_data_file:
        return None

    model_data = pd.read_csv(model_data_file)
    asset_data = asset_data.merge(model_data, on="MODELNO", how="left")

    return asset_data.sort_values(
        by=["ROW", "RACK", "RACK_UNIT"],
        ascending=[True, True, False],
    )
