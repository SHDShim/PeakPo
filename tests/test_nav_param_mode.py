import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy import QtWidgets

from peakpo.control import maincontroller
from peakpo.control.maincontroller import MainController
from peakpo.model.model import PeakPoModel
from peakpo.model.param_session_io import model_param_signature
from peakpo.utils import writechi
from peakpo.view.mainwidget import MainWindow
import numpy as np


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_param_mode_controls_and_waterfall_button_layout():
    window = MainWindow()
    assert window.layout_TopToolbarRow1.indexOf(
        window.comboBox_NavParamMode) >= 0
    assert window.layout_TopToolbarRow1.indexOf(
        window.pushButton_AddBasePtn) == -1
    assert window.verticalLayout_35.indexOf(
        window.pushButton_AddBasePtn) < window.verticalLayout_35.indexOf(
            window.pushButton_ApplyWaterfallChange)
    assert window.pushButton_AddBasePtn.text() == (
        "Add Current Chi to Waterfall List")
    window.resize(1600, 1000)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Bkgn)
    window.tabWidget_5.setCurrentWidget(window.tabWidget_5Page2)
    _APP.processEvents()
    assert window.pushButton_AddBasePtn.width() == (
        window.pushButton_ApplyWaterfallChange.width())
    assert window.comboBox_NavParamMode.currentData() == "saved"
    assert window.comboBox_NavParamModeConfig.currentData() == "saved"
    assert window.comboBox_CarryNavExistingJCPDS.isHidden()
    window.close()
    _APP.processEvents()


@pytest.mark.parametrize(
    ("mode", "has_param", "category_present", "expected"),
    [
        ("saved", True, True, "skip"),
        ("saved", True, False, "skip"),
        ("saved", False, False, "carry_blank"),
        ("carry", True, True, "overwrite_existing"),
        ("carry", True, False, "carry_blank"),
        ("custom", True, True, "keep_existing"),
    ],
)
def test_navigation_param_mode_decision(
        mode, has_param, category_present, expected):
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        comboBox_NavParamMode=SimpleNamespace(currentData=lambda: mode),
        checkBox_CarryNavJCPDS=SimpleNamespace(isChecked=lambda: True),
        comboBox_CarryNavExistingJCPDS=SimpleNamespace(
            currentText=lambda: "Keep existing JCPDS"))
    assert controller._get_nav_carry_action(
        "jcpds", "checkBox_CarryNavJCPDS",
        {"jcpds": category_present},
        destination_has_param=has_param) == expected


def test_toolbar_and_config_mode_share_one_setting():
    window = MainWindow()
    controller = MainController.__new__(MainController)
    controller.widget = window
    values = {}
    controller.settings = SimpleNamespace(
        setValue=lambda key, value: values.__setitem__(key, value))
    controller._refresh_nav_destination_indicators = lambda: None

    window.comboBox_NavParamMode.setCurrentIndex(
        window.comboBox_NavParamMode.findData("custom"))
    controller._on_nav_param_mode_changed(window.comboBox_NavParamMode)
    assert window.comboBox_NavParamModeConfig.currentData() == "custom"
    assert not window.comboBox_CarryNavExistingJCPDS.isHidden()
    assert values["nav_param_mode"] == "custom"

    window.comboBox_NavParamModeConfig.setCurrentIndex(
        window.comboBox_NavParamModeConfig.findData("carry"))
    controller._on_nav_param_mode_changed(window.comboBox_NavParamModeConfig)
    assert window.comboBox_NavParamMode.currentData() == "carry"
    assert window.comboBox_CarryNavExistingJCPDS.isHidden()
    window.close()


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, "saved"),
        ({"carry_nav_existing_jcpds": "Keep existing JCPDS"}, "custom"),
        ({"nav_param_mode": "carry",
          "carry_nav_existing_jcpds": "Keep existing JCPDS"}, "carry"),
        ({"nav_param_mode": "invalid"}, "saved"),
    ],
)
def test_existing_navigation_preferences_migrate_without_loss(values, expected):
    controller = MainController.__new__(MainController)
    controller.settings = SimpleNamespace(
        contains=lambda key: key in values,
        value=lambda key, default=None: values.get(key, default))
    assert controller._read_nav_param_mode_setting() == expected


def test_navigation_buttons_preview_actual_step_destination(
        monkeypatch, tmp_path):
    for name in ("file_001.chi", "file_002.chi", "file_003.chi"):
        (tmp_path / name).write_text("", encoding="utf-8")
    window = MainWindow()
    window.spinBox_FileStep.setValue(2)
    controller = MainController.__new__(MainController)
    controller.widget = window
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: str(tmp_path / "file_001.chi"))
    monkeypatch.setattr(maincontroller, "is_new_param_folder",
                        lambda path: path.endswith("file_003-param"))

    controller._refresh_nav_destination_indicators()

    assert not window.pushButton_S_PrevBasePtn.isEnabled()
    assert window.pushButton_S_NextBasePtn.isEnabled()
    assert "file_003.chi" in window.pushButton_S_NextBasePtn.toolTip()
    assert "Use saved PARAM" in window.pushButton_S_NextBasePtn.toolTip()

    controller.model.get_base_ptn_filename = lambda: str(
        tmp_path / "file_002.chi")
    controller._refresh_nav_destination_indicators()
    assert "file_003.chi" in window.pushButton_S_NextBasePtn.toolTip()
    assert "file_001.chi" in window.pushButton_S_PrevBasePtn.toolTip()
    window.close()


def test_param_signature_tracks_changes_and_reversion(tmp_path):
    chi_file = tmp_path / "file_001.chi"
    writechi(str(chi_file), np.asarray([1.0, 2.0]),
             np.asarray([10.0, 12.0]))
    model = PeakPoModel()
    model.set_base_ptn(str(chi_file), 0.3344)
    original = model_param_signature(model, ui_state={})
    pressure = model.saved_pressure

    model.save_pressure(pressure + 10.0)
    assert model_param_signature(model, ui_state={}) != original
    model.save_pressure(pressure)
    assert model_param_signature(model, ui_state={}) == original


def test_save_button_yellow_only_for_changed_param():
    window = MainWindow()
    window.set_param_dirty_status(False)
    assert "#d6a800" not in window.pushButton_LoadDPP.styleSheet()
    window.set_param_dirty_status(True)
    assert "#d6a800" in window.pushButton_LoadDPP.styleSheet()
    assert "Unsaved" in window.pushButton_LoadDPP.toolTip()
    window.close()


def test_dirty_status_compares_current_file_with_loaded_baseline(tmp_path):
    chi_file = tmp_path / "file_001.chi"
    chi_file.write_text("", encoding="utf-8")
    statuses = []
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: str(chi_file))
    controller.widget = SimpleNamespace(
        set_param_dirty_status=statuses.append)
    signature = ["original"]
    controller._current_param_signature = lambda: signature[0]
    controller._navigation_in_progress = False

    controller._on_pattern_ready(str(chi_file))
    signature[0] = "changed"
    controller._refresh_param_dirty_status()
    signature[0] = "original"
    controller._refresh_param_dirty_status()

    assert statuses == [False, True, False]
