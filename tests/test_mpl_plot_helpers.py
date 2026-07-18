import os
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from matplotlib import colors as mcolors
from qtpy import QtWidgets
from qtpy import QtCore

from peakpo.control.mplcontroller import (
    MplController,
    _azimuth_shift_rows,
    _bragg_dspacing,
    _coordinate_edges,
    _coordinates_are_uniform,
    _nearest_coordinate_index,
)
from peakpo.control.plotinteractioncontroller import (
    PlotInteractionController,
    _PlotKeyStateFilter,
)
from peakpo.ds_section.section import Section
from peakpo.view.mplwidget import MplCanvas


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_coordinate_edges_expand_pixel_centers_by_half_a_bin():
    centers = np.asarray([10.0, 10.5, 11.0])

    np.testing.assert_allclose(
        _coordinate_edges(centers), [9.75, 10.25, 10.75, 11.25])


def test_coordinate_edges_support_nonuniform_monotonic_centers():
    centers = np.asarray([1.0, 2.0, 4.0])

    np.testing.assert_allclose(
        _coordinate_edges(centers), [0.5, 1.5, 3.0, 5.0])
    assert not _coordinates_are_uniform(centers)


def test_uniform_coordinates_use_fast_image_rendering_path():
    assert _coordinates_are_uniform(np.linspace(-180.0, 180.0, 361))


def test_nearest_coordinate_index_uses_real_ascending_coordinates():
    centers = np.asarray([1.0, 2.0, 4.0, 8.0])

    assert _nearest_coordinate_index(centers, 3.6) == 2


def test_nearest_coordinate_index_supports_descending_coordinates():
    centers = np.asarray([8.0, 4.0, 2.0, 1.0])

    assert _nearest_coordinate_index(centers, 3.6) == 1


def test_azimuth_shift_uses_actual_chi_spacing():
    chi = np.linspace(-90.0, 90.0, 181)

    assert _azimuth_shift_rows(chi, 10.0) == 10


def test_bragg_dspacing_validates_domain_and_uses_two_theta():
    assert _bragg_dspacing(0.0, 0.3344) is None
    assert _bragg_dspacing(181.0, 0.3344) is None
    assert _bragg_dspacing(20.0, -1.0) is None

    expected = 0.3344 / (2.0 * np.sin(np.deg2rad(10.0)))
    assert np.isclose(_bragg_dspacing(20.0, 0.3344), expected)


def test_update_impl_unchecks_show_cake_when_cake_cannot_be_plotted():
    container = QtWidgets.QWidget()
    canvas = MplCanvas()
    canvas.toolbar = None
    canvas.resize_axes(30)
    canvas.ax_pattern.set_xlim(20.0, 40.0)
    canvas.ax_pattern.set_ylim(1.0, 2.0)

    show_cake = QtWidgets.QCheckBox(container)
    show_cake.setChecked(True)
    auto_y = QtWidgets.QCheckBox(container)
    auto_y.setChecked(False)
    long_cursor = QtWidgets.QCheckBox(container)
    long_cursor.setChecked(False)
    axis_size = QtWidgets.QSlider(QtCore.Qt.Horizontal, container)
    axis_size.setRange(1, 100)
    axis_size.setValue(30)
    wavelength = QtWidgets.QDoubleSpinBox(container)
    wavelength.setValue(0.3344)
    short_title = QtWidgets.QCheckBox(container)
    short_title.setChecked(True)
    intensity = QtWidgets.QCheckBox(container)
    intensity.setChecked(True)

    widget = container
    widget.mpl = SimpleNamespace(canvas=canvas)
    widget.checkBox_ShowCake = show_cake
    widget.checkBox_AutoY = auto_y
    widget.checkBox_LongCursor = long_cursor
    widget.horizontalSlider_CakeAxisSize = axis_size
    widget.doubleSpinBox_SetWavelength = wavelength
    widget.checkBox_ShortPlotTitle = short_title
    widget.checkBox_Intensity = intensity

    model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        jcpds_exist=lambda: False,
        diff_img_exist=lambda: True,
        waterfall_exist=lambda: False,
    )

    ctrl = object.__new__(MplController)
    ctrl.model = model
    ctrl.widget = widget
    ctrl.obj_color = "k"
    ctrl._is_drawing = False
    ctrl._toolbar_active = False
    ctrl._pending_update_args = None
    ctrl._derived_label_visible = False
    ctrl._plot_cake = Mock(return_value=False)
    ctrl._set_nightday_view = Mock()
    ctrl._apply_pattern_background_style = Mock()
    ctrl._plot_diffpattern = Mock()
    ctrl._plot_derived_pattern_label = Mock(return_value=False)
    ctrl._fits_tab_active = Mock(return_value=False)
    ctrl._update_pnt_artist = Mock()
    ctrl._ensure_vertical_cursor_artists = Mock()
    ctrl.clear_vertical_cursor_position = Mock()
    ctrl._schedule_canvas_draw = Mock()
    ctrl._display_pattern_filename = Mock(return_value="/tmp/sample.chi")

    ctrl._update_impl()

    assert not widget.checkBox_ShowCake.isChecked()
    ctrl._plot_cake.assert_called_once()


