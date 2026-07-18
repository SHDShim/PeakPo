from types import SimpleNamespace

import numpy as np
import pytest
from lmfit.models import PseudoVoigtModel

from peakpo.control.peakfitcontroller import PeakFitController
from peakpo.ds_section.section import Section
from peakpo.model.model import PeakPoModel
from peakpo.model.param_session_io import _dict_to_section


class _Param:
    def __init__(self, value, vary=True):
        self.value = value
        self.vary = vary


class _CheckBox:
    def __init__(self):
        self.checked = False

    def isChecked(self):
        return self.checked

    def setChecked(self, checked):
        self.checked = bool(checked)


def _peak(sigma):
    return {
        "amplitude": 1.0,
        "center": 7.0,
        "sigma": sigma,
        "fraction": 0.5,
    }


def test_single_peak_initial_height_matches_nearest_observed_intensity():
    section = Section()
    section.set(
        np.asarray([6.9, 7.0, 7.1]),
        np.asarray([4.0, 20.0, 8.0]),
        np.zeros(3),
    )

    assert section.set_single_peak(7.03, 0.04)

    peak = section.peaks_in_queue[0]
    model = PseudoVoigtModel()
    params = model.make_params(
        amplitude=peak["amplitude"],
        center=peak["center"],
        sigma=peak["sigma"],
        fraction=peak["fraction"],
    )
    calculated_height = model.eval(
        params=params, x=np.asarray([peak["center"]]))[0]
    assert calculated_height == pytest.approx(20.0)


def test_peak_constraint_value_change_targets_selected_peak_row():
    section = Section()
    section.peaks_in_queue = [_peak(0.03), _peak(0.04)]
    model = SimpleNamespace(
        current_section=section,
        current_section_exist=lambda: True,
    )
    controller = PeakFitController.__new__(PeakFitController)
    controller.model = model
    controller.widget = SimpleNamespace()
    controller.set_tableWidget_PkParams_unsaved = lambda: None

    controller._on_peak_param_changed(1, "sigma", "value", 0.08)

    assert section.peaks_in_queue[0]["sigma"] == 0.03
    assert section.peaks_in_queue[1]["sigma"] == 0.08


def test_peak_constraint_value_change_ignores_stale_out_of_range_row():
    section = Section()
    section.peaks_in_queue = [_peak(0.03), _peak(0.04)]
    model = SimpleNamespace(
        current_section=section,
        current_section_exist=lambda: True,
    )
    controller = PeakFitController.__new__(PeakFitController)
    controller.model = model

    controller._on_peak_param_changed(2, "sigma", "value", 0.08)

    assert section.peaks_in_queue[0]["sigma"] == 0.03
    assert section.peaks_in_queue[1]["sigma"] == 0.04


def test_prepare_for_fitting_can_ignore_stored_peak_constraints():
    section = Section()
    section.set(np.linspace(6.8, 7.2, 20), np.ones(20), np.zeros(20))
    section.peaks_in_queue = [{
        "amplitude": 1.0,
        "center": 7.0,
        "sigma": 0.03,
        "fraction": 0.5,
        "phasename": "MgO",
        "h": 1,
        "k": 1,
        "l": 1,
        "center_vary": False,
        "sigma_vary": False,
        "amplitude_vary": False,
        "fraction_vary": False,
        "center_min": 6.95,
        "center_max": 7.05,
        "sigma_min": 0.02,
        "sigma_max": 0.04,
    }]

    section.prepare_for_fitting(
        0, 0.0, 0.0, apply_peak_constraints=False)

    center = section.parameters["p0_center"]
    sigma = section.parameters["p0_sigma"]
    assert center.vary is True
    assert sigma.vary is True
    assert center.min != 6.95
    assert center.max != 7.05
    assert section.peaks_in_queue[0]["center_min"] == 6.95
    assert section.peaks_in_queue[0]["center_vary"] is False


