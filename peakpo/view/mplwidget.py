import os
import sys
import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets

# ✅ Fixed imports for matplotlib 3.7+
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5 import FigureCanvasQT
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.style as mplstyle
from matplotlib.transforms import Bbox
from matplotlib import cbook

DEBUG = False


class FigureCanvasQT_modified(FigureCanvasQT):
    """Modified FigureCanvasQT to add rectangle drawing"""
    
    def drawRectangle(self, rect):
        if rect is not None:
            def _draw_rect_callback(painter):
                # ✅ Ensure _dpi_ratio exists
                dpi = getattr(self, '_dpi_ratio', 1.0)
                
                pen = QtGui.QPen(QtCore.Qt.red, 5 / dpi, QtCore.Qt.DotLine)
                painter.setPen(pen)
                
                # ✅ FIX: Properly scale and create QRectF
                try:
                    scaled_rect = [pt / dpi for pt in rect]
                    qrect = QtCore.QRectF(*scaled_rect)
                    painter.drawRect(qrect)
                except Exception as e:
                    print(f"Error drawing rectangle: {e}")
        else:
            def _draw_rect_callback(painter):
                return
        
        self._draw_rect_callback = _draw_rect_callback
        self.update()


class FigureCanvasQTAgg_modified(FigureCanvasQTAgg, FigureCanvasQT_modified):
    """Modified FigureCanvasQTAgg with custom blitting and rectangle drawing"""
    
    def __init__(self, figure):
        super(FigureCanvasQTAgg_modified, self).__init__(figure)
        self._bbox_queue = []
        self._draw_rect_callback = lambda painter: None

    @property
    def blitbox(self):
        return self._bbox_queue

    def paintEvent(self, e):
        """Copy the image from the Agg canvas to the qt.drawable."""
        # Handle DPI updates
        if hasattr(self, '_update_dpi'):
            try:
                if self._update_dpi():
                    return
            except:
                pass
        
        # ✅ CRITICAL FIX: Ensure renderer exists before custom painting
        if not hasattr(self, 'renderer') or self.renderer is None:
            # On first paint, let the parent class initialize the renderer
            try:
                # This will create the renderer and do the initial draw
                FigureCanvasQTAgg.paintEvent(self, e)
            except Exception as ex:
                print(f"Initial paintEvent failed: {ex}")
            return
        
        # ✅ Ensure _dpi_ratio is set
        if not hasattr(self, '_dpi_ratio'):
            self._dpi_ratio = 1.0
            try:
                self._dpi_ratio = self.devicePixelRatio()
            except:
                pass
        
        # Custom blitting code (only runs after renderer is initialized)
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
            
            # ✅ Safely set device pixel ratio
            if hasattr(qimage, 'setDevicePixelRatio'):
                try:
                    qimage.setDevicePixelRatio(self._dpi_ratio)
                except:
                    pass
            
            # ✅ FIX: Ensure both arguments to QPoint are Python int
            origin = QtCore.QPoint(int(l), int(self.renderer.height - t))
            painter.drawImage(origin / self._dpi_ratio, qimage)

        if hasattr(self, '_draw_rect_callback'):
            self._draw_rect_callback(painter)

        painter.end()

    def blit(self, bbox=None):
        """Blit the region in bbox."""
        if bbox is None and self.figure:
            bbox = self.figure.bbox

        self._bbox_queue.append(bbox)

        l, b, w, h = [pt / self._dpi_ratio for pt in bbox.bounds]
        t = b + h
        self.repaint(l, self.renderer.height / self._dpi_ratio - t, w, h)

    def print_figure(self, *args, **kwargs):
        super(FigureCanvasQTAgg, self).print_figure(*args, **kwargs)
        self.draw()


class MplCanvas(FigureCanvasQTAgg_modified):
    """Class to represent the FigureCanvas widget"""

class MplCanvas(FigureCanvasQTAgg_modified):
    """Class to represent the FigureCanvas widget"""

    def __init__(self):
        # Create figure
        self.fig = Figure()
        bbox = self.fig.get_window_extent().transformed(
            self.fig.dpi_scale_trans.inverted())
        width, height = bbox.width * self.fig.dpi, bbox.height * self.fig.dpi
        
        # Adjust layout
        self.fig.subplots_adjust(
            left = 50 / width,
            bottom = 30 / height,
            right = 1 - 20 / width,
            top = 1 - 30 / height,
            hspace = 0.0)
        
        # Set defaults BEFORE creating axes
        self.bgColor = 'black'
        self.objColor = 'white'
        
        # Create axes
        self._define_axes(1)
        
        # Apply basic style
        try:
            mplstyle.use('dark_background')
        except:
            pass
        self.fig.set_facecolor(self.bgColor)
        
        # Initialize parent
        FigureCanvasQTAgg_modified.__init__(self, self.fig)
        
        # ✅ Initialize DPI ratio for HiDPI displays
        self._dpi_ratio = 1.0
        try:
            self._dpi_ratio = self.devicePixelRatioF()  # Use F version for float
        except:
            try:
                self._dpi_ratio = self.devicePixelRatio()
            except:
                pass
        
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
        """Apply matplotlib style"""
        if NightView:
            try:
                mplstyle.use('dark_background')
            except:
                pass
            self.bgColor = 'black'
            self.objColor = 'white'
        else:
            try:
                mplstyle.use('classic')
            except:
                pass
            self.bgColor = 'white'
            self.objColor = 'black'
        
        self.fig.set_facecolor(self.bgColor)
        self.ax_cake.tick_params(which='both', axis='x',
                                 colors=self.objColor, direction='in',
                                 labelbottom=False, labeltop=False)
        self.ax_cake.tick_params(axis='x', which='both', length=0)
        self.ax_pattern.xaxis.set_label_position('bottom')
        
        try:
            self.draw_idle()
        except:
            pass

class MplWidget(QtWidgets.QWidget):
    """Widget defined in Qt Designer"""

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.canvas = MplCanvas()
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.setFocus()
        
        self.vbl = QtWidgets.QVBoxLayout()
        self.ntb = NavigationToolbar(self.canvas, self)
        self.vbl.addWidget(self.ntb)
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)