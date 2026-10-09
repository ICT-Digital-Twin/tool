"""
This will load a yaml layout file and csv asset data files.
"""
from pathlib import Path
from io import BytesIO

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
        "SNMP", "SIZE", "POWERLOAD", "AIRFLOW DIRECTION", "FUNCTION"
    ]
    if list(asset_data.columns) == expected_columns:
        return "Schema validation PASSED"
    return "Schema validation FAILED"


def loadroom(file_data=None):
    """Load room layout YAML from a path or uploaded file bytes."""
    if not file_data:
        return None

    if isinstance(file_data, (bytes, bytearray)):
        room_layout_data = yaml.safe_load(file_data)
    else:
        with open(file_data, "r", encoding="utf-8") as file:
            room_layout_data = yaml.safe_load(file)

    return room_layout_data


def loadassets(asset_data_file=None, model_data_file=None):
    """Load and join asset CSV data from paths or uploaded file bytes."""
    if not asset_data_file or not model_data_file:
        return None

    asset_source = BytesIO(asset_data_file) if isinstance(asset_data_file, (bytes, bytearray)) else asset_data_file
    model_source = BytesIO(model_data_file) if isinstance(model_data_file, (bytes, bytearray)) else model_data_file
    asset_data = pd.read_csv(asset_source)
    model_data = pd.read_csv(model_source)
    asset_data = asset_data.merge(model_data, on="MODELNO", how="left")

    return asset_data.sort_values(
        by=["ROW", "RACK", "RACK_UNIT"],
        ascending=[True, True, False],
    )