def test_prepare_for_fitting_applies_stored_peak_constraints_when_enabled():
    section = Section()
    section.set(np.linspace(6.8, 7.2, 20), np.ones(20), np.zeros(20))
    section.peaks_in_queue = [{
        "amplitude": 1.0,
        "center": 7.0,
        "sigma": 0.03,
        "fraction": 0.5,
        "phasename": "MgO",
        "h": 1,
        "k": 1,
        "l": 1,
        "center_vary": False,
        "sigma_vary": True,
        "amplitude_vary": True,
        "fraction_vary": True,
        "center_min": 6.95,
        "center_max": 7.05,
        "sigma_min": 0.02,
        "sigma_max": 0.04,
    }]

    section.prepare_for_fitting(
        0, 0.0, 0.0, apply_peak_constraints=True)

    center = section.parameters["p0_center"]
    sigma = section.parameters["p0_sigma"]
    assert center.vary is False
    assert center.min == 6.95
    assert center.max == 7.05
    assert sigma.min == 0.02
    assert sigma.max == 0.04


def test_prepare_for_fitting_respects_disabled_individual_bounds():
    section = Section()
    section.set(np.linspace(6.8, 7.2, 20), np.ones(20), np.zeros(20))
    section.peaks_in_queue = [{
        "amplitude": 1.0,
        "center": 7.0,
        "sigma": 0.03,
        "fraction": 0.5,
        "phasename": "MgO",
        "h": 1,
        "k": 1,
        "l": 1,
        "center_vary": False,
        "sigma_vary": True,
        "amplitude_vary": True,
        "fraction_vary": True,
        "center_min": 6.95,
        "center_max": 7.05,
        "center_min_enabled": False,
        "center_max_enabled": True,
        "sigma_min": 0.02,
        "sigma_max": 0.04,
        "sigma_min_enabled": True,
        "sigma_max_enabled": False,
    }]

    section.prepare_for_fitting(
        0, 0.0, 0.0, apply_peak_constraints=True)

    center = section.parameters["p0_center"]
    sigma = section.parameters["p0_sigma"]
    assert center.vary is False
    assert np.isneginf(center.min)
    assert center.max == 7.05
    assert sigma.min == 0.02
    assert np.isposinf(sigma.max)


def test_unconstrained_fit_result_does_not_overwrite_stored_vary_flags():
    section = Section()
    section.peaks_in_queue = [{
        "amplitude": 1.0,
        "center": 7.0,
        "sigma": 0.03,
        "fraction": 0.5,
        "phasename": "MgO",
        "h": 1,
        "k": 1,
        "l": 1,
        "center_vary": False,
        "sigma_vary": False,
        "amplitude_vary": False,
        "fraction_vary": False,
    }]
    section.peakinfo = {
        "p0_phasename": "MgO",
        "p0_h": 1,
        "p0_k": 1,
        "p0_l": 1,
    }
    section.baseline_in_queue = [{"value": 0.0, "vary": True}]
    section.fit_result = SimpleNamespace(params={
        "p0_center": _Param(7.01, vary=True),
        "p0_amplitude": _Param(2.0, vary=True),
        "p0_sigma": _Param(0.04, vary=True),
        "p0_fraction": _Param(0.6, vary=True),
        "b_c0": _Param(0.1, vary=True),
    })
    section._apply_peak_constraints_for_current_fit = False

    section.copy_fit_result_to_queue()

    peak = section.peaks_in_queue[0]
    assert peak["center"] == 7.01
    assert peak["center_vary"] is False
    assert peak["sigma_vary"] is False
    assert peak["amplitude_vary"] is False
    assert peak["fraction_vary"] is False


def test_selecting_saved_section_preserves_stored_vary_flags():
    section = Section()
    section.peaks_in_queue = [{
        **_peak(0.03),
        "center_vary": False,
        "sigma_vary": False,
        "amplitude_vary": False,
        "fraction_vary": False,
    }]
    section.fit_result = SimpleNamespace(params={
        "p0_center": _Param(7.0, vary=True),
        "p0_amplitude": _Param(1.0, vary=True),
        "p0_sigma": _Param(0.03, vary=True),
        "p0_fraction": _Param(0.5, vary=True),
    })
    model = PeakPoModel()
    model.section_lst = [section]

    model.set_this_section_current(0)

    peak = model.current_section.peaks_in_queue[0]
    assert peak["center_vary"] is False
    assert peak["sigma_vary"] is False
    assert peak["amplitude_vary"] is False
    assert peak["fraction_vary"] is False


