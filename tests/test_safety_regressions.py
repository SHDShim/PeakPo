import json
import os
from types import SimpleNamespace

import numpy as np
import pytest

from peakpo.control.sessioncontroller import SessionController
from peakpo.ds_powdiff.DiffractionPattern import Pattern
from peakpo.model import param_session_io
from peakpo.model.model import PeakPoModel
from peakpo.utils import writechi


def _chi(path):
    writechi(str(path), np.arange(1.0, 51.0), np.arange(1.0, 51.0))


def test_param_save_ignores_macos_appledouble_background_sidecars(tmp_path):
    chi = tmp_path / "base.chi"
    _chi(chi)
    model = PeakPoModel()
    model.set_base_ptn(str(chi), 0.3344)
    param_dir = tmp_path / "base-param"
    param_dir.mkdir()
    sidecar = param_dir / "._base.bgsub.chi"
    sidecar.write_bytes(b"macOS resource fork")

    assert "._base.bgsub.chi" not in param_session_io._collect_companion_files(
        str(param_dir))
    result = param_session_io.save_model_to_param(model, create_backup=False)

    assert os.path.isfile(result.manifest_path)
    assert sidecar.read_bytes() == b"macOS resource fork"


def test_param_save_survives_disappearing_macos_staging_sidecar(
        monkeypatch, tmp_path):
    chi = tmp_path / "base.chi"
    _chi(chi)
    model = PeakPoModel()
    model.set_base_ptn(str(chi), 0.3344)
    original_rmtree = param_session_io.shutil.rmtree
    saw_staging_cleanup = False

    def simulate_sidecar_race(path, *args, **kwargs):
        nonlocal saw_staging_cleanup
        if os.path.basename(path).startswith(".stage-"):
            saw_staging_cleanup = True
            missing = FileNotFoundError(2, "No such file or directory",
                                        "._base.bgsub.chi")
            kwargs["onerror"](os.unlink, missing.filename,
                              (FileNotFoundError, missing, None))
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(param_session_io.shutil, "rmtree",
                        simulate_sidecar_race)
    result = param_session_io.save_model_to_param(model, create_backup=False)

    assert saw_staging_cleanup
    assert os.path.isfile(result.manifest_path)
    assert not list((tmp_path / "base-param").glob(".stage-*"))


def test_background_controls_use_order_then_iteration(monkeypatch):
    pattern = Pattern()
    pattern.x_raw = np.arange(50.0)
    pattern.y_raw = np.ones(50)
    received = {}

    def fit(x, y, **kwargs):
        received.update(kwargs)
        return np.zeros_like(y)

    monkeypatch.setattr("peakpo.ds_powdiff.DiffractionPattern.fit_bg_cheb_auto", fit)
    pattern.subtract_bg([0.0, 49.0], [10, 20, 40])
    assert received == {"n_points": 10, "n_iteration": 40, "n_cheborder": 20}
    assert pattern.x_bg[-1] == 49.0


def test_background_rejects_empty_and_single_point_roi():
    pattern = Pattern()
    pattern.x_raw = np.arange(10.0)
    pattern.y_raw = np.ones(10)
    for roi in ([2.0, 2.1], [3.0, 2.0]):
        with pytest.raises(ValueError, match="Background ROI"):
            pattern.subtract_bg(roi, [10, 20, 40])


def test_existing_setup_wins_over_unsaved_navigation_recovery(tmp_path):
    first, second = tmp_path / "first.chi", tmp_path / "second.chi"
    _chi(first)
    _chi(second)
    model = PeakPoModel()
    model.set_base_ptn(str(first), 0.3344)
    model.save_pressure(10.0)
    param_session_io.save_model_to_param(model, create_backup=False)
    model.save_pressure(15.0)

    controller = SessionController.__new__(SessionController)
    controller.model = model
    controller.widget = SimpleNamespace(
        checkBox_RestoreWorkingState=SimpleNamespace(isChecked=lambda: True))
    controller._recovery_root = lambda: str(tmp_path / "private")
    controller._commit_inputs_before_save = lambda: None
    controller._collect_ui_state = lambda: {}
    controller._sync_ui_from_model = lambda **kwargs: None
    controller.param_dirty_callback = lambda: (
        model.get_base_ptn_filename() == str(first))
    controller._manual_saved_chi = None
    controller._recovered_current_chi = None

    assert controller.save_recovery_state()
    first_recovery = controller._recovery_dir(str(first))
    model.set_base_ptn(str(second), 0.3344)
    assert controller.save_recovery_state()
    assert os.path.isdir(first_recovery)
    model.set_base_ptn(str(first), 0.3344)
    assert controller.autoload_param_for_chi(str(first))
    assert model.get_saved_pressure() == 10.0
    assert controller._recovered_current_chi is None
    assert controller._recovery_has_unsaved_changes(str(first))


def test_recovery_loads_for_chi_without_visible_param(tmp_path):
    chi = tmp_path / "unsaved.chi"
    _chi(chi)
    model = PeakPoModel()
    model.set_base_ptn(str(chi), 0.3344)
    model.save_pressure(15.0)
    controller = SessionController.__new__(SessionController)
    controller.model = model
    controller.widget = SimpleNamespace(
        checkBox_RestoreWorkingState=SimpleNamespace(isChecked=lambda: True))
    controller._recovery_root = lambda: str(tmp_path / "private")
    controller._commit_inputs_before_save = lambda: None
    controller._collect_ui_state = lambda: {}
    controller._sync_ui_from_model = lambda **kwargs: None
    controller.param_dirty_callback = lambda: True
    controller._manual_saved_chi = None
    controller._recovered_current_chi = None
    assert controller.save_recovery_state()
    model.set_base_ptn(str(chi), 0.3344)
    assert controller.autoload_param_for_chi(str(chi))
    assert model.get_saved_pressure() == 15.0
    assert controller._recovered_current_chi == str(chi)


