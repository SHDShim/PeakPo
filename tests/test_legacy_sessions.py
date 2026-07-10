import pickle
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from peakpo.compat_pickle import PeakPoCompatDillUnpickler
from peakpo.control.sessioncontroller import SessionController
from peakpo.ds_jcpds import Session
from peakpo.model.model import PeakPoModel


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_SESSION_DIR = REPO_ROOT / "jupyter-tools" / "5_xrdfile_conversion"


class LegacySessionCompatibilityTests(unittest.TestCase):
    def test_bundled_legacy_dpp_files_are_readable(self):
        for path in sorted(LEGACY_SESSION_DIR.glob("*.dpp")):
            with self.subTest(path=path.name), path.open("rb") as stream:
                model = PeakPoCompatDillUnpickler(stream).load()
            self.assertIsNotNone(model.base_ptn)
            self.assertTrue(model.chi_path)

    def test_bundled_legacy_ppss_files_are_readable(self):
        for path in sorted(LEGACY_SESSION_DIR.glob("*.ppss")):
            model = PeakPoModel()
            with self.subTest(path=path.name), warnings.catch_warnings():
                warnings.simplefilter("ignore", category=Warning)
                model.read_ppss(path)
            self.assertIsNotNone(model.session.pattern)
            self.assertTrue(hasattr(model.session, "waterfallpatterns"))
            self.assertTrue(hasattr(model.session, "bg_params"))

    def test_missing_legacy_ppss_fields_receive_defaults(self):
        session = Session()
        del session.waterfallpatterns
        del session.temperature
        del session.bg_params

        with tempfile.NamedTemporaryFile(suffix=".ppss") as stream:
            pickle.dump(session, stream)
            stream.flush()
            model = PeakPoModel()
            model.read_ppss(stream.name)

        self.assertEqual(model.session.waterfallpatterns, [])
        self.assertEqual(model.session.temperature, 300.0)
        self.assertEqual(model.session.bg_params, [20, 10, 20])

    def test_ppss_waterfall_at_original_path_keeps_its_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            pattern_path = Path(directory) / "waterfall.chi"
            pattern_path.write_text("# test\n1.0 10.0\n2.0 12.0\n")

            model = PeakPoModel()
            model.chi_path = directory
            session = Session()
            session.chi_path = directory
            session.waterfallpatterns = [SimpleNamespace(
                fname=str(pattern_path), wavelength=0.5, display=True)]
            model.session = session

            controller = object.__new__(SessionController)
            controller.model = model
            self.assertTrue(controller._load_waterfall_ptn_from_ppss())

        self.assertEqual(len(model.waterfall_ptn), 1)
        self.assertEqual(model.waterfall_ptn[0].wavelength, 0.5)
        self.assertTrue(model.waterfall_ptn[0].display)

    def test_legacy_dpp_button_load_does_not_migrate_or_archive(self):
        controller = object.__new__(SessionController)
        controller.widget = object()
        controller.model = SimpleNamespace(chi_path="")
        controller._load_dpp = Mock(return_value=True)
        controller._finish_session_load = Mock()
        controller.migrate_dpp_for_chi_if_exists = Mock(
            side_effect=AssertionError("legacy DPP button must not migrate"))
        controller._archive_legacy_dpp = Mock(
            side_effect=AssertionError("legacy DPP button must not archive"))

        with patch(
                "peakpo.control.sessioncontroller.dialog_openfile_hide_param_dirs",
                return_value=("/tmp/legacy.dpp", "")):
            controller.load_legacy_dpp()

        controller._load_dpp.assert_called_once_with(
            "/tmp/legacy.dpp", jlistonly=False)
        controller._finish_session_load.assert_called_once_with(True)
        controller.migrate_dpp_for_chi_if_exists.assert_not_called()
        controller._archive_legacy_dpp.assert_not_called()

    def test_dpp_ppss_tab_position_and_button_grid(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from qtpy import QtWidgets
        from peakpo.view.mainwidget import MainWindow
        from peakpo.view.qtd import Ui_MainWindow

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = QtWidgets.QMainWindow()
        ui = Ui_MainWindow()
        ui.setupUi(window)
        MainWindow._setup_file_dpp_ppss_tab(ui)

        labels = [ui.tabWidget_3.tabText(i)
                  for i in range(ui.tabWidget_3.count())]
        self.assertEqual(labels[:3], ["Data", "dpp, ppss", "Config"])
        self.assertIs(ui.groupBox_12.parent(), ui.tabWidget_3PageDppPpss)

        expected = {
            ui.pushButton_LoadLegacyDPP: (0, 0),
            ui.pushButton_LoadPPSS: (0, 1),
            ui.pushButton_SaveDPPandPPSS: (1, 0),
            ui.pushButton_SavePPSS: (1, 1),
            ui.pushButton_ZipSession: (2, 0),
        }
        for button, position in expected.items():
            index = ui.gridLayout.indexOf(button)
            row, column, __, ___ = ui.gridLayout.getItemPosition(index)
            self.assertEqual((row, column), position)


if __name__ == "__main__":
    unittest.main()
