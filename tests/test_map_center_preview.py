import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from qtpy import QtCore, QtWidgets

from peakpo.control.mapcontroller import MapController
from peakpo.control.maincontroller import MainController


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize("current_in_set", [False, True])
def test_map_file_set_previews_center_only_for_external_chi(
        tmp_path, current_in_set):
    selected = [str(tmp_path / f"map_{index:03d}.chi") for index in range(3)]
    # The external file deliberately has the same basename as a selected file.
    current = selected[0] if current_in_set else str(
        tmp_path / "other" / "map_001.chi")
    controller = MapController.__new__(MapController)
    controller._chi_input_files = selected
    controller._ordered_chi_files = list
    controller._derive_position_indices = lambda files: list(range(len(files)))
    controller._rebuild_linear_lookup = lambda: None
    controller._clear_hover_file = lambda: None
    controller._set_loaded_count = lambda: None
    controller._detect_scan_coordinates = lambda progress=False: None
    controller._current_displayed_chi = lambda: current
    controller._grid = (3, 1)
    controller.widget = SimpleNamespace(
        spinBox_MapNx=SimpleNamespace(value=lambda: 3),
        spinBox_MapNy=SimpleNamespace(value=lambda: 1))
    previews = []
    controller._preview_center_file = lambda: previews.append(True)

    controller._refresh_loaded_files()

    assert previews == ([] if current_in_set else [True])


def test_map_progress_is_hidden_during_forced_save_prompt(tmp_path):
    selected = [str(tmp_path / "map_001.chi")]
    controller = MapController.__new__(MapController)
    controller._chi_input_files = selected
    controller._ordered_chi_files = list
    controller._derive_position_indices = lambda files: [0]
    controller._rebuild_linear_lookup = lambda: None
    controller._clear_hover_file = lambda: None
    controller._set_loaded_count = lambda: None
    controller._detect_scan_coordinates = lambda progress=False: None
    controller._current_displayed_chi = lambda: str(tmp_path / "outside.chi")
    controller._grid = (1, 1)
    controller.widget = SimpleNamespace(
        spinBox_MapNx=SimpleNamespace(value=lambda: 1),
        spinBox_MapNy=SimpleNamespace(value=lambda: 1))
    events = []
    controller._update_progress = lambda *args: None
    controller._progress_dialog = SimpleNamespace(
        hide=lambda: events.append("hide"),
        show=lambda: events.append("show"))
    controller._preview_center_file = lambda: events.append("prompt")

    controller._refresh_loaded_files(progress=True)

    assert events == ["hide", "prompt", "show"]


@pytest.mark.parametrize("current_in_set", [False, True])
def test_entering_map_tab_previews_center_only_for_external_chi(
        tmp_path, current_in_set):
    selected = [str(tmp_path / "map_001.chi")]
    current = selected[0] if current_in_set else str(tmp_path / "other.chi")
    controller = MapController.__new__(MapController)
    controller._chi_files = selected
    controller._current_displayed_chi = lambda: current
    active_tab = object()
    controller.widget = SimpleNamespace(
        tab_Map=active_tab,
        tabWidget=SimpleNamespace(currentWidget=lambda: active_tab))
    previews = []
    controller._preview_center_file = lambda: previews.append(True)
    controller.refresh_current_marker = lambda: None
    controller.refresh_roi_overlays = lambda: None

    controller._on_main_tab_changed(0)

    assert previews == ([] if current_in_set else [True])


def test_center_preview_uses_normal_chi_opening_path(tmp_path):
    selected = [str(tmp_path / f"map_{index:03d}.chi") for index in range(9)]
    controller = MapController.__new__(MapController)
    controller._chi_files = selected
    controller._grid = (3, 3)
    controller._lin_to_file = {index: index for index in range(9)}
    controller._grid_to_linear = lambda x, y: y * 3 + x
    opened = []
    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=lambda path: opened.append(path))
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)
    controller._schedule_overlay_refresh = lambda: None

    controller._preview_center_file()

    assert opened == [selected[4]]


def test_center_preview_uses_middle_file_when_grid_is_incomplete(tmp_path):
    controller = MapController.__new__(MapController)
    controller._chi_files = [
        str(tmp_path / f"map_{index:03d}.chi") for index in range(5)]
    controller._grid = (3, 2)
    controller._set_status = lambda message: None
    opened = []
    controller._load_file_to_main_plot = (
        lambda index, prompt_save=False: opened.append(
            (index, prompt_save)))

    controller._preview_center_file()

    assert opened == [(2, True)]