def test_update_impl_unchecks_show_cake_when_no_cake_image_exists():
    container = QtWidgets.QWidget()
    canvas = MplCanvas()
    canvas.toolbar = None
    canvas.resize_axes(30)
    canvas.ax_pattern.set_xlim(20.0, 40.0)
    canvas.ax_pattern.set_ylim(1.0, 2.0)

    show_cake = QtWidgets.QCheckBox(container)
    show_cake.setChecked(True)
    auto_y = QtWidgets.QCheckBox(container)
    auto_y.setChecked(False)
    long_cursor = QtWidgets.QCheckBox(container)
    long_cursor.setChecked(False)
    axis_size = QtWidgets.QSlider(QtCore.Qt.Horizontal, container)
    axis_size.setRange(1, 100)
    axis_size.setValue(30)
    wavelength = QtWidgets.QDoubleSpinBox(container)
    wavelength.setValue(0.3344)
    short_title = QtWidgets.QCheckBox(container)
    short_title.setChecked(True)
    intensity = QtWidgets.QCheckBox(container)
    intensity.setChecked(True)

    widget = container
    widget.mpl = SimpleNamespace(canvas=canvas)
    widget.checkBox_ShowCake = show_cake
    widget.checkBox_AutoY = auto_y
    widget.checkBox_LongCursor = long_cursor
    widget.horizontalSlider_CakeAxisSize = axis_size
    widget.doubleSpinBox_SetWavelength = wavelength
    widget.checkBox_ShortPlotTitle = short_title
    widget.checkBox_Intensity = intensity

    model = SimpleNamespace(
        base_ptn_exist=lambda: True,
        jcpds_exist=lambda: False,
        diff_img_exist=lambda: False,
        waterfall_exist=lambda: False,
    )

    ctrl = object.__new__(MplController)
    ctrl.model = model
    ctrl.widget = widget
    ctrl.obj_color = "k"
    ctrl._is_drawing = False
    ctrl._toolbar_active = False
    ctrl._pending_update_args = None
    ctrl._derived_label_visible = False
    ctrl._plot_cake = Mock()
    ctrl._set_nightday_view = Mock()
    ctrl._apply_pattern_background_style = Mock()
    ctrl._plot_diffpattern = Mock()
    ctrl._plot_derived_pattern_label = Mock(return_value=False)
    ctrl._fits_tab_active = Mock(return_value=False)
    ctrl._update_pnt_artist = Mock()
    ctrl._ensure_vertical_cursor_artists = Mock()
    ctrl.clear_vertical_cursor_position = Mock()
    ctrl._schedule_canvas_draw = Mock()
    ctrl._display_pattern_filename = Mock(return_value="/tmp/sample.chi")

    ctrl._update_impl()

    assert not widget.checkBox_ShowCake.isChecked()
    ctrl._plot_cake.assert_not_called()


