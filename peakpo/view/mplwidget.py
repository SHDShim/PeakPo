import os
import sys
import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets
from matplotlib.backends.backend_qt5agg \
    import FigureCanvasQTAgg  # as FigureCanvas
#    import FigureCanvasQTAgg  # as FigureCanvas
from matplotlib.backends.backend_qt5agg \
    import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.style as mplstyle
from matplotlib.transforms import Bbox

DEBUG = False


class FigureCanvas(FigureCanvasQTAgg):
    # class FigureCanvas(FigureCanvasQTAgg):
    # the code below works only with matplotlib 2.1
    def __draw_idle_agg(self, *args):
        if not self._agg_draw_pending:
            return
        if self.height() < 0 or self.width() < 0:
            self._agg_draw_pending = False
            return
        try:
            self.draw()
        except Exception:
            # Uncaught exceptions are fatal for PyQt5, so catch them instead.
            traceback.print_exc()
        finally:
            self._agg_draw_pending = False

    def paintEvent(self, e):
        """Copy the image from the Agg canvas to the qt.drawable.
        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        # if there is a pending draw, run it now as we need the updated render
        # to paint the widget
        thickness = 5
        if self._agg_draw_pending:
            self.__draw_idle_agg()
        # As described in __init__ above, we need to be careful in cases with
        # mixed resolution displays if dpi_ratio is changing between painting
        # events.
        if self._dpi_ratio != self._dpi_ratio_prev:
            # We need to update the figure DPI
            self._update_figure_dpi()
            self._dpi_ratio_prev = self._dpi_ratio
            # The easiest way to resize the canvas is to emit a resizeEvent
            # since we implement all the logic for resizing the canvas for
            # that event.
            event = QtGui.QResizeEvent(self.size(), self.size())
            # We use self.resizeEvent here instead of QApplication.postEvent
            # since the latter doesn't guarantee that the event will be emitted
            # straight away, and this causes visual delays in the changes.
            self.resizeEvent(event)
            # resizeEvent triggers a paintEvent itself, so we exit this one.
            return

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
            if hasattr(qimage, 'setDevicePixelRatio'):
                # Not available on Qt4 or some older Qt5.
                qimage.setDevicePixelRatio(self._dpi_ratio)
            origin = QtCore.QPoint(l, self.renderer.height - t)
            painter.drawImage(origin / self._dpi_ratio, qimage)
            # Adjust the buf reference count to work around a memory
            # leak bug in QImage under PySide on Python 3.
            """
            if QT_API == 'PySide' and six.PY3:
                ctypes.c_long.from_address(id(buf)).value = 1
            """
        # draw the zoom rectangle to the QPainter
        if self._drawRect is not None:
            pen = QtGui.QPen(QtCore.Qt.red, thickness / self._dpi_ratio,
                             QtCore.Qt.DotLine)
            painter.setPen(pen)
            x, y, w, h = self._drawRect
            painter.drawRect(x, y, w, h)

        painter.end()

    def paintEvent_old(self, e):
        """
        Copy the image from the Agg canvas to the qt.drawable.
        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        # if the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called
        thickness = 5
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
                pen = QtGui.QPen(QtCore.Qt.red, thickness / self._dpi_ratio,
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
                """
                if QT_API == 'PySide' and six.PY3:
                    ctypes.c_long.from_address(id(stringBuffer)).value = 1
                """
                origin = QtCore.QPoint(l, self.renderer.height - t)
                pixmap = QtGui.QPixmap.fromImage(qImage)
                p.drawPixmap(origin / self._dpi_ratio, pixmap)

            # draw the zoom rectangle to the QPainter
            if self._drawRect is not None:
                pen = QtGui.QPen(QtCore.Qt.black, thickness / self._dpi_ratio,
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
        bbox = self.fig.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted())
        width, height = bbox.width * self.fig.dpi, bbox.height * self.fig.dpi
        self.fig.subplots_adjust(
            left=40 / width,
            bottom=20 / height,
            right=1 - 5 / width,
            top=1 - 30 / height,
            hspace=0.0)
        # left=0.07, right=0.98,
        # top=0.94, bottom=0.07, hspace=0.0)
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
