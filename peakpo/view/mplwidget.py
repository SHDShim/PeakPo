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
        self.show_empty_state(draw=False)

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
        self.fig.set_facecolor(self.bgColor)
        self.ax_pattern.set_facecolor(self.bgColor)
        self.ax_cake.set_facecolor(self.bgColor)
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

    def show_empty_state(self, draw=True):
        self.fig.clf()
        self._define_axes(1)
        self.fig.set_facecolor("black")
        for ax in (self.ax_pattern, self.ax_cake):
            ax.clear()
            ax.set_facecolor("black")
            ax.set_axis_off()
        if draw:
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
        self.vbl.setContentsMargins(0, 0, 0, 0)
        self.ntb = NavigationToolbar(self.canvas, self)
        self.control_bar = QtWidgets.QFrame(self)
        self.control_bar.setObjectName("plotMouseControlBar")
        self.control_bar.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.control_layout = QtWidgets.QHBoxLayout(self.control_bar)
        self.control_layout.setContentsMargins(8, 6, 8, 6)
        self.control_layout.setSpacing(8)
        self.control_bar.hide()
        self.footer_bar = QtWidgets.QFrame(self)
        self.footer_bar.setObjectName("plotFooterBar")
        self.footer_bar.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.footer_layout = QtWidgets.QHBoxLayout(self.footer_bar)
        self.footer_layout.setContentsMargins(0, 4, 0, 0)
        self.footer_layout.setSpacing(8)
        self.footer_left = QtWidgets.QLabel("", self.footer_bar)
        self.footer_left.setObjectName("plotFooterLeft")
        self.footer_left.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.footer_left.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.footer_right = QtWidgets.QLabel("", self.footer_bar)
        self.footer_right.setObjectName("plotFooterRight")
        self.footer_right.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.footer_right.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.footer_layout.addWidget(self.footer_left, 1)
        self.footer_layout.addWidget(self.footer_right, 1)
        self.footer_bar.hide()
        self.vbl.addWidget(self.control_bar)
        self.vbl.addWidget(self.canvas)
        self.vbl.addWidget(self.footer_bar)
        self.setLayout(self.vbl)
        self.ntb.hide()
        self._shutdown_done = False

    def add_control_widget(self, widget, stretch=0):
        if widget is None:
            return
        self.control_layout.addWidget(widget, stretch)
        self.control_bar.show()

    def add_control_stretch(self, stretch=1):
        self.control_layout.addStretch(stretch)
        self.control_bar.show()

    def insert_control_widget(self, index, widget, stretch=0):
        if widget is None:
            return
        self.control_layout.insertWidget(index, widget, stretch)
        self.control_bar.show()

    def show_footer(self):
        self.footer_bar.show()

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
