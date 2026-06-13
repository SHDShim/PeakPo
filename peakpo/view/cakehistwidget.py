import numpy as np
from qtpy import QtCore, QtWidgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from ..utils import align_spinbox_right


class CakeHistogramWidget(QtWidgets.QWidget):
    boundChanged = QtCore.Signal(str, float)
    rangeChanged = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._vmin = None
        self._vmax = None
        self._xlims = None
        self._line_min = None
        self._line_max = None
        self._span_patch = None
        self._data_max = None
        self._drag_target = None
        self._drag_start_x = None
        self._drag_start_vmin = None
        self._drag_start_vmax = None

        self.check_log = QtWidgets.QCheckBox("Log Y")
        self.check_log.setChecked(True)
        self.check_focus = QtWidgets.QCheckBox("Focus range")
        self.check_focus.setChecked(True)
        self.spin_low_pct = QtWidgets.QDoubleSpinBox()
        align_spinbox_right(self.spin_low_pct)
        self.spin_low_pct.setRange(0.0, 100.0)
        self.spin_low_pct.setDecimals(2)
        self.spin_low_pct.setSingleStep(0.01)
        self.spin_low_pct.setValue(0.0)
        self.spin_high_pct = QtWidgets.QDoubleSpinBox()
        align_spinbox_right(self.spin_high_pct)
        self.spin_high_pct.setRange(0.0, 100.0)
        self.spin_high_pct.setDecimals(2)
        self.spin_high_pct.setSingleStep(0.01)
        self.spin_high_pct.setValue(20.0)
        self.button_apply_pct = QtWidgets.QPushButton("Apply pct")
        self.combo_scale_mode = QtWidgets.QComboBox()
        self.combo_scale_mode.addItem("0-fine", 0)
        self.combo_scale_mode.setCurrentIndex(0)

        self.fig = Figure(figsize=(4, 1.05), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._draw_empty_state(draw=False)

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
        self.spin_low_pct.valueChanged.connect(self._redraw_only)
        self.spin_high_pct.valueChanged.connect(self._redraw_only)

    def _draw_empty_state(self, draw=True):
        self.fig.patch.set_facecolor("black")
        self.ax.clear()
        self.ax.set_facecolor("black")
        self.ax.set_axis_off()
        if draw:
            self.canvas.draw_idle()

    def set_data(self, values, vmin=None, vmax=None):
        if np.ma.isMaskedArray(values):
            arr = np.asarray(values.compressed(), dtype=float).ravel()
        else:
            arr = np.asarray(values, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            self._draw_empty_state()
            return

        self._data = arr
        self._data_max = float(arr.max())
        self._vmin = None if vmin is None else float(vmin)
        self._vmax = None if vmax is None else float(vmax)

        self._xlims = self._calc_view_xlim(float(arr.min()), float(arr.max()))

        self.ax.clear()
        self.fig.patch.set_facecolor("black")
        self.ax.set_facecolor("black")
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
        self.ax.tick_params(axis="x", labelsize=8, colors="white")
        for spine in self.ax.spines.values():
            spine.set_color("white")

        self._draw_guides()
        self.canvas.draw_idle()

    def _calc_view_xlim(self, lo, hi_data):
        if hi_data <= 0:
            if hi_data <= lo:
                return lo, lo + 1.0
            pad = 0.05 * (hi_data - lo)
            return lo - pad, hi_data + pad

        low_pct = float(self.spin_low_pct.value())
        high_pct = float(self.spin_high_pct.value())
        if high_pct <= low_pct:
            high_pct = min(100.0, low_pct + 0.01)
        view_lo = (low_pct / 100.0) * hi_data
        view_hi = (high_pct / 100.0) * hi_data
        if view_hi <= view_lo:
            view_hi = view_lo + max(1.0, 1e-6 * max(abs(view_lo), 1.0))
        pad = 0.05 * (view_hi - view_lo)
        return view_lo - pad, view_hi + pad

    def _draw_guides(self):
        self._line_min = None
        self._line_max = None
        self._span_patch = None
        if self._xlims is None:
            return
        if self._vmin is None or self._vmax is None:
            return
        x0, x1 = self._xlims
        left = float(np.clip(min(self._vmin, self._vmax), x0, x1))
        right = float(np.clip(max(self._vmin, self._vmax), x0, x1))
        if right > left:
            self._span_patch = self.ax.axvspan(
                left, right, facecolor="#4aa3ff", alpha=0.18, linewidth=0)
        self._line_min = self.ax.axvline(self._vmin, color="#5ec7ff", linewidth=1.6)
        self._line_max = self.ax.axvline(self._vmax, color="#ff9d5c", linewidth=1.6)

    def _redraw_only(self):
        if self._data is None:
            return
        self.set_data(self._data, self._vmin, self._vmax)

    def current_bounds(self, data_max=None):
        if self._vmin is None or self._vmax is None:
            return None
        if data_max is not None and self._data_max is not None:
            data_max = float(data_max)
            scale = max(abs(data_max), abs(self._data_max), 1.0)
            if abs(data_max - self._data_max) > scale * 1e-9:
                return None
        vmin = float(self._vmin)
        vmax = float(self._vmax)
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            return None
        return vmin, vmax

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
        self.rangeChanged.emit(vmin, vmax)

    def _get_pct_bounds(self):
        """Return display x-range bounds based on the spin box percentages."""
        if self._data is None:
            return None, None
        x0, x1 = self._calc_view_xlim(float(self._data.min()), float(self._data.max()))
        return x0, x1

    def _on_click(self, event):
        if event.xdata is None or self._xlims is None or event.inaxes != self.ax:
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        # Only allow dragging to change bar positions — no click-to-set.
        picked = self._pick_drag_target(x)
        if picked is not None:
            self._drag_target = picked
            self._drag_start_x = x
            self._drag_start_vmin = self._vmin
            self._drag_start_vmax = self._vmax

    def _pick_drag_target(self, x):
        if self._xlims is None or self._vmin is None or self._vmax is None:
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
        left = min(self._vmin, self._vmax)
        right = max(self._vmin, self._vmax)
        width = right - left
        if width <= 0:
            return None
        center = 0.5 * (left + right)
        if left <= x <= right and abs(x - center) <= 0.25 * width:
            return "range"
        return None

    def _update_guides(self, vmin, vmax):
        self._vmin = float(vmin)
        self._vmax = float(vmax)
        if self._span_patch is not None:
            self._span_patch.remove()
        left = min(self._vmin, self._vmax)
        right = max(self._vmin, self._vmax)
        self._span_patch = self.ax.axvspan(
            left, right, facecolor="#4aa3ff", alpha=0.18, linewidth=0)
        if self._line_min is not None:
            self._line_min.remove()
        if self._line_max is not None:
            self._line_max.remove()
        self._line_min = self.ax.axvline(self._vmin, color="#5ec7ff", linewidth=1.6)
        self._line_max = self.ax.axvline(self._vmax, color="#ff9d5c", linewidth=1.6)
        self.canvas.draw_idle()

    def _on_motion(self, event):
        if self._drag_target is None:
            return
        if event.xdata is None or self._xlims is None:
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        x0, x1 = self._xlims
        min_gap = max(1e-12, (x1 - x0) * 1e-9)
        if self._drag_target == "min":
            x = min(x, self._vmax - min_gap)
            self._update_guides(vmin=x, vmax=self._vmax)
        elif self._drag_target == "max":
            x = max(x, self._vmin + min_gap)
            self._update_guides(vmin=self._vmin, vmax=x)
        elif self._drag_target == "range":
            delta = x - self._drag_start_x
            vmin = self._drag_start_vmin + delta
            vmax = self._drag_start_vmax + delta
            width = vmax - vmin
            if vmin < x0:
                vmin = x0
                vmax = x0 + width
            if vmax > x1:
                vmax = x1
                vmin = x1 - width
            self._update_guides(vmin=vmin, vmax=vmax)

    def _on_release(self, event):
        del event
        if self._drag_target is None:
            return
        target = self._drag_target
        vmin = self._vmin
        vmax = self._vmax
        self._drag_target = None
        self._drag_start_x = None
        self._drag_start_vmin = None
        self._drag_start_vmax = None
        if target == "range":
            self.rangeChanged.emit(float(vmin), float(vmax))
        elif target == "min":
            self.boundChanged.emit("min", float(vmin))
        elif target == "max":
            self.boundChanged.emit("max", float(vmax))
