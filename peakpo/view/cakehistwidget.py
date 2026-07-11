import numpy as np
from qtpy import QtCore, QtWidgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from ..utils import align_spinbox_right


class CakeHistogramWidget(QtWidgets.QWidget):
    boundChanged = QtCore.Signal(str, float)
    rangeChanged = QtCore.Signal(float, float)
    _GUIDE_MARGIN_FRACTION = 0.05
    _DEFAULT_EDGE_WIDTH_PERCENT = 30.0
    _DEFAULT_EDGE_POSITION_PERCENT = 75.0

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
        self._data_signature = None
        self._data_token = None
        self._drag_target = None
        self._drag_start_x = None
        self._drag_start_vmin = None
        self._drag_start_vmax = None
        self._edge_width_percent = self._DEFAULT_EDGE_WIDTH_PERCENT
        self._edge_position_percent = self._DEFAULT_EDGE_POSITION_PERCENT

        self.check_log = QtWidgets.QCheckBox("Log Y")
        self.check_log.setChecked(True)
        self.button_reset_view = QtWidgets.QPushButton("Full")
        self.button_reset_view.setToolTip(
            "Show the full histogram range by setting Low % to 0 and High % to 100.")
        self.button_edge = QtWidgets.QPushButton("Edge")
        self.button_edge.setToolTip(
            "Find the sharp histogram edge and place the blue/orange limits "
            "around it using the configured +/- percent.")
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
        controls_top.addWidget(self.button_reset_view)
        controls_top.addWidget(self.button_edge)
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
        self.button_reset_view.clicked.connect(self.reset_view_percentages)
        self.button_edge.clicked.connect(self.apply_edge_to_current_data)
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

    def clear(self):
        self._data = None
        self._vmin = None
        self._vmax = None
        self._xlims = None
        self._line_min = None
        self._line_max = None
        self._span_patch = None
        self._data_max = None
        self._data_signature = None
        self._data_token = None
        self._drag_target = None
        self._drag_start_x = None
        self._drag_start_vmin = None
        self._drag_start_vmax = None
        self._draw_empty_state()

    def _finite_array(self, values):
        if np.ma.isMaskedArray(values):
            arr = np.asarray(values.compressed(), dtype=float).ravel()
        else:
            arr = np.asarray(values, dtype=float).ravel()
        return arr[np.isfinite(arr)]

    def data_signature_for_values(self, values):
        arr = self._finite_array(values)
        if arr.size == 0:
            return None
        return (
            int(arr.size),
            float(arr.min()),
            float(arr.max()),
            float(arr.mean()),
        )

    def set_data(self, values, vmin=None, vmax=None, *, data_token=None,
                 finite_values=None, data_signature=None):
        next_vmin = None if vmin is None else max(0.0, float(vmin))
        next_vmax = None if vmax is None else float(vmax)
        if data_token is not None and data_token == self._data_token and \
                next_vmin == self._vmin and next_vmax == self._vmax:
            return
        arr = self._finite_array(values) if finite_values is None else \
            np.asarray(finite_values, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            self.clear()
            return

        self._data = arr
        self._data_max = float(arr.max())
        self._data_signature = data_signature
        if self._data_signature is None:
            self._data_signature = (
                int(arr.size), float(arr.min()), float(arr.max()),
                float(arr.mean()))
        self._data_token = data_token
        self._vmin = next_vmin
        self._vmax = next_vmax

        self._xlims = self._calc_view_xlim(
            float(arr.min()), float(arr.max()), self._vmin, self._vmax)

        self.ax.clear()
        self.fig.patch.set_facecolor("black")
        self.ax.set_facecolor("black")
        hist_lo, hist_hi = self._xlims
        if hist_hi <= hist_lo:
            hist_lo, hist_hi = float(arr.min()), float(arr.max())
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

    def _calc_view_xlim(self, lo, hi_data, vmin=None, vmax=None):
        if hi_data <= 0:
            if hi_data <= lo:
                return self._expand_view_for_guides(lo, lo + 1.0, vmin, vmax)
            pad = 0.05 * (hi_data - lo)
            return self._expand_view_for_guides(
                lo - pad, hi_data + pad, vmin, vmax)

        low_pct = float(self.spin_low_pct.value())
        high_pct = float(self.spin_high_pct.value())
        if high_pct <= low_pct:
            high_pct = min(100.0, low_pct + 0.01)
        view_lo = (low_pct / 100.0) * hi_data
        view_hi = (high_pct / 100.0) * hi_data
        if view_hi <= view_lo:
            view_hi = view_lo + max(1.0, 1e-6 * max(abs(view_lo), 1.0))
        return self._expand_view_for_guides(view_lo, view_hi, vmin, vmax)

    def _expand_view_for_guides(self, view_lo, view_hi, vmin=None, vmax=None):
        bounds = [float(view_lo), float(view_hi)]
        for value in (vmin, vmax):
            if value is None:
                continue
            value = float(value)
            if np.isfinite(value):
                bounds.append(value)
        lo = min(bounds)
        hi = max(bounds)
        if hi <= lo:
            pad = max(0.5, 0.5e-6 * max(abs(lo), 1.0))
            return lo - pad, hi + pad

        # Pad so guide lines that define the selected range are inset by
        # approximately 5% of the visible axis width.
        margin = self._GUIDE_MARGIN_FRACTION
        pad = margin / (1.0 - 2.0 * margin) * (hi - lo)
        return lo - pad, hi + pad

    def _ensure_guides_in_xrange(self):
        if self._xlims is None or self._vmin is None or self._vmax is None:
            return
        guide_lo = min(self._vmin, self._vmax)
        guide_hi = max(self._vmin, self._vmax)
        if self._xlims[0] <= guide_lo and guide_hi <= self._xlims[1]:
            return
        x0, x1 = self._expand_view_for_guides(
            self._xlims[0], self._xlims[1], self._vmin, self._vmax)
        self._xlims = (x0, x1)
        self.ax.set_xlim(x0, x1)

    def _draw_guides(self):
        self._line_min = None
        self._line_max = None
        self._span_patch = None
        if self._xlims is None:
            return
        if self._vmin is None or self._vmax is None:
            return
        self._ensure_guides_in_xrange()
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

    def reset_view_percentages(self):
        blocker_low = QtCore.QSignalBlocker(self.spin_low_pct)
        blocker_high = QtCore.QSignalBlocker(self.spin_high_pct)
        try:
            self.spin_low_pct.setValue(0.0)
            self.spin_high_pct.setValue(100.0)
        finally:
            del blocker_high
            del blocker_low
        self._redraw_only()

    def set_edge_width_percent(self, value):
        self._edge_width_percent = float(np.clip(float(value), 0.0, 100.0))

    def set_edge_position_percent(self, value):
        self._edge_position_percent = float(np.clip(float(value), 0.01, 99.99))

    def current_bounds(self, data_max=None, data_signature=None):
        if self._vmin is None or self._vmax is None:
            return None
        if data_signature is not None and self._data_signature is not None:
            if tuple(data_signature) != tuple(self._data_signature):
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
        return max(0.0, vmin), vmax

    def auto_edge_bounds_for_values(
            self, values, edge_width_percent=None, edge_position_percent=None):
        arr = self._finite_array(values)
        arr = arr[arr > 0]
        if arr.size < 16:
            return None

        data_max = float(arr.max())
        if not np.isfinite(data_max) or data_max <= 0:
            return None

        edge = self._detect_largest_drop_edge(arr, data_max)
        if edge is None:
            return None

        width = self._edge_width_percent
        if edge_width_percent is not None:
            width = float(edge_width_percent)
        width = float(np.clip(width, 0.0, 100.0)) / 100.0
        edge_fraction = self._edge_position_percent
        if edge_position_percent is not None:
            edge_fraction = float(edge_position_percent)
        edge_fraction = float(np.clip(edge_fraction, 0.01, 99.99)) / 100.0

        span = 2.0 * width * edge
        vmin = max(0.0, edge - edge_fraction * span)
        vmax = edge + (1.0 - edge_fraction) * span
        view_span = 2.0 * span
        view_lo = max(0.0, edge - edge_fraction * view_span)
        view_hi = edge + (1.0 - edge_fraction) * view_span
        low_pct = float(np.clip(100.0 * view_lo / data_max, 0.0, 100.0))
        high_pct = float(np.clip(100.0 * view_hi / data_max, 0.01, 100.0))
        if high_pct <= low_pct:
            high_pct = min(100.0, low_pct + 0.01)
        return {
            "vmin": vmin,
            "vmax": vmax,
            "low_pct": low_pct,
            "high_pct": high_pct,
            "data_signature": self.data_signature_for_values(values),
        }

    @staticmethod
    def _detect_largest_drop_edge(arr, data_max):
        hist_max = CakeHistogramWidget._edge_histogram_upper_bound(arr, data_max)
        if not np.isfinite(hist_max) or hist_max <= 0:
            return None

        # The visible saturation edge is clearest in a log-count histogram.
        # Find the strongest populated drop after the main low-intensity peak.
        hist, edges = np.histogram(arr, bins=256, range=(0.0, hist_max))
        counts = np.log10(hist.astype(float) + 1.0)
        if counts.size < 5 or np.max(counts) <= 0:
            return None

        kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
        kernel /= kernel.sum()
        smooth = np.convolve(counts, kernel, mode="same")
        hist_smooth = np.convolve(hist.astype(float), kernel, mode="same")
        peak_idx = int(np.argmax(smooth))
        if peak_idx >= smooth.size - 2:
            return None

        drops = smooth[:-1] - smooth[1:]
        start = min(peak_idx + 1, drops.size - 1)
        if start >= drops.size:
            return None

        # Ignore sparse tails: a low-count bin followed by zero can be a
        # large log-scale drop but is not the dominant image-background edge.
        min_populated_count = max(3.0, 0.02 * float(np.max(hist_smooth)))
        populated = hist_smooth[:-1] >= min_populated_count
        candidates = np.flatnonzero((drops > 0.0) & populated)
        candidates = candidates[candidates >= start]
        if candidates.size == 0:
            return None

        scores = drops[candidates]
        edge_idx = int(candidates[int(np.argmax(scores))] + 1)
        edge = float(edges[edge_idx])
        if not np.isfinite(edge) or edge <= 0:
            return None
        return edge

    @staticmethod
    def _edge_histogram_upper_bound(arr, data_max):
        data_max = float(data_max)
        if not np.isfinite(data_max) or data_max <= 0:
            return None

        q25, q75, q999 = np.nanpercentile(arr, [25.0, 75.0, 99.9])
        iqr = float(q75 - q25)
        if np.isfinite(iqr) and iqr > 0:
            robust_upper = float(q75 + 8.0 * iqr)
        else:
            robust_upper = float(q999)

        if not np.isfinite(robust_upper) or robust_upper <= 0:
            robust_upper = float(q999)
        if not np.isfinite(robust_upper) or robust_upper <= 0:
            return data_max

        hist_max = max(float(q999), robust_upper)
        return min(data_max, hist_max)

    def apply_auto_view(self, low_pct, high_pct):
        blocker_low = QtCore.QSignalBlocker(self.spin_low_pct)
        blocker_high = QtCore.QSignalBlocker(self.spin_high_pct)
        try:
            self.spin_low_pct.setValue(float(np.clip(low_pct, 0.0, 100.0)))
            self.spin_high_pct.setValue(float(np.clip(high_pct, 0.0, 100.0)))
        finally:
            del blocker_high
            del blocker_low

    def apply_edge_to_current_data(self):
        if self._data is None:
            return
        auto_bounds = self.auto_edge_bounds_for_values(
            self._data, self._edge_width_percent, self._edge_position_percent)
        if auto_bounds is None:
            return
        self.apply_auto_view(auto_bounds["low_pct"], auto_bounds["high_pct"])
        self._update_guides(auto_bounds["vmin"], auto_bounds["vmax"])
        self.rangeChanged.emit(
            float(auto_bounds["vmin"]), float(auto_bounds["vmax"]))

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
        x0, x1 = self._calc_view_xlim(
            float(self._data.min()), float(self._data.max()),
            self._vmin, self._vmax)
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
        self._vmin = max(0.0, float(vmin))
        self._vmax = float(vmax)
        if self._vmax <= self._vmin:
            gap = max(1e-12, abs(self._vmin) * 1e-9)
            self._vmax = self._vmin + gap
        self._ensure_guides_in_xrange()
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
            x = max(0.0, x)
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
            if vmin < 0.0:
                vmin = 0.0
                vmax = width
            if vmax > x1:
                vmax = x1
                vmin = x1 - width
            if vmin < 0.0:
                vmin = 0.0
                vmax = width
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
