import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
import numpy as np
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from qtpy import QtCore, QtWidgets

from peakpo.control import maincontroller
from peakpo.control.maincontroller import MainController
from peakpo.control.sessioncontroller import SessionController
from peakpo.control import sessioncontroller
from peakpo.utils import dialogs
from peakpo.utils import apply_spinbox_fix_style
from peakpo.utils.fileutils import chi_name_set, find_from_filelist
from peakpo.utils import writechi
from peakpo.model.model import PeakPoModel


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Value:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class _Checked:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


@pytest.mark.parametrize(
    ("mode", "valid", "filled_missing", "expected_saves"),
    [
        ("never", False, True, 0),
        ("incomplete", False, True, 1),
        ("incomplete", True, False, 0),
        ("incomplete", True, True, 1),
        ("all", True, False, 1),
    ],
)
def test_param_navigation_save_policy(
        monkeypatch, tmp_path, mode, valid, filled_missing, expected_saves):
    chi_file = tmp_path / "file_001.chi"
    chi_file.write_text("", encoding="utf-8")
    controller = SessionController.__new__(SessionController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: str(chi_file),
        jcpds_lst=[], section_lst=[], waterfall_ptn=[], poni=None)
    controller._manual_saved_chi = None
    controller._recovered_current_chi = None
    controller._carryover_source_chi = None
    controller._last_param_category_presence = {}
    controller._commit_inputs_before_save = lambda: None
    controller._collect_ui_state = lambda: {}
    controller.refresh_backup_table = lambda: None
    saves = []
    monkeypatch.setattr(sessioncontroller, "is_new_param_folder",
                        lambda path: valid)
    monkeypatch.setattr(sessioncontroller, "save_model_to_param",
                        lambda *args, **kwargs: (
                            saves.append(kwargs) or
                            SimpleNamespace(manifest_path="saved")))

    assert controller.save_for_navigation(mode, filled_missing)
    assert len(saves) == expected_saves
    if saves:
        assert saves[0]["force_backup"] is False
        assert saves[0]["create_backup"] is True


def test_manual_save_takes_precedence_over_default_navigation_save(
        monkeypatch, tmp_path):
    chi_file = tmp_path / "file_001.chi"
    chi_file.write_text("", encoding="utf-8")
    controller = SessionController.__new__(SessionController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: str(chi_file))
    controller._manual_saved_chi = str(chi_file)
    monkeypatch.setattr(sessioncontroller, "save_model_to_param",
                        lambda *args, **kwargs: pytest.fail("unexpected auto save"))

    assert controller.save_for_navigation("incomplete", filled_missing=True)


def test_recovery_state_restores_last_chi_and_model(tmp_path):
    chi_file = tmp_path / "file_001.chi"
    writechi(str(chi_file), np.asarray([1.0, 2.0]),
             np.asarray([10.0, 12.0]))
    model = PeakPoModel()
    model.set_base_ptn(str(chi_file), 0.3344)
    model.save_pressure(15.0)
    widget = SimpleNamespace(
        checkBox_RestoreWorkingState=_Checked(True),
        textEdit_SessionFileName=SimpleNamespace(setText=lambda value: None),
        textEdit_Jlist=SimpleNamespace(setText=lambda value: None))
    controller = SessionController.__new__(SessionController)
    controller.model = model
    controller.widget = widget
    controller._recovery_root = lambda: str(tmp_path / "app-data")
    controller._commit_inputs_before_save = lambda: None
    controller._collect_ui_state = lambda: {}
    controller._sync_ui_from_model = lambda **kwargs: None
    controller.refresh_backup_table = lambda: None

    assert controller.save_recovery_state()
    assert not (tmp_path / "file_001-param").exists()
    controller.model = PeakPoModel()
    loader = SimpleNamespace(_load_a_new_pattern=lambda path: None)
    updates = []
    plot = SimpleNamespace(update=lambda: updates.append(True))
    assert controller.restore_recovery_state(loader, plot)
    assert controller.model.get_base_ptn_filename() == str(chi_file)
    assert controller.model.get_saved_pressure() == 15.0
    assert updates == [True]


