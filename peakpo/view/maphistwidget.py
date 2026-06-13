import numpy as np
from qtpy import QtCore, QtWidgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class MapHistogramWidget(QtWidgets.QWidget):
    boundChanged = QtCore.Signal(str, float)
    rangeChanged = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._xlims = None
        self._vmin = None
        self._vmax = None
        self._line_min = None
        self._line_max = None
        self._span_patch = None
        self._drag_target = None
        self._drag_start_x = None
        self._drag_start_vmin = None
        self._drag_start_vmax = None

        self.fig = Figure(figsize=(4, 1.05), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._draw_empty_state(draw=False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

    def _draw_empty_state(self, draw=True):
        self.fig.patch.set_facecolor("black")
        self.ax.clear()
        self.ax.set_facecolor("black")
        self.ax.set_axis_off()
        if draw:
            self.canvas.draw_idle()

    def clear(self):
        self._data = None
        self._xlims = None
        self._vmin = None
        self._vmax = None
        self._draw_empty_state()

    def set_data(self, values, vmin=None, vmax=None):
        arr = np.asarray(values, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            self._data = None
            self._xlims = None
            self._draw_empty_state()
            return

        self._data = arr
        self._vmin = None if vmin is None else float(vmin)
        self._vmax = None if vmax is None else float(vmax)

        lo = float(arr.min())
        hi = float(arr.max())
        if hi <= lo:
            pad = max(1.0, 1e-6 * max(abs(lo), 1.0))
            lo -= 0.5 * pad
            hi += 0.5 * pad
        else:
            pad = 0.05 * (hi - lo)
            lo -= pad
            hi += pad
        self._xlims = (lo, hi)
        self._redraw()

    def _redraw(self):
        if self._data is None or self._xlims is None:
            self._draw_empty_state()
            return

        self.ax.clear()
        self.fig.patch.set_facecolor("black")
        self.ax.set_facecolor("black")
        self.ax.hist(
            self._data,
            bins=128,
            range=self._xlims,
            color="#5c5c5c",
            alpha=0.9,
        )
        self.ax.set_xlim(*self._xlims)
        self.ax.set_yticks([])
        self.ax.set_xlabel("Map intensity histogram", fontsize=8)
        self.ax.tick_params(axis="x", labelsize=8, colors="white")
        self.ax.xaxis.label.set_color("white")
        for spine in self.ax.spines.values():
            spine.set_color("white")

        self._draw_guides()
        self.canvas.draw_idle()

    def _draw_guides(self):
        self._line_min = None
        self._line_max = None
        self._span_patch = None
        if self._xlims is None:
            return
        x0, x1 = self._xlims
        if self._vmin is None or self._vmax is None:
            return
        left = float(np.clip(min(self._vmin, self._vmax), x0, x1))
        right = float(np.clip(max(self._vmin, self._vmax), x0, x1))
        if right > left:
            self._span_patch = self.ax.axvspan(
                left, right, facecolor="#4aa3ff", alpha=0.18, linewidth=0)
        self._line_min = self.ax.axvline(self._vmin, color="#5ec7ff", linewidth=1.7)
        self._line_max = self.ax.axvline(self._vmax, color="#ff9d5c", linewidth=1.7)

    def _pick_drag_target(self, x):
        if self._xlims is None or self._vmin is None or self._vmax is None:
            return None
        x0, x1 = self._xlims
        span = max(1e-12, x1 - x0)
        line_tol = span * 0.018

        min_dist = abs(x - self._vmin)
        max_dist = abs(x - self._vmax)
        if min(min_dist, max_dist) <= line_tol:
            return "min" if min_dist <= max_dist else "max"

        left = min(self._vmin, self._vmax)
        right = max(self._vmin, self._vmax)
        width = right - left
        if width <= 0:
            return None
        center = 0.5 * (left + right)
        # Middle half of the selected range drags the whole range.
        if left <= x <= right and abs(x - center) <= 0.25 * width:
            return "range"
        return None

    def _on_click(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        if self._xlims is None:
            return
        x = float(np.clip(event.xdata, self._xlims[0], self._xlims[1]))
        target = self._pick_drag_target(x)
        if target is None:
            return
        self._drag_target = target
        self._drag_start_x = x
        self._drag_start_vmin = self._vmin
        self._drag_start_vmax = self._vmax

    def _on_motion(self, event):
        if self._drag_target is None or self._xlims is None:
            return
        if event.xdata is None:
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

    def _update_guides(self, vmin, vmax):
        self._vmin = float(vmin)
        self._vmax = float(vmax)
        if self._line_min is not None:
            self._line_min.set_xdata([self._vmin, self._vmin])
        if self._line_max is not None:
            self._line_max.set_xdata([self._vmax, self._vmax])
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
        self._line_min = self.ax.axvline(self._vmin, color="#5ec7ff", linewidth=1.7)
        self._line_max = self.ax.axvline(self._vmax, color="#ff9d5c", linewidth=1.7)
        self.canvas.draw_idle()

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
