import os
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy import QtCore, QtWidgets

from peakpo.control import maincontroller
from peakpo.control.maincontroller import MainController
from peakpo.control.sessioncontroller import SessionController
from peakpo.model.model import PeakPoModel
from peakpo.model.param_session_io import model_param_signature
from peakpo.utils import writechi
from peakpo.view.mainwidget import MainWindow
from peakpo.view.ui_policy import COLORS
import numpy as np


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_restored_pressure_and_temperature_sync_to_toolbar():
    window = MainWindow()
    window.doubleSpinBox_Pressure.setValue(8.0)
    window.doubleSpinBox_Temperature.setValue(400.0)
    assert window.doubleSpinBox_ToolbarPressure.value() == 8.0
    assert window.spinBox_ToolbarTemperature.value() == 400

    controller = SessionController.__new__(SessionController)
    controller.widget = window
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: False,
        poni_exist=lambda: False,
        diff_img_exist=lambda: False,
        get_saved_pressure=lambda: 0.0,
        get_saved_temperature=lambda: 300.0,
    )
    controller.cake_ctrl = None
    controller._apply_ui_state = lambda state: None
    controller.update_inputs = lambda: None
    controller._sync_peakfit_selection_to_current_section = lambda: None
    controller.plot_ctrl = SimpleNamespace(zoom_out_graph=lambda: None)

    controller._sync_ui_from_model()

    assert window.doubleSpinBox_Pressure.value() == 0.0
    assert window.doubleSpinBox_ToolbarPressure.value() == 0.0
    assert window.doubleSpinBox_Temperature.value() == 300.0
    assert window.spinBox_ToolbarTemperature.value() == 300
    window.close()


def test_pressure_and_temperature_controls_sync_both_ways_and_emit_changes():
    window = MainWindow()
    pressure_changes = []
    temperature_changes = []
    window.doubleSpinBox_Pressure.valueChanged.connect(
        pressure_changes.append)
    window.doubleSpinBox_Temperature.valueChanged.connect(
        temperature_changes.append)

    window.doubleSpinBox_ToolbarPressure.setValue(8.25)
    window.spinBox_ToolbarTemperature.setValue(450)
    assert window.doubleSpinBox_Pressure.value() == 8.25
    assert window.doubleSpinBox_Temperature.value() == 450
    assert pressure_changes == [8.25]
    assert temperature_changes == [450.0]

    window.doubleSpinBox_Pressure.setValue(2.5)
    window.doubleSpinBox_Temperature.setValue(600)
    assert window.doubleSpinBox_ToolbarPressure.value() == 2.5
    assert window.spinBox_ToolbarTemperature.value() == 600
    assert pressure_changes == [8.25, 2.5]
    assert temperature_changes == [450.0, 600.0]
    window.close()


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
    assert window.comboBox_NavParamMode.currentText() == "Carry if none"
    assert window.label_NavParamMode.text() == (
        "How Prev/Next opens another CHI")
    assert [window.comboBox_NavParamMode.itemText(index)
            for index in range(window.comboBox_NavParamMode.count())] == [
        "Carry if none", "Force carry", "Existing only", "Custom"]
    assert [window.comboBox_NavParamModeConfig.itemText(index)
            for index in range(window.comboBox_NavParamModeConfig.count())] == [
        "Carry over only if no existing", "Force carryover",
        "Use existing", "Custom category rules"]
    assert [window.comboBox_NavParamMode.itemData(index)
            for index in range(window.comboBox_NavParamMode.count())] == [
        "saved", "carry", "existing_only", "custom"]
    combo = window.comboBox_NavParamMode
    widest_label = max(combo.fontMetrics().horizontalAdvance(
        combo.itemText(index)) for index in range(combo.count()))
    assert 30 <= combo.width() - widest_label <= 42
    assert combo.width() < 155
    style_option = QtWidgets.QStyleOptionComboBox()
    style_option.initFrom(combo)
    text_rect = combo.style().subControlRect(
        QtWidgets.QStyle.CC_ComboBox, style_option,
        QtWidgets.QStyle.SC_ComboBoxEditField, combo)
    assert text_rect.width() >= widest_label
    assert window.comboBox_NavParamModeConfig.currentText() == (
        "Carry over only if no existing")
    assert window.comboBox_CarryNavExistingJCPDS.currentText() == (
        "Keep existing JCPDS")
    assert window.comboBox_CarryNavExistingOther.currentText() == (
        "Keep existing information")
    assert window.comboBox_NavSaveMode.currentData() == "incomplete"
    assert window.comboBox_NavSaveMode.currentText() == (
        "New or incomplete sessions")
    assert window.comboBox_NavParamMode.styleSheet() == ""
    for index in range(window.comboBox_NavParamMode.count()):
        assert window.comboBox_NavParamMode.itemData(
            index, QtCore.Qt.ForegroundRole) is None
    assert window.comboBox_NavParamModeConfig.styleSheet() == ""
    for index in range(window.comboBox_NavParamModeConfig.count()):
        assert window.comboBox_NavParamModeConfig.itemData(
            index, QtCore.Qt.ForegroundRole) is None
    for group in (window.groupBox_NavSave,
                  window.groupBox_WorkingStateRecovery):
        assert group.sizePolicy().verticalPolicy() == (
            QtWidgets.QSizePolicy.Fixed)
        assert group.height() <= group.sizeHint().height() + 2
    assert window.comboBox_CarryNavExistingJCPDS.isHidden()
    window.close()
    _APP.processEvents()


