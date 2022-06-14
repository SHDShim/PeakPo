import os
import sys
import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg \
    import FigureCanvasQTAgg, FigureCanvasQT  # as FigureCanvas
#    import FigureCanvasQTAgg  # as FigureCanvas
from matplotlib.backends.backend_qt5agg \
    import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.style as mplstyle
from matplotlib.transforms import Bbox
from matplotlib import cbook

DEBUG = False


class FigureCanvasQT_modified(FigureCanvasQT):
    def drawRectangle(self, rect):
        # Draw the zoom rectangle to the QPainter.  _draw_rect_callback needs
        # to be called at the end of paintEvent.
        if rect is not None:
            def _draw_rect_callback(painter):
                pen = QtGui.QPen(QtCore.Qt.red, 5 / self._dpi_ratio,
                                 QtCore.Qt.DotLine)
                painter.setPen(pen)
                painter.drawRect(*(pt / self._dpi_ratio for pt in rect))
        else:
            def _draw_rect_callback(painter):
                return
        self._draw_rect_callback = _draw_rect_callback
        self.update()


class FigureCanvasQTAgg_modified(FigureCanvasQTAgg, FigureCanvasQT_modified):
    def __init__(self, figure):
        super(FigureCanvasQTAgg, self).__init__(figure=figure)
        self._bbox_queue = []

    @property
    #@cbook.deprecated("2.1")
    def blitbox(self):
        return self._bbox_queue

    def paintEvent(self, e):
        """Copy the image from the Agg canvas to the qt.drawable.

        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        if self._update_dpi():
            # The dpi update triggered its own paintEvent.
            return
        self._draw_idle()  # Only does something if a draw is pending.

        # if the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called
        if not hasattr(self, 'renderer'):
            return

        painter = QtGui.QPainter(self)

        if self._bbox_queue:
            bbox_queue = self._bbox_queue
        else:
            painter.eraseRect(self.rect())
            bbox_queue = [
                Bbox([[0, 0], [self.renderer.width, self.renderer.height]])]
        self._bbox_queue = []
        for bbox in bbox_queue:
            l, b, r, t = map(int, bbox.extents)
            w = r - l
            h = t - b
            reg = self.copy_from_bbox(bbox)
            buf = reg.to_string_argb()
            qimage = QtGui.QImage(buf, w, h, QtGui.QImage.Format_ARGB32)
            # Adjust the buf reference count to work around a memory leak bug
            # in QImage under PySide on Python 3.
            if hasattr(qimage, 'setDevicePixelRatio'):
                # Not available on Qt4 or some older Qt5.
                qimage.setDevicePixelRatio(self._dpi_ratio)
            origin = QtCore.QPoint(l, self.renderer.height - t)
            painter.drawImage(origin / self._dpi_ratio, qimage)

        self._draw_rect_callback(painter)

        painter.end()

    def blit(self, bbox=None):
        """Blit the region in bbox.
        """
        # If bbox is None, blit the entire canvas. Otherwise
        # blit only the area defined by the bbox.
        if bbox is None and self.figure:
            bbox = self.figure.bbox

        self._bbox_queue.append(bbox)

        # repaint uses logical pixels, not physical pixels like the renderer.
        l, b, w, h = [pt / self._dpi_ratio for pt in bbox.bounds]
        t = b + h
        self.repaint(l, self.renderer.height / self._dpi_ratio - t, w, h)

    def print_figure(self, *args, **kwargs):
        super(FigureCanvasQTAgg, self).print_figure(*args, **kwargs)
        self.draw()


class MplCanvas(FigureCanvasQTAgg_modified):
    """Class to represent the FigureCanvas widget"""

    def __init__(self):
        # setup Matplotlib Figure and Axis
        self.fig = Figure()
        bbox = self.fig.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted())
        width, height = bbox.width * self.fig.dpi, bbox.height * self.fig.dpi
        self.fig.subplots_adjust(
            left = 50 / width, #40 / width,
            bottom = 30 / height, #20 / height
            right = 1 - 20 / width, # 1 - 5 / width,
            top = 1 - 30 / height,
            hspace = 0.0)
        # left=0.07, right=0.98,
        # top=0.94, bottom=0.07, hspace=0.0)
        self._define_axes(1)
        self.set_toNight(True)
        FigureCanvasQTAgg_modified.__init__(self, self.fig)
        FigureCanvasQTAgg_modified.setSizePolicy(
            self, QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding)
        FigureCanvasQTAgg_modified.updateGeometry(self)

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
            try:
                mplstyle.use(
                    os.path.join(os.path.curdir, 'mplstyle', 'night.mplstyle'))
            except:
                mplstyle.use('dark_background')
            self.bgColor = 'black'
            self.objColor = 'white'
        else:
            try:
                mplstyle.use(
                    os.path.join(os.path.curdir, 'mplstyle', 'day.mplstyle'))
            except:
                mplstyle.use('classic')
            self.bgColor = 'white'
            self.objColor = 'black'
#        self.fig.clf()
#        self.ax_pattern.cla()
#        Cursor(self.ax, useblit=True, color=self.objColor, linewidth=2 )
        self.fig.set_facecolor(self.bgColor)
        self.ax_cake.tick_params(which='both', axis='x',
                                 colors=self.objColor, direction='in',
                                 labelbottom=False, labeltop=False)
        #self.ax_cake.tick_params(axis='both', which='both', length=0)
        self.ax_cake.tick_params(axis='x', which='both', length=0)
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
