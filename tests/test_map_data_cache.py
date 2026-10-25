import os
import json
import shutil
from types import SimpleNamespace

import numpy as np
import pytest
from qtpy import QtWidgets

from peakpo.control.mapdatacache import MapDataCache
from peakpo.control.mapcontroller import MapController
from peakpo.control.xrdiohelpers import load_cake_data, sum_cake_roi
from peakpo.ds_powdiff.DiffractionPattern import Pattern
from peakpo.model.model import PeakPoModel
from peakpo.utils import writechi
from peakpo.view.mainwidget import MainWindow


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_map_roi_cache_reuses_background_and_invalidates_changed_source(
        tmp_path, monkeypatch):
    path = tmp_path / "map_001.chi"
    path.write_text("original", encoding="utf-8")
    x = np.linspace(1, 5, 41)
    y = 2 + np.sin(x) ** 2
    fit_calls = []
    original_fit = MapDataCache._background_xy

    def fit(*args):
        fit_calls.append(args[2:])
        return original_fit(*args)

    monkeypatch.setattr(MapDataCache, "_background_xy", staticmethod(fit))
    cache = MapDataCache()
    cache.set_files([str(path)])
    monkeypatch.setattr(cache, "_raw_xy", lambda _path: (x, y))
    bg_roi = (1.0, 5.0)
    params = (5, 3, 2)
    expected_x, expected_y = original_fit(x, y, bg_roi, params)
    roi = (2.0, 4.0)
    expected = np.nansum(expected_y[(expected_x >= 2) & (expected_x <= 4)])
    assert np.isclose(cache.sum_roi(str(path), roi, bg_roi, params), expected)
    assert np.isclose(cache.sum_roi(str(path), (3.0, 5.0), bg_roi, params),
                      np.nansum(expected_y[(expected_x >= 3) & (expected_x <= 5)]))
    assert len(fit_calls) == 1
    assert list((tmp_path / "map_param").glob("*/*.npz"))

    restored = MapDataCache()
    restored.set_files([str(path)])
    monkeypatch.setattr(restored, "_raw_xy", lambda _path: (_ for _ in ()).throw(
        AssertionError("recomputed saved map data")))
    assert np.isclose(restored.sum_roi(str(path), roi, bg_roi, params), expected)
    assert len(fit_calls) == 1

    path.write_text("modified", encoding="utf-8")
    os.utime(path, None)
    monkeypatch.setattr(cache, "_raw_xy", lambda _path: (x, y))
    cache.sum_roi(str(path), roi, bg_roi, params)
    assert len(fit_calls) == 2


def test_map_roi_sum_handles_nan_empty_and_unordered_axes(tmp_path, monkeypatch):
    path = tmp_path / "map_001.chi"
    path.write_text("data", encoding="utf-8")
    cache = MapDataCache()
    cache.set_files([str(path)])
    monkeypatch.setattr(cache, "_raw_xy", lambda _path: (
        np.array([1., 2., 3., 4.]), np.array([2., np.nan, 5., 7.])))
    assert cache.sum_roi(str(path), (1.5, 3.5)) == 5
    assert np.isnan(cache.sum_roi(str(path), (8., 9.)))

    other = tmp_path / "map_002.chi"
    other.write_text("data", encoding="utf-8")
    cache.set_files([str(path), str(other)])
    monkeypatch.setattr(cache, "_raw_xy", lambda _path: (
        np.array([3., 1., 2.]), np.array([5., 2., 4.])))
    assert cache.sum_roi(str(other), (1.5, 3.0)) == 9


def test_map_cake_load_can_use_memory_mapping(tmp_path, monkeypatch):
    paths = [tmp_path / f"cake.{part}.npy" for part in ("tth", "azi", "int")]
    for path, data in zip(paths, (
            np.arange(3.), np.arange(2.), np.arange(6.).reshape(2, 3))):
        np.save(path, data)
    monkeypatch.setattr(
        "peakpo.control.xrdiohelpers.find_temp_cake_triplet",
        lambda _path: tuple(str(path) for path in paths))
    loaded = load_cake_data("sample.chi", {}, mmap_mode="r")
    assert isinstance(loaded[2], np.memmap)
    assert float(np.nansum(loaded[2])) == 15
    assert sum_cake_roi(loaded, (1., 2., 0., 1.)) == 12
    assert np.isnan(sum_cake_roi(loaded, (4., 5., 0., 1.)))
    reversed_cake = (loaded[0][::-1], loaded[1], loaded[2][:, ::-1])
    assert sum_cake_roi(reversed_cake, (1., 2., 0., 1.)) == 12