def test_selecting_legacy_section_fills_only_missing_vary_flags():
    section = Section()
    section.peaks_in_queue = [{
        **_peak(0.03),
        "center_vary": False,
    }]
    section.fit_result = SimpleNamespace(params={
        "p0_center": _Param(7.0, vary=True),
        "p0_amplitude": _Param(1.0, vary=False),
        "p0_sigma": _Param(0.03, vary=True),
        "p0_fraction": _Param(0.5, vary=False),
    })
    model = PeakPoModel()
    model.section_lst = [section]

    model.set_this_section_current(0)

    peak = model.current_section.peaks_in_queue[0]
    assert peak["center_vary"] is False
    assert peak["amplitude_vary"] is False
    assert peak["sigma_vary"] is True
    assert peak["fraction_vary"] is False


def test_param_section_load_preserves_stored_vary_flags(tmp_path):
    peak = {
        **_peak(0.03),
        "center_vary": False,
        "sigma_vary": False,
        "amplitude_vary": False,
        "fraction_vary": False,
    }
    fit_params = {
        f"p0_{name}": {"value": value, "vary": True}
        for name, value in (
            ("center", 7.0),
            ("amplitude", 1.0),
            ("sigma", 0.03),
            ("fraction", 0.5),
        )
    }

    section = _dict_to_section({
        "peaks_in_queue": [peak],
        "fit_result": {"params": fit_params},
    }, str(tmp_path), str(tmp_path))

    restored = section.peaks_in_queue[0]
    assert restored["center_vary"] is False
    assert restored["sigma_vary"] is False
    assert restored["amplitude_vary"] is False
    assert restored["fraction_vary"] is False


def test_prepare_for_fitting_respects_disabled_area_minimum():
    section = Section()
    section.set(np.linspace(6.8, 7.2, 20), np.ones(20), np.zeros(20))
    section.peaks_in_queue = [{
        **_peak(0.03),
        "phasename": "MgO",
        "h": 1,
        "k": 1,
        "l": 1,
        "center_vary": True,
        "sigma_vary": True,
        "amplitude_vary": True,
        "fraction_vary": True,
        "amplitude_min": None,
        "amplitude_min_enabled": False,
    }]

    section.prepare_for_fitting(
        0, 0.0, 0.0, apply_peak_constraints=True)

    assert np.isneginf(section.parameters["p0_amplitude"].min)


def test_area_minimum_checkbox_updates_setup_and_master_checkbox():
    section = Section()
    section.peaks_in_queue = [{
        **_peak(0.03),
        "amplitude_min": 0.0,
        "amplitude_min_enabled": True,
    }]
    apply_box = _CheckBox()
    controller = PeakFitController.__new__(PeakFitController)
    controller.model = SimpleNamespace(
        current_section=section,
        current_section_exist=lambda: True,
    )
    controller.widget = SimpleNamespace(
        checkBox_ApplyPeakConstraints=apply_box)
    controller.set_tableWidget_PkParams_unsaved = lambda: None

    controller._on_peak_param_changed(0, "amplitude", "use_min", False)

    peak = section.peaks_in_queue[0]
    assert peak["amplitude_min_enabled"] is False
    assert peak["amplitude_min"] is None
    assert apply_box.isChecked() is True


def test_default_constraint_changes_enable_master_checkbox():
    apply_box = _CheckBox()
    controller = PeakFitController.__new__(PeakFitController)
    controller.widget = SimpleNamespace(
        checkBox_ApplyPeakConstraints=apply_box)

    controller.set_default_peak_bounds_values(0.1, 0.01, 0.2)

    assert apply_box.checked is True


def test_applying_default_bounds_enables_master_checkbox():
    section = Section()
    section.peaks_in_queue = [_peak(0.03)]
    apply_box = _CheckBox()
    controller = PeakFitController.__new__(PeakFitController)
    controller.model = SimpleNamespace(
        current_section=section,
        current_section_exist=lambda: True,
    )
    controller.widget = SimpleNamespace(
        checkBox_ApplyPeakConstraints=apply_box)
    controller._default_peak_bounds = {
        "center_half_range": 0.1,
        "fwhm_min": 0.01,
        "fwhm_max": 0.2,
    }
    controller.set_tableWidget_PkParams_unsaved = lambda: None
    controller.peakfit_table_ctrl = SimpleNamespace(
        update_peak_constraints=lambda: None)
    controller._constraints_dialog = None
    controller.plot_ctrl = SimpleNamespace(update=lambda: None)

    controller.apply_default_peak_bounds_to_all_peaks()

    assert apply_box.checked is True
