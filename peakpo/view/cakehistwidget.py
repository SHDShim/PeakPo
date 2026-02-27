import numpy as np
from qtpy import QtCore, QtWidgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class CakeHistogramWidget(QtWidgets.QWidget):
    boundChanged = QtCore.Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._vmin = None
        self._vmax = None
        self._xlims = None
        self._line_min = None
        self._line_max = None

        self.check_log = QtWidgets.QCheckBox("Log Y")
        self.check_log.setChecked(True)
        self.check_focus = QtWidgets.QCheckBox("Focus range")
        self.check_focus.setChecked(True)
        self.spin_low_pct = QtWidgets.QDoubleSpinBox()
        self.spin_low_pct.setRange(0.0, 100.0)
        self.spin_low_pct.setDecimals(2)
        self.spin_low_pct.setSingleStep(0.01)
        # Typical useful lower cutoff starts around 30-40% for cake contrast.
        self.spin_low_pct.setValue(40.0)
        self.spin_high_pct = QtWidgets.QDoubleSpinBox()
        self.spin_high_pct.setRange(0.0, 100.0)
        self.spin_high_pct.setDecimals(2)
        self.spin_high_pct.setSingleStep(0.01)
        self.spin_high_pct.setValue(99.95)
        self.button_apply_pct = QtWidgets.QPushButton("Apply pct")

        self.fig = Figure(figsize=(4, 1.5), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_yticks([])
        self.ax.set_xlabel("Intensity histogram (Left click=min, Right click=max)")
        self.ax.tick_params(axis="x", labelsize=8)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self.check_log)
        controls.addWidget(self.check_focus)
        controls.addWidget(QtWidgets.QLabel("Low %"))
        controls.addWidget(self.spin_low_pct)
        controls.addWidget(QtWidgets.QLabel("High %"))
        controls.addWidget(self.spin_high_pct)
        controls.addWidget(self.button_apply_pct)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.canvas)

        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.check_log.stateChanged.connect(self._redraw_only)
        self.check_focus.stateChanged.connect(self._redraw_only)
        self.button_apply_pct.clicked.connect(self._apply_percentiles)

    def set_data(self, values, vmin=None, vmax=None):
        if np.ma.isMaskedArray(values):
            arr = np.asarray(values.compressed(), dtype=float).ravel()
        else:
            arr = np.asarray(values, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            self.ax.clear()
            self.ax.set_yticks([])
            self.ax.set_xlabel("Intensity histogram (no data)")
            self.canvas.draw_idle()
            return

        self._data = arr
        self._vmin = vmin
        self._vmax = vmax

        lo, hi_data = float(arr.min()), float(arr.max())
        if hi_data <= lo:
            hi_data = lo + 1.0
        self._xlims = self._calc_view_xlim(lo, hi_data, vmin, vmax)

        self.ax.clear()
        hist_lo, hist_hi = self._xlims
        if hist_hi <= hist_lo:
            hist_lo, hist_hi = lo, hi_data
        self.ax.hist(arr, bins=128, range=(hist_lo, hist_hi), color="#5c5c5c", alpha=0.9)
        self.ax.set_xlim(*self._xlims)
        if self.check_log.isChecked():
            self.ax.set_yscale("log")
        else:
            self.ax.set_yscale("linear")
        self.ax.set_yticks([])
        self.ax.set_xlabel("Intensity histogram (Left click=min, Right click=max)")

        if vmin is not None:
            self._line_min = self.ax.axvline(vmin, color="#5ec7ff", linewidth=1.6)
        if vmax is not None:
            self._line_max = self.ax.axvline(vmax, color="#ff9d5c", linewidth=1.6)
        self.canvas.draw_idle()

    def _calc_view_xlim(self, lo, hi_data, vmin, vmax):
        if not self.check_focus.isChecked() or vmin is None or vmax is None:
            return lo, hi_data
        left = float(min(vmin, vmax))
        right = float(max(vmin, vmax))
        if right <= left:
            right = left + max(1.0, 1e-6 * max(abs(left), 1.0))
        span = right - left
        pad = max(0.1 * span, 1e-6 * max(abs(right), 1.0))
        x0 = max(lo, left - pad)
        x1 = min(hi_data, right + pad)
        if x1 <= x0:
            return lo, hi_data
        return x0, x1

    def _redraw_only(self):
        if self._data is None:
            return
        self.set_data(self._data, self._vmin, self._vmax)

    def _apply_percentiles(self):
        if self._data is None:
            return
        low = float(self.spin_low_pct.value())
        high = float(self.spin_high_pct.value())
        if high <= low:
            high = min(100.0, low + 0.01)
            self.spin_high_pct.setValue(high)
        vmin = float(np.percentile(self._data, low))
        vmax = float(np.percentile(self._data, high))
        self.boundChanged.emit("min", vmin)
        self.boundChanged.emit("max", vmax)

    def _on_click(self, event):
        if event.xdata is None or self._xlims is None:
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        if event.button == 1:
            self.boundChanged.emit("min", x)
        elif event.button == 3:
            self.boundChanged.emit("max", x)