@pytest.mark.parametrize(
    ("mode", "has_param", "category_present", "expected"),
    [
        ("existing_only", True, True, "skip"),
        ("existing_only", False, False, "skip"),
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


def test_strict_existing_resets_previous_setup_for_unsaved_chi():
    window = MainWindow()
    model = PeakPoModel()
    model.jcpds_lst = [object()]
    model.ucfit_lst = [object()]
    model.waterfall_ptn = [object()]
    model.section_lst = [object()]
    model.current_section = object()
    model.poni = "previous.poni"
    model.diff_img = object()
    model.save_pressure(8.0)
    model.save_temperature(700.0)
    window.doubleSpinBox_Pressure.setValue(8.0)
    window.doubleSpinBox_Temperature.setValue(700.0)
    window.spinBox_BGParam0.setValue(30)
    controller = MainController.__new__(MainController)
    controller.model = model
    controller.widget = window
    controller.jcpdstable_ctrl = SimpleNamespace(update=lambda: None)
    controller.waterfalltable_ctrl = SimpleNamespace(update=lambda: None)

    controller._reset_setup_for_unsaved_navigation()

    assert model.jcpds_lst == []
    assert model.ucfit_lst == []
    assert model.waterfall_ptn == []
    assert model.section_lst == []
    assert model.current_section is None
    assert model.poni is None
    assert model.diff_img is None
    assert model.get_saved_pressure() == 10.0
    assert model.get_saved_temperature() == 300.0
    assert window.doubleSpinBox_Pressure.value() == 10.0
    assert window.doubleSpinBox_ToolbarPressure.value() == 10.0
    assert window.doubleSpinBox_Temperature.value() == 300.0
    assert window.spinBox_ToolbarTemperature.value() == 300
    assert [window.spinBox_BGParam0.value(), window.spinBox_BGParam1.value(),
            window.spinBox_BGParam2.value()] == [10, 20, 40]
    window.close()


def test_strict_existing_navigation_skips_private_recovery(
        monkeypatch, tmp_path):
    current = tmp_path / "file_001.chi"
    destination = tmp_path / "file_002.chi"
    current.write_text("", encoding="utf-8")
    destination.write_text("", encoding="utf-8")
    monkeypatch.setattr(maincontroller, "is_new_param_folder",
                        lambda path: False)
    base_ptn = SimpleNamespace(fname=str(current))
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path), base_ptn=base_ptn,
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: base_ptn.fname)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=SimpleNamespace(isChecked=lambda: True),
        spinBox_FileStep=SimpleNamespace(value=lambda: 1),
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "never"),
        comboBox_NavParamMode=SimpleNamespace(
            currentData=lambda: "existing_only"))
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda *args: True,
        save_recovery_state=lambda **kwargs: True)
    calls = []
    controller._capture_nav_carry_state = lambda: {}
    controller._reset_setup_for_unsaved_navigation = lambda: calls.append("reset")
    controller._reset_cake_scale_for_fresh_navigation = (
        lambda filename: calls.append("reset cake"))
    controller._on_pattern_ready = lambda filename: calls.append("baseline")
    controller._defer_plot_updates = nullcontext
    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=lambda filename, **kwargs: (
            calls.append(kwargs), setattr(base_ptn, "fname", filename)))
    controller._apply_nav_carry_state = lambda state: calls.append("apply")
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)
    controller._schedule_roi_overlays_after_plot_update = lambda **kwargs: None
    controller._nav_filled_missing = False
    controller._confirm_missing_destination_poni = lambda path: None

    controller._goto_chi_next_file("next")

    assert base_ptn.fname == str(destination)
    assert calls == ["reset", {"allow_private_recovery": False},
                     "reset cake", "apply", "baseline"]


