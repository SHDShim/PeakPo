import os
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from peakpo.control import maincontroller
from peakpo.control.maincontroller import MainController


@pytest.mark.parametrize(
    ("has_param", "choice", "expected_open", "expected_carry"),
    [
        (True, "cancel", False, False),
        (True, "existing", True, False),
        (True, "carry", True, True),
        (False, "existing", True, False),
    ],
)
def test_manual_open_existing_param_choice(
        monkeypatch, tmp_path, has_param, choice,
        expected_open, expected_carry):
    current = tmp_path / "file_001.chi"
    selected = tmp_path / "file_002.chi"
    current.write_text("", encoding="utf-8")
    selected.write_text("", encoding="utf-8")
    active = [str(current)]
    opened = []
    applied = []
    prompted = []
    saved = []

    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: active[0])
    controller.widget = SimpleNamespace(
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "incomplete"))
    controller._nav_filled_missing = False
    controller._capture_nav_carry_state = lambda: {"source_chi": current.name}
    controller._defer_plot_updates = nullcontext
    controller._apply_nav_carry_state = lambda snap, **kwargs: applied.append(
        (snap, kwargs))
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda *args: saved.append("param") or True,
        save_recovery_state=lambda **kwargs: saved.append("recovery"))
    controller.base_ptn_ctrl = SimpleNamespace(
        _is_derived_provenance=lambda provenance: False,
        _same_path=lambda a, b: os.path.normcase(os.path.abspath(a)) ==
        os.path.normcase(os.path.abspath(b)),
        _setshow_new_base_ptn=lambda filename: (
            opened.append(filename), active.__setitem__(0, filename)))
    controller._confirm_manual_open_param_choice = lambda *args: (
        prompted.append(args) or choice)
    controller._confirm_missing_destination_poni = lambda path: None
    monkeypatch.setattr(maincontroller, "provenance_for_chi", lambda _: {})
    monkeypatch.setattr(maincontroller, "is_new_param_folder",
                        lambda _: has_param)

    controller._open_chi_manually(str(selected))

    assert bool(opened) is expected_open
    assert bool(applied) is expected_carry
    assert bool(prompted) is has_param
    assert bool(saved) is expected_open
    if expected_carry:
        assert applied[0][1] == {"force_overwrite_existing": True}


def test_explicit_carry_replaces_enabled_existing_categories():
    controller = MainController.__new__(MainController)
    controller.widget = SimpleNamespace(
        checkBox_CarryNavJCPDS=SimpleNamespace(isChecked=lambda: True),
        checkBox_CarryNavPressure=SimpleNamespace(isChecked=lambda: False))
    presence = {"jcpds": True, "pressure": True}

    assert controller._get_nav_carry_action(
        "jcpds", "checkBox_CarryNavJCPDS", presence,
        force_overwrite_existing=True) == "overwrite_existing"
    assert controller._get_nav_carry_action(
        "pressure", "checkBox_CarryNavPressure", presence,
        force_overwrite_existing=True) == "skip"