def test_peakfit_individual_profiles_are_yellow_and_total_remains_red():
    canvas = MplCanvas()
    canvas.resize_axes(30)
    x = np.asarray([1.0, 2.0, 3.0])
    section = SimpleNamespace(
        x=x,
        peaks_exist=lambda: False,
        fitted=lambda: True,
        get_individual_profiles=lambda bgsub=False: {
            "p0_": np.asarray([0.0, 1.0, 0.0]),
            "p1_": np.asarray([0.0, 0.5, 0.0]),
        },
        get_fit_profile=lambda bgsub=False: np.asarray([0.0, 1.5, 0.0]),
        get_fit_residue=lambda bgsub=False: np.zeros(3),
        get_fit_residue_baseline=lambda bgsub=False: np.zeros(3),
        get_yrange=lambda bgsub=False: (0.0, 1.5),
    )
    ctrl = object.__new__(MplController)
    ctrl.model = SimpleNamespace(
        current_section=section,
        current_section_exist=lambda: True,
    )
    ctrl.widget = SimpleNamespace(
        mpl=SimpleNamespace(canvas=canvas),
        checkBox_BgSub=SimpleNamespace(isChecked=lambda: False),
        comboBox_BasePtnLineThickness=SimpleNamespace(currentText=lambda: "1.0"),
    )
    ctrl._peakfit_overlay_artists = []
    ctrl._clear_selected_peak_marker = lambda: None
    ctrl._clear_peak_center_markers = lambda: None

    ctrl._plot_peakfit()

    lines = canvas.ax_pattern.lines
    assert len(lines) == 3
    assert all(
        mcolors.to_rgba(line.get_color()) == mcolors.to_rgba("yellow")
        for line in lines[:2])
    assert mcolors.to_rgba(lines[2].get_color()) == mcolors.to_rgba("red")


def test_unfitted_peaks_plot_initial_profiles_without_gray_center_lines():
    class TableStub:
        def selectionModel(self):
            return None

        def currentItem(self):
            return None

        def currentRow(self):
            return -1

    canvas = MplCanvas()
    canvas.resize_axes(30)
    x = np.linspace(6.8, 7.2, 101)
    section = Section()
    section.set(
        x,
        50.0 * np.exp(-((x - 7.0) / 0.03) ** 2),
        np.zeros_like(x),
    )
    assert section.set_single_peak(7.0, 0.01)
    ctrl = object.__new__(MplController)
    ctrl.model = SimpleNamespace(
        current_section=section,
        current_section_exist=lambda: True,
        jcpds_lst=[],
    )
    ctrl.widget = SimpleNamespace(
        mpl=SimpleNamespace(canvas=canvas),
        checkBox_BgSub=SimpleNamespace(isChecked=lambda: False),
        checkBox_ShowCake=SimpleNamespace(isChecked=lambda: False),
        comboBox_BasePtnLineThickness=SimpleNamespace(currentText=lambda: "1.0"),
        tableWidget_PkParams=TableStub(),
        tableWidget_PeakConstraints=TableStub(),
    )
    ctrl._peakfit_overlay_artists = []
    ctrl._peak_center_marker_artists = []
    ctrl._selected_peak_marker_artists = []

    ctrl._plot_peakfit()

    assert len(canvas.ax_pattern.lines) == 1
    line = canvas.ax_pattern.lines[0]
    assert len(line.get_xdata()) == len(x)
    assert mcolors.to_rgba(line.get_color()) == mcolors.to_rgba("yellow")


class _LabelStub:
    def __init__(self):
        self.text = None

    def setText(self, text):
        self.text = text


def _make_controller():
    canvas = MplCanvas()
    canvas.resize_axes(30)
    canvas.ax_pattern.set_xlim(20.0, 40.0)
    canvas.ax_pattern.set_ylim(1.0, 2.0)
    canvas.ax_cake.set_xlim(20.0, 40.0)
    canvas.ax_cake.set_ylim(-30.0, 30.0)

    widget = SimpleNamespace(
        mpl=SimpleNamespace(canvas=canvas),
        label_PlotHelp=_LabelStub(),
    )
    main = SimpleNamespace(
        model=SimpleNamespace(
            base_ptn_exist=lambda: True,
            current_section_exist=lambda: False,
        ),
        widget=widget,
        plot_ctrl=SimpleNamespace(
            _get_data_limits=lambda: (0.0, 100.0, 10.0, 20.0),
        ),
        _deactivate_toolbar_modes=lambda: None,
        plot_new_graph=lambda: None,
        read_plot=lambda *args, **kwargs: None,
    )
    return PlotInteractionController(main), canvas


