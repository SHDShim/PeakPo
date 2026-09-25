import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
from types import SimpleNamespace

import pytest
from qtpy import QtWidgets

from peakpo.control import maincontroller
from peakpo.control.maincontroller import MainController
from peakpo.utils import dialogs
from peakpo.utils import apply_spinbox_fix_style


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


def test_macos_warning_disables_native_dialog(monkeypatch):
    observed = {}

    def fake_exec(box):
        option = QtWidgets.QMessageBox.Option.DontUseNativeDialog
        observed["non_native"] = box.testOption(option)
        return QtWidgets.QMessageBox.Ok

    monkeypatch.setattr(dialogs.sys, "platform", "darwin")
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", fake_exec)

    dialogs.show_warning(None, "Warning", "It is already the last file.")

    assert observed == {"non_native": True}


def test_spinbox_retains_python_proxy_style_after_garbage_collection():
    spinbox = QtWidgets.QDoubleSpinBox()
    apply_spinbox_fix_style(spinbox)

    gc.collect()

    assert spinbox.style() is spinbox._peakpo_spinbox_fix_style
    spinbox.close()