def test_map_coordinate_cache_invalidates_metadata_changes(tmp_path):
    chi = tmp_path / "map_001.chi"
    metadata = tmp_path / "map_001.metadata.json"
    chi.write_text("chi", encoding="utf-8")
    metadata.write_text("one", encoding="utf-8")
    calls = []
    cache = MapDataCache()
    cache.set_files([str(chi)])

    def resolve():
        calls.append(True)
        return (1.0, 2.0)

    assert cache.coordinates(str(chi), [str(metadata)], resolve) == (1.0, 2.0)
    cache.save_coordinates()
    restored = MapDataCache()
    restored.set_files([str(chi)])
    assert restored.coordinates(str(chi), [str(metadata)], resolve) == [1.0, 2.0]
    assert len(calls) == 1
    metadata.write_text("changed", encoding="utf-8")
    assert restored.coordinates(str(chi), [str(metadata)], resolve) == (1.0, 2.0)
    assert len(calls) == 2


def test_map_cache_survives_folder_move(tmp_path, monkeypatch):
    source = tmp_path / "from_windows"
    source.mkdir()
    chi = source / "map_001.chi"
    chi.write_text("same CHI", encoding="utf-8")
    cache = MapDataCache()
    cache.set_files([str(chi)])
    monkeypatch.setattr(cache, "_raw_xy", lambda _path: (
        np.array([1., 2., 3.]), np.array([2., 3., 4.])))
    assert cache.sum_roi(str(chi), (1., 3.)) == 9
    destination = tmp_path / "on_mac"
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    moved = destination / chi.name
    restored = MapDataCache()
    restored.set_files([str(moved)])
    monkeypatch.setattr(restored, "_raw_xy", lambda _path: (_ for _ in ()).throw(
        AssertionError("cache did not survive folder move")))
    assert restored.sum_roi(str(moved), (1., 3.)) == 9


def test_flat_map_cache_remains_readable(tmp_path, monkeypatch):
    chi = tmp_path / "map_001.chi"
    chi.write_text("chi", encoding="utf-8")
    cache = MapDataCache()
    cache.set_files([str(chi)])
    monkeypatch.setattr(cache, "_raw_xy", lambda _path: (
        np.array([1., 2.]), np.array([3., 4.])))
    assert cache.sum_roi(str(chi), (1., 2.)) == 7
    subfolder_file = next((tmp_path / "map_param").glob("*/*.npz"))
    shutil.move(subfolder_file, tmp_path / "map_param" / subfolder_file.name)
    restored = MapDataCache()
    restored.set_files([str(chi)])
    monkeypatch.setattr(restored, "_raw_xy", lambda _path: (_ for _ in ()).throw(
        AssertionError("legacy cache was ignored")))
    assert restored.sum_roi(str(chi), (1., 2.)) == 7


def test_multiple_map_sets_restore_matching_current_chi(tmp_path):
    a = [tmp_path / f"alpha_map_{i}_0001.chi" for i in (1, 2)]
    b = [tmp_path / f"beta_map_{i}_0001.chi" for i in (1, 2)]
    for path in a + b:
        path.write_text("chi", encoding="utf-8")
    for paths, grid, roi in ((a, [2, 1], [1.0, 2.0]),
                              (b, [1, 2], [3.0, 4.0])):
        cache = MapDataCache()
        cache.set_files([str(path) for path in paths])
        assert cache.save_state({
            "name": cache.set_name,
            "files": [path.name for path in paths],
            "grid": grid,
            "roi_1d": roi,
            "roi_2d": None,
            "order": 0,
        })
    states = MapDataCache.discover_states(str(tmp_path))
    assert len(states) == 2
    assert len({state["_directory"] for state in states}) == 2
    assert MapDataCache.file_set_name([str(a[0])]) != MapDataCache.file_set_name(
        [str(path) for path in a])

    order = QtWidgets.QComboBox()
    order.addItems(["Row-major", "Snake"])
    cmap = QtWidgets.QComboBox()
    cmap.addItems(["viridis", "plasma"])
    controller = MapController.__new__(MapController)
    controller._chi_files = []
    controller._chi_input_files = []
    controller._restoring_state = False
    controller._loading_map_files = False
    controller._map_cache = MapDataCache()
    controller.widget = SimpleNamespace(
        comboBox_MapSet=QtWidgets.QComboBox(),
        label_MapSet=QtWidgets.QLabel(),
        spinBox_MapNx=QtWidgets.QSpinBox(),
        spinBox_MapNy=QtWidgets.QSpinBox(),
        comboBox_MapOrder=order,
        comboBox_MapCmap=cmap,
        checkBox_MapLog=QtWidgets.QCheckBox(),
        doubleSpinBox_MapVmin=QtWidgets.QDoubleSpinBox(),
        doubleSpinBox_MapVmax=QtWidgets.QDoubleSpinBox(),
        doubleSpinBox_MapPctLow=QtWidgets.QDoubleSpinBox(),
        doubleSpinBox_MapPctHigh=QtWidgets.QDoubleSpinBox(),
        lineEdit_MapRoiSummary=QtWidgets.QLineEdit(),
    )
    controller.widget.spinBox_MapNx.setRange(1, 9999)
    controller.widget.spinBox_MapNy.setRange(1, 9999)
    controller._refresh_loaded_files = lambda reset_grid=False: (
        controller._chi_files.extend(controller._chi_input_files),
        setattr(controller, "_grid", (
            controller.widget.spinBox_MapNx.value(),
            controller.widget.spinBox_MapNy.value())))
    computed = []
    controller._compute_map = lambda: computed.append(True)
    controller._draw_map = lambda: None
    controller._set_status = lambda message: None
    controller._is_map_tab_active = lambda: True

    assert controller.maybe_restore_for_chi(str(b[0]))
    assert controller._chi_input_files == [str(path) for path in b]
    assert controller._grid == (1, 2)
    assert controller._roi_1d == (3.0, 4.0)
    assert controller.widget.comboBox_MapSet.count() == 3
    assert computed == [True]
    controller._is_map_tab_active = lambda: False
    controller._chi_files = []
    assert controller._restore_map_state(states[0])
    assert computed == [True]
    assert controller._pending_map_compute is True


