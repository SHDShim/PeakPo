#!/usr/bin/env python

# Python Qt4 bindings for GUI objects
from PyQt5 import QtGui, QtWidgets
from PyQt5 import QtCore, QtWidgets

# import the Qt4Agg FigureCanvas object, that binds Figure to
# Qt4Agg backend. It also inherits from QWidget
from matplotlib.backends.backend_qt5agg \
    import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg \
    import NavigationToolbar2QT as NavigationToolbar

# Matplotlib Figure object
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt


class MplCanvas(FigureCanvas):
    """Class to represent the FigureCanvas widget"""

    def __init__(self):
        # setup Matplotlib Figure and Axis
        self.fig = Figure()
        self.fig.subplots_adjust(left=0.05, right=0.98,
                                 top=0.92, bottom=0.07, hspace=0.0)
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

    def _define_axes(self, h_bottom):
        self.gs = GridSpec(100, 1)
        self.ax = self.fig.add_subplot(self.gs[h_bottom + 1:99, 0])
        self.ax_bottom = self.fig.add_subplot(self.gs[0:h_bottom, 0],
                                              sharex=self.ax)

    def resize_axes(self, h_bottom):
        self.fig.clf()
        self._define_axes(h_bottom)

    def set_toNight(self, NightView=True):
        if NightView:
            bgColor = 'black'
            objColor = 'white'
        else:
            bgColor = 'white'
            objColor = 'black'
#        self.fig.clf()
#        self.ax.cla()
#        Cursor(self.ax, useblit=True, color=objColor, linewidth=2 )

        self.ax_bottom.set_facecolor(bgColor)
        self.ax_bottom.spines['bottom'].set_color(objColor)
        self.ax_bottom.spines['left'].set_color(objColor)
        self.ax_bottom.spines['top'].set_color(objColor)
        self.ax_bottom.spines['right'].set_color(objColor)
        self.ax_bottom.yaxis.label.set_color(objColor)
        self.ax_bottom.xaxis.label.set_color(objColor)
        self.ax_bottom.tick_params(which='both', axis='x',
                                   colors=objColor, direction='in',
                                   labelbottom=False, labeltop=False)
        # self.ax_bottom.tick_params(axis='y', colors=objColor, direction='in')
        self.ax_bottom.tick_params(axis='both', which='both', length=0,
                                   colors=objColor)
        # self.ax_bottom.tick_params(axis='y', colors=objColor)
        # self.ax_bottom.xaxis.set_label_position('Top')

        self.fig.set_facecolor(bgColor)
        self.ax.set_facecolor(bgColor)
        self.ax.spines['bottom'].set_color(objColor)
        self.ax.spines['left'].set_color(objColor)
        self.ax.spines['top'].set_color(objColor)
        self.ax.spines['right'].set_color(objColor)
        self.ax.title.set_color(objColor)
        self.ax.yaxis.label.set_color(objColor)
        self.ax.xaxis.label.set_color(objColor)
        self.ax.tick_params(which='both', axis='x', colors=objColor,
                            direction='in')
        self.ax.tick_params(axis='y', colors=objColor, direction='in')
        self.ax.tick_params(axis='x', which='major', length=6)
        self.ax.tick_params(axis='x', which='minor', length=3)
        self.ax.tick_params(axis='y', which='both', length=0)
        # self.ax.tick_params(axis='y', colors=objColor)
        self.ax.xaxis.set_label_position('bottom')


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