@pytest.mark.parametrize(
    ("selection", "expected"),
    [("Use current PONI", True), ("Open without PONI", False),
     ("Stay on current file", "cancel")])
def test_missing_destination_poni_prompt_has_explicit_choices(
        monkeypatch, tmp_path, selection, expected):
    source = tmp_path / "current-param" / "calibration.poni"
    source.parent.mkdir()
    source.write_text(
        "poni_version: 2\nDetector: Detector\n"
        'Detector_config: {"pixel1": 7.5e-05, "pixel2": 7.5e-05}\n'
        "Distance: 0.2\nPoni1: 0.1\nPoni2: 0.1\n"
        "Rot1: 0\nRot2: 0\nRot3: 0\nWavelength: 3.34e-11\n",
        encoding="utf-8")
    destination = tmp_path / "next.chi"
    destination.write_text("", encoding="utf-8")
    shown = {}

    class FakeMessageBox:
        DontUseNativeDialog = 1
        Warning = 2
        AcceptRole = 3
        ActionRole = 4
        RejectRole = 5

        def __init__(self, parent):
            self.buttons = {}

        def setOption(self, *args):
            pass

        def setTextFormat(self, *args):
            pass

        def setIcon(self, *args):
            pass

        def setWindowTitle(self, value):
            shown["title"] = value

        def setText(self, value):
            shown["text"] = value

        def setInformativeText(self, value):
            shown["detail"] = value

        def addButton(self, label, role):
            self.buttons[label] = label
            return label

        def setDefaultButton(self, button):
            pass

        def setEscapeButton(self, button):
            pass

        def exec(self):
            pass

        def clickedButton(self):
            return self.buttons[selection]

    monkeypatch.setattr(maincontroller.QtWidgets, "QMessageBox", FakeMessageBox)
    controller = MainController.__new__(MainController)
    controller.widget = None
    controller.model = SimpleNamespace(poni=str(source))

    assert controller._confirm_missing_destination_poni(
        str(destination)) == expected
    assert destination.name in shown["text"]
    assert "unique usable PONI" in shown["text"]


def test_missing_poni_prompt_chooses_file(monkeypatch, tmp_path):
    destination = tmp_path / "next.chi"
    destination.write_text("", encoding="utf-8")
    selected = tmp_path / "calibration.poni"
    selected.write_text(
        "poni_version: 2\nDetector: Detector\n"
        'Detector_config: {"pixel1": 7.5e-05, "pixel2": 7.5e-05}\n'
        "Distance: 0.2\nPoni1: 0.1\nPoni2: 0.1\n"
        "Rot1: 0\nRot2: 0\nRot3: 0\nWavelength: 3.34e-11\n",
        encoding="utf-8")

    class FakeMessageBox:
        DontUseNativeDialog = 1
        Warning = 2
        AcceptRole = 3
        ActionRole = 4
        RejectRole = 5

        def __init__(self, parent):
            self.buttons = {}

        def addButton(self, label, role):
            self.buttons[label] = label
            return label

        def clickedButton(self):
            return self.buttons["Choose PONI"]

        def __getattr__(self, name):
            return lambda *args: None

    monkeypatch.setattr(maincontroller.QtWidgets, "QMessageBox", FakeMessageBox)
    monkeypatch.setattr(maincontroller, "dialog_openfile_hide_param_dirs",
                        lambda *args, **kwargs: (str(selected), ""))
    controller = MainController.__new__(MainController)
    controller.widget = None
    controller.model = SimpleNamespace(poni=None, chi_path=str(tmp_path))

    assert controller._confirm_missing_destination_poni(
        str(destination)) == str(selected)