@pytest.mark.parametrize(
    ("move", "message"),
    [
        ("previous", "It is already the first file."),
        ("next", "It is already the last file."),
    ],
)
def test_chi_navigation_boundary_shows_warning_without_loading(
        monkeypatch, tmp_path, move, message):
    chi_file = tmp_path / "only.chi"
    chi_file.write_text("", encoding="utf-8")
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=_Checked(True),
        spinBox_FileStep=_Value(1),
    )
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=SimpleNamespace(fname=str(chi_file)),
    )
    controller._capture_nav_carry_state = lambda: None
    warnings = []
    monkeypatch.setattr(
        maincontroller, "get_sorted_filelist", lambda *args, **kwargs: [str(chi_file)])
    monkeypatch.setattr(
        maincontroller, "show_warning", lambda *args: warnings.append(args[2]))

    controller._goto_chi_next_file(move)

    assert warnings == [message]


def test_filelist_lookup_requires_complete_filename(tmp_path):
    map_file = tmp_path / "map_1.chi"
    last_file = tmp_path / "1.chi"

    assert find_from_filelist([str(map_file), str(last_file)], "1.chi") == 1
    assert find_from_filelist(
        [str(map_file), str(last_file)], str(last_file)) == 1


@pytest.mark.parametrize("sort_by_name", [True, False])
def test_last_chi_with_name_contained_in_another_file_stops_at_boundary(
        monkeypatch, tmp_path, sort_by_name):
    map_file = tmp_path / "map_1.chi"
    last_file = tmp_path / "1.chi"
    map_file.write_text("", encoding="utf-8")
    last_file.write_text("", encoding="utf-8")
    os.utime(map_file, (1, 1))
    os.utime(last_file, (2, 2))
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=_Checked(sort_by_name),
        spinBox_FileStep=_Value(1),
    )
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=SimpleNamespace(fname=str(last_file)),
    )
    controller._capture_nav_carry_state = lambda: None
    warnings = []
    monkeypatch.setattr(
        maincontroller, "show_warning", lambda *args: warnings.append(args[2]))

    controller._goto_chi_next_file("next")

    assert warnings == ["It is already the last file."]


def test_next_never_reloads_current_chi_when_lookup_is_wrong(
        monkeypatch, tmp_path):
    map_file = tmp_path / "map_1.chi"
    last_file = tmp_path / "1.chi"
    map_file.write_text("", encoding="utf-8")
    last_file.write_text("", encoding="utf-8")
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=_Checked(True),
        spinBox_FileStep=_Value(1),
    )
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=SimpleNamespace(fname=str(last_file)),
    )
    controller._capture_nav_carry_state = lambda: None
    monkeypatch.setattr(maincontroller, "find_from_filelist", lambda *args: 0)
    warnings = []
    monkeypatch.setattr(
        maincontroller, "show_warning", lambda *args: warnings.append(args[2]))

    controller._goto_chi_next_file("next")

    assert warnings == ["It is already the last file."]


def test_chi_name_set_uses_stem_before_final_number():
    assert chi_name_set("file_001.chi") == chi_name_set("FILE_011.chi")
    assert chi_name_set("file_011.chi") != chi_name_set("picture_001.chi")
    assert chi_name_set("file.chi") != chi_name_set("picture.chi")


def test_same_name_set_needs_no_confirmation(tmp_path):
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn=SimpleNamespace(fname=str(tmp_path / "file_001.chi")))

    assert controller._confirm_chi_name_set_transition(
        str(tmp_path / "file_002.chi")) is True


