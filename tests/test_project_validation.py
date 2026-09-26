import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pyvista as pv

from main import main
from modules.filemanager.filemanager import checkoutputdir, loadassets


class ProjectValidationTests(unittest.TestCase):
    def test_loadassets_sorts_by_row_rack_and_descending_rack_unit(self):
        asset_data = pd.DataFrame(
            [
                {"ROW": 2, "RACK": "RACK-01", "RACK_UNIT": 1},
                {"ROW": 1, "RACK": "RACK-02", "RACK_UNIT": 2},
                {"ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 3},
                {"ROW": 1, "RACK": "RACK-02", "RACK_UNIT": 10},
                {"ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 40},
            ]
        )

        with patch(
            "modules.filemanager.filemanager.filedialog.askopenfilename",
            return_value="assets.csv",
        ), patch("modules.filemanager.filemanager.pd.read_csv", return_value=asset_data):
            sorted_data = loadassets()

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

    def test_checkoutputdir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "nested" / "output"
            created_dir = checkoutputdir(output_dir)
            self.assertTrue(created_dir.exists())
            self.assertTrue(created_dir.is_dir())

    def test_main_handles_cancelled_asset_selection(self):
        room_layout = {
            "room": {"width": 20, "length": 20, "height": 2},
            "power": {
                "feed_a_voltage": 400,
                "feed_a_capacity": 80000,
                "feed_b_voltage": 400,
                "feed_b_capacity": 80000,
            },
        }

        with patch("main.checkoutputdir"), patch("main.loadroom", return_value=room_layout), patch(
            "main.loadassets",
            return_value=None,
        ), patch("main.display_assets") as mock_display:
            main()

        mock_display.assert_not_called()

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

        mock_add_text.assert_called_once()
        self.assertEqual(mock_add_text.call_args.kwargs["name"], "asset_hover")
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
                }
            ]
        )

        from modules.display.display import build_scene

        plotter = build_scene(asset_data)
        try:
            plotter.render()
            renderer = plotter.renderer
            renderer.SetWorldPoint(0, 0, 0.022225, 1)
            renderer.WorldToDisplay()
            x, y, _ = renderer.GetDisplayPoint()
            plotter.iren.interactor.SetEventPosition(int(x), int(y))
            plotter.iren.interactor.InvokeEvent("MouseMoveEvent")

            hover_label = plotter.actors["asset_hover"]
            hover_text = hover_label.GetText(hover_label.UpperLeft)
            self.assertIn("NAME: ASSET-001", hover_text)
            self.assertIn("MODELNO: MODEL-X", hover_text)
        finally:
            plotter.close()


if __name__ == "__main__":
    unittest.main()