def test_invalid_local_poni_still_triggers_missing_calibration_prompt(
        monkeypatch, tmp_path):
    destination = tmp_path / "next.chi"
    destination.write_text("", encoding="utf-8")
    param_dir = tmp_path / "next-param"
    param_dir.mkdir()
    (param_dir / "broken.poni").write_text("calibration", encoding="utf-8")
    prompts = []

    class FakeMessageBox:
        DontUseNativeDialog = 1
        Warning = 2
        AcceptRole = 3
        ActionRole = 4
        RejectRole = 5

        def __init__(self, parent):
            prompts.append(self)

        def addButton(self, label, role):
            return label

        def clickedButton(self):
            return "Open without PONI"

        def __getattr__(self, name):
            return lambda *args: None

    monkeypatch.setattr(maincontroller.QtWidgets, "QMessageBox", FakeMessageBox)
    controller = MainController.__new__(MainController)
    controller.widget = None
    controller.model = SimpleNamespace(poni=None)

    assert controller._confirm_missing_destination_poni(str(destination)) is False
    assert len(prompts) == 1


def test_carried_poni_is_copied_into_destination_param(tmp_path):
    source = tmp_path / "current-param" / "calibration.poni"
    source.parent.mkdir()
    source.write_text("calibration", encoding="utf-8")
    destination = tmp_path / "next.chi"
    destination.write_text("", encoding="utf-8")

    copied = MainController._copy_poni_for_navigation(
        str(source), str(destination))

    assert copied == str(tmp_path / "next-param" / "calibration.poni")
    assert (tmp_path / "next-param" / "calibration.poni").read_text(
        encoding="utf-8") == "calibration"
    assert source.read_text(encoding="utf-8") == "calibration"


def test_usable_saved_poni_reference_skips_missing_poni_prompt(
        monkeypatch, tmp_path):
    current_poni = tmp_path / "current.poni"
    current_poni.write_text("calibration", encoding="utf-8")
    destination = tmp_path / "next.chi"
    destination.write_text("", encoding="utf-8")
    saved_poni = tmp_path / "other-param" / "calibration.poni"
    saved_poni.parent.mkdir()
    saved_poni.write_text("calibration", encoding="utf-8")
    monkeypatch.setattr(maincontroller, "saved_poni_for_chi",
                        lambda path: str(saved_poni))
    monkeypatch.setattr(
        maincontroller.QtWidgets, "QMessageBox",
        lambda parent: pytest.fail("unexpected missing-PONI prompt"))
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(poni=str(current_poni))

    assert controller._confirm_missing_destination_poni(
        str(destination)) is None


def test_missing_poni_prompt_prioritizes_calibration(
        monkeypatch, tmp_path):
    destination = tmp_path / "next.chi"
    destination.write_text("", encoding="utf-8")
    param_dir = tmp_path / "next-param"
    param_dir.mkdir()
    for suffix in ("tth", "azi", "int"):
        (param_dir / f"next.{suffix}.cake.npy").write_bytes(b"cached")
    shown = {}

    class FakeMessageBox:
        DontUseNativeDialog = 1
        Warning = 2
        AcceptRole = 3
        ActionRole = 4
        RejectRole = 5

        def __init__(self, parent):
            self.buttons = {}

        def setOption(self, *args):
            pass

        def setTextFormat(self, *args):
            pass

        def setIcon(self, *args):
            pass

        def setWindowTitle(self, value):
            pass

        def setText(self, value):
            shown["text"] = value

        def setInformativeText(self, value):
            shown["detail"] = value

        def addButton(self, label, role):
            self.buttons[label] = label
            return label

        def setDefaultButton(self, button):
            shown["default"] = button

        def setEscapeButton(self, button):
            pass

        def exec(self):
            pass

        def clickedButton(self):
            return self.buttons["Open without PONI"]

    monkeypatch.setattr(maincontroller.QtWidgets, "QMessageBox", FakeMessageBox)
    controller = MainController.__new__(MainController)
    controller.widget = None
    controller.model = SimpleNamespace(poni=None)

    assert controller._confirm_missing_destination_poni(
        str(destination)) is False
    assert "Saved Cake data can still be displayed" in shown["detail"]
    assert shown["default"] == "Choose PONI"


