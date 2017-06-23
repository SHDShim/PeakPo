#!/usr/bin/env python

# Python Qt4 bindings for GUI objects
from PyQt5 import QtGui, QtWidgets
from PyQt5 import QtCore, QtWidgets
import os
# import the Qt4Agg FigureCanvas object, that binds Figure to
# Qt4Agg backend. It also inherits from QWidget
from matplotlib.backends.backend_qt5agg \
    import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg \
    import NavigationToolbar2QT as NavigationToolbar
# Matplotlib Figure object
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
# import matplotlib.ticker as mtick
import matplotlib.pyplot as plt


class MplCanvas(FigureCanvas):
    """Class to represent the FigureCanvas widget"""

    def __init__(self):
        # setup Matplotlib Figure and Axis
        self.fig = Figure()
        self.fig.subplots_adjust(left=0.07, right=0.98,
                                 top=0.94, bottom=0.07, hspace=0.0)
        self._define_axes(1)
        self.set_toNight(True)
        # initialization of the canvas
        FigureCanvas.__init__(self, self.fig)
        # we define the widget as expandable
        FigureCanvas.setSizePolicy(self,
                                   QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Expanding)
        # notify the system of updated policy
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
            plt.style.use(os.path.join(os.path.curdir,
                                       'mplstyle', 'night.mplstyle'))
            self.bgColor = 'black'
            self.objColor = 'white'
        else:
            plt.style.use(os.path.join(os.path.curdir,
                                       'mplstyle', 'day.mplstyle'))
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

        """
        self.ax_pattern.tick_params(which='both', axis='x', direction='in')
        self.ax_pattern.tick_params(axis='y', direction='in')
        self.ax_pattern.tick_params(axis='x', which='major', length=6)
        self.ax_pattern.tick_params(axis='y', which='both', length=0)
        self.ax_cake.set_facecolor(self.bgColor)
        self.ax_cake.spines['bottom'].set_color(self.objColor)
        self.ax_cake.spines['left'].set_color(self.objColor)
        self.ax_cake.spines['top'].set_color(self.objColor)
        self.ax_cake.spines['right'].set_color(self.objColor)
        self.ax_cake.yaxis.label.set_color(self.objColor)
        self.ax_cake.xaxis.label.set_color(self.objColor)
        self.ax_cake.tick_params(which='both', axis='x',
                                 colors=self.objColor, direction='in',
                                 labelbottom=False, labeltop=False)
        # self.ax_cake.tick_params(axis='y', colors=self.objColor, direction='in')
        self.ax_cake.tick_params(axis='both', which='both', length=0,
                                 colors=self.objColor)
        # self.ax_cake.tick_params(axis='y', colors=self.objColor)
        # self.ax_cake.xaxis.set_label_position('Top')
        self.fig.set_facecolor(self.bgColor)
        self.ax_pattern.set_facecolor(self.bgColor)
        self.ax_pattern.spines['bottom'].set_color(self.objColor)
        self.ax_pattern.spines['left'].set_color(self.objColor)
        self.ax_pattern.spines['top'].set_color(self.objColor)
        self.ax_pattern.spines['right'].set_color(self.objColor)
        self.ax_pattern.title.set_color(self.objColor)
        self.ax_pattern.yaxis.label.set_color(self.objColor)
        self.ax_pattern.xaxis.label.set_color(self.objColor)
        self.ax_pattern.tick_params(which='both', axis='x', colors=self.objColor,
                                    direction='in')
        self.ax_pattern.tick_params(axis='y', colors=self.objColor, direction='in')
        self.ax_pattern.tick_params(axis='x', which='major', length=6)
        self.ax_pattern.tick_params(axis='x', which='minor', length=3)
        self.ax_pattern.tick_params(axis='y', which='both', length=0)
        # self.ax_pattern.tick_params(axis='y', colors=self.objColor)
        self.ax_pattern.xaxis.set_label_position('bottom')
        """


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
