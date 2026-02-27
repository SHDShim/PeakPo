from qtpy import QtCore, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.style as mplstyle


class MplCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas used by PeakPo."""

    def __init__(self):
        self.fig = Figure()
        bbox = self.fig.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted()
        )
        width, height = bbox.width * self.fig.dpi, bbox.height * self.fig.dpi

        self.fig.subplots_adjust(
            left=50 / width,
            bottom=30 / height,
            right=1 - 20 / width,
            top=1 - 30 / height,
            hspace=0.0,
        )

        self.bgColor = "black"
        self.objColor = "white"
        self._define_axes(1)

        try:
            mplstyle.use("dark_background")
        except Exception:
            pass
        self.fig.set_facecolor(self.bgColor)

        super().__init__(self.fig)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.updateGeometry()

    def _define_axes(self, h_cake):
        self.gs = GridSpec(100, 1)
        self.ax_pattern = self.fig.add_subplot(self.gs[h_cake + 1 : 99, 0])
        self.ax_cake = self.fig.add_subplot(self.gs[0:h_cake, 0], sharex=self.ax_pattern)
        self.ax_pattern.set_ylabel("Intensity (arbitrary unit)")
        self.ax_pattern.ticklabel_format(axis="y", style="sci", scilimits=(-2, 2))
        self.ax_pattern.get_yaxis().get_offset_text().set_position((-0.04, -0.1))

    def resize_axes(self, h_cake):
        self.fig.clf()
        self._define_axes(h_cake)
        if h_cake == 1:
            self.ax_cake.tick_params(axis="y", colors=self.objColor, labelleft=False)
            self.ax_cake.spines["right"].set_visible(False)
            self.ax_cake.spines["left"].set_visible(False)
            self.ax_cake.spines["top"].set_visible(False)
            self.ax_cake.spines["bottom"].set_visible(False)
        elif h_cake >= 10:
            self.ax_cake.set_ylabel("Azimuth (degrees)")

    def set_toNight(self, NightView=True):
        if NightView:
            try:
                mplstyle.use("dark_background")
            except Exception:
                pass
            self.bgColor = "black"
            self.objColor = "white"
        else:
            try:
                mplstyle.use("classic")
            except Exception:
                pass
            self.bgColor = "white"
            self.objColor = "black"

        self.fig.set_facecolor(self.bgColor)
        self.ax_cake.tick_params(
            which="both",
            axis="x",
            colors=self.objColor,
            direction="in",
            labelbottom=False,
            labeltop=False,
        )
        self.ax_cake.tick_params(axis="x", which="both", length=0)
        self.ax_pattern.xaxis.set_label_position("bottom")

        try:
            self.draw_idle()
        except Exception:
            pass


class MplWidget(QtWidgets.QWidget):
    """Widget defined in Qt Designer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = MplCanvas()
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.setFocus()

        self.vbl = QtWidgets.QVBoxLayout()
        self.ntb = NavigationToolbar(self.canvas, self)
        self.vbl.addWidget(self.ntb)
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
        self._shutdown_done = False

    def shutdown(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True

        try:
            if self.ntb is not None:
                self.ntb.hide()
                self.vbl.removeWidget(self.ntb)
                self.ntb.deleteLater()
                self.ntb = None
        except Exception:
            pass

        try:
            if self.canvas is not None and hasattr(self.canvas, "fig"):
                self.canvas.fig.clf()
        except Exception:
            pass

        try:
            if self.canvas is not None:
                self.canvas.hide()
                self.vbl.removeWidget(self.canvas)
                self.canvas.deleteLater()
                self.canvas = None
        except Exception:
            pass