def test_failed_navigation_removes_newly_copied_poni(
        monkeypatch, tmp_path):
    current = tmp_path / "file_001.chi"
    destination = tmp_path / "file_002.chi"
    current.write_text("", encoding="utf-8")
    destination.write_text("", encoding="utf-8")
    source = tmp_path / "file_001-param" / "calibration.poni"
    source.parent.mkdir()
    source.write_text("calibration", encoding="utf-8")
    monkeypatch.setattr(maincontroller, "is_new_param_folder",
                        lambda path: False)
    base_ptn = SimpleNamespace(fname=str(current))
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path), base_ptn=base_ptn,
        base_ptn_exist=lambda: True)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=SimpleNamespace(isChecked=lambda: True),
        spinBox_FileStep=SimpleNamespace(value=lambda: 1),
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "never"),
        comboBox_NavParamMode=SimpleNamespace(currentData=lambda: "saved"))
    controller._confirm_missing_destination_poni = lambda path: True
    controller._nav_filled_missing = False
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda *args: True)
    controller._snapshot_departing_chi = lambda: True
    controller._capture_nav_carry_state = lambda: {"poni": str(source)}
    controller._reset_setup_for_unsaved_navigation = lambda: None
    controller._defer_plot_updates = nullcontext

    def fail_to_load(path):
        raise ValueError("invalid CHI")

    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=fail_to_load)

    with pytest.raises(ValueError, match="invalid CHI"):
        controller._goto_chi_next_file("next")

    assert base_ptn.fname == str(current)
    assert not (tmp_path / "file_002-param" / "calibration.poni").exists()
    assert source.exists()
    assert controller._navigation_in_progress is False


def test_carried_poni_is_copied_before_cached_cake_load(
        monkeypatch, tmp_path):
    current = tmp_path / "file_001.chi"
    destination = tmp_path / "file_002.chi"
    current.write_text("", encoding="utf-8")
    destination.write_text("", encoding="utf-8")
    source = tmp_path / "file_001-param" / "calibration.poni"
    source.parent.mkdir()
    source.write_text("calibration", encoding="utf-8")
    param_dir = tmp_path / "file_002-param"
    param_dir.mkdir()
    for suffix in ("tth", "azi", "int"):
        (param_dir / f"file_002.{suffix}.cake.npy").write_bytes(b"cached")
    monkeypatch.setattr(maincontroller, "is_new_param_folder",
                        lambda path: False)
    base_ptn = SimpleNamespace(fname=str(current))
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path), base_ptn=base_ptn,
        base_ptn_exist=lambda: True)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=SimpleNamespace(isChecked=lambda: True),
        spinBox_FileStep=SimpleNamespace(value=lambda: 1),
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "never"),
        comboBox_NavParamMode=SimpleNamespace(currentData=lambda: "saved"))
    controller._confirm_missing_destination_poni = lambda path: True
    controller._nav_filled_missing = False
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda *args: True,
        save_recovery_state=lambda **kwargs: True)
    controller._snapshot_departing_chi = lambda: True
    controller._capture_nav_carry_state = lambda: {"poni": str(source)}
    controller._reset_setup_for_unsaved_navigation = lambda: None
    controller._defer_plot_updates = nullcontext
    events = []

    def load_destination(path):
        assert (param_dir / source.name).exists()
        events.append("loaded cached Cake")
        base_ptn.fname = path

    def apply_carry(state, **kwargs):
        assert kwargs["poni_choice"] is True
        assert state["poni"] == str(param_dir / source.name)
        assert (param_dir / source.name).is_file()
        events.append("carried PONI")

    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=load_destination)
    controller._apply_nav_carry_state = apply_carry
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)
    controller._schedule_roi_overlays_after_plot_update = lambda **kwargs: None

    controller._goto_chi_next_file("next")

    assert events == ["loaded cached Cake", "carried PONI"]


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
    assert window.comboBox_NavParamMode.styleSheet() == ""
    assert window.comboBox_NavParamModeConfig.styleSheet() == ""
    assert not window.comboBox_CarryNavExistingJCPDS.isHidden()
    assert values["nav_param_mode"] == "custom"

    window.comboBox_NavParamModeConfig.setCurrentIndex(
        window.comboBox_NavParamModeConfig.findData("existing_only"))
    controller._on_nav_param_mode_changed(window.comboBox_NavParamModeConfig)
    assert COLORS["existing_setup"] in (
        window.comboBox_NavParamModeConfig.styleSheet())
    window.comboBox_NavParamModeConfig.setCurrentIndex(
        window.comboBox_NavParamModeConfig.findData("custom"))
    controller._on_nav_param_mode_changed(window.comboBox_NavParamModeConfig)
    assert window.comboBox_NavParamModeConfig.styleSheet() == ""

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
        ({"carry_nav_existing_jcpds": "Keep existing JCPDS"}, "saved"),
        ({"nav_param_mode": "carry",
          "carry_nav_existing_jcpds": "Keep existing JCPDS"}, "carry"),
        ({"nav_param_mode": "saved"}, "saved"),
        ({"nav_param_mode": "existing_only"}, "existing_only"),
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
    assert "Use existing setup" in (
        window.pushButton_S_NextBasePtn.toolTip())
    icon_color = window.pushButton_S_NextBasePtn.icon().pixmap(
        12, 12).toImage().pixelColor(6, 6).name()
    assert icon_color == COLORS["existing_setup"]

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