def _event_from_data(ax, *, button, xdata, ydata, key="", dblclick=False):
    xpix, ypix = ax.transData.transform((xdata, ydata))
    return SimpleNamespace(
        inaxes=ax,
        button=button,
        xdata=float(xdata),
        ydata=float(ydata),
        x=float(xpix),
        y=float(ypix),
        key=key,
        dblclick=dblclick,
    )


def test_x_modifier_zoom_drag_changes_x_only():
    ctrl, canvas = _make_controller()
    press = _event_from_data(
        canvas.ax_pattern, button=1, xdata=25.0, ydata=1.5, key="x")
    release = _event_from_data(
        canvas.ax_pattern, button=1, xdata=35.0, ydata=1.8, key="x")

    ctrl.set_zoom_x_modifier(True)
    ctrl.on_press(press)
    ctrl.on_release(release)
    ctrl.set_zoom_x_modifier(False)

    np.testing.assert_allclose(canvas.ax_pattern.get_xlim(), [25.0, 35.0])
    np.testing.assert_allclose(canvas.ax_pattern.get_ylim(), [1.0, 2.0])


def test_x_modifier_right_click_zooms_x_only():
    ctrl, canvas = _make_controller()
    event = _event_from_data(
        canvas.ax_pattern, button=3, xdata=30.0, ydata=1.5, key="x")

    ctrl.set_zoom_x_modifier(True)
    ctrl.on_press(event)
    ctrl.set_zoom_x_modifier(False)

    np.testing.assert_allclose(canvas.ax_pattern.get_xlim(), [18.0, 42.0])
    np.testing.assert_allclose(canvas.ax_pattern.get_ylim(), [1.0, 2.0])


def test_plot_key_state_filter_tracks_keys_before_canvas_focus():
    ctrl, _canvas = _make_controller()
    key_filter = _PlotKeyStateFilter(ctrl)

    press = SimpleNamespace(
        type=lambda: QtCore.QEvent.KeyPress,
        text=lambda: "x",
        key=lambda: QtCore.Qt.Key_X,
    )
    release = SimpleNamespace(
        type=lambda: QtCore.QEvent.KeyRelease,
        text=lambda: "x",
        key=lambda: QtCore.Qt.Key_X,
    )

    assert key_filter.eventFilter(None, press) is False
    assert ctrl._zoom_x_modifier is True
    assert key_filter.eventFilter(None, release) is False
    assert ctrl._zoom_x_modifier is False


class _PhaseStub:
    def __init__(self, name, color, volume):
        self.name = name
        self.color = color
        self.v = volume
        self.display = True
        self.twk_int = 1.0
        self.symmetry = "cubic"

    def cal_dsp(self, pressure, temperature, use_table_for_0GPa=True):
        del pressure, temperature, use_table_for_0GPa

    def get_tthVSint(self, wavelength):
        del wavelength
        return np.asarray([5.0, 8.0]), np.asarray([10.0, 20.0])

    def get_hkl_in_text(self):
        return ["111", "200"]