@pytest.mark.parametrize(
    ("button_text", "expected"),
    [("Open selected file", True), ("Stay on current file", False)],
)
def test_name_set_dialog_shows_destination_and_respects_choice(
        tmp_path, button_text, expected):
    window = QtWidgets.QMainWindow()
    controller = MainController.__new__(MainController)
    controller.widget = window
    controller.model = SimpleNamespace(
        base_ptn=SimpleNamespace(fname=str(tmp_path / "file_011.chi")))
    observed = []

    def choose():
        box = next(
            widget for widget in _APP.topLevelWidgets()
            if isinstance(widget, QtWidgets.QMessageBox) and widget.isVisible()
        )
        observed.append((
            box.testOption(QtWidgets.QMessageBox.DontUseNativeDialog),
            box.informativeText(),
            box.defaultButton().text(),
        ))
        next(button for button in box.buttons()
             if button.text() == button_text).click()

    QtCore.QTimer.singleShot(0, choose)
    try:
        result = controller._confirm_chi_name_set_transition(
            str(tmp_path / "picture_001.chi"))
        assert result is expected
        assert observed[0][0] is True
        assert "file_011.chi" in observed[0][1]
        assert "picture_001.chi" in observed[0][1]
        assert observed[0][2] == "Stay on current file"
    finally:
        window.close()


@pytest.mark.parametrize("use_dpp", [False, True])
def test_declining_new_name_set_leaves_current_file_open(
        tmp_path, use_dpp):
    current = tmp_path / "file_011.chi"
    destination = tmp_path / "picture_001.chi"
    current.write_text("", encoding="utf-8")
    destination.write_text("", encoding="utf-8")
    if use_dpp:
        (tmp_path / "file_011.dpp").write_text("", encoding="utf-8")
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=_Checked(True),
        spinBox_FileStep=_Value(1),
    )
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=SimpleNamespace(fname=str(current)),
    )
    confirmations = []
    controller._confirm_chi_name_set_transition = lambda filename: (
        confirmations.append(filename) or False)
    controller._capture_nav_carry_state = lambda: pytest.fail(
        "cancelled navigation must not capture carry-over state")
    controller.session_ctrl = SimpleNamespace(
        save_dpp=lambda **kwargs: pytest.fail("cancelled navigation must not save DPP"))

    if use_dpp:
        controller._goto_dpp_next_file("next")
    else:
        controller._goto_chi_next_file("next")

    assert confirmations == [str(destination)]
    assert controller.model.base_ptn.fname == str(current)


@pytest.mark.parametrize("sort_by_name", [True, False])
def test_name_set_confirmation_only_applies_to_name_navigation(
        tmp_path, sort_by_name):
    current = tmp_path / "file_011.chi"
    destination = tmp_path / "picture_001.chi"
    current.write_text("", encoding="utf-8")
    destination.write_text("", encoding="utf-8")
    os.utime(current, (1, 1))
    os.utime(destination, (2, 2))
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        radioButton_SortbyNme=_Checked(sort_by_name),
        spinBox_FileStep=_Value(1),
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "incomplete"),
    )
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=SimpleNamespace(fname=str(current)),
    )
    confirmations = []
    controller._confirm_chi_name_set_transition = lambda filename: (
        confirmations.append(filename) or True)
    controller._capture_nav_carry_state = lambda: {}
    controller._defer_plot_updates = nullcontext
    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=lambda filename: setattr(
            controller.model.base_ptn, "fname", filename))
    controller._apply_nav_carry_state = lambda state: None
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)
    controller._schedule_roi_overlays_after_plot_update = lambda **kwargs: None
    controller._nav_filled_missing = False
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda *args: True,
        save_recovery_state=lambda: None)

    controller._goto_chi_next_file("next")

    assert controller.model.base_ptn.fname == str(destination)
    assert confirmations == ([str(destination)] if sort_by_name else [])


