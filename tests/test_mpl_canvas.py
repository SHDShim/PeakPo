import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy import QtWidgets
from qtpy import QtCore
import matplotlib as mpl
import matplotlib.style as mplstyle

from peakpo.view.mplwidget import MplCanvas


_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_initial_night_axes_remain_visible_from_default_matplotlib_style():
    with mpl.rc_context():
        mplstyle.use("default")
        canvas = MplCanvas()
        canvas.resize_axes(30)

        assert canvas.ax_pattern.xaxis.label.get_color() == "white"
        assert canvas.ax_pattern.yaxis.label.get_color() == "white"
        assert all(spine.get_edgecolor() == (1.0, 1.0, 1.0, 1.0)
                   for spine in canvas.ax_pattern.spines.values())
        assert canvas.ax_pattern.xaxis.get_tick_params()["labelcolor"] == "white"
        assert canvas.ax_pattern.yaxis.get_tick_params()["labelcolor"] == "white"
        canvas.close()


def test_cake_x_tick_labels_stay_hidden_after_axis_rebuild():
    canvas = MplCanvas()
    canvas.resize_axes(30)
    canvas.set_toNight(True)  # Cached theme: should not be needed for hiding.

    canvas.ax_cake.set_xticks([1.0, 2.0, 3.0])
    canvas.draw()

    assert not canvas.ax_cake.xaxis.get_tick_params()["labelbottom"]
    assert all(not label.get_visible() for label in canvas.ax_cake.get_xticklabels())


def test_compact_subplot_margins_survive_canvas_rebuild():
    canvas = MplCanvas()
    canvas.resize_axes(30)

    subplotpars = canvas.fig.subplotpars
    assert subplotpars.left == canvas._SUBPLOT_MARGINS["left"]
    assert subplotpars.right == canvas._SUBPLOT_MARGINS["right"]


def test_canvas_uses_keyboard_focus():
    canvas = MplCanvas()
    assert canvas.focusPolicy() == QtCore.Qt.StrongFocus
