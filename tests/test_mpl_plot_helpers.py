from types import SimpleNamespace

import numpy as np
from qtpy import QtWidgets
from qtpy import QtCore

from peakpo.control.mplcontroller import (
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
from peakpo.view.mplwidget import MplCanvas


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
