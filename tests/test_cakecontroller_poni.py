import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from peakpo.control.cakecontroller import CakeController
from peakpo.ds_cake.DiffractionImage import DiffImg
from peakpo.utils import cached_cake_exists_for_chi, usable_poni_file
from peakpo.view.mainwidget import MainWindow
from qtpy import QtWidgets


VALID_PONI = (
    "poni_version: 2\nDetector: Detector\n"
    'Detector_config: {"pixel1": 7.5e-05, "pixel2": 7.5e-05}\n'
    "Distance: 0.2\nPoni1: 0.1\nPoni2: 0.1\n"
    "Rot1: 0\nRot2: 0\nRot3: 0\nWavelength: 3.34e-11\n"
)


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
    def test_unreadable_poni_does_not_enable_cake_and_recheck_detects_repair(self):
        with tempfile.TemporaryDirectory() as root:
            poni = Path(root) / "calibration.poni"
            poni.write_text("calibration", encoding="utf-8")
            self.assertFalse(usable_poni_file(str(poni)))
            poni.write_text(VALID_PONI, encoding="utf-8")
            self.assertTrue(usable_poni_file(str(poni)))

    def test_invalid_selected_poni_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as root:
            param_dir = Path(root) / "sample-param"
            param_dir.mkdir()
            existing = param_dir / "existing.poni"
            existing.write_text(VALID_PONI, encoding="utf-8")
            selected = Path(root) / "invalid.poni"
            selected.write_text("calibration", encoding="utf-8")
            controller = object.__new__(CakeController)
            controller.widget = None
            with patch("peakpo.control.cakecontroller.QtWidgets.QMessageBox.warning"):
                self.assertFalse(controller._store_selected_poni(
                    str(selected), str(param_dir)))
            self.assertEqual(existing.read_text(encoding="utf-8"), VALID_PONI)
            self.assertFalse((param_dir / selected.name).exists())

    def test_invalid_typed_poni_restores_current_calibration(self):
        with tempfile.TemporaryDirectory() as root:
            existing = Path(root) / "existing.poni"
            existing.write_text(VALID_PONI, encoding="utf-8")
            invalid = Path(root) / "invalid.poni"
            invalid.write_text("calibration", encoding="utf-8")
            line_edit = _LineEditStub()
            line_edit.value = str(invalid)
            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                poni=str(existing), base_ptn_exist=lambda: True)
            controller.widget = SimpleNamespace(lineEdit_PONI=line_edit)
            with patch("peakpo.control.cakecontroller.QtWidgets.QMessageBox.warning"):
                self.assertFalse(controller._sync_poni_from_line_edit(
                    warn_if_missing=True))
            self.assertEqual(controller.model.poni, str(existing))
            self.assertEqual(line_edit.text(), str(existing))

    def test_missing_poni_disables_cake_actions_until_selected(self):
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        with tempfile.TemporaryDirectory() as root:
            chi = Path(root) / "sample.chi"
            chi.write_text("", encoding="utf-8")
            window = MainWindow()
            controller = object.__new__(CakeController)
            controller.widget = window
            controller.model = SimpleNamespace(
                poni=None, base_ptn_exist=lambda: True,
                get_base_ptn_filename=lambda: str(chi))

            controller._update_poni_availability()
            self.assertFalse(window.checkBox_ShowCake.isEnabled())
            self.assertFalse(window.pushButton_ApplyCakeView.isEnabled())
            self.assertFalse(window.pushButton_ToolbarCakeZAdj.isEnabled())
            self.assertFalse(window.tabWidget_2Page2.isEnabled())
            self.assertTrue(window.pushButton_GetPONI.isEnabled())

            poni = Path(root) / "calibration.poni"
            poni.write_text(VALID_PONI, encoding="utf-8")
            controller.model.poni = str(poni)
            controller._update_poni_availability()
            self.assertTrue(window.checkBox_ShowCake.isEnabled())
            self.assertTrue(window.pushButton_ApplyCakeView.isEnabled())
            self.assertTrue(window.pushButton_ToolbarCakeZAdj.isEnabled())
            self.assertTrue(window.tabWidget_2Page2.isEnabled())
            window.close()
        del app

    def test_missing_poni_skips_cake_regeneration(self):
        controller = object.__new__(CakeController)
        controller.model = SimpleNamespace(poni=None)
        controller._load_new_image = Mock()

        self.assertFalse(controller.produce_cake())
        controller._load_new_image.assert_not_called()

    def test_show_cake_processes_once_when_one_poni_is_found(self):
        controller = object.__new__(CakeController)
        controller.model = SimpleNamespace(
            poni="calibration.poni", base_ptn_exist=lambda: True,
            associated_image_exists=lambda: True)
        controller.widget = SimpleNamespace(
            checkBox_ShowCake=SimpleNamespace(isChecked=lambda: True))
        controller._current_azimuth_source_chi = lambda: None
        controller.get_all_temp_poni = lambda: ["calibration.poni"]
        controller._set_current_poni = Mock()
        controller._usable_poni = lambda: True
        controller.process_temp_cake = Mock(return_value=True)

        self.assertTrue(controller._addremove_cake())
        controller.process_temp_cake.assert_called_once_with()

    def test_saved_cake_loads_without_poni_or_raw_image(self):
        with tempfile.TemporaryDirectory() as root:
            chi = Path(root) / "sample.chi"
            chi.write_text("", encoding="utf-8")
            param_dir = Path(root) / "sample-param"
            param_dir.mkdir()
            for suffix in ("tth", "azi", "int"):
                np.save(param_dir / f"sample.{suffix}.cake.npy",
                        np.ones((2, 3)))
            self.assertTrue(cached_cake_exists_for_chi(str(chi)))

            model = SimpleNamespace(
                poni=None, diff_img=None,
                get_base_ptn_filename=lambda: str(chi),
                associated_image_exists=lambda: False)
            model.reset_diff_img = lambda: setattr(model, "diff_img", DiffImg())
            controller = object.__new__(CakeController)
            controller.model = model
            controller._current_azimuth_source_chi = lambda: None
            controller.refresh_config_metadata_panel = Mock()
            controller.produce_cake = Mock(
                side_effect=AssertionError("unexpected Cake regeneration"))

            self.assertTrue(controller.process_temp_cake())
            self.assertEqual(model.diff_img.intensity_cake.shape, (2, 3))
            controller.produce_cake.assert_not_called()

    def test_show_cake_uses_cached_data_when_poni_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            chi = Path(root) / "sample.chi"
            chi.write_text("", encoding="utf-8")
            param_dir = Path(root) / "sample-param"
            param_dir.mkdir()
            for suffix in ("tth", "azi", "int"):
                np.save(param_dir / f"sample.{suffix}.cake.npy", np.ones((2, 3)))
            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                poni=None, base_ptn_exist=lambda: True,
                get_base_ptn_filename=lambda: str(chi))
            controller.widget = SimpleNamespace(
                checkBox_ShowCake=SimpleNamespace(isChecked=lambda: True))
            controller._current_azimuth_source_chi = lambda: None
            controller.get_all_temp_poni = lambda: []
            controller.process_temp_cake = Mock(return_value=True)

            self.assertTrue(controller._addremove_cake())
            controller.process_temp_cake.assert_called_once_with()

    def test_cake_metadata_reminds_user_when_cached_cake_has_no_poni(self):
        diff_img = DiffImg()
        diff_img.intensity_cake = np.ones((2, 3))
        diff_img.tth_cake = np.ones((2, 3))
        diff_img.chi_cake = np.ones((2, 3))
        controller = object.__new__(CakeController)
        controller.model = SimpleNamespace(poni=None, diff_img=diff_img)

        entries = controller._build_poni_table_entries()

        self.assertIn("PONI missing", entries[0][1])
        self.assertIn("choose a PONI", entries[0][1])

    def test_failed_cake_regeneration_is_reported_to_navigation(self):
        with tempfile.TemporaryDirectory() as root:
            chi = Path(root) / "sample.chi"
            chi.write_text("", encoding="utf-8")
            poni = Path(root) / "calibration.poni"
            poni.write_text("calibration", encoding="utf-8")
            controller = object.__new__(CakeController)
            controller.model = SimpleNamespace(
                poni=str(poni), diff_img=None,
                get_base_ptn_filename=lambda: str(chi),
                associated_image_exists=lambda: True)
            controller.widget = SimpleNamespace(
                checkBox_UseTempCake=SimpleNamespace(isChecked=lambda: False))
            controller._current_azimuth_source_chi = lambda: None
            controller.produce_cake = Mock(return_value=False)

            self.assertFalse(controller.process_temp_cake())

    def test_dioptas_detector_config_error_uses_normalized_private_poni(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "calibration.poni"
            source.write_text(
                "poni_version: 2\n"
                "Detector: Detector\n"
                'Detector_config: {"pixel1": 7.5e-05, "pixel2": 7.5e-05}\n'
                "Distance: 0.2\nPoni1: 0.1\nPoni2: 0.1\n"
                "Rot1: 0\nRot2: 0\nRot3: 0\n"
                "Wavelength: 3.34e-11\n", encoding="utf-8")
            original = source.read_text(encoding="utf-8")
            loaded_paths = []

            def load_poni(path):
                loaded_paths.append(path)
                if len(loaded_paths) == 1:
                    raise KeyError("detector_config")
                self.assertIn(
                    "Detector_config:", Path(path).read_text(encoding="utf-8"))

            diff_img = DiffImg()
            diff_img._dioptas_config = SimpleNamespace(
                calibration_model=SimpleNamespace(load=load_poni))
            diff_img.set_calibration(str(source))

            self.assertEqual(loaded_paths[0], str(source))
            self.assertNotEqual(loaded_paths[1], str(source))
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_selected_poni_is_copied_into_param_folder_and_replaces_old_file(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source_dir = root_path / "source"
            source_dir.mkdir()
            temp_dir = root_path / "sample-param"
            temp_dir.mkdir()

            selected = source_dir / "new_calibration.poni"
            selected.write_text(VALID_PONI)
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
                "Detector: Detector\n"
                'Detector_config: {"pixel1": 7.5e-05, "pixel2": 7.5e-05, "orientation": 3}\n'
                "Distance: 0.2\nPoni1: 0.1\nPoni2: 0.1\n"
                "Rot1: 0\nRot2: 0\nRot3: 0\nWavelength: 3.34e-11\n"
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
            selected.write_text(VALID_PONI)
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
            poni_path.write_text(VALID_PONI)

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
            self.assertIn(("Wavelength", "3.34e-11"), poni_entries)
            self.assertIn(("Image pixels X", "4"), cake_entries)
            self.assertIn(("Image pixels Y", "3"), cake_entries)
            self.assertIn(("Cake pixels X", "5"), cake_entries)
            self.assertIn(("Cake pixels Y", "4"), cake_entries)


if __name__ == "__main__":
    unittest.main()
