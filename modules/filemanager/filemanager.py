"""
Docstring for filemanager
This will load files and create and update temp files
"""

from fileinput import filename
from pathlib import Path
from isort import file
import pandas as pd

class filemanager:

    def load(self, filepath):

        file = Path(filepath)

        if file.suffix == ".yaml":
            return pd.read_xml(file)

        raise ValueError(
        f"Unsupported file type: {file.suffix}"
        )