@pytest.mark.parametrize(
    ("action", "button_text", "expected"),
    [
        ("keep_existing", "Carry over", "overwrite_existing"),
        ("overwrite_existing", "Use existing", "keep_existing"),
    ],
)
def test_nav_carry_choice_uses_qt_dialog(action, button_text, expected):
    window = QtWidgets.QMainWindow()
    controller = MainController.__new__(MainController)
    controller.widget = window
    window.checkBox_CarryNavPopupConflict = _Checked(True)
    window.checkBox_CarryNavPopupOverwrite = _Checked(True)
    observed = []

    def choose():
        boxes = [
            widget for widget in _APP.topLevelWidgets()
            if isinstance(widget, QtWidgets.QMessageBox) and widget.isVisible()
        ]
        assert len(boxes) == 1
        box = boxes[0]
        observed.append(box.testOption(QtWidgets.QMessageBox.DontUseNativeDialog))
        button = next(
            button for button in box.buttons() if button.text() == button_text
        )
        button.click()

    QtCore.QTimer.singleShot(0, choose)
    try:
        result = controller._prompt_for_nav_carry_action("JCPDS", action)
        assert result == expected
        assert observed == [True]
    finally:
        window.close()


def test_navigation_warning_is_in_window_and_preserves_focus():
    window = QtWidgets.QMainWindow()
    spinbox = QtWidgets.QDoubleSpinBox(window)
    window.setCentralWidget(spinbox)
    window.show()
    spinbox.setFocus()
    _APP.processEvents()

    popup = dialogs.show_warning(
        window, "Warning", "It is already the last file.")
    _APP.processEvents()

    assert popup.parent() is spinbox
    assert popup.isVisible()
    assert _APP.focusWidget() is spinbox
    assert popup.testAttribute(QtCore.Qt.WA_ShowWithoutActivating)
    window.close()


def test_first_file_navigation_uses_focus_preserving_popup(
        monkeypatch, tmp_path):
    chi_file = tmp_path / "only.chi"
    chi_file.write_text("", encoding="utf-8")
    window = QtWidgets.QMainWindow()
    focused = QtWidgets.QDoubleSpinBox(window)
    window.setCentralWidget(focused)
    window.radioButton_SortbyNme = _Checked(True)
    window.spinBox_FileStep = _Value(1)
    window.show()
    focused.setFocus()
    _APP.processEvents()

    controller = MainController.__new__(MainController)
    controller.widget = window
    controller.model = SimpleNamespace(
        chi_path=str(tmp_path),
        base_ptn=SimpleNamespace(fname=str(chi_file)),
    )
    controller._capture_nav_carry_state = lambda: None
    monkeypatch.setattr(
        maincontroller,
        "get_sorted_filelist",
        lambda *args, **kwargs: [str(chi_file)],
    )

    controller._goto_chi_next_file("previous")
    _APP.processEvents()

    assert window._peakpo_warning_popup.isVisible()
    assert _APP.focusWidget() is focused
    window.close()


def test_prev_button_without_valid_pattern_uses_safe_warning(monkeypatch):
    window = QtWidgets.QMainWindow()
    button = QtWidgets.QPushButton("Prev", window)
    window.setCentralWidget(button)
    window.show()

    controller = MainController.__new__(MainController)
    controller.widget = window
    controller.model = SimpleNamespace(base_ptn_exist=lambda: False)
    button.clicked.connect(lambda: controller.goto_next_file("previous"))

    warnings = []
    monkeypatch.setattr(
        maincontroller,
        "show_warning",
        lambda *args: warnings.append(args[2]),
    )
    button.click()

    assert warnings == ["Choose a base pattern first."]
    window.close()


def test_spinbox_uses_shared_application_style_after_garbage_collection():
    spinbox = QtWidgets.QDoubleSpinBox()
    inherited_style = apply_spinbox_fix_style(spinbox)

    gc.collect()

    assert spinbox.style() is inherited_style
    assert not hasattr(spinbox, "_peakpo_spinbox_fix_style")
    spinbox.close()
