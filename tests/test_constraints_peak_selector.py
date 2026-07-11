import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from qtpy import QtWidgets

from peakpo.control.peakfitcontroller import PeakFitController
from peakpo.ds_section.section import Section
from peakpo.model.model import PeakPoModel
from peakpo.view.mainwidget import MainWindow


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _peak(phase, h, k, l, area, center):
    return {
        "phasename": phase,
        "h": h,
        "k": k,
        "l": l,
        "amplitude": area,
        "center": center,
        "sigma": 0.03,
        "fraction": 0.4,
        "amplitude_vary": True,
        "center_vary": True,
        "sigma_vary": True,
        "fraction_vary": True,
    }


def test_constraints_peak_selector_updates_peak_selection_and_marker():
    window = MainWindow()
    model = PeakPoModel()
    section = Section()
    section.set(np.linspace(7.0, 8.0, 20), np.ones(20), np.zeros(20))
    section.peaks_in_queue = [
        _peak("MgO.jcpds", 1, 1, 1, 25.0, 7.25),
        _peak("FeO", 2, 0, 0, 10.5, 7.75),
    ]
    model.current_section = section
    controller = PeakFitController(model, window)
    controller.peakfit_table_ctrl.update_peak_parameters()

    marker_refreshes = []
    controller.plot_ctrl.refresh_selected_peak_marker = (
        lambda: marker_refreshes.append(True) or True)
    window.tabWidget_PeakFit.setCurrentWidget(window.tab_PeakFitConstraints)
    _APP.processEvents()

    selector = window.comboBox_ConstraintPeak
    content_layout = window.verticalLayout_ConstraintsContent
    assert content_layout.indexOf(selector) < \
        content_layout.indexOf(window.groupBox_PeakConstraintEditor)
    assert selector.count() == 3
    assert selector.itemText(0) == "Select a peak…"
    assert selector.itemText(1) == "MgO (1 1 1) | Area 25 | Position 7.25000°"
    assert selector.itemText(2) == "FeO (2 0 0) | Area 10.5 | Position 7.75000°"

    selector.setCurrentIndex(2)
    _APP.processEvents()

    assert window.tableWidget_PkParams.currentRow() == 1
    assert controller._constraints_tab_current_row == 1
    assert window.tableWidget_PeakConstraintDetail.rowCount() == 4
    assert marker_refreshes

    window.close()
    _APP.processEvents()


def test_fit_quality_statistics_use_original_section_samples_only():
    class FitResult:
        success = False
        chisqr = 0.125
        nfev = 12

        @staticmethod
        def eval(x):
            assert len(x) == 3
            return np.array([1.0, 1.5, 4.0])

    section = Section()
    section.set(np.array([1.0, 2.0, 3.0]),
                np.array([1.0, 2.0, 3.0]), np.zeros(3))
    section.fit_result = FitResult()

    statistics = section.get_fit_quality_statistics()

    assert statistics["function_evaluations"] == 12
    assert statistics["chi_square"] == 0.125
    assert statistics["rp"] == 0.25
    assert statistics["rwp"] == np.sqrt(1.25 / 14.0)
