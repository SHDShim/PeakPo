import os
import importlib.util
import sys
import tempfile
import types
import unittest

import numpy as np

import peakpo


CONTROL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "peakpo", "control")
if "peakpo.control" not in sys.modules:
    control_pkg = types.ModuleType("peakpo.control")
    control_pkg.__path__ = [CONTROL_DIR]
    sys.modules["peakpo.control"] = control_pkg
if "peakpo.utils" not in sys.modules:
    utils_pkg = types.ModuleType("peakpo.utils")
    utils_pkg.get_temp_dir = lambda path, branch="-param": path + branch
    utils_pkg.readchi = lambda path: ([], [], np.array([]), np.array([]))
    sys.modules["peakpo.utils"] = utils_pkg
if "peakpo.ds_powdiff" not in sys.modules:
    ds_powdiff_pkg = types.ModuleType("peakpo.ds_powdiff")
    ds_powdiff_pkg.__path__ = []
    sys.modules["peakpo.ds_powdiff"] = ds_powdiff_pkg
if "peakpo.ds_powdiff.DiffractionPattern" not in sys.modules:
    diff_ptn_mod = types.ModuleType("peakpo.ds_powdiff.DiffractionPattern")
    diff_ptn_mod.Pattern = object
    sys.modules["peakpo.ds_powdiff.DiffractionPattern"] = diff_ptn_mod

spec = importlib.util.spec_from_file_location(
    "peakpo.control.xrdiohelpers",
    os.path.join(CONTROL_DIR, "xrdiohelpers.py"),
)
xrdiohelpers = importlib.util.module_from_spec(spec)
sys.modules["peakpo.control.xrdiohelpers"] = xrdiohelpers
spec.loader.exec_module(xrdiohelpers)

build_coordinate_grid = xrdiohelpers.build_coordinate_grid
DioptasMetadataExport = xrdiohelpers.DioptasMetadataExport
DioptasMetadataCollection = xrdiohelpers.DioptasMetadataCollection
discover_dioptas_metadata_files = xrdiohelpers.discover_dioptas_metadata_files
extract_scan_coordinates = xrdiohelpers.extract_scan_coordinates
has_valid_scan_coordinates = xrdiohelpers.has_valid_scan_coordinates
parse_dioptas_map_filename = xrdiohelpers.parse_dioptas_map_filename


REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
REFERENCE_METADATA = os.path.join(
    REPO_ROOT, "cell32_initialmap_S1_map_1_001_0001.metadata.v1.json")


try:
    import h5py
except Exception:  # pragma: no cover
    h5py = None


