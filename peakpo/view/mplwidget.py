import os
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg \
    import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg \
    import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.style as mplstyle

class MplCanvas(FigureCanvas):
    """Class to represent the FigureCanvas widget"""

    def __init__(self):
        # setup Matplotlib Figure and Axis
        self.fig = Figure()
        self.fig.subplots_adjust(left=0.07, right=0.98,
                                 top=0.94, bottom=0.07, hspace=0.0)
        self._define_axes(1)
        self.set_toNight(True)
        FigureCanvas.__init__(self, self.fig)
        FigureCanvas.setSizePolicy(
            self, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def _define_axes(self, h_cake):
        self.gs = GridSpec(100, 1)
        self.ax_pattern = self.fig.add_subplot(self.gs[h_cake + 1:99, 0])
        self.ax_cake = self.fig.add_subplot(self.gs[0:h_cake, 0],
                                            sharex=self.ax_pattern)
        self.ax_pattern.set_ylabel('Intensity (arbitrary unit)')
        self.ax_pattern.ticklabel_format(
            axis='y', style='sci', scilimits=(-2, 2))
        self.ax_pattern.get_yaxis().get_offset_text().set_position(
            (-0.04, -0.1))

    def resize_axes(self, h_cake):
        self.fig.clf()
        self._define_axes(h_cake)
        if h_cake == 1:
            self.ax_cake.tick_params(
                axis='y', colors=self.objColor, labelleft=False)
            self.ax_cake.spines['right'].set_visible(False)
            self.ax_cake.spines['left'].set_visible(False)
            self.ax_cake.spines['top'].set_visible(False)
            self.ax_cake.spines['bottom'].set_visible(False)
        elif h_cake >= 10:
            self.ax_cake.set_ylabel("Azimuth (degrees)")

    def set_toNight(self, NightView=True):
        if NightView:
            mplstyle.use(
                os.path.join(os.path.curdir, 'mplstyle', 'night.mplstyle'))
            self.bgColor = 'black'
            self.objColor = 'white'
        else:
            mplstyle.use(
                os.path.join(os.path.curdir, 'mplstyle', 'day.mplstyle'))
            self.bgColor = 'white'
            self.objColor = 'black'
#        self.fig.clf()
#        self.ax_pattern.cla()
#        Cursor(self.ax, useblit=True, color=self.objColor, linewidth=2 )
        self.fig.set_facecolor(self.bgColor)
        self.ax_cake.tick_params(which='both', axis='x',
                                 colors=self.objColor, direction='in',
                                 labelbottom=False, labeltop=False)
        self.ax_cake.tick_params(axis='both', which='both', length=0)

        self.ax_pattern.xaxis.set_label_position('bottom')

class MplWidget(QtWidgets.QWidget):
    """Widget defined in Qt Designer"""

    def __init__(self, parent=None):
        # initialization of Qt MainWindow widget
        QtWidgets.QWidget.__init__(self, parent)
        # set the canvas to the Matplotlib widget
        self.canvas = MplCanvas()
        #
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.setFocus()
        # create a vertical box layout
        self.vbl = QtWidgets.QVBoxLayout()
        # add navigation toolbar
        self.ntb = NavigationToolbar(self.canvas, self)
        # pack these widget into the vertical box
        self.vbl.addWidget(self.ntb)
        # add mpl widget to the vertical box
        self.vbl.addWidget(self.canvas)
        # set the layout to the vertical box
        self.setLayout(self.vbl)
