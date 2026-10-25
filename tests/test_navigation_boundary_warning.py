import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
from types import SimpleNamespace

import pytest
from qtpy import QtCore, QtWidgets

from peakpo.control import maincontroller
from peakpo.control.maincontroller import MainController
from peakpo.utils import dialogs
from peakpo.utils import apply_spinbox_fix_style
from peakpo.utils.fileutils import find_from_filelist


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
