import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import numpy as np
from qtpy import QtWidgets

from peakpo.control.maincontroller import MainController
from peakpo.view.mainwidget import MainWindow
from peakpo.view.mplwidget import MplCanvas


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_cake_integration_tables_have_similar_heights():
    window = MainWindow()
    window.resize(1800, 1200)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Cake1)
    window.tabWidget_2.setCurrentWidget(window.tabWidget_2Page2)
    _APP.processEvents()

    roi_height = window.tableWidget_DiffImgAzi.height()
    chi_height = window.tableWidget_AziChiList.height()

    window.close()
    _APP.processEvents()

    assert abs(roi_height - chi_height) <= 12


def test_cake_config_has_readonly_poni_and_summary_tables():
    window = MainWindow()
    window.resize(1800, 1200)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Cake1)
    window.tabWidget_2.setCurrentWidget(window.tabWidget_2Page1)
    _APP.processEvents()

    assert window.groupBox_CakePoniTable.title() == "PONI contents"
    assert window.groupBox_CakeSummary.title() == "Cake information"
    assert window.tableWidget_CakePoniInfo.columnCount() == 2
    assert window.tableWidget_CakeSummary.columnCount() == 2
    assert window.tableWidget_CakePoniInfo.editTriggers() == (
        QtWidgets.QAbstractItemView.NoEditTriggers)
    assert window.tableWidget_CakeSummary.editTriggers() == (
        QtWidgets.QAbstractItemView.NoEditTriggers)

    window.close()
    _APP.processEvents()


def test_cake_config_low_high_labels_are_compact_and_close_to_spinboxes():
    window = MainWindow()
    window.resize(1800, 1200)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Cake1)
    window.tabWidget_2.setCurrentWidget(window.tabWidget_2Page2)
    _APP.processEvents()

    assert window.cake_hist_widget.label_low.maximumWidth() == 42
    assert window.cake_hist_widget.label_high.maximumWidth() == 46
    assert window.gridLayout_CakeTop.columnStretch(2) == 0
    assert window.gridLayout_CakeTop.columnStretch(4) == 0
    assert window.gridLayout_CakeTop.columnMinimumWidth(2) == 8
    assert window.gridLayout_CakeTop.columnMinimumWidth(4) == 8

    window.close()
    _APP.processEvents()


def test_pattern_background_tab_has_full_width_range_and_default_buttons():
    window = MainWindow()
    window.resize(1800, 1200)
    window.show()
    window.tabWidget.setCurrentWidget(window.tab_Bkgn)
    window.tabWidget_5.setCurrentWidget(window.tabWidget_5Page1)
    _APP.processEvents()

    assert window.pushButton_SetBackgroundROIToCurrentRange.text() == (
        "Set to current two theta range")
    assert window.pushButton_SetBackgroundROIToCurrentRange.sizePolicy().horizontalPolicy() == (
        QtWidgets.QSizePolicy.Expanding)
    assert window.pushButton_SetBackgroundROIToCurrentRange.parent() == (
        window.groupBox_4)
    assert window.label_4.text() == "N Points:"
    assert window.label_6.text() == "N Order:"
    assert window.label_5.text() == "N Iteration:"
    assert window.pushButton_ResetBGParams.text() == (
        "Reset to default")
    assert window.pushButton_ResetBGParams.sizePolicy().horizontalPolicy() == (
        QtWidgets.QSizePolicy.Minimum)
    assert window.pushButton_ResetBGParams.minimumWidth() == (
        window.spinBox_BGParam0.minimumWidth())
    assert window.verticalLayout_21.indexOf(window.groupBox_7) < (
        window.verticalLayout_21.indexOf(window.pushButton_UpdateBackground))

    window.close()
    _APP.processEvents()


def test_set_background_roi_to_current_range_copies_plot_xlim():
    canvas = MplCanvas()
    canvas.resize_axes(30)
    canvas.ax_pattern.set_xlim(7.25, 18.75)

    min_box = QtWidgets.QDoubleSpinBox()
    max_box = QtWidgets.QDoubleSpinBox()

    ctrl = MainController.__new__(MainController)
    ctrl.widget = SimpleNamespace(
        mpl=SimpleNamespace(canvas=canvas),
        doubleSpinBox_Background_ROI_min=min_box,
        doubleSpinBox_Background_ROI_max=max_box,
    )

    ctrl.set_background_roi_to_current_range()

    assert min_box.value() == 7.25
    assert max_box.value() == 18.75


def test_update_background_preserves_current_plot_limits():
    class _PatternStub:
        def __init__(self):
            self.x_raw = np.asarray([5.0, 10.0, 15.0, 20.0])
            self.y_raw = np.asarray([1.0, 2.0, 3.0, 4.0])
            self.calls = []

        def subtract_bg(self, roi, params, yshift=0):
            self.calls.append((list(roi), list(params), yshift))

        def write_temporary_bgfiles(self, temp_dir=None):
            self.temp_dir = temp_dir

    class _PlotCtrlStub:
        def __init__(self):
            self.limits = None
            self.updated_jcpds = 0

        def refresh_pattern_data(self, limits=None):
            self.limits = limits

        def update_jcpds_only(self):
            self.updated_jcpds += 1

    canvas = MplCanvas()
    canvas.resize_axes(30)
    canvas.ax_pattern.set_xlim(8.0, 16.0)
    canvas.ax_pattern.set_ylim(-2.0, 50.0)

    base_pattern = _PatternStub()
    plot_ctrl = _PlotCtrlStub()

    ctrl = MainController.__new__(MainController)
    ctrl.widget = SimpleNamespace(
        mpl=SimpleNamespace(canvas=canvas),
        spinBox_BGParam0=SimpleNamespace(value=lambda: 20),
        spinBox_BGParam1=SimpleNamespace(value=lambda: 10),
        spinBox_BGParam2=SimpleNamespace(value=lambda: 20),
        doubleSpinBox_Background_ROI_min=SimpleNamespace(
            value=lambda: 6.0, setValue=lambda value: None),
        doubleSpinBox_Background_ROI_max=SimpleNamespace(
            value=lambda: 18.0, setValue=lambda value: None),
    )
    ctrl.model = SimpleNamespace(
        base_ptn=base_pattern,
        base_ptn_exist=lambda: True,
        get_base_ptn_filename=lambda: "/tmp/example.chi",
        display_ptn_exist=lambda: False,
        waterfall_exist=lambda: False,
    )
    ctrl.plot_ctrl = plot_ctrl
    ctrl._plot_update_deferred = lambda: False
    ctrl._schedule_roi_overlays_after_plot_update = lambda *args, **kwargs: None
    ctrl.plot_new_graph = lambda: (_ for _ in ()).throw(
        AssertionError("plot_new_graph should not be used when limits are available"))

    ctrl.update_bgsub()

    assert plot_ctrl.limits == [8.0, 16.0, -2.0, 50.0]
    assert plot_ctrl.updated_jcpds == 1
    assert base_pattern.calls == [([6.0, 18.0], [20, 10, 20], 0)]
