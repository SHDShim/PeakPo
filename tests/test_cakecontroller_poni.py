import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from peakpo.control.cakecontroller import CakeController


class _LineEditStub:
    def __init__(self):
        self.value = ""
        self.modified = False
        self._signals_blocked = False

    def setText(self, text):
        self.value = str(text)

    def text(self):
        return self.value

    def isModified(self):
        return self.modified

    def setModified(self, value):
        self.modified = bool(value)

    def setStyleSheet(self, value):
        self.style = str(value)

    def blockSignals(self, value):
        old = self._signals_blocked
        self._signals_blocked = bool(value)
        return old


class CakeControllerPoniTests(unittest.TestCase):
    def test_selected_poni_is_copied_into_param_folder_and_replaces_old_file(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source_dir = root_path / "source"
            source_dir.mkdir()
            temp_dir = root_path / "sample-param"
            temp_dir.mkdir()

            selected = source_dir / "new_calibration.poni"
            selected.write_text("poni_version: 2\n")
            old_poni = temp_dir / "old_calibration.poni"
            old_poni.write_text("poni_version: 2\n")

            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                chi_path=str(source_dir),
                poni=None,
                diff_img_exist=lambda: False,
                base_ptn_exist=lambda: False,
            )
            controller.widget = SimpleNamespace(
                lineEdit_PONI=_LineEditStub(),
            )
            controller.get_all_temp_poni = Mock(return_value=[str(old_poni)])
            controller._apply_changes_to_graph = Mock()
            controller.produce_cake = Mock()
            controller.refresh_config_metadata_panel = Mock()

            with patch(
                    "peakpo.control.cakecontroller.dialog_openfile_hide_param_dirs",
                    return_value=(str(selected), "")):
                success = controller._choose_and_store_poni(str(temp_dir))

            expected_path = temp_dir / "new_calibration.poni"
            self.assertTrue(success)
            self.assertTrue(selected.exists())
            self.assertFalse(old_poni.exists())
            self.assertTrue(expected_path.exists())
            self.assertEqual(controller.model.poni, str(expected_path))
            self.assertEqual(controller.widget.lineEdit_PONI.value, str(expected_path))
            controller._apply_changes_to_graph.assert_called_once()

    def test_selected_poni21_is_copied_and_converted_in_place(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source_dir = root_path / "source"
            source_dir.mkdir()
            temp_dir = root_path / "sample-param"
            temp_dir.mkdir()

            selected = source_dir / "new_calibration.poni"
            selected.write_text(
                "poni_version: 2.1\n"
                "Detector_config: {\"pixel1\": 1, \"orientation\": 3}\n"
            )

            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                chi_path=str(source_dir),
                poni=None,
                diff_img_exist=lambda: False,
                base_ptn_exist=lambda: False,
            )
            controller.widget = SimpleNamespace(
                lineEdit_PONI=_LineEditStub(),
            )
            controller.get_all_temp_poni = Mock(return_value=[])
            controller._apply_changes_to_graph = Mock()
            controller.produce_cake = Mock()
            controller.refresh_config_metadata_panel = Mock()

            success = controller._store_selected_poni(str(selected), str(temp_dir))

            expected_path = temp_dir / "new_calibration.poni"
            self.assertTrue(success)
            self.assertTrue(selected.exists())
            self.assertTrue(expected_path.exists())
            self.assertEqual(controller.model.poni, str(expected_path))
            self.assertIn("poni_version: 2.1", selected.read_text())
            contents = expected_path.read_text()
            self.assertIn("poni_version: 2", contents)
            self.assertNotIn("orientation", contents)

    def test_manual_poni_entry_copies_file_into_param_folder(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source_dir = root_path / "source"
            source_dir.mkdir()
            chi_path = source_dir / "sample.chi"
            chi_path.write_text("# chi\n")
            temp_dir = root_path / "source" / "sample-param"
            temp_dir.mkdir()

            selected = source_dir / "typed_calibration.poni"
            selected.write_text("poni_version: 2\n")
            line_edit = _LineEditStub()
            line_edit.value = str(selected)
            line_edit.modified = True

            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                chi_path=str(source_dir),
                poni=None,
                diff_img_exist=lambda: False,
                base_ptn_exist=lambda: True,
                get_base_ptn_filename=lambda: str(chi_path),
            )
            controller.widget = SimpleNamespace(
                lineEdit_PONI=line_edit,
            )
            controller.get_all_temp_poni = Mock(return_value=[])
            controller._apply_changes_to_graph = Mock()
            controller.produce_cake = Mock()

            controller.load_new_poni_from_name()

            expected_path = temp_dir / "typed_calibration.poni"
            self.assertTrue(selected.exists())
            self.assertTrue(expected_path.exists())
            self.assertEqual(controller.model.poni, str(expected_path))
            self.assertEqual(controller.widget.lineEdit_PONI.value, str(expected_path))

    def test_programmatic_poni_update_clears_modified_flag(self):
        line_edit = _LineEditStub()
        line_edit.modified = True

        controller = object.__new__(CakeController)
        controller.widget = SimpleNamespace(lineEdit_PONI=line_edit)
        controller.model = SimpleNamespace(
            poni=None,
            base_ptn_exist=lambda: False,
            diff_img=None,
        )
        controller.refresh_config_metadata_panel = Mock()

        controller._set_current_poni("/tmp/example.poni")

        self.assertEqual(controller.widget.lineEdit_PONI.value, "/tmp/example.poni")
        self.assertFalse(controller.widget.lineEdit_PONI.modified)

    def test_image_file_dialog_uses_compact_filter_label(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            image_path = root_path / "sample.cbf"
            image_path.write_bytes(b"fake image")
            allowed = ("tif", "tiff", "cbf", "edf", "h5", "hdf5")

            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                chi_path=str(root_path),
                raw_image_path=None,
                h5_path=None,
                base_ptn_exist=lambda: True,
                get_allowed_image_extensions=lambda: allowed,
            )
            controller.widget = SimpleNamespace(
                lineEdit_H5=_LineEditStub(),
            )
            controller._is_valid_raw_image_for_current_chi = Mock(return_value=True)
            controller._set_raw_image_line_edit_text = Mock()
            controller.refresh_config_metadata_panel = Mock()

            with patch(
                    "peakpo.control.cakecontroller.dialog_openfile_hide_param_dirs",
                    return_value=(str(image_path), "")) as dialog_mock:
                controller.get_h5()

            dialog_mock.assert_called_once()
            args, kwargs = dialog_mock.call_args
            self.assertEqual(args[3], "Supported image files (*)")
            self.assertEqual(kwargs["allowed_file_extensions"], allowed)
            self.assertNotIn("*.tif", args[3])
            self.assertEqual(controller.model.raw_image_path, str(image_path))

    def test_refresh_config_metadata_panel_populates_poni_and_cake_tables(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            poni_path = root_path / "example.poni"
            poni_path.write_text("poni_version: 2\nwavelength: 0.3344\n")

            diff_img = SimpleNamespace(
                img=np.arange(12, dtype=float).reshape(3, 4),
                get_img_zrange=lambda: [0.0, 11.0],
                get_cake=lambda: (
                    np.arange(20, dtype=float).reshape(4, 5),
                    np.linspace(1.0, 5.0, 5),
                    np.linspace(-180.0, 180.0, 4),
                ),
            )
            table_values = {}

            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                poni=str(poni_path),
                diff_img=diff_img,
                base_ptn_exist=lambda: False,
            )
            controller.widget = SimpleNamespace(
                lineEdit_PONI=_LineEditStub(),
                tableWidget_CakePoniInfo="poni_table",
                tableWidget_CakeSummary="cake_table",
                set_key_value_table_rows=lambda table, entries: table_values.__setitem__(
                    table, list(entries)),
            )

            controller.refresh_config_metadata_panel()

            poni_entries = table_values["poni_table"]
            cake_entries = table_values["cake_table"]
            self.assertNotIn(("Path", str(poni_path)), poni_entries)
            self.assertIn(("PONI version", "2"), poni_entries)
            self.assertIn(("Wavelength", "0.3344"), poni_entries)
            self.assertIn(("Image pixels X", "4"), cake_entries)
            self.assertIn(("Image pixels Y", "3"), cake_entries)
            self.assertIn(("Cake pixels X", "5"), cake_entries)
            self.assertIn(("Cake pixels Y", "4"), cake_entries)


if __name__ == "__main__":
    unittest.main()
