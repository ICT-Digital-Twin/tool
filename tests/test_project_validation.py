import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pyvista as pv

from main import main
from modules.filemanager.filemanager import asset_schema_validation_message, checkoutputdir, loadassets


class ProjectValidationTests(unittest.TestCase):
    def test_pyvista_and_panel_can_be_imported_in_order(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pyvista; import panel; print('ok', panel.__version__)",
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("ok", result.stdout)

    def test_dearpygui_is_not_a_runtime_dependency(self):
        requirements = Path("requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("dearpygui", requirements.lower())

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
            "modules.filemanager.filemanager.pd.read_csv",
            side_effect=[asset_data, model_data],
        ):
            sorted_data = loadassets("assets.csv", "model_details.csv")

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
            "modules.filemanager.filemanager.pd.read_csv",
            side_effect=[asset_data, model_data],
        ):
            joined_data = loadassets("assets.csv", "model_details.csv")

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

    def test_run_interface_serves_the_main_page_once(self):
        from modules.interface.interface import run_interface

        page = MagicMock()
        with patch("modules.interface.interface.create_main_layout", return_value=page), patch(
            "modules.interface.interface.serve_layout"
        ) as mock_serve:
            mock_serve.return_value = MagicMock()
            run_interface()

        mock_serve.assert_called_once_with(page, threaded=True)
        mock_serve.return_value.join.assert_called_once_with()

    def test_run_interface_stops_server_when_page_session_is_destroyed(self):
        from modules.interface.interface import run_interface

        page = MagicMock()
        server_thread = MagicMock()
        session_destroyed = None

        def register_session_destroyed(callback):
            nonlocal session_destroyed
            session_destroyed = callback

        with patch("modules.interface.interface.create_main_layout", return_value=page), patch(
            "modules.interface.interface.pn.state.on_session_destroyed",
            side_effect=register_session_destroyed,
        ), patch("modules.interface.interface.serve_layout", return_value=server_thread):
            run_interface()

        self.assertIsNotNone(session_destroyed)
        session_destroyed(MagicMock())
        server_thread.stop.assert_called_once_with()
        server_thread.join.assert_called_once_with()

    def test_main_page_has_three_browser_upload_controls(self):
        import panel as pn

        from modules.interface.interface import create_main_layout

        page = create_main_layout()

        self.assertIsInstance(page, pn.Column)
        self.assertEqual(len(page.select(pn.widgets.FileInput)), 3)

    def test_configuration_follows_visualization_and_starts_collapsed(self):
        import panel as pn

        from modules.interface.interface import create_main_layout

        page = create_main_layout()
        configuration_heading_index = next(
            index
            for index, item in enumerate(page.objects)
            if isinstance(item, pn.pane.Markdown) and item.object == "## Configuration"
        )
        visualization_index = next(
            index
            for index, item in enumerate(page.objects)
            if isinstance(item, pn.Column)
            and item.objects
            and isinstance(item.objects[0], pn.pane.Markdown)
            and item.objects[0].object.startswith("### Visualization")
        )
        accordion = next(item for item in page.objects if isinstance(item, pn.Accordion))

        self.assertLess(visualization_index, configuration_heading_index)
        self.assertEqual(accordion.active, [])

    def test_loadroom_accepts_uploaded_yaml_bytes(self):
        from modules.filemanager.filemanager import loadroom

        room_layout = loadroom(b"room:\n  width: 20\n  length: 12\n  height: 3\n")

        self.assertEqual(room_layout["room"]["width"], 20)

    def test_loadassets_accepts_uploaded_csv_bytes(self):
        asset_csv = b"ROW,RACK,RACK_UNIT,MODELNO\n1,A01,2,R670\n"
        model_csv = b"MODELNO,POWERLOAD\nR670,450\n"

        joined_data = loadassets(asset_csv, model_csv)

        self.assertEqual(joined_data.loc[0, "POWERLOAD"], 450)
        self.assertEqual(joined_data.loc[0, "RACK"], "A01")

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

    def test_build_scene_adds_row_and_rack_labels_for_panel_vtk(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": "A", "RACK": "A01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": "A", "RACK": "A02", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-003", "ROW": "B", "RACK": "B01", "RACK_UNIT": 1, "SIZE": 1},
            ]
        )

        from bokeh.document import Document
        from modules.datadisplay import build_data_layout
        from modules.display.display import build_scene

        plotter = build_scene(asset_data)
        try:
            self.assertEqual(
                [name for name in plotter.actors if name.startswith("_ict_row_label_")],
                ["_ict_row_label_0", "_ict_row_label_1"],
            )
            self.assertEqual(
                [name for name in plotter.actors if name.startswith("_ict_rack_label_")],
                ["_ict_rack_label_0", "_ict_rack_label_1", "_ict_rack_label_2"],
            )
            layout = build_data_layout(asset_data, plotter)
            self.assertIs(layout[0].object, plotter.ren_win)
            self.assertIsNotNone(layout[0].get_root(Document()))
        finally:
            plotter.close()

    def test_build_scene_flips_row_and_rack_labels_vertically(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": "A", "RACK": "A01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": "B", "RACK": "B01", "RACK_UNIT": 1, "SIZE": 1},
            ]
        )

        from modules.display.display import build_scene

        original_text3d = pv.Text3D
        labels = []

        def capture_text3d(*args, **kwargs):
            label = original_text3d(*args, **kwargs)
            labels.append((label, label.points.copy(), label.center))
            return label

        with patch("modules.display.display.pv.Text3D", new=capture_text3d):
            plotter = build_scene(asset_data)

        try:
            self.assertEqual(len(labels), 4)
            for label, original_points, original_center in labels:
                centered_original = original_points - original_center
                centered_label = label.points - label.center
                np.testing.assert_allclose(
                    centered_label[:, 0], -centered_original[:, 0], atol=1e-6
                )
                np.testing.assert_allclose(
                    centered_label[:, 1], -centered_original[:, 1], atol=1e-6
                )
                np.testing.assert_allclose(
                    centered_label[:, 2], centered_original[:, 2], atol=1e-6
                )
        finally:
            plotter.close()

    def test_build_scene_places_row_labels_on_opposite_side_of_rows(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": "A", "RACK": "A01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": "B", "RACK": "B01", "RACK_UNIT": 1, "SIZE": 1},
            ]
        )

        from modules.display.display import build_scene

        original_text3d = pv.Text3D
        labels = []

        def capture_text3d(*args, **kwargs):
            label = original_text3d(*args, **kwargs)
            labels.append(label)
            return label

        with patch("modules.display.display.pv.Text3D", new=capture_text3d):
            plotter = build_scene(asset_data)

        try:
            self.assertAlmostEqual(labels[0].center[1], 0.7)
            self.assertAlmostEqual(labels[1].center[1], 2.7)
        finally:
            plotter.close()

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

    def test_interface_has_no_dearpygui_dependency(self):
        interface_source = Path("modules/interface/interface.py").read_text(encoding="utf-8")

        self.assertNotIn("dearpygui", interface_source.lower())
        self.assertIn("pn.widgets.FileInput", interface_source)

    def test_build_scene_has_no_information_or_axis_labels(self):
        asset_data = pd.DataFrame(
            [
                {"NAME": "ASSET-001", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 1, "SIZE": 1},
                {"NAME": "ASSET-002", "ROW": 1, "RACK": "RACK-01", "RACK_UNIT": 2, "SIZE": 2},
            ]
        )

        from modules.display.display import build_scene

        with patch.object(pv.Plotter, "add_text") as mock_add_text, patch.object(pv.Plotter, "add_axes") as mock_add_axes:
            build_scene(asset_data)

        mock_add_text.assert_not_called()
        mock_add_axes.assert_not_called()

    def test_data_figure_contains_inventory_and_visualizations(self):
        from modules.datadisplay import build_data_figure
        import plotly.graph_objects as go

        asset_data = pd.DataFrame(
            [
                {
                    "INDEX": 1,
                    "NAME": "Server A",
                    "ROW": "A",
                    "RACK": "A01",
                    "RACK_UNIT": 1,
                    "MODELNO": "R670",
                    "AIRFLOW DIRECTION": "Front-to-Rear",
                    "FUNCTION": "Compute",
                    "POWERLOAD": 450,
                },
                {
                    "INDEX": 2,
                    "NAME": "Switch A",
                    "ROW": "A",
                    "RACK": "A01",
                    "RACK_UNIT": 2,
                    "MODELNO": "S5200",
                    "AIRFLOW DIRECTION": "Front-to-Rear",
                    "FUNCTION": "Network",
                    "POWERLOAD": 80,
                },
            ]
        )

        figure = build_data_figure(asset_data)

        self.assertIsInstance(figure, go.Figure)
        self.assertEqual(len(figure.data), 4)
        first_feed, second_feed = figure.data[:2]
        self.assertIsInstance(first_feed, go.Bar)
        self.assertEqual(first_feed.name, "Feed 1 powerload")
        self.assertEqual(list(first_feed.y), [265])
        self.assertEqual(first_feed.marker.color, "#1f77b4")
        self.assertEqual(list(first_feed.customdata), [["ROW", "A"]])
        self.assertEqual(second_feed.name, "Feed 2 powerload")
        self.assertEqual(list(second_feed.y), [265])
        self.assertEqual(second_feed.marker.color, "#d62728")
        self.assertEqual(figure.layout.barmode, "group")
        self.assertEqual(figure.data[2].name, "Feed 1 powerload")
        self.assertEqual(list(figure.data[2].y), [265])
        self.assertEqual(figure.data[2].marker.color, "#1f77b4")
        self.assertEqual(list(figure.data[2].customdata), [["RACK", "A01"]])
        self.assertEqual(figure.data[3].name, "Feed 2 powerload")
        self.assertEqual(list(figure.data[3].y), [265])
        self.assertEqual(figure.data[3].marker.color, "#d62728")
        self.assertTrue(figure.layout.yaxis.autorange)
        self.assertTrue(figure.layout.yaxis2.autorange)

    def test_data_figure_omits_total_feed_capacity_line_and_plots_individual_feeds(self):
        from modules.datadisplay import build_data_figure

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "ROW": "A", "RACK": "A01", "POWERLOAD": 450},
                {"NAME": "Server B", "ROW": "B", "RACK": "B01", "POWERLOAD": 250},
            ]
        )
        room_layout_data = {
            "power": {
                "feed_a_capacity": 1000,
                "feed_b_capacity": 2000,
            }
        }

        figure = build_data_figure(asset_data, room_layout_data)

        self.assertEqual(len(figure.data), 4)
        self.assertEqual(list(figure.data[0].x), ["A", "B"])
        self.assertEqual(list(figure.data[0].y), [225, 125])
        self.assertEqual(list(figure.data[1].y), [225, 125])
        self.assertEqual([trace.name for trace in figure.data], [
            "Feed 1 powerload",
            "Feed 2 powerload",
            "Feed 1 powerload",
            "Feed 2 powerload",
        ])
        self.assertEqual(list(figure.data[2].customdata), [["RACK", "A01"], ["RACK", "B01"]])

    def test_data_figure_sums_numbered_feed_capacities_and_plots_each_feed(self):
        from modules.datadisplay import build_data_figure

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "ROW": "A", "RACK": "A01", "POWERLOAD": 450},
                {"NAME": "Server B", "ROW": "B", "RACK": "B01", "POWERLOAD": 250},
            ]
        )
        room_layout_data = {
            "power": {
                "feed_a1_capacity": 40000,
                "feed_a2_capacity": 35000,
                "feed_b1_capacity": 30000,
                "feed_b2_capacity": 25000,
            }
        }

        figure = build_data_figure(asset_data, room_layout_data)

        self.assertEqual(list(figure.data[0].y), [225, 125])
        self.assertEqual(list(figure.data[1].y), [225, 125])
        first_feed_trace, second_feed_trace = figure.data[2:4]
        self.assertEqual(first_feed_trace.name, "Feed 1 capacity")
        self.assertEqual(list(first_feed_trace.y), [40000, 30000])
        self.assertEqual(first_feed_trace.line.color, "#d62728")
        self.assertEqual(first_feed_trace.line.dash, "dot")
        self.assertEqual(second_feed_trace.name, "Feed 2 capacity")
        self.assertEqual(list(second_feed_trace.y), [35000, 25000])
        self.assertEqual(second_feed_trace.line.dash, "dot")
        self.assertEqual(figure.data[4].name, "Feed 1 powerload")
        self.assertEqual(figure.data[5].name, "Feed 2 powerload")

    def test_data_figure_plots_a1_and_b1_capacities_for_rows_with_two_powerloads(self):
        from modules.datadisplay import build_data_figure

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "ROW": "A", "RACK": "A01", "POWERLOAD": 450},
                {"NAME": "Switch A", "ROW": "A", "RACK": "A01", "POWERLOAD": 80},
                {"NAME": "Server B", "ROW": "B", "RACK": "B01", "POWERLOAD": 250},
            ]
        )
        room_layout_data = {
            "power": {
                "feed_a1_capacity": 40000,
                "feed_b1_capacity": 30000,
            }
        }

        figure = build_data_figure(asset_data, room_layout_data)

        self.assertEqual(list(figure.data[0].y), [265, 125])
        self.assertEqual(list(figure.data[1].y), [265, 125])
        a1_trace, b1_trace = figure.data[2:4]
        self.assertEqual(a1_trace.name, "A1 capacity")
        self.assertEqual(list(a1_trace.y), [40000, None])
        self.assertEqual(a1_trace.line.color, "#1f77b4")
        self.assertEqual(b1_trace.name, "B1 capacity")
        self.assertEqual(list(b1_trace.y), [30000, None])
        self.assertEqual(b1_trace.line.color, "#d62728")

    def test_data_figure_plots_numbered_feed_capacities_for_any_row_label(self):
        from modules.datadisplay import build_data_figure

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "ROW": "A", "RACK": "A01", "POWERLOAD": 450},
                {"NAME": "Switch A", "ROW": "A", "RACK": "A01", "POWERLOAD": 80},
                {"NAME": "Server C", "ROW": "C", "RACK": "C01", "POWERLOAD": 320},
            ]
        )
        room_layout_data = {
            "power": {
                "feed_a1_capacity": 40000,
                "feed_c1_capacity": 50000,
            }
        }

        figure = build_data_figure(asset_data, room_layout_data)

        self.assertEqual(list(figure.data[0].y), [265, 160])
        self.assertEqual(list(figure.data[1].y), [265, 160])
        trace_names = [trace.name for trace in figure.data[2:]]
        self.assertIn("A1 capacity", trace_names)
        self.assertIn("C1 capacity", trace_names)

    def test_data_figure_omits_rpdu_capacity_reference_line(self):
        from modules.datadisplay import build_data_figure

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "RACK": "A01", "POWERLOAD": 450},
                {"NAME": "Switch A", "RACK": "A01", "POWERLOAD": 80},
            ]
        )
        room_layout_data = {"power": {"rpdu_capacity": 14000}}

        figure = build_data_figure(asset_data, room_layout_data)

        self.assertEqual(len(figure.data), 3)
        self.assertEqual(figure.data[1].name, "Feed 1 powerload")
        self.assertEqual(figure.data[1].y, (265,))
        self.assertEqual(figure.data[2].name, "Feed 2 powerload")
        self.assertEqual(figure.data[2].y, (265,))

    def test_data_figure_redistributes_load_and_shows_exceeded_rpdu_limit(self):
        from modules.datadisplay import build_data_figure

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "ROW": "A", "RACK": "A01", "POWERLOAD": 20000},
            ]
        )
        room_layout_data = {"power": {"rpdu_capacity": 14000}}

        figure = build_data_figure(asset_data, room_layout_data)

        self.assertEqual(list(figure.data[0].y), [10000])
        self.assertEqual(list(figure.data[1].y), [10000])
        self.assertNotIn("RPDU limit", [trace.name for trace in figure.data])

        figure = build_data_figure(
            asset_data,
            room_layout_data,
            row_feeds=(True, False),
            rack_feeds=(False, True),
        )

        self.assertEqual(list(figure.data[0].y), [20000])
        self.assertTrue(figure.data[0].visible)
        self.assertEqual(list(figure.data[1].y), [0])
        self.assertFalse(figure.data[1].visible)
        self.assertEqual(list(figure.data[2].y), [0])
        self.assertFalse(figure.data[2].visible)
        self.assertEqual(list(figure.data[3].y), [20000])
        self.assertTrue(figure.data[3].visible)
        self.assertEqual(figure.data[4].name, "RPDU limit")
        self.assertEqual(list(figure.data[4].y), [14000])
        self.assertEqual(figure.data[4].line.color, "#d62728")
        self.assertEqual(figure.data[4].line.dash, "dot")

    def test_plotly_feed_controls_and_selection_highlight_matching_devices_and_racks(self):
        from modules.datadisplay import build_data_layout
        from modules.display.display import build_scene
        import panel as pn

        asset_data = pd.DataFrame(
            [
                {"NAME": "Server A", "ROW": "A", "RACK": "A01", "RACK_UNIT": 1, "SIZE": 1, "POWERLOAD": 20000},
                {"NAME": "Server B", "ROW": "A", "RACK": "A01", "RACK_UNIT": 2, "SIZE": 1, "POWERLOAD": 10000},
                {"NAME": "Server C", "ROW": "B", "RACK": "B01", "RACK_UNIT": 1, "SIZE": 1, "POWERLOAD": 8000},
            ]
        )
        plotter = build_scene(asset_data)
        try:
            layout = build_data_layout(
                asset_data, plotter, {"power": {"rpdu_capacity": 14000}}
            )
            self.assertIsInstance(layout, pn.Row)
            self.assertIn("VTK", type(layout[0]).__name__)
            self.assertIs(layout[0].object, plotter.ren_win)
            self.assertIsInstance(layout[1], pn.Column)
            plotly_pane = layout[1][0]
            feed_controls = layout[1][1]
            clear_button = layout[1][2][1]
            inventory = layout[1][3]
            self.assertIsInstance(plotly_pane, pn.pane.Plotly)
            self.assertIsInstance(feed_controls, pn.Column)
            self.assertEqual(feed_controls[0].object, "Power feed toggle")
            self.assertEqual(len(feed_controls), 3)
            row_a_controls, row_b_controls = feed_controls[1:]
            self.assertEqual(row_a_controls[0].object, "**Row A**")
            self.assertEqual(row_b_controls[0].object, "**Row B**")
            feed_1, feed_2 = row_a_controls[1:]
            self.assertEqual(
                [control.name for control in (feed_1, feed_2)],
                ["Feed 1", "Feed 2"],
            )
            self.assertEqual(
                [control.name for control in row_b_controls[1:]],
                ["Feed 1", "Feed 2"],
            )
            self.assertEqual(feed_1.styles["color"], "#1f77b4")
            self.assertEqual(feed_2.styles["color"], "#d62728")
            self.assertIsInstance(inventory, pn.widgets.Tabulator)
            self.assertEqual(len(layout.objects), 2)

            feed_1.value = False

            updated_figure = plotly_pane.object
            self.assertEqual(list(updated_figure.data[0].y), [0, 4000])
            self.assertTrue(updated_figure.data[0].visible)
            self.assertEqual(list(updated_figure.data[1].y), [30000, 4000])
            self.assertTrue(updated_figure.data[1].visible)
            self.assertEqual(list(updated_figure.data[2].y), [0, 4000])
            self.assertTrue(updated_figure.data[2].visible)
            self.assertEqual(list(updated_figure.data[3].y), [30000, 4000])
            self.assertEqual(updated_figure.data[4].name, "RPDU limit")

            plotly_pane.click_data = {"points": [{"customdata": ["ROW", "A"]}]}

            self.assertEqual(plotter.actors["_ict_device_0"].prop.color.hex_rgba[:7], "#fff176")
            self.assertEqual(plotter.actors["_ict_device_1"].prop.color.hex_rgba[:7], "#fff176")
            self.assertNotEqual(plotter.actors["_ict_device_2"].prop.color.hex_rgba[:7], "#fff176")
            self.assertEqual(plotter.actors["_ict_rack_0"].prop.color.hex_rgba[:7], "#26c6da")
            self.assertEqual(inventory.selection, [0, 1])

            plotly_pane.click_data = {"points": [{"customdata": ["RACK", "B01"]}]}

            self.assertNotEqual(plotter.actors["_ict_device_0"].prop.color.hex_rgba[:7], "#fff176")
            self.assertEqual(plotter.actors["_ict_device_2"].prop.color.hex_rgba[:7], "#fff176")
            self.assertEqual(plotter.actors["_ict_rack_1"].prop.color.hex_rgba[:7], "#26c6da")
            self.assertEqual(inventory.selection, [2])

            inventory.selection = [0]

            self.assertEqual(plotter.actors["_ict_device_0"].prop.color.hex_rgba[:7], "#fff176")
            self.assertNotEqual(plotter.actors["_ict_device_2"].prop.color.hex_rgba[:7], "#fff176")
            self.assertEqual(plotter.actors["_ict_rack_0"].prop.color.hex_rgba[:7], "#26c6da")

            clear_button.clicks += 1

            self.assertEqual(inventory.selection, [])
            self.assertNotEqual(plotter.actors["_ict_device_0"].prop.color.hex_rgba[:7], "#fff176")
            self.assertNotEqual(plotter.actors["_ict_rack_0"].prop.color.hex_rgba[:7], "#26c6da")
        finally:
            plotter.close()

    def test_display_data_serves_combined_layout_in_browser(self):
        from modules.datadisplay import datadisplay

        plotter = MagicMock()
        layout = MagicMock()
        server = MagicMock()
        with patch("modules.datadisplay.datadisplay.build_data_layout", return_value=layout), patch(
            "modules.datadisplay.datadisplay.pn.serve", return_value=server
        ) as mock_serve:
            result = datadisplay.display_data(pd.DataFrame(), plotter)

        self.assertIs(result, server)
        mock_serve.assert_called_once_with(
            layout,
            port=0,
            show=True,
            threaded=True,
            title="ICT Digital Twin",
            extra_patterns=[
                (
                    r"/ict-digital-twin/(.*)",
                    datadisplay.StaticFileHandler,
                    {"path": str(datadisplay._VTK_INTERACTION_SCRIPT.parent)},
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
