import os
import sys
import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg \
    import FigureCanvasQTAgg #as FigureCanvas
from matplotlib.backends.backend_qt5agg \
    import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.style as mplstyle

DEBUG = False

class FigureCanvas(FigureCanvasQTAgg):

    def paintEvent(self, e):
        """
        Copy the image from the Agg canvas to the qt.drawable.
        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        # if the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called
        if not hasattr(self, 'renderer'):
            return

        if DEBUG:
            print('FigureCanvasQtAgg.paintEvent: ', self,
                  self.get_width_height())

        if len(self.blitbox) == 0:
            # matplotlib is in rgba byte order.  QImage wants to put the bytes
            # into argb format and is in a 4 byte unsigned int.  Little endian
            # system is LSB first and expects the bytes in reverse order
            # (bgra).
            if QtCore.QSysInfo.ByteOrder == QtCore.QSysInfo.LittleEndian:
                stringBuffer = self.renderer._renderer.tostring_bgra()
            else:
                stringBuffer = self.renderer._renderer.tostring_argb()

            refcnt = sys.getrefcount(stringBuffer)

            # convert the Agg rendered image -> qImage
            qImage = QtGui.QImage(stringBuffer, self.renderer.width,
                                  self.renderer.height,
                                  QtGui.QImage.Format_ARGB32)
            if hasattr(qImage, 'setDevicePixelRatio'):
                # Not available on Qt4 or some older Qt5.
                qImage.setDevicePixelRatio(self._dpi_ratio)
            # get the rectangle for the image
            rect = qImage.rect()
            p = QtGui.QPainter(self)
            # reset the image area of the canvas to be the back-ground color
            p.eraseRect(rect)
            # draw the rendered image on to the canvas
            p.drawPixmap(QtCore.QPoint(0, 0), QtGui.QPixmap.fromImage(qImage))

            # draw the zoom rectangle to the QPainter
            if self._drawRect is not None:
                pen = QtGui.QPen(QtCore.Qt.red, 5 / self._dpi_ratio,
                                 QtCore.Qt.DotLine)
                p.setPen(pen)
                x, y, w, h = self._drawRect
                p.drawRect(x, y, w, h)
            p.end()

            # This works around a bug in PySide 1.1.2 on Python 3.x,
            # where the reference count of stringBuffer is incremented
            # but never decremented by QImage.
            # TODO: revert PR #1323 once the issue is fixed in PySide.
            del qImage
            if refcnt != sys.getrefcount(stringBuffer):
                _decref(stringBuffer)
        else:
            p = QtGui.QPainter(self)

            while len(self.blitbox):
                bbox = self.blitbox.pop()
                l, b, r, t = bbox.extents
                w = int(r) - int(l)
                h = int(t) - int(b)
                t = int(b) + h
                reg = self.copy_from_bbox(bbox)
                stringBuffer = reg.to_string_argb()
                qImage = QtGui.QImage(stringBuffer, w, h,
                                      QtGui.QImage.Format_ARGB32)
                if hasattr(qImage, 'setDevicePixelRatio'):
                    # Not available on Qt4 or some older Qt5.
                    qImage.setDevicePixelRatio(self._dpi_ratio)
                # Adjust the stringBuffer reference count to work
                # around a memory leak bug in QImage() under PySide on
                # Python 3.x
                if QT_API == 'PySide' and six.PY3:
                    ctypes.c_long.from_address(id(stringBuffer)).value = 1

                origin = QtCore.QPoint(l, self.renderer.height - t)
                pixmap = QtGui.QPixmap.fromImage(qImage)
                p.drawPixmap(origin / self._dpi_ratio, pixmap)

            # draw the zoom rectangle to the QPainter
            if self._drawRect is not None:
                pen = QtGui.QPen(QtCore.Qt.black, 1 / self._dpi_ratio,
                                 QtCore.Qt.DotLine)
                p.setPen(pen)
                x, y, w, h = self._drawRect
                p.drawRect(x, y, w, h)

            p.end()

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
