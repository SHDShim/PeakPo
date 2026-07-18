from types import SimpleNamespace

import numpy as np

from peakpo.control.peakfitcontroller import PeakFitController
from peakpo.ds_section.section import Section


def _peak(sigma):
    return {
        "amplitude": 1.0,
        "center": 7.0,
        "sigma": sigma,
        "fraction": 0.5,
    }


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
    class Param:
        def __init__(self, value, vary=True):
            self.value = value
            self.vary = vary

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
        "p0_center": Param(7.01, vary=True),
        "p0_amplitude": Param(2.0, vary=True),
        "p0_sigma": Param(0.04, vary=True),
        "p0_fraction": Param(0.6, vary=True),
        "b_c0": Param(0.1, vary=True),
    })
    section._apply_peak_constraints_for_current_fit = False

    section.copy_fit_result_to_queue()

    peak = section.peaks_in_queue[0]
    assert peak["center"] == 7.01
    assert peak["center_vary"] is False
    assert peak["sigma_vary"] is False
    assert peak["amplitude_vary"] is False
    assert peak["fraction_vary"] is False