@pytest.mark.parametrize("save_succeeds", [False, True])
def test_map_file_open_respects_param_navigation_save(
        tmp_path, save_succeeds):
    current = tmp_path / "other.chi"
    selected = tmp_path / "map_001.chi"
    current.write_text("", encoding="utf-8")
    selected.write_text("", encoding="utf-8")
    active = [str(current)]
    actions = []
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: active[0])
    controller.widget = SimpleNamespace(
        comboBox_NavSaveMode=SimpleNamespace(currentData=lambda: "incomplete"))
    controller._nav_filled_missing = True
    controller.session_ctrl = SimpleNamespace(
        save_for_navigation=lambda mode, filled: (
            actions.append(("save", mode, filled)) or save_succeeds),
        save_recovery_state=lambda: actions.append(("recovery",)))
    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=lambda path: (
            actions.append(("open", path)), active.__setitem__(0, path)))
    controller.plot_ctrl = SimpleNamespace(
        update=lambda: actions.append(("plot",)))

    result = controller._open_chi_from_map(str(selected))

    assert result is save_succeeds
    assert actions[0] == ("save", "incomplete", True)
    assert (("open", str(selected)) in actions) is save_succeeds


@pytest.mark.parametrize(
    ("choice", "expected_result", "expected_save", "expected_open"),
    [
        ("save", True, True, True),
        ("skip", True, False, True),
        ("cancel", False, False, False),
    ],
)
def test_forced_map_switch_honors_param_prompt(
        tmp_path, choice, expected_result, expected_save, expected_open):
    current = tmp_path / "outside.chi"
    selected = tmp_path / "map_002.chi"
    current.write_text("", encoding="utf-8")
    selected.write_text("", encoding="utf-8")
    active = [str(current)]
    actions = []
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: active[0])
    controller._confirm_map_param_save = lambda old, new: choice
    controller.session_ctrl = SimpleNamespace(
        save_dpp=lambda: actions.append("manual save") or True,
        save_for_navigation=lambda *args: pytest.fail("unexpected auto save"),
        save_recovery_state=lambda: None)
    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=lambda path: (
            actions.append("open"), active.__setitem__(0, path)))
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)

    assert controller._open_chi_from_map(
        str(selected), prompt_save=True) is expected_result
    assert ("manual save" in actions) is expected_save
    assert ("open" in actions) is expected_open


def test_failed_param_save_keeps_current_chi(tmp_path):
    current = tmp_path / "outside.chi"
    selected = tmp_path / "map_002.chi"
    current.write_text("", encoding="utf-8")
    selected.write_text("", encoding="utf-8")
    controller = MainController.__new__(MainController)
    controller.model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: str(current))
    controller._confirm_map_param_save = lambda old, new: "save"
    controller.session_ctrl = SimpleNamespace(save_dpp=lambda: False)
    controller.base_ptn_ctrl = SimpleNamespace(
        _load_a_new_pattern=lambda path: pytest.fail("unexpected CHI open"))

    assert not controller._open_chi_from_map(
        str(selected), prompt_save=True)


def test_forced_map_prompt_defaults_to_saving_and_shows_filenames(tmp_path):
    window = QtWidgets.QMainWindow()
    controller = MainController.__new__(MainController)
    controller.widget = window
    observed = []

    def choose():
        box = next(
            item for item in _APP.topLevelWidgets()
            if isinstance(item, QtWidgets.QMessageBox) and item.isVisible())
        observed.append((
            box.testOption(QtWidgets.QMessageBox.DontUseNativeDialog),
            box.informativeText(), box.defaultButton().text()))
        box.defaultButton().click()

    QtCore.QTimer.singleShot(0, choose)
    try:
        choice = controller._confirm_map_param_save(
            str(tmp_path / "outside.chi"),
            str(tmp_path / "map_002.chi"))
        assert choice == "save"
        assert observed[0][0] is True
        assert "outside.chi" in observed[0][1]
        assert "map_002.chi" in observed[0][1]
        assert observed[0][2] == "Save PARAM and open"
    finally:
        window.close()
