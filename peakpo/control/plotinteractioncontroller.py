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
        self._zoom_x_modifier = False
        self._zoom_y_modifier = False
        self._pan_modifier = False
        self._pan_drag = None
        self._pan_patch = None
        self._pan_last_draw_px = None
        self._pan_last_draw_time = 0.0
        self._pan_blit_background = None
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
        self._editable_xrange = None
        self._editable_xrange_drag = None

    def connect(self):
        canvas = self.widget.mpl.canvas
        canvas.mpl_connect('button_press_event', self.on_press)
        canvas.mpl_connect('button_release_event', self.on_release)
        canvas.mpl_connect('motion_notify_event', self.on_motion)
        canvas.mpl_connect('figure_leave_event', self.on_leave)
        self.main._deactivate_toolbar_modes()

    def set_zoom_y_modifier(self, active):
        self._zoom_y_modifier = bool(active)

    def set_zoom_x_modifier(self, active):
        self._zoom_x_modifier = bool(active)

    def set_pan_modifier(self, active):
        self._pan_modifier = bool(active)

    def on_press(self, event):
        self.main._deactivate_toolbar_modes()
        if event is None:
            return
        if self._editable_xrange is not None:
            self._handle_editable_xrange_press(event)
            return
        if self._range_tool is not None:
            self._handle_range_tool_press(event)
            return
        if self._is_left(event) and bool(getattr(event, "dblclick", False)):
            self._inspect(event)
            return
        if self._is_right(event):
            mode = self._zoom_mode(event)
            if bool(getattr(event, "dblclick", False)):
                self.main.plot_new_graph()
                return
            if self._shift_down(event) and self._peak_action_allowed(event):
                self.main.pick_peak('right', event.xdata, event.ydata)
                return
            self._zoom_out_current_view(event.inaxes, mode)
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
        if self._pan_modifier and self._plot_axis(event.inaxes):
            self._start_pan_drag(event)
            return
        if self._plot_axis(event.inaxes):
            self._start_zoom_drag(event)

    def on_motion(self, event):
        if self._editable_xrange_drag is not None:
            self._update_editable_xrange_drag(event)
            return
        if self._range_drag is not None:
            self._update_range_drag(event)
            return
        if self._peak_drag_row is not None:
            self._drag_selected_peak(event)
            return
        if self._pan_drag is not None:
            self._update_pan_drag(event)
            return
        if self._zoom_drag is not None:
            self._update_zoom_drag(event)
            return
        self._update_plot_mouse_help(event)
        self.main._update_cursor_position_readout(event)

    def on_release(self, event):
        if self._editable_xrange_drag is not None:
            self._finish_editable_xrange_drag(event)
            return
        if self._range_drag is not None:
            self._finish_range_drag(event)
            return
        if self._peak_drag_row is not None:
            self._finish_peak_drag()
            return
        if self._pan_drag is not None:
            self._finish_pan_drag(event)
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

    def _zoom_mode(self, event=None):
        key = str(getattr(event, "key", "") or "").lower()
        x_active = self._zoom_x_modifier or ("x" in key)
        y_active = self._zoom_y_modifier or ("y" in key)
        if x_active and y_active:
            return "xy"
        if x_active:
            return "x"
        if y_active:
            return "y"
        return "xy"

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
                "1D plot: left-drag to zoom in; hold X and left-drag to "
                "zoom X only; hold Y and left-drag to zoom Y only; hold P "
                "and left-drag to pan; right-click zooms out 20%; hold X or "
                "Y with right-click zooms that axis out 20%; double right-"
                "click returns to full range."
            )
        if hasattr(self.widget.mpl.canvas, 'ax_cake') and \
                axes == self.widget.mpl.canvas.ax_cake:
            return (
                "Cake plot: left-drag to zoom in; hold X and left-drag to "
                "zoom X only; hold Y and left-drag to zoom Y only; hold P "
                "and left-drag to pan; right-click zooms out 20%; hold X or "
                "Y with right-click zooms that axis out 20%; double right-"
                "click returns to full range."
            )
        return ""

    def _xrange_handle_tolerance_px(self):
        return 10.0

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
            "mode": self._zoom_mode(event),
        }
        self._zoom_last_draw_px = None
        self._zoom_last_draw_time = 0.0

    def _start_pan_drag(self, event):
        if event.xdata is None or event.ydata is None:
            return
        self._clear_pan_patch()
        ax = event.inaxes
        self._pan_blit_background = self._copy_axes_background(ax)
        self._pan_drag = {
            "axes": ax,
            "x0": float(event.xdata),
            "y0": float(event.ydata),
            "x_px0": float(event.x),
            "y_px0": float(event.y),
            "xlim0": tuple(float(v) for v in ax.get_xlim()),
            "ylim0": tuple(float(v) for v in ax.get_ylim()),
            "bbox_w": float(ax.bbox.width or 1.0),
            "bbox_h": float(ax.bbox.height or 1.0),
        }
        self._pan_last_draw_px = None
        self._pan_last_draw_time = 0.0

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
        x_limits = ax.get_xlim()
        y_limits = ax.get_ylim()
        x_left = float(min(x_limits))
        x_right = float(max(x_limits))
        y_bottom = float(min(y_limits))
        y_top = float(max(y_limits))
        mode = drag.get("mode", "xy")
        if mode == "y":
            x0 = x_left
            x1 = x_right
        elif mode == "x":
            y0 = y_bottom
            y1 = y_top
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

    def _update_pan_drag(self, event):
        if event is None:
            return
        drag = self._pan_drag
        if drag is None:
            return
        ax = drag["axes"]
        x1, y1 = self._event_data_in_axes(event, ax, clamp=False)
        if x1 is None or y1 is None:
            return
        dx = abs(float(event.x) - drag["x_px0"])
        dy = abs(float(event.y) - drag["y_px0"])
        if max(dx, dy) < self.MIN_ZOOM_DRAG_PX:
            return
        now = time.monotonic()
        if self._pan_last_draw_px is not None:
            last_x, last_y = self._pan_last_draw_px
            moved_px = max(abs(float(event.x) - last_x),
                           abs(float(event.y) - last_y))
            if moved_px < 8.0 and (now - self._pan_last_draw_time) < 0.025:
                return
        self._pan_last_draw_px = (float(event.x), float(event.y))
        self._pan_last_draw_time = now
        xlim0 = drag["xlim0"]
        ylim0 = drag["ylim0"]
        bbox_w = max(float(drag.get("bbox_w", 1.0)), 1.0)
        bbox_h = max(float(drag.get("bbox_h", 1.0)), 1.0)
        dx_px = float(event.x) - float(drag["x_px0"])
        dy_px = float(event.y) - float(drag["y_px0"])
        x_span = xlim0[1] - xlim0[0]
        y_span = ylim0[1] - ylim0[0]
        x_shift = dx_px * x_span / bbox_w
        y_shift = dy_px * y_span / bbox_h
        ax.set_xlim(xlim0[0] - x_shift, xlim0[1] - x_shift)
        ax.set_ylim(ylim0[0] - y_shift, ylim0[1] - y_shift)
        self.widget.mpl.canvas.draw_idle()

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

    def _clear_pan_patch(self):
        self._pan_drag = None
        self._pan_last_draw_px = None
        self._pan_last_draw_time = 0.0
        self._pan_blit_background = None

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
        mode = drag.get("mode", "xy")
        if mode == "y":
            ax.set_ylim(y0, y1)
        elif mode == "x":
            ax.set_xlim(x0, x1)
        else:
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
        self.widget.mpl.canvas.draw_idle()

    def _finish_pan_drag(self, event):
        drag = self._pan_drag
        self._clear_pan_patch()
        if drag is None or event is None:
            return
        ax = drag["axes"]
        dx = abs(float(event.x) - drag["x_px0"])
        dy = abs(float(event.y) - drag["y_px0"])
        if max(dx, dy) < self.MIN_ZOOM_DRAG_PX:
            self._set_status("Pan ignored: drag farther to move the view.")
            return
        self.widget.mpl.canvas.draw_idle()

    def _zoom_out_current_view(self, axes, mode="xy"):
        ax = axes if self._plot_axis(axes) else None
        if ax is None:
            return
        self._zoom_axes_out(
            ax, 1.2, zoom_x=(mode in ("x", "xy")), zoom_y=(mode in ("y", "xy")))
        self.widget.mpl.canvas.draw_idle()

    def _zoom_axes_out(self, ax, factor, zoom_x=True, zoom_y=True):
        if ax is None or factor <= 1.0:
            return
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        x_center = 0.5 * (x0 + x1)
        y_center = 0.5 * (y0 + y1)
        if zoom_x:
            x_half = 0.5 * (x1 - x0) * factor
            ax.set_xlim(x_center - x_half, x_center + x_half)
        if zoom_y:
            y_half = 0.5 * (y1 - y0) * factor
            ax.set_ylim(y_center - y_half, y_center + y_half)

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

    def start_editable_xrange_tool(self, label, xmin, xmax, callback,
                                   cancel_callback=None,
                                   facecolor="#ffbf47",
                                   edgecolor="#ff8f00",
                                   axes=None):
        self.cancel_range_tool()
        self._clear_editable_xrange()
        if axes is None:
            axes = self.widget.mpl.canvas.ax_pattern
        if axes is None:
            return False
        x0, x1 = sorted([float(xmin), float(xmax)])
        y0, y1 = axes.get_ylim()
        patch = patches.Rectangle(
            (x0, y0), x1 - x0, y1 - y0,
            facecolor=facecolor,
            edgecolor=edgecolor,
            alpha=0.25,
            linewidth=1.4,
            zorder=101,
        )
        axes.add_patch(patch)
        self._editable_xrange = {
            "label": str(label),
            "callback": callback,
            "cancel_callback": cancel_callback,
            "axes": axes,
            "xmin": x0,
            "xmax": x1,
            "ymin": y0,
            "ymax": y1,
            "patch": patch,
            "facecolor": facecolor,
            "edgecolor": edgecolor,
        }
        self._set_status(
            str(label) + ": drag left/right edge to resize, drag inside to move, right-click to cancel.")
        self.widget.mpl.canvas.draw_idle()
        return True

    def get_editable_xrange(self):
        tool = self._editable_xrange
        if tool is None:
            return None
        return float(tool["xmin"]), float(tool["xmax"])

    def cancel_editable_xrange(self):
        tool = self._editable_xrange
        self._editable_xrange_drag = None
        self._clear_editable_xrange()
        if tool is not None:
            cancel_callback = tool.get("cancel_callback")
            if callable(cancel_callback):
                cancel_callback()

    def _clear_editable_xrange(self):
        tool = self._editable_xrange
        self._editable_xrange = None
        self._editable_xrange_drag = None
        if tool is None:
            return
        patch = tool.get("patch")
        if patch is not None:
            try:
                patch.remove()
            except Exception:
                pass
        self.widget.mpl.canvas.draw_idle()

    def _hit_test_editable_xrange(self, event):
        tool = self._editable_xrange
        if tool is None or event is None or event.inaxes != tool["axes"]:
            return None
        x0 = tool["xmin"]
        x1 = tool["xmax"]
        y0 = tool["ymin"]
        y1 = tool["ymax"]
        if event.xdata is None or event.ydata is None:
            return None
        if not (min(y0, y1) <= event.ydata <= max(y0, y1)):
            return None
        ax = tool["axes"]
        left_px = ax.transData.transform((x0, event.ydata))[0]
        right_px = ax.transData.transform((x1, event.ydata))[0]
        click_px = float(event.x)
        tol = self._xrange_handle_tolerance_px()
        if abs(click_px - left_px) <= tol:
            return "left"
        if abs(click_px - right_px) <= tol:
            return "right"
        if min(left_px, right_px) < click_px < max(left_px, right_px):
            return "move"
        return None

    def _handle_editable_xrange_press(self, event):
        if self._editable_xrange is None:
            return
        if self._is_right(event):
            self.cancel_editable_xrange()
            self._set_status("Range edit canceled.")
            return
        if not self._is_left(event):
            return
        mode = self._hit_test_editable_xrange(event)
        if mode is None:
            return
        tool = self._editable_xrange
        tool["press_x"] = float(event.xdata)
        tool["orig_xmin"] = float(tool["xmin"])
        tool["orig_xmax"] = float(tool["xmax"])
        tool["mode"] = mode
        self._editable_xrange_drag = tool

    def _update_editable_xrange_drag(self, event):
        tool = self._editable_xrange_drag
        if tool is None or event is None or event.xdata is None:
            return
        ax = tool["axes"]
        xdata = float(event.xdata)
        x_limits = ax.get_xlim()
        x_lo = float(min(x_limits))
        x_hi = float(max(x_limits))
        orig_xmin = float(tool["orig_xmin"])
        orig_xmax = float(tool["orig_xmax"])
        width = max(0.0, orig_xmax - orig_xmin)
        mode = tool.get("mode")
        if mode == "left":
            xmin = min(max(xdata, x_lo), orig_xmax)
            xmax = orig_xmax
        elif mode == "right":
            xmin = orig_xmin
            xmax = max(min(xdata, x_hi), orig_xmin)
        else:
            delta = xdata - float(tool.get("press_x", xdata))
            xmin = orig_xmin + delta
            xmax = orig_xmax + delta
            if xmin < x_lo:
                xmax += (x_lo - xmin)
                xmin = x_lo
            if xmax > x_hi:
                xmin -= (xmax - x_hi)
                xmax = x_hi
            if xmin < x_lo:
                xmin = x_lo
                xmax = min(x_lo + width, x_hi)
        xmin = min(max(xmin, x_lo), x_hi)
        xmax = min(max(xmax, x_lo), x_hi)
        if xmax < xmin:
            xmax = xmin
        self._set_editable_xrange(tool, xmin, xmax)
        self.widget.mpl.canvas.draw_idle()

    def _set_editable_xrange(self, tool, xmin, xmax):
        axes = tool["axes"]
        y0, y1 = axes.get_ylim()
        tool["xmin"] = float(min(xmin, xmax))
        tool["xmax"] = float(max(xmin, xmax))
        tool["ymin"] = float(y0)
        tool["ymax"] = float(y1)
        patch = tool.get("patch")
        if patch is not None:
            patch.set_xy((tool["xmin"], y0))
            patch.set_width(tool["xmax"] - tool["xmin"])
            patch.set_height(y1 - y0)

    def _finish_editable_xrange_drag(self, event):
        tool = self._editable_xrange_drag
        self._editable_xrange_drag = None
        if tool is None:
            return
        callback = tool.get("callback")
        try:
            if callable(callback):
                callback(float(tool["xmin"]), float(tool["xmax"]))
        finally:
            self.widget.mpl.canvas.draw_idle()

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
        if self._editable_xrange is not None:
            self.cancel_editable_xrange()

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
