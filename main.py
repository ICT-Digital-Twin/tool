"""
ICT Digital Twin Tool
PD
2026
"""
import config
from modules.filemanager import checkoutputdir
from modules.interface import run_interface


def main():
    """ICT Digital Twin Tool main function."""
    checkoutputdir(config.OUTPUT_DIR)
    run_interface()


if __name__ == "__main__":
    main()