def test_existing_flat_map_cache_seeds_only_matching_file_set(tmp_path):
    (tmp_path / "map_param").mkdir()
    (tmp_path / "map_param" / "coordinates.json").write_text(
        json.dumps({"entries": {"alpha_map_1_0001.chi": {
            "sources": [], "xy": None}}}), encoding="utf-8")
    for name in ("alpha_map_1_0001.chi", "alpha_map_2_0001.chi",
                 "beta_map_1_0001.chi", "alpha_map_1_0001.bgsub.chi"):
        (tmp_path / name).write_text("chi", encoding="utf-8")
    controller = MapController.__new__(MapController)
    controller._loading_map_files = False
    controller._filename_sort_key = lambda path: path
    controller._refresh_loaded_files = lambda reset_grid=False: None
    controller._set_default_1d_full_range_roi = lambda: setattr(
        controller, "_roi_1d", (1., 2.))
    computed = []
    controller._compute_map = lambda: computed.append(True)
    controller._save_map_state = lambda: None
    controller._chi_files = []
    controller._is_map_tab_active = lambda: True

    assert controller._restore_unrecorded_set(
        str(tmp_path / "alpha_map_1_0001.chi"), str(tmp_path))
    assert [os.path.basename(path) for path in controller._chi_input_files] == [
        "alpha_map_1_0001.chi", "alpha_map_2_0001.chi"]
    assert computed == [True]


def test_map_tab_uses_working_folder_when_no_chi_is_open(tmp_path):
    controller = MapController.__new__(MapController)
    controller._chi_files = []
    controller.model = SimpleNamespace(chi_path=str(tmp_path))
    controller._current_displayed_chi = lambda: None
    active_tab = object()
    controller.widget = SimpleNamespace(
        tab_Map=active_tab,
        tabWidget=SimpleNamespace(currentWidget=lambda: active_tab))
    state = {"name": "saved-map"}
    controller._refresh_available_sets = lambda folder: [state]
    restored = []
    controller._restore_map_state = lambda found: restored.append(found)
    controller.refresh_current_marker = lambda: None
    controller.refresh_roi_overlays = lambda: None

    controller._on_main_tab_changed(0)

    assert restored == [state]


def test_map_tab_computes_restored_map_only_when_opened():
    controller = MapController.__new__(MapController)
    controller._chi_files = []
    controller._pending_map_compute = True
    controller._current_displayed_chi = lambda: None
    controller.maybe_restore_for_chi = lambda filename: False
    active_tab = object()
    controller.widget = SimpleNamespace(
        tab_Map=active_tab,
        tabWidget=SimpleNamespace(currentWidget=lambda: active_tab))
    computed = []
    controller._compute_map = lambda: computed.append(True)
    controller.refresh_current_marker = lambda: None
    controller.refresh_roi_overlays = lambda: None

    controller._on_main_tab_changed(0)

    assert computed == [True]
    assert controller._pending_map_compute is False


@pytest.mark.parametrize("outside_name", (
    "beta_map_1_0001.chi", "alpha_map_3_0001.chi"))
def test_nonmember_chi_clears_map_without_deleting_saved_set(
        tmp_path, outside_name):
    members = [tmp_path / f"alpha_map_{i}_0001.chi" for i in (1, 2)]
    outside = tmp_path / outside_name
    for index, path in enumerate(members + [outside]):
        writechi(str(path), np.linspace(1, 10, 20),
                 np.linspace(1, 10, 20) + index)
    window = MainWindow()
    model = PeakPoModel()
    model.base_ptn = SimpleNamespace(fname=str(members[0]))
    controller = MapController(model, window)
    controller._chi_input_files = [str(path) for path in members]
    controller._refresh_loaded_files(reset_grid=True)
    controller._set_default_1d_full_range_roi()
    controller._compute_map()
    saved_state = next((tmp_path / "map_param").glob("*/state.json"))
    assert controller._map_data is not None

    model.base_ptn.fname = str(outside)
    assert not controller.maybe_restore_for_chi(str(outside))

    assert controller._chi_files == []
    assert controller._map_data is None
    assert controller._roi_1d is None
    assert window.label_MapLoaded.text() == "Loaded: 0"
    assert window.lineEdit_MapRoiSummary.text() == ""
    assert controller._map_ax.axison is False
    assert saved_state.is_file()
    window.close()