def test_strict_existing_ignores_private_recovery_without_visible_param(tmp_path):
    chi = tmp_path / "unsaved.chi"
    _chi(chi)
    model = PeakPoModel()
    model.set_base_ptn(str(chi), 0.3344)
    model.save_pressure(15.0)
    controller = SessionController.__new__(SessionController)
    controller.model = model
    controller.widget = SimpleNamespace(
        checkBox_RestoreWorkingState=SimpleNamespace(isChecked=lambda: True))
    controller._recovery_root = lambda: str(tmp_path / "private")
    controller._commit_inputs_before_save = lambda: None
    controller._collect_ui_state = lambda: {}
    controller._sync_ui_from_model = lambda **kwargs: None
    controller.param_dirty_callback = lambda: True
    controller._manual_saved_chi = None
    controller._recovered_current_chi = None
    assert controller.save_recovery_state()

    model.set_base_ptn(str(chi), 0.3344)
    assert not controller.autoload_param_for_chi(
        str(chi), allow_private_recovery=False)
    assert controller._recovered_current_chi is None


def test_interrupted_param_save_rolls_back_complete_previous_state(
        monkeypatch, tmp_path):
    chi = tmp_path / "base.chi"
    _chi(chi)
    model = PeakPoModel()
    model.set_base_ptn(str(chi), 0.3344)
    model.save_pressure(10.0)
    result = param_session_io.save_model_to_param(model, create_backup=False)
    model.save_pressure(15.0)
    original_write = param_session_io._atomic_write_bytes
    failed = False

    def interrupted(path, payload):
        nonlocal failed
        if path.endswith(param_session_io.BACKUP_INDEX_FILE) and not failed:
            failed = True
            raise OSError("simulated interruption")
        return original_write(path, payload)

    monkeypatch.setattr(param_session_io, "_atomic_write_bytes", interrupted)
    with pytest.raises(OSError, match="simulated interruption"):
        param_session_io.save_model_to_param(model, create_backup=False)
    monkeypatch.setattr(param_session_io, "_atomic_write_bytes", original_write)
    restored = PeakPoModel()
    success, _ = param_session_io.load_model_from_param(restored, str(chi))
    assert success
    assert restored.get_saved_pressure() == 10.0
    assert not os.path.exists(os.path.join(result.param_dir, ".pending-save"))


def test_next_load_recovers_save_stopped_without_exception_cleanup(
        monkeypatch, tmp_path):
    chi = tmp_path / "base.chi"
    _chi(chi)
    model = PeakPoModel()
    model.set_base_ptn(str(chi), 0.3344)
    model.save_pressure(10.0)
    result = param_session_io.save_model_to_param(model, create_backup=False)
    model.save_pressure(15.0)
    original_write = param_session_io._atomic_write_bytes

    def stopped(path, payload):
        if path.endswith(param_session_io.BACKUP_INDEX_FILE):
            raise KeyboardInterrupt("simulated process stop")
        return original_write(path, payload)

    monkeypatch.setattr(param_session_io, "_atomic_write_bytes", stopped)
    with pytest.raises(KeyboardInterrupt, match="simulated process stop"):
        param_session_io.save_model_to_param(model, create_backup=False)
    monkeypatch.setattr(param_session_io, "_atomic_write_bytes", original_write)
    assert os.path.isdir(os.path.join(result.param_dir, ".pending-save"))
    restored = PeakPoModel()
    success, _ = param_session_io.load_model_from_param(restored, str(chi))
    assert success
    assert restored.get_saved_pressure() == 10.0


@pytest.mark.parametrize(
    ("key", "invalid"),
    [
        ("saved_pressure", "bad-value"),
        ("saved_pressure", float("nan")),
        ("saved_pressure", 1001.0),
        ("saved_temperature", None),
        ("saved_temperature", -1.0),
    ],
)
def test_invalid_saved_pt_rejected_before_model_changes(tmp_path, key, invalid):
    chi = tmp_path / "base.chi"
    _chi(chi)
    source = PeakPoModel()
    source.set_base_ptn(str(chi), 0.3344)
    result = param_session_io.save_model_to_param(
        source, create_backup=False)
    jcpds_path = os.path.join(result.param_dir, param_session_io.JCPDS_FILE)
    with open(jcpds_path, encoding="utf-8") as stream:
        payload = json.load(stream)
    payload[key] = invalid
    with open(jcpds_path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream)

    restored = PeakPoModel()
    original_pressure = restored.get_saved_pressure()
    original_temperature = restored.get_saved_temperature()
    success, meta = param_session_io.load_model_from_param(restored, str(chi))

    assert not success
    assert key.removeprefix("saved_") in meta["reason"]
    assert restored.base_ptn is None
    assert restored.get_saved_pressure() == original_pressure
    assert restored.get_saved_temperature() == original_temperature


def test_numeric_string_saved_pressure_remains_readable(tmp_path):
    chi = tmp_path / "base.chi"
    _chi(chi)
    source = PeakPoModel()
    source.set_base_ptn(str(chi), 0.3344)
    result = param_session_io.save_model_to_param(source, create_backup=False)
    jcpds_path = os.path.join(result.param_dir, param_session_io.JCPDS_FILE)
    with open(jcpds_path, encoding="utf-8") as stream:
        payload = json.load(stream)
    payload["saved_pressure"] = "8.25"
    with open(jcpds_path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream)

    restored = PeakPoModel()
    success, meta = param_session_io.load_model_from_param(restored, str(chi))

    assert success, meta
    assert restored.get_saved_pressure() == 8.25
