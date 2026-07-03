import numpy as np
import time
from qtpy import QtCore, QtWidgets
from matplotlib.backend_bases import MouseButton
from matplotlib import patches


class PlotInteractionController(object):
    """Centralized mouse handling for the shared 1D/Cake plot."""

    MIN_ZOOM_DRAG_PX = 8.0

    def __init__(self, main_ctrl):
        self.main = main_ctrl
        self.model = main_ctrl.model
        self.widget = main_ctrl.widget
        self._zoom_drag = None
        self._zoom_patch = None
        self._zoom_last_draw_px = None
        self._zoom_last_draw_time = 0.0
        self._zoom_blit_background = None
        self._peak_drag_row = None
        self._peak_drag_latest_center = None
        self._peak_drag_marked_unsaved = False
        self._peak_drag_invalidated_fit = False
        self._range_tool = None
        self._range_drag = None
        self._range_patch = None
        self._range_last_draw_px = None
        self._plot_help_active = False

    def connect(self):
        canvas = self.widget.mpl.canvas
        canvas.mpl_connect('button_press_event', self.on_press)
        canvas.mpl_connect('button_release_event', self.on_release)
        canvas.mpl_connect('motion_notify_event', self.on_motion)
        canvas.mpl_connect('figure_leave_event', self.on_leave)
        self.main._deactivate_toolbar_modes()

    def on_press(self, event):
        self.main._deactivate_toolbar_modes()
        if event is None:
            return
        if self._range_tool is not None:
            self._handle_range_tool_press(event)
            return
        if self._is_left(event) and bool(getattr(event, "dblclick", False)):
            self._inspect(event)
            return
        if self._is_right(event):
            if self._shift_down(event) and self._peak_action_allowed(event):
                self.main.pick_peak('right', event.xdata, event.ydata)
                return
            self.main.plot_new_graph()
            return
        if not self._is_left(event):
            return
        if self._roi_selector_active():
            return
        if self._shift_down(event):
            if self._start_peak_drag(event):
                return
            if self._peak_action_allowed(event):
                self.main.pick_peak('left', event.xdata, event.ydata)
            return
        if self._plot_axis(event.inaxes):
            self._start_zoom_drag(event)

    def on_motion(self, event):
        if self._range_drag is not None:
            self._update_range_drag(event)
            return
        if self._peak_drag_row is not None:
            self._drag_selected_peak(event)
            return
        if self._zoom_drag is not None:
            self._update_zoom_drag(event)
            return
        self._update_plot_mouse_help(event)
        self.main._update_cursor_position_readout(event)

    def on_release(self, event):
        if self._range_drag is not None:
            self._finish_range_drag(event)
            return
        if self._peak_drag_row is not None:
            self._finish_peak_drag()
            return
        if self._zoom_drag is not None:
            self._finish_zoom_drag(event)

    def on_leave(self, event=None):
        del event
        self.main._clear_cursor_position_readout()
        self._restore_plot_mouse_help()

    def _is_left(self, event):
        button = getattr(event, "button", None)
        return button == MouseButton.LEFT or button == 1

    def _is_right(self, event):
        button = getattr(event, "button", None)
        return button == MouseButton.RIGHT or button == 3

    def _shift_down(self, event):
        key = str(getattr(event, "key", "") or "").lower()
        if "shift" in key:
            return True
        try:
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            shift_modifier = getattr(QtCore.Qt, "ShiftModifier", None)
            if shift_modifier is None:
                shift_modifier = QtCore.Qt.KeyboardModifier.ShiftModifier
            return bool(modifiers & shift_modifier)
        except Exception:
            return False

    def _plot_axis(self, axes):
        if axes is None:
            return False
        if axes == self.widget.mpl.canvas.ax_pattern:
            return True
        return hasattr(self.widget.mpl.canvas, 'ax_cake') and \
            axes == self.widget.mpl.canvas.ax_cake

    def _plot_mouse_help_text(self, axes):
        if axes == self.widget.mpl.canvas.ax_pattern:
            return (
                "1D plot: left-drag to zoom in; right-click to return "
                "to the full current view."
            )
        if hasattr(self.widget.mpl.canvas, 'ax_cake') and \
                axes == self.widget.mpl.canvas.ax_cake:
            return (
                "Cake plot: left-drag to zoom in; right-click to return "
                "to the full current view."
            )
        return ""

    def _update_plot_mouse_help(self, event):
        if self._range_tool is not None:
            return
        if event is not None and self._plot_axis(event.inaxes):
            text = self._plot_mouse_help_text(event.inaxes)
            if text:
                self._set_status(text)
                self._plot_help_active = True
                return
        self._restore_plot_mouse_help()

    def _restore_plot_mouse_help(self):
        if not self._plot_help_active:
            return
        default = getattr(
            self.widget,
            "_compact_help_default",
            "Hover a compact control to see details.",
        )
        self._set_status(default)
        self._plot_help_active = False

    def _roi_selector_active(self):
        for ctrl_name in ("map_ctrl", "seq_ctrl", "cakeazi_ctrl"):
            ctrl = getattr(self.main, ctrl_name, None)
            is_active = getattr(ctrl, "is_roi_selection_active", None)
            if callable(is_active) and is_active():
                return True
            for selector_name in ("_selector_1d", "_selector_2d"):
                selector = getattr(ctrl, selector_name, None)
                if selector is None:
                    continue
                active = getattr(selector, "active", False)
                get_active = getattr(selector, "get_active", None)
                if callable(get_active):
                    active = get_active()
                if active:
                    return True
        return False

    def deactivate_roi_selectors(self):
        for ctrl_name in ("map_ctrl", "seq_ctrl", "cakeazi_ctrl"):
            ctrl = getattr(self.main, ctrl_name, None)
            if ctrl is None:
                continue
            deactivate = getattr(ctrl, "deactivate_interactions", None)
            if callable(deactivate):
                deactivate()

    def _inspect(self, event):
        if (event.xdata is None) or (event.ydata is None):
            return
        if not self._plot_axis(event.inaxes):
            return
        self.main.read_plot('left', event.xdata, event.ydata)

    def _peak_action_allowed(self, event):
        if (event.xdata is None) or (event.ydata is None):
            return False
        if not self._plot_axis(event.inaxes):
            return False
        if not self.model.current_section_exist():
            self._set_status("Set a fit section before editing peaks.")
            return False
        return True

    def _start_peak_drag(self, event):
        if not self._peak_action_allowed(event):
            return False
        row = self.main._get_selected_peak_parameter_row()
        if row is None:
            if self._event_on_any_peak(event):
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Select a peak row in the table before moving a peak.")
                return True
            return False
        if not self.main._event_on_selected_peak(event, row):
            return False
        if self.model.current_section.fitted():
            self.model.current_section.invalidate_fit_result()
            self._peak_drag_invalidated_fit = True
        else:
            self._peak_drag_invalidated_fit = False
        self._peak_drag_row = row
        self._peak_drag_latest_center = None
        self._peak_drag_marked_unsaved = False
        self._set_peak_center_from_xdata(row, event.xdata, during_drag=True)
        return True

    def _drag_selected_peak(self, event):
        row = self._peak_drag_row
        if row is None:
            return
        if (event is None) or (event.xdata is None):
            return
        if not self._plot_axis(event.inaxes):
            return
        self._set_peak_center_from_xdata(row, event.xdata, during_drag=True)

    def _finish_peak_drag(self):
        row = self._peak_drag_row
        center = self._peak_drag_latest_center
        invalidated_fit = self._peak_drag_invalidated_fit
        self._peak_drag_row = None
        self._peak_drag_latest_center = None
        self._peak_drag_marked_unsaved = False
        self._peak_drag_invalidated_fit = False
        if row is not None and center is not None:
            self.main._update_peak_position_widgets(row, center)
        if invalidated_fit or not self.main.plot_ctrl.refresh_peakfit_markers():
            self.main.plot_ctrl.update()

    def _event_on_any_peak(self, event):
        if not self.model.current_section_exist():
            return False
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        for row in range(n_peaks):
            if self.main._event_on_selected_peak(event, row):
                return True
        return False

    def _set_peak_center_from_xdata(self, row, xdata, during_drag=False):
        section = self.model.current_section
        if section is None or section.x is None or len(section.x) == 0:
            return
        if row < 0 or row >= section.get_number_of_peaks_in_queue():
            return
        x_min = float(np.min(section.x))
        x_max = float(np.max(section.x))
        center = min(max(float(xdata), x_min), x_max)
        section.peaks_in_queue[row]['center'] = center
        if during_drag:
            self._peak_drag_latest_center = center
        if (not during_drag) or (not self._peak_drag_marked_unsaved):
            self.main.peakfit_ctrl.set_tableWidget_PkParams_unsaved()
            if during_drag:
                self._peak_drag_marked_unsaved = True
        if during_drag and self.main.plot_ctrl.update_dragged_peak_marker(center):
            return
        self.main.plot_ctrl.update()

    def _start_zoom_drag(self, event):
        if event.xdata is None or event.ydata is None:
            return
        self._clear_zoom_patch()
        ax = event.inaxes
        self._zoom_blit_background = self._copy_axes_background(ax)
        self._zoom_drag = {
            "axes": ax,
            "x0": float(event.xdata),
            "y0": float(event.ydata),
            "x_px0": float(event.x),
            "y_px0": float(event.y),
        }
        self._zoom_last_draw_px = None
        self._zoom_last_draw_time = 0.0

    def _update_zoom_drag(self, event):
        if event is None:
            return
        drag = self._zoom_drag
        if drag is None:
            return
        ax = drag["axes"]
        x1, y1 = self._event_data_in_axes(event, ax, clamp=True)
        if x1 is None or y1 is None:
            return
        dx = abs(float(event.x) - drag["x_px0"])
        dy = abs(float(event.y) - drag["y_px0"])
        if max(dx, dy) < self.MIN_ZOOM_DRAG_PX:
            return
        now = time.monotonic()
        if self._zoom_last_draw_px is not None:
            last_x, last_y = self._zoom_last_draw_px
            moved_px = max(abs(float(event.x) - last_x),
                           abs(float(event.y) - last_y))
            if moved_px < 8.0 and (now - self._zoom_last_draw_time) < 0.025:
                return
        self._zoom_last_draw_px = (float(event.x), float(event.y))
        self._zoom_last_draw_time = now
        x0, y0 = drag["x0"], drag["y0"]
        if self._zoom_patch is None:
            edge_color = self._zoom_edge_color(ax)
            self._zoom_patch = patches.Rectangle(
                (min(x0, x1), min(y0, y1)),
                abs(x1 - x0),
                abs(y1 - y0),
                facecolor="#808080",
                edgecolor=edge_color,
                alpha=0.28,
                linewidth=1.2,
                zorder=100,
            )
            ax.add_patch(self._zoom_patch)
        else:
            self._zoom_patch.set_xy((min(x0, x1), min(y0, y1)))
            self._zoom_patch.set_width(abs(x1 - x0))
            self._zoom_patch.set_height(abs(y1 - y0))
        self._draw_zoom_patch()

    def _event_data_in_axes(self, event, ax, clamp=False):
        if event is None or ax is None:
            return None, None
        try:
            x_data, y_data = ax.transData.inverted().transform(
                (float(event.x), float(event.y)))
        except Exception:
            return None, None
        if not np.isfinite(x_data) or not np.isfinite(y_data):
            return None, None
        if clamp:
            x_limits = ax.get_xlim()
            y_limits = ax.get_ylim()
            x_data = min(max(float(x_data), min(x_limits)), max(x_limits))
            y_data = min(max(float(y_data), min(y_limits)), max(y_limits))
        return float(x_data), float(y_data)

    def _copy_axes_background(self, ax):
        try:
            canvas = self.widget.mpl.canvas
            canvas.draw_idle()
            canvas.flush_events()
            return canvas.copy_from_bbox(ax.bbox)
        except Exception:
            return None

    def _draw_zoom_patch(self):
        canvas = self.widget.mpl.canvas
        ax = None if self._zoom_patch is None else self._zoom_patch.axes
        if ax is None or self._zoom_blit_background is None:
            canvas.draw_idle()
            return
        try:
            canvas.restore_region(self._zoom_blit_background)
            ax.draw_artist(self._zoom_patch)
            canvas.blit(ax.bbox)
        except Exception:
            canvas.draw_idle()

    def _zoom_edge_color(self, ax):
        if ax == getattr(self.widget.mpl.canvas, "ax_cake", None):
            colormap = ""
            combo = getattr(self.widget, "comboBox_CakeColormap", None)
            if combo is not None:
                colormap = str(combo.currentText()).lower()
            return "black" if colormap.endswith("_r") else "white"
        face = ax.get_facecolor()
        luminance = 0.2126 * face[0] + 0.7152 * face[1] + 0.0722 * face[2]
        return "black" if luminance > 0.5 else "white"

    def _finish_zoom_drag(self, event):
        drag = self._zoom_drag
        self._zoom_drag = None
        self._zoom_last_draw_px = None
        self._zoom_last_draw_time = 0.0
        self._clear_zoom_patch()
        self._zoom_blit_background = None
        if drag is None or event is None:
            return
        ax = drag["axes"]
        x_end, y_end = self._event_data_in_axes(event, ax, clamp=True)
        if x_end is None or y_end is None:
            return
        dx = abs(float(event.x) - drag["x_px0"])
        dy = abs(float(event.y) - drag["y_px0"])
        if max(dx, dy) < self.MIN_ZOOM_DRAG_PX:
            self._set_status("Zoom ignored: drag a wider rectangle.")
            return
        x0, x1 = sorted([drag["x0"], x_end])
        y0, y1 = sorted([drag["y0"], y_end])
        if x1 <= x0 or y1 <= y0:
            return
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        self.widget.mpl.canvas.draw_idle()

    def _clear_zoom_patch(self):
        if self._zoom_patch is not None:
            ax = self._zoom_patch.axes
            try:
                self._zoom_patch.remove()
            except Exception:
                pass
            self._zoom_patch = None
            if self._zoom_blit_background is not None:
                try:
                    canvas = self.widget.mpl.canvas
                    canvas.restore_region(self._zoom_blit_background)
                    if ax is not None:
                        canvas.blit(ax.bbox)
                    return
                except Exception:
                    pass
            self.widget.mpl.canvas.draw_idle()

    def _set_status(self, text):
        label = getattr(self.widget, "label_PlotHelp", None)
        if label is not None:
            label.setText(str(text))

    def start_range_tool(self, label, callback, repeat=False,
                         cancel_callback=None):
        self.cancel_range_tool()
        self._plot_help_active = False
        self._range_tool = {
            "label": str(label),
            "callback": callback,
            "repeat": bool(repeat),
            "cancel_callback": cancel_callback,
        }
        if repeat:
            suffix = ": drag one or more ranges on the 1D or Cake plot; right-click to finish."
        else:
            suffix = ": drag a range on the 1D or Cake plot."
        self._set_status(str(label) + suffix)

    def cancel_range_tool(self):
        tool = self._range_tool
        self._range_tool = None
        self._range_drag = None
        self._range_last_draw_px = None
        self._clear_range_patch()
        if tool is not None:
            cancel_callback = tool.get("cancel_callback")
            if callable(cancel_callback):
                cancel_callback()

    def _handle_range_tool_press(self, event):
        if self._is_right(event):
            self.cancel_range_tool()
            self._set_status("Visual range selection canceled.")
            return
        if not self._is_left(event):
            return
        if not self._plot_axis(event.inaxes):
            return
        x0, __ = self._event_data_in_axes(event, event.inaxes, clamp=True)
        if x0 is None:
            return
        self._range_drag = {
            "axes": event.inaxes,
            "x0": float(x0),
            "x_px0": float(event.x),
        }
        self._range_last_draw_px = None

    def _update_range_drag(self, event):
        if event is None:
            return
        drag = self._range_drag
        if drag is None:
            return
        x1, __ = self._event_data_in_axes(event, drag["axes"], clamp=True)
        if x1 is None:
            return
        x0 = drag["x0"]
        if self._range_last_draw_px is not None:
            if abs(float(event.x) - self._range_last_draw_px) < 3.0:
                return
        self._range_last_draw_px = float(event.x)
        ax = drag["axes"]
        y0, y1 = ax.get_ylim()
        if self._range_patch is None:
            self._range_patch = patches.Rectangle(
                (min(x0, x1), min(y0, y1)),
                abs(x1 - x0),
                abs(y1 - y0),
                facecolor="#ffbf47",
                edgecolor="#ffbf47",
                alpha=0.22,
                linewidth=1.0,
                zorder=99,
            )
            ax.add_patch(self._range_patch)
        else:
            self._range_patch.set_xy((min(x0, x1), min(y0, y1)))
            self._range_patch.set_width(abs(x1 - x0))
            self._range_patch.set_height(abs(y1 - y0))
        self.widget.mpl.canvas.draw_idle()

    def _finish_range_drag(self, event):
        drag = self._range_drag
        tool = self._range_tool
        repeat = bool(tool.get("repeat", False)) if tool is not None else False
        self._range_drag = None
        self._range_tool = None
        self._range_last_draw_px = None
        self._clear_range_patch()
        if drag is None or tool is None:
            return
        x_end, __ = self._event_data_in_axes(
            event, drag["axes"], clamp=True)
        if x_end is None:
            if repeat:
                self._range_tool = tool
            return
        if abs(float(event.x) - drag["x_px0"]) < self.MIN_ZOOM_DRAG_PX:
            self._set_status("Range ignored: drag a wider interval.")
            if repeat:
                self._range_tool = tool
            return
        xmin, xmax = sorted([drag["x0"], float(x_end)])
        callback = tool.get("callback")
        if repeat:
            self._range_tool = tool
        try:
            if callable(callback):
                callback(xmin, xmax)
        finally:
            if repeat:
                self._range_tool = tool
                self._set_status(
                    str(tool.get("label", "Visual range")) +
                    ": range added. Drag another range or right-click to finish.")

    def _clear_range_patch(self):
        if self._range_patch is not None:
            try:
                self._range_patch.remove()
            except Exception:
                pass
            self._range_patch = None
            self.widget.mpl.canvas.draw_idle()