@unittest.skipIf(h5py is None, "h5py is required for HDF5 coordinate tests")
class CoordinateExtractionTests(unittest.TestCase):
    def _h5_path(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        return tmp.name

    def test_scan_group_coordinates_preferred_over_instrument(self):
        path = self._h5_path()
        with h5py.File(path, "w") as h5:
            scan = h5.create_group("scan")
            scan.create_dataset("x", data=1.25)
            scan.create_dataset("y", data=2.5)
            inst = h5.create_group("instrument")
            inst.create_dataset("x", data=10.0)
            inst.create_dataset("y", data=20.0)

        self.assertEqual(extract_scan_coordinates(path), (1.25, 2.5))
        self.assertTrue(has_valid_scan_coordinates(path))

    def test_measurement_array_uses_frame_index(self):
        path = self._h5_path()
        with h5py.File(path, "w") as h5:
            meas = h5.create_group("measurement")
            meas.create_dataset("sample_x", data=np.array([0.0, 1.0, 2.0]))
            meas.create_dataset("sample_y", data=np.array([5.0, 6.0, 7.0]))

        self.assertEqual(extract_scan_coordinates(path, frame_index=1), (1.0, 6.0))
        self.assertIsNone(extract_scan_coordinates(path))

    def test_snapshot_coordinates_are_fallback(self):
        path = self._h5_path()
        with h5py.File(path, "w") as h5:
            snap = h5.create_group("scan_snapshot")
            snap.create_dataset("motor_x", data=3.0)
            snap.create_dataset("motor_y", data=4.0)

        self.assertEqual(extract_scan_coordinates(path), (3.0, 4.0))

    def test_ambiguous_same_priority_coordinates_return_none(self):
        path = self._h5_path()
        with h5py.File(path, "w") as h5:
            scan_a = h5.create_group("scan_a")
            scan_a.create_dataset("x", data=1.0)
            scan_a.create_dataset("y", data=2.0)
            scan_b = h5.create_group("scan_b")
            scan_b.create_dataset("x", data=3.0)
            scan_b.create_dataset("y", data=4.0)

        self.assertIsNone(extract_scan_coordinates(path))


class CoordinateGridTests(unittest.TestCase):
    def test_incomplete_grid_preserves_missing_pixels(self):
        values = np.array([10, 11, 12, 13, 14, 15, 16], dtype=float)
        xs = [0, 1, 2, 0, 2, 0, 1]
        ys = [0, 0, 0, 1, 1, 2, 2]

        grid, unique_x, unique_y, coord_to_index = build_coordinate_grid(values, xs, ys)

        self.assertEqual(unique_x, [0.0, 1.0, 2.0])
        self.assertEqual(unique_y, [0.0, 1.0, 2.0])
        self.assertEqual(grid.shape, (3, 3))
        self.assertTrue(np.isnan(grid[1, 1]))
        self.assertTrue(np.isnan(grid[2, 2]))
        self.assertEqual(grid[0, 2], 12.0)
        self.assertEqual(coord_to_index[(2, 1)], 4)

    def test_duplicate_coordinate_assignment_is_invalid(self):
        result = build_coordinate_grid([1.0, 2.0], [0.0, 0.0], [0.0, 0.0])
        self.assertIsNone(result)

    def test_float_noise_normalization(self):
        grid, unique_x, unique_y, coord_to_index = build_coordinate_grid(
            [1.0, 2.0],
            [0.2004, 0.4],
            [0.1996, 0.2],
        )
        self.assertEqual(unique_x[0], 0.2)
        self.assertEqual(unique_y[0], 0.2)

    def test_float_noise_duplicate_pixel_is_invalid(self):
        result = build_coordinate_grid(
            [1.0, 2.0],
            [0.2004, 0.1996],
            [0.1004, 0.0996],
        )
        self.assertIsNone(result)

    def test_uniform_axis_fills_missing_binned_positions(self):
        grid, unique_x, unique_y, __ = build_coordinate_grid(
            [1.0, 2.0, 4.0],
            [0.0, 0.001, 0.003],
            [0.0, 0.0, 0.0],
        )
        self.assertEqual(unique_x, [0.0, 0.001, 0.002, 0.003])
        self.assertTrue(np.isnan(grid[0, 2]))

    def test_target_shape_regularizes_noisy_positions(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        xs = [0.1001, 0.1998, 0.3002, 0.0997, 0.2003, 0.2999]
        ys = [0.0002, -0.0001, 0.0003, 0.1002, 0.0997, 0.1001]

        grid, unique_x, unique_y, coord_to_index = build_coordinate_grid(
            values, xs, ys, target_shape=(2, 3))

        self.assertEqual(grid.shape, (2, 3))
        self.assertEqual(unique_x, [0.1, 0.2, 0.3])
        self.assertEqual(unique_y, [0.0, 0.1])
        self.assertFalse(np.isnan(grid).any())
        self.assertEqual(grid[1, 2], 60.0)
        self.assertEqual(coord_to_index[(0.3, 0.1)], 5)

    def test_target_shape_uses_min_max_for_irregular_metadata_steps(self):
        grid, unique_x, unique_y, __ = build_coordinate_grid(
            [1.0, 2.0, 4.0],
            [0.6546, 0.6506, 0.6424],
            [-0.05, -0.05, -0.05],
            target_shape=(1, 4),
        )
        self.assertEqual(grid.shape, (1, 4))
        self.assertEqual(unique_x, [0.642, 0.646, 0.651, 0.655])
        self.assertEqual(unique_y, [-0.05])
        self.assertTrue(np.isnan(grid[0, 1]))


class DioptasMetadataTests(unittest.TestCase):
    def test_parse_map_filename_ignores_final_numeric_block(self):
        parsed = parse_dioptas_map_filename("cell32_initialmap_S1_map_1_001_0001.chi")
        self.assertEqual(parsed["row_index"], 1)
        self.assertEqual(parsed["snapshot_index"], 1)

    def test_metadata_discovery_in_param_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_path = os.path.join(tmpdir, "sample.metadata.v1.json")
            with open(REFERENCE_METADATA, "r", encoding="utf-8") as src:
                payload = src.read()
            with open(metadata_path, "w", encoding="utf-8") as dst:
                dst.write(payload)
            self.assertEqual(discover_dioptas_metadata_files(tmpdir), [metadata_path])

    def test_load_reference_metadata_schema_and_arrays(self):
        export = DioptasMetadataExport.from_file(REFERENCE_METADATA)
        self.assertEqual(export.schema_version, "1.0")
        self.assertEqual(len(export.horizontal), 18)
        self.assertEqual(len(export.vertical), 18)
        self.assertEqual(export.get_coordinates(
            filename="cell32_initialmap_S1_map_1_001_0001.chi"),
            (0.6546, -0.05))

    def test_unsupported_schema_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".metadata.v1.json", delete=False) as tmp:
            tmp.write(b'{"schema_version": "9.9"}')
            tmp_path = tmp.name
        self.addCleanup(lambda: os.path.exists(tmp_path) and os.remove(tmp_path))
        with self.assertRaises(ValueError):
            DioptasMetadataExport.from_file(tmp_path)

    def test_collection_coordinate_selection(self):
        collection = DioptasMetadataCollection([
            DioptasMetadataExport.from_file(REFERENCE_METADATA)
        ])
        coords = collection.get_coordinates(
            filename="cell32_initialmap_S1_map_1_002_9999.chi")
        self.assertEqual(coords, (0.6506, -0.05))

    def test_metadata_coordinates_build_incomplete_map(self):
        export = DioptasMetadataExport.from_file(REFERENCE_METADATA)
        names = [
            "cell32_initialmap_S1_map_1_001_0001.chi",
            "cell32_initialmap_S1_map_1_002_9999.chi",
            "cell32_initialmap_S1_map_1_004_9999.chi",
        ]
        coords = [export.get_coordinates(filename=name) for name in names]
        grid, unique_x, unique_y, __ = build_coordinate_grid(
            [10.0, 20.0, 40.0],
            [c[0] for c in coords],
            [c[1] for c in coords],
        )
        self.assertEqual(grid.shape, (1, 14))
        self.assertEqual(unique_x[0], 0.642)
        self.assertEqual(unique_x[-1], 0.655)
        self.assertTrue(np.isnan(grid).any())


if __name__ == "__main__":
    unittest.main()
