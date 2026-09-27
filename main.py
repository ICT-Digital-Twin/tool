"""
ICT Digital Twin Tool
PD
2026
"""
from config import OUTPUT_DIR
from modules.filemanager import checkoutputdir, loadroom, loadassets
from modules.display import display_assets


def main():
    """ICT Digital Twin Tool entry point."""
    checkoutputdir(OUTPUT_DIR)

    room_layout_data = loadroom()
    if not room_layout_data:
        print("No room layout selected. Exiting.")
        return

    asset_data = loadassets()
    if asset_data is None:
        print("No asset data selected. Exiting.")
        return

    display_assets(asset_data, room_layout_data)


if __name__ == "__main__":
    main()
