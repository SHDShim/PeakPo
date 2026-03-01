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
        self._drag_target = None

        self.check_log = QtWidgets.QCheckBox("Log Y")
        self.check_log.setChecked(True)
        self.check_focus = QtWidgets.QCheckBox("Focus range")
        self.check_focus.setChecked(True)
        self.spin_low_pct = QtWidgets.QDoubleSpinBox()
        self.spin_low_pct.setRange(0.0, 100.0)
        self.spin_low_pct.setDecimals(2)
        self.spin_low_pct.setSingleStep(0.01)
        self.spin_low_pct.setValue(5.0)
        self.spin_high_pct = QtWidgets.QDoubleSpinBox()
        self.spin_high_pct.setRange(0.0, 100.0)
        self.spin_high_pct.setDecimals(2)
        self.spin_high_pct.setSingleStep(0.01)
        self.spin_high_pct.setValue(99.95)
        self.button_apply_pct = QtWidgets.QPushButton("Apply pct")

        self.fig = Figure(figsize=(4, 1.05), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_yticks([])
        self.ax.set_xlabel("Intensity histogram (Drag blue/orange lines for min/max)")
        self.ax.tick_params(axis="x", labelsize=8)

        self.label_low = QtWidgets.QLabel("Low %")
        self.label_high = QtWidgets.QLabel("High %")

        controls_top = QtWidgets.QHBoxLayout()
        controls_top.setContentsMargins(0, 0, 0, 0)
        controls_top.addWidget(self.check_log)
        controls_top.addWidget(self.check_focus)
        controls_top.addStretch(1)

        controls_bottom = QtWidgets.QHBoxLayout()
        controls_bottom.setContentsMargins(0, 0, 0, 0)
        controls_bottom.addWidget(self.label_low)
        controls_bottom.addWidget(self.spin_low_pct, 1)
        controls_bottom.addSpacing(10)
        controls_bottom.addWidget(self.label_high)
        controls_bottom.addWidget(self.spin_high_pct, 1)
        controls_bottom.addSpacing(10)
        controls_bottom.addWidget(self.button_apply_pct)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls_top)
        layout.addLayout(controls_bottom)
        layout.addWidget(self.canvas)

        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
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
        self.ax.set_xlabel("Intensity histogram (Drag blue/orange lines for min/max)")

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
        # Keep min/max guides at 20% and 80% of the histogram x-range.
        # For x = x0 + p*(x1-x0):
        # left at p=0.2 and right at p=0.8 gives:
        # x0 = 4/3*left - 1/3*right, x1 = 4/3*right - 1/3*left
        x0 = (4.0 / 3.0) * left - (1.0 / 3.0) * right
        x1 = (4.0 / 3.0) * right - (1.0 / 3.0) * left
        if x1 <= x0:
            return lo, hi_data
        # Expand, rather than clamp, to keep the 25/75 geometry stable.
        if x0 > lo:
            x0 = max(lo, x0)
        if x1 < hi_data:
            x1 = min(hi_data, x1)
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
        if event.xdata is None or self._xlims is None or event.inaxes != self.ax:
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        # Prefer dragging when pressing near existing min/max guide lines.
        picked = self._pick_drag_target(x)
        if picked is not None:
            self._drag_target = picked
            self._update_drag_line(x)
            return
        if event.button == 1:
            self.boundChanged.emit("min", x)
        elif event.button == 3:
            self.boundChanged.emit("max", x)

    def _pick_drag_target(self, x):
        if (self._vmin is None) and (self._vmax is None):
            return None
        span = max(1e-9, float(self._xlims[1] - self._xlims[0]))
        tol = span * 0.02
        candidates = []
        if self._vmin is not None:
            candidates.append(("min", abs(x - float(self._vmin))))
        if self._vmax is not None:
            candidates.append(("max", abs(x - float(self._vmax))))
        if candidates == []:
            return None
        target, dist = sorted(candidates, key=lambda t: t[1])[0]
        if dist <= tol:
            return target
        return None

    def _update_drag_line(self, x):
        if self._drag_target == "min" and self._line_min is not None:
            self._line_min.set_xdata([x, x])
        elif self._drag_target == "max" and self._line_max is not None:
            self._line_max.set_xdata([x, x])
        self.canvas.draw_idle()

    def _on_motion(self, event):
        if self._drag_target is None:
            return
        if event.xdata is None or self._xlims is None:
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        self._update_drag_line(x)

    def _on_release(self, event):
        if self._drag_target is None:
            return
        if event.xdata is None or self._xlims is None:
            self._drag_target = None
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        if self._drag_target == "min":
            self.boundChanged.emit("min", x)
        elif self._drag_target == "max":
            self.boundChanged.emit("max", x)
        self._drag_target = None