def _make_jcpds_plot_controller():
    container = QtWidgets.QWidget()
    canvas = MplCanvas()
    canvas.toolbar = None
    canvas.resize_axes(30)
    canvas.ax_pattern.set_xlim(4.0, 12.0)
    canvas.ax_pattern.set_ylim(0.0, 100.0)
    canvas.ax_cake.set_xlim(4.0, 12.0)
    canvas.ax_cake.set_ylim(-180.0, 180.0)

    table = QtWidgets.QTableWidget(2, 1, container)
    for row, label in enumerate(("phase a", "phase b")):
        table.setItem(row, 0, QtWidgets.QTableWidgetItem(label))
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    def _checkbox(checked=False):
        box = QtWidgets.QCheckBox(container)
        box.setChecked(checked)
        return box

    def _spinbox(value):
        box = QtWidgets.QDoubleSpinBox(container)
        box.setValue(value)
        return box

    def _slider(value):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, container)
        slider.setRange(0, 100)
        slider.setValue(value)
        return slider

    def _combo(text):
        combo = QtWidgets.QComboBox(container)
        combo.addItem(text)
        combo.setCurrentText(text)
        return combo

    widget = container
    widget.mpl = SimpleNamespace(canvas=canvas)
    widget.tableWidget_JCPDS = table
    widget.checkBox_JCPDSinPattern = _checkbox(True)
    widget.checkBox_JCPDSinCake = _checkbox(False)
    widget.checkBox_ShowCake = _checkbox(False)
    widget.checkBox_Intensity = _checkbox(True)
    widget.checkBox_ShowMillerIndices = _checkbox(False)
    widget.checkBox_UseJCPDSTable1bar = _checkbox(True)
    widget.horizontalSlider_JCPDSBarScale = _slider(100)
    widget.horizontalSlider_JCPDSBarPosition = _slider(0)
    widget.doubleSpinBox_Pressure = _spinbox(0.0)
    widget.doubleSpinBox_Temperature = _spinbox(300.0)
    widget.doubleSpinBox_SetWavelength = _spinbox(0.3344)
    widget.doubleSpinBox_JCPDS_ptn_Alpha = _spinbox(1.0)
    widget.doubleSpinBox_JCPDS_cake_Alpha = _spinbox(0.25)
    widget.comboBox_PtnJCPDSBarThickness = _combo("1")
    widget.comboBox_LegendFontSize = _combo("12")

    model = SimpleNamespace(
        jcpds_lst=[
            _PhaseStub("phase a", "#ff0000", 10.0),
            _PhaseStub("phase b", "#00ff00", 20.0),
        ],
        jcpds_exist=lambda: True,
    )
    return MplController(model, widget), widget


def test_jcpds_legend_text_highlight_tracks_selected_table_row():
    ctrl, widget = _make_jcpds_plot_controller()

    ctrl._plot_jcpds(widget.mpl.canvas.ax_pattern.axis())
    legend = widget.mpl.canvas.ax_pattern.get_legend()
    assert legend is not None
    handles = getattr(legend, "legend_handles", None)
    if handles is None:
        handles = getattr(legend, "legendHandles", [])
    assert all(not handle.get_visible() for handle in handles)

    widget.tableWidget_JCPDS.selectRow(1)
    ctrl.refresh_jcpds_overlay()

    text_colors = {
        text.get_text().split(",")[0]: mcolors.to_rgba(text.get_color())
        for text in legend.get_texts()
    }
    assert np.isclose(text_colors["phase a"][-1], 0.25)
    assert np.isclose(text_colors["phase b"][-1], 1.0)
    assert np.isclose(ctrl._get_jcpds_plot_alpha(0, {1}), 0.25)
    assert np.isclose(ctrl._get_jcpds_plot_alpha(0, {1}, 0.6), 0.15)
    assert ctrl._jcpds_bar_alphas() == (1.0, 0.6)


def test_active_peak_guide_uses_nearest_displayed_observed_intensity():
    controller = object.__new__(MplController)
    controller.model = SimpleNamespace(current_section=SimpleNamespace(
        x=np.asarray([8.1, 8.2, 8.3]),
        y_bgsub=np.asarray([10.0, 20.0, 30.0]),
        y_bg=np.asarray([1.0, 2.0, 3.0]),
    ))
    controller.widget = SimpleNamespace(
        checkBox_BgSub=SimpleNamespace(isChecked=lambda: False))

    assert controller._nearest_observed_peak_intensity(8.24) == 22.0

    controller.widget.checkBox_BgSub = SimpleNamespace(isChecked=lambda: True)
    assert controller._nearest_observed_peak_intensity(8.24) == 20.0


def test_active_peak_triangle_sits_just_above_observed_intensity():
    canvas = MplCanvas()
    canvas.ax_pattern.set_ylim(0.0, 100.0)

    assert MplController._active_peak_triangle_y(
        canvas.ax_pattern, 40.0) == 42.0