def test_existing_param_is_clean_even_with_older_dirty_recovery(tmp_path):
    chi_file = tmp_path / "file_002.chi"
    chi_file.write_text("", encoding="utf-8")
    statuses = []
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: str(chi_file))
    controller.widget = SimpleNamespace(set_param_dirty_status=statuses.append)
    controller.session_ctrl = SimpleNamespace(
        _recovered_current_chi=None,
        _recovery_has_unsaved_changes=lambda path: True)
    controller._current_param_signature = lambda: "saved setup"
    controller._navigation_in_progress = False

    controller._on_pattern_ready(str(chi_file))
    controller._refresh_param_dirty_status()
    assert statuses == [False, False]

    controller.session_ctrl._recovered_current_chi = str(chi_file)
    controller._on_pattern_ready(str(chi_file))
    assert statuses[-1] is True


@pytest.mark.parametrize("mode", ["saved", "carry"])
def test_navigation_baseline_accounts_for_plot_normalization(
        monkeypatch, tmp_path, mode):
    current = tmp_path / "file_001.chi"
    destination = tmp_path / "file_002.chi"
    current.write_text("", encoding="utf-8")
    destination.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        maincontroller, "is_new_param_folder",
        lambda path: path.endswith("file_002-param"))

    base_ptn = SimpleNamespace(fname=str(current))
    model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=base_ptn,
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: base_ptn.fname)
    statuses = []
    controller = MainController.__new__(MainController)
    controller.model = model
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=SimpleNamespace(isChecked=lambda: True),
        spinBox_FileStep=SimpleNamespace(value=lambda: 1),
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "never"),
        comboBox_NavParamMode=SimpleNamespace(currentData=lambda: mode),
        set_param_dirty_status=statuses.append)
    controller._navigation_in_progress = False
    controller._nav_filled_missing = False
    signature = ["loaded"]
    controller._current_param_signature = lambda: signature[0]
    controller._capture_nav_carry_state = lambda: {}
    controller._confirm_missing_destination_poni = lambda path: None
    controller._defer_plot_updates = nullcontext
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda *args: True,
        save_recovery_state=lambda **kwargs: None)

    def load(filename):
        base_ptn.fname = filename
        signature[0] = "loaded"
        controller._on_pattern_ready(filename)

    def apply_carry(_state):
        if mode == "carry":
            signature[0] = "carried"

    controller.base_ptn_ctrl = SimpleNamespace(_load_a_new_pattern=load)
    controller._apply_nav_carry_state = apply_carry
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)
    controller._schedule_roi_overlays_after_plot_update = (
        lambda **_kwargs: signature.__setitem__(
            0, "normalized" if mode == "saved" else "carried and normalized"))

    controller._goto_chi_next_file("next")
    controller._refresh_param_dirty_status()

    assert base_ptn.fname == str(destination)
    assert statuses[-1] is (mode == "carry")
    if mode == "saved":
        signature[0] = "user edit"
        controller._refresh_param_dirty_status()
        assert statuses[-1] is True
