import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pyvista as pv

from main import main
from modules.filemanager.filemanager import asset_schema_validation_message, checkoutputdir, loadassets


class ProjectValidationTests(unittest.TestCase):
    def test_pyvista_and_dearpygui_can_be_imported_in_order(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pyvista; import dearpygui.dearpygui as dpg; print('ok', dpg.__file__)",
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)

    def test_asset_schema_validation_message_reports_matching_columns(self):
        asset_data = pd.DataFrame(columns=[
            "INDEX", "NAME", "ROW", "RACK", "RACK_UNIT", "MODELNO",
            "SIZE", "POWERLOAD", "AIRFLOW DIRECTION", "FUNCTION",
        ])

        self.assertEqual(asset_schema_validation_message(asset_data), "Schema validation PASSED")

    def test_asset_schema_validation_message_reports_mismatched_columns(self):
        asset_data = pd.DataFrame(columns=["NAME", "ROW"])

        self.assertEqual(asset_schema_validation_message(asset_data), "Schema validation FAILED")

    def test_loadassets_sorts_by_row_rack_and_descending_rack_unit(self):
        asset_data = pd.DataFrame(
            [
                {"ROW": 2, "RACK": "RACK-01", "RACK_UNIT": 1, "MODELNO": "MODEL"},
                {"ROW": 1, "RACK": "RACK-02", "RACK_UNIT": 2, "MODELNO": "MODEL"},
                {"ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 3, "MODELNO": "MODEL"},
                {"ROW": 1, "RACK": "RACK-02", "RACK_UNIT": 10, "MODELNO": "MODEL"},
                {"ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 40, "MODELNO": "MODEL"},
            ]
        )
        model_data = pd.DataFrame(columns=["MODELNO", "POWERLOAD", "AIRFLOW DIRECTION", "FUNCTION"])

        with patch(
            "modules.filemanager.filemanager.filedialog.askopenfilename",
            side_effect=["assets.csv", "model_details.csv"],
        ), patch(
            "modules.filemanager.filemanager.pd.read_csv",
            side_effect=[asset_data, model_data],
        ):
            sorted_data = loadassets()

        assert sorted_data is not None
        self.assertEqual(
            list(sorted_data[["ROW", "RACK", "RACK_UNIT"]].itertuples(index=False, name=None)),
            [
                (1, "RACK-01", 40),
                (1, "RACK-01", 3),
                (1, "RACK-02", 10),
                (1, "RACK-02", 2),
                (2, "RACK-01", 1),
            ],
        )

    def test_loadassets_joins_model_details_by_modelno(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "Asset 1", "ROW": 1, "RACK": "A01", "RACK_UNIT": 1, "MODELNO": "R670"},
                {"NAME": "Asset 2", "ROW": 1, "RACK": "A01", "RACK_UNIT": 2, "MODELNO": "UNKNOWN"},
            ]
        )
        model_data = pd.DataFrame(
            [
                {
                    "MODELNO": "R670",
                    "POWERLOAD": 450,
                    "AIRFLOW": "Front",
                    "DIRECTION": "Rear",
                    "FUNCTION": "Compute",
                }
            ]
        )

        with patch(
            "modules.filemanager.filemanager.filedialog.askopenfilename",
            side_effect=["assets.csv", "model_details.csv"],
        ), patch(
            "modules.filemanager.filemanager.pd.read_csv",
            side_effect=[asset_data, model_data],
        ):
            joined_data = loadassets()

        assert joined_data is not None
        self.assertEqual(joined_data.loc[0, "POWERLOAD"], 450)
        self.assertEqual(joined_data.loc[0, "AIRFLOW"], "Front")
        self.assertEqual(joined_data.loc[0, "DIRECTION"], "Rear")
        self.assertTrue(pd.isna(joined_data.loc[1, "POWERLOAD"]))

    def test_checkoutputdir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "nested" / "output"
            created_dir = checkoutputdir(output_dir)
            self.assertTrue(created_dir.exists())
            self.assertTrue(created_dir.is_dir())

    def test_main_starts_interface_after_checking_output_directory(self):
        with patch("main.checkoutputdir") as mock_check, patch("main.run_interface") as mock_interface:
            main()

        mock_check.assert_called_once()
        mock_interface.assert_called_once_with()

    def test_function_colors_use_live_configuration(self):
        from modules.display.display import _function_colors

        asset_data = pd.DataFrame({"FUNCTION": ["Compute", "Unclassified"]})
        with patch("config.FUNCTION_COLORS", {"Compute": "#010203", "Other": "#040506"}), patch(
            "config.FUNCTION_COLOR_SATURATION",
            0.1,
        ):
            colors = _function_colors(asset_data)

        self.assertEqual(colors["Compute"], "#010203")
        self.assertNotEqual(colors["Unclassified"], "#040506")

    def test_build_scene_accepts_valid_asset_dataframe(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 2, "SIZE": 2},
            ]
        )

        from modules.display.display import build_scene

        plotter = build_scene(asset_data)
        self.assertIsNotNone(plotter)

    def test_build_scene_colors_devices_by_function(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1, "FUNCTION": "Compute"},
                {"NAME": "ASSET-002", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 2, "SIZE": 1, "FUNCTION": "Storage"},
                {"NAME": "ASSET-003", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 3, "SIZE": 1, "FUNCTION": "Compute"},
            ]
        )

        from modules.display.display import build_scene

        mesh_colors = []
        add_mesh = pv.Plotter.add_mesh

        def capture_add_mesh(plotter, mesh, *args, **kwargs):
            mesh_colors.append(kwargs.get("color"))
            return add_mesh(plotter, mesh, *args, **kwargs)

        with patch.object(pv.Plotter, "add_mesh", new=capture_add_mesh):
            plotter = build_scene(asset_data)

        try:
            device_colors = mesh_colors[1:]
            self.assertEqual(device_colors[0], device_colors[2])
            self.assertNotEqual(device_colors[0], device_colors[1])
        finally:
            plotter.close()

    def test_build_scene_places_rack_rows_with_one_meter_aisle(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": 2, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
            ]
        )

        from modules.display.display import build_scene

        with patch("modules.display.display.pv.Box", wraps=pv.Box) as mock_box:
            plotter = build_scene(asset_data)

        try:
            first_rack_bounds = mock_box.call_args_list[0].kwargs["bounds"]
            second_rack_bounds = mock_box.call_args_list[2].kwargs["bounds"]
            self.assertEqual(first_rack_bounds[2:4], (-0.5, 0.5))
            self.assertEqual(second_rack_bounds[2:4], (1.5, 2.5))
        finally:
            plotter.close()

    def test_build_scene_places_racks_three_millimeters_apart(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": 1, "RACK": "RACK-02", "RACK_UNIT": 1, "SIZE": 1},
            ]
        )

        from modules.display.display import build_scene

        with patch("modules.display.display.pv.Box", wraps=pv.Box) as mock_box:
            plotter = build_scene(asset_data)

        try:
            first_rack_bounds = mock_box.call_args_list[0].kwargs["bounds"]
            second_rack_bounds = mock_box.call_args_list[2].kwargs["bounds"]
            self.assertEqual(first_rack_bounds[:2], (-0.4, 0.4))
            rack_gap = second_rack_bounds[0] - first_rack_bounds[1]
            self.assertAlmostEqual(rack_gap, 0.003)
        finally:
            plotter.close()

    def test_build_scene_centers_rack_group_in_room(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": 1, "RACK": "RACK-02", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-003", "ROW": 2, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
            ]
        )
        room_layout = {"room": {"width": 20, "length": 12, "height": 3}}

        from modules.display.display import build_scene

        with patch("modules.display.display.pv.Box", wraps=pv.Box) as mock_box:
            plotter = build_scene(asset_data, room_layout)

        try:
            rack_bounds = [call.kwargs["bounds"] for call in mock_box.call_args_list[::2]][:3]
            group_x_center = (min(bounds[0] for bounds in rack_bounds) + max(bounds[1] for bounds in rack_bounds)) / 2
            group_y_center = (min(bounds[2] for bounds in rack_bounds) + max(bounds[3] for bounds in rack_bounds)) / 2
            self.assertAlmostEqual(group_x_center, 10)
            self.assertAlmostEqual(group_y_center, 6)
        finally:
            plotter.close()

    def test_gui_configuration_omits_removed_controls(self):
        interface_source = Path("modules/interface/interface.py").read_text(encoding="utf-8")

        self.assertNotIn("Room opacity", interface_source)
        self.assertNotIn("Function color hue step", interface_source)
        self.assertNotIn("Function color saturation", interface_source)
        self.assertNotIn("Function color brightness", interface_source)
        self.assertNotIn('with dpg.collapsing_header(label="Display"', interface_source)

    def test_build_scene_has_no_rack_or_axis_labels(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 2, "SIZE": 2},
            ]
        )

        from modules.display.display import build_scene

        with patch.object(pv.Plotter, "add_text") as mock_add_text, patch.object(pv.Plotter, "add_axes") as mock_add_axes:
            build_scene(asset_data)

        self.assertEqual(mock_add_text.call_count, 4)
        self.assertEqual(mock_add_text.call_args_list[0].kwargs["name"], "asset_hover")
        self.assertEqual(mock_add_text.call_args_list[1].kwargs["name"], "rack_powerload")
        self.assertEqual(mock_add_text.call_args_list[1].kwargs["position"], (0.98, 0.10))
        self.assertEqual(mock_add_text.call_args_list[2].kwargs["name"], "room_powerload")
        self.assertEqual(mock_add_text.call_args_list[2].kwargs["position"], (0.98, 0.02))
        self.assertEqual(mock_add_text.call_args_list[3].kwargs["name"], "room_power_summary")
        self.assertEqual(mock_add_text.call_args_list[3].kwargs["position"], (0.98, 0.98))
        mock_add_axes.assert_not_called()

    def test_build_scene_shows_asset_details_on_mouseover(self):
        asset_data = pd.DataFrame(
            [
                {
                    "NAME": "ASSET-001",
                    "ROW": 1,
                    "RACK": "RACK-01",
                    "RACK_UNIT": 1,
                    "SIZE": 1,
                    "MODELNO": "MODEL-X",
                    "POWERLOAD": 450,
                },
                {
                    "NAME": "ASSET-002",
                    "ROW": 1,
                    "RACK": "RACK-01",
                    "RACK_UNIT": 2,
                    "SIZE": 1,
                    "MODELNO": "MODEL-Y",
                    "POWERLOAD": 850,
                },
                {
                    "NAME": "ASSET-003",
                    "ROW": 2,
                    "RACK": "RACK-02",
                    "RACK_UNIT": 1,
                    "SIZE": 1,
                    "MODELNO": "MODEL-Z",
                    "POWERLOAD": 200,
                },
            ]
        )

        from modules.display.display import build_scene

        room_layout = {
            "power": {
                "feed_a_voltage": 400,
                "feed_a_capacity": 80000,
                "feed_b_voltage": 400,
                "feed_b_capacity": 80000,
            }
        }
        plotter = build_scene(asset_data, room_layout)
        try:
            plotter.render()
            room_power_label = plotter.actors["room_powerload"]
            power_summary = plotter.actors["room_power_summary"]
            self.assertEqual(
                power_summary.GetInput(),
                "Room power: 1500 W consumed / 160000 W available",
            )
            self.assertEqual(room_power_label.GetInput(), "Room powerload: 1500 W")
            renderer = plotter.renderer
            renderer.SetWorldPoint(0, 0, 0.01, 1)
            renderer.WorldToDisplay()
            x, y, _ = renderer.GetDisplayPoint()
            plotter.iren.interactor.SetEventPosition(int(x), int(y))
            plotter.iren.interactor.InvokeEvent("MouseMoveEvent")

            hover_label = plotter.actors["asset_hover"]
            hover_text = hover_label.GetInput()
            rack_power_label = plotter.actors["rack_powerload"]
            self.assertAlmostEqual(hover_label.position[0], 0.02)
            self.assertAlmostEqual(hover_label.position[1], 0.98)
            self.assertIn("NAME: ASSET-002", hover_text)
            self.assertIn("MODELNO: MODEL-Y", hover_text)
            self.assertEqual(rack_power_label.GetInput(), "Rack powerload: 1300 W")
            self.assertEqual(room_power_label.GetInput(), "Row powerload: 1300 W")
            self.assertEqual(
                power_summary.GetInput(),
                "Room power: 1500 W consumed / 160000 W available",
            )
        finally:
            plotter.close()

    def test_export_button_saves_png_to_configured_output_directory(self):
        from modules.display.display import _add_export_button

        plotter = MagicMock()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "pyvista_view.png"
            with patch("modules.display.display.config.OUTPUT_DIR", Path(temporary_directory)):
                _add_export_button(plotter)

            callback = plotter.add_checkbox_button_widget.call_args.args[0]
            callback(False)

        plotter.screenshot.assert_called_once_with(output_path, return_img=False)
        plotter.add_text.return_value.SetInput.assert_called_once_with("PNG exported")
        representation = plotter.add_checkbox_button_widget.return_value.GetRepresentation()
        representation.SetButtonTexture.assert_called_once_with(
            1,
            representation.GetButtonTexture.return_value,
        )
        representation.PlaceWidget.assert_called_once_with((10, 150, 10, 46, 0, 0))

    def test_export_button_reports_screenshot_failures(self):
        from modules.display.display import _add_export_button

        plotter = MagicMock()
        plotter.screenshot.side_effect = OSError("disk unavailable")
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch("modules.display.display.config.OUTPUT_DIR", Path(temporary_directory)):
                _add_export_button(plotter)
            callback = plotter.add_checkbox_button_widget.call_args.args[0]
            callback(False)

        plotter.add_text.return_value.SetInput.assert_called_once_with(
            "PNG export failed: disk unavailable",
        )


if __name__ == "__main__":
    unittest.main()
