import os
import re
import numpy as np
from qtpy import QtWidgets, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.widgets import RectangleSelector
from matplotlib.ticker import MaxNLocator, FormatStrFormatter
import matplotlib.patches as mpatches

from .xrdiohelpers import (
    load_chi_xy,
    load_bgsub_or_raw_xy,
    refresh_temp_bgsub_for_chi_files,
    find_temp_cake_triplet,
    load_cake_data,
)
from ..utils.dialogs import dialog_openfiles_hide_param_dirs


class SequenceController(object):
    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.base_ptn_ctrl = None
        self.plot_ctrl = None
        self.mouse_mode_done_cb = None
        self.export_current_view_cb = None

        self._seq_canvas = None
        self._seq_ax = None
        self._seq_line = None
        self._seq_x = None
        self._seq_y = None
        self._seq_current_marker = None

        self._selector_1d = None
        self._selector_2d = None
        self._roi_artist_1d = None
        self._roi_artist_2d = None

        self._chi_files = []
        self._file_numbers = []
        self._chi_cache = {}
        self._cake_cache = {}
        self._roi_1d = None
        self._roi_2d = None

        self._build_canvas()
        self._connect_channel()

    def set_helpers(self, base_ptn_ctrl=None, plot_ctrl=None,
                    mouse_mode_done_cb=None, export_current_view_cb=None):
        self.base_ptn_ctrl = base_ptn_ctrl
        self.plot_ctrl = plot_ctrl
        self.mouse_mode_done_cb = mouse_mode_done_cb
        self.export_current_view_cb = export_current_view_cb

    def _build_canvas(self):
        if not hasattr(self.widget, "verticalLayout_SeqCanvas"):
            return
        self._seq_fig = Figure()
        self._seq_fig.patch.set_facecolor("black")
        self._seq_fig.subplots_adjust(left=0.09, right=0.985, top=0.96, bottom=0.14)
        self._seq_ax = self._seq_fig.add_subplot(111)
        self._seq_ax.set_facecolor("black")
        self._seq_canvas = FigureCanvasQTAgg(self._seq_fig)
        self.widget.verticalLayout_SeqCanvas.addWidget(self._seq_canvas, 1)
        self._seq_canvas.mpl_connect("button_press_event", self._on_seq_click)
        self._seq_canvas.mpl_connect("motion_notify_event", self._on_seq_hover)
        self._seq_canvas.mpl_connect("figure_leave_event", self._clear_hover_file)
        self._draw_sequence()

    def _connect_channel(self):
        if not hasattr(self.widget, "tabWidget"):
            return
        self.widget.tabWidget.currentChanged.connect(self._on_main_tab_changed)

        self.widget.pushButton_SeqLoadChi.clicked.connect(self._load_chi_files)
        self.widget.pushButton_SeqSetRoi.clicked.connect(self._arm_roi_selection)
        self.widget.pushButton_SeqClearRoi.clicked.connect(self._clear_roi)
        self.widget.pushButton_SeqCompute.clicked.connect(self._compute_sequence)
        if hasattr(self.widget, "pushButton_SeqExportImage"):
            self.widget.pushButton_SeqExportImage.clicked.connect(self._export_image)
        if hasattr(self.widget, "pushButton_SeqExportNpy"):
            self.widget.pushButton_SeqExportNpy.clicked.connect(self._export_current_view)

    def _export_current_view(self):
        if self._seq_fig is None:
            self._set_status("No sequence view to export.")
            return
        if self.export_current_view_cb is None:
            self._set_status("Export view is not available.")
            return
        self.export_current_view_cb(
            fig=self._seq_fig,
            folder_prefix="seq-pkpo-export",
        )

    def _on_main_tab_changed(self, _idx):
        if not hasattr(self.widget, "tab_Seq"):
            return
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Seq:
            self.deactivate_interactions()
            self._clear_roi_overlays()
        else:
            self.refresh_current_marker()
            self.refresh_roi_overlays()

    def deactivate_interactions(self):
        self._disable_roi_selectors()
        if hasattr(self.widget, "pushButton_SeqSetRoi"):
            self.widget.pushButton_SeqSetRoi.setChecked(False)
            self._update_roi_button_state(False)

    def is_roi_selection_active(self):
        sel_1d_active = self._selector_is_active(self._selector_1d)
        sel_2d_active = self._selector_is_active(self._selector_2d)
        return bool(sel_1d_active or sel_2d_active)

    def _selector_is_active(self, selector):
        if selector is None:
            return False
        get_active = getattr(selector, "get_active", None)
        if callable(get_active):
            return bool(get_active())
        return bool(getattr(selector, "active", False))

    def _update_roi_button_state(self, active):
        button = getattr(self.widget, "pushButton_SeqSetRoi", None)
        if button is None:
            return
        button.setChecked(bool(active))
        if active:
            button.setText("ROI ON")
            button.setStyleSheet(
                "QPushButton { background-color: #d6a800; color: #1f1f1f; border: 1px solid #b88a00; }")
            button.setToolTip("ROI selection is active. Click again to cancel.")
        else:
            button.setText("Set ROI")
            button.setStyleSheet(
                "QPushButton { background-color: #444444; border: 1px solid #d6a800; color: #f0f0f0; }"
                "QPushButton:hover { background-color: #505050; }"
                "QPushButton:pressed { background-color: #383838; }")
            button.setToolTip("Click to draw an ROI on the 1D or Cake plot.")

    def _set_status(self, msg):
        text = str(msg or "")
        if hasattr(self.widget, "lineEdit_SeqStatus"):
            self.widget.lineEdit_SeqStatus.setText(text)
            self.widget.lineEdit_SeqStatus.setToolTip(text)

    def _default_hover_text(self):
        if not self._chi_files:
            return "Load CHI files to start."
        return "Hover over a sequence point to see its file name"

    def _set_hover_file_text(self, text):
        if hasattr(self.widget, "lineEdit_SeqHoverFile"):
            self.widget.lineEdit_SeqHoverFile.setText(str(text))

    def _clear_hover_file(self, _event=None):
        if hasattr(self.widget, "lineEdit_SeqHoverFile"):
            self.widget.lineEdit_SeqHoverFile.setPlaceholderText(
                self._default_hover_text()
            )
        self._set_hover_file_text("")

    def _set_loaded_count(self):
        if hasattr(self.widget, "label_SeqLoaded"):
            self.widget.label_SeqLoaded.setText(f"Loaded: {len(self._chi_files)}")

    def _load_chi_files(self):
        files, _ = dialog_openfiles_hide_param_dirs(
            self.widget,
            "Select CHI files for sequence",
            self.model.chi_path,
            "CHI files (*.chi)",
            default_hide_param_dirs=True,
        )
        if not files:
            return

        self._chi_files, self._file_numbers = \
            self._ordered_files_and_numbers(files)
        self._chi_cache = {}
        self._cake_cache = {}
        self._roi_1d = None
        self._roi_2d = None
        self._seq_x = None
        self._seq_y = None
        self._clear_hover_file()

        self._set_loaded_count()
        self._set_status(f"Loaded {len(self._chi_files)} CHI files.")
        self._preview_first_file()
        self._set_default_1d_full_range_roi()
        if self._roi_1d is not None:
            self._compute_sequence()
        else:
            self._draw_sequence()

    def _filename_sort_key(self, filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        name_lower = name.lower()
        nums = re.findall(r"(\d+)", name_lower)
        if nums:
            return (0, name_lower[:name_lower.rfind(nums[-1])], int(nums[-1]))
        return (1, name_lower)

    def _ordered_files_and_numbers(self, files):
        ordered_files = sorted(list(files), key=self._filename_sort_key)
        file_numbers = self._derive_file_numbers(ordered_files)
        if len(ordered_files) <= 1:
            return ordered_files, file_numbers

        # Plot lines in increasing displayed file-number order. Filename sort
        # can put map_10_0001 before map_1_0001 when the final numeric block is
        # shared; that produces a spurious line from the last point to the first.
        if len(set(file_numbers)) == len(file_numbers):
            pairs = list(zip(ordered_files, file_numbers))
            pairs.sort(key=lambda pair: (pair[1], self._filename_sort_key(pair[0])))
            ordered_files = [pair[0] for pair in pairs]
            file_numbers = [pair[1] for pair in pairs]
        return ordered_files, file_numbers

    def _derive_file_numbers(self, files):
        if not files:
            return []

        number_groups = []
        for f in files:
            name = os.path.splitext(os.path.basename(f))[0].lower()
            nums = [int(m.group(1)) for m in re.finditer(r"(\d+)", name)]
            number_groups.append(nums)

        max_groups = max((len(nums) for nums in number_groups), default=0)
        if max_groups == 0:
            return list(range(1, len(files) + 1))

        # Prefer the rightmost numeric group, but only if it distinguishes
        # every file. If that group collapses (for example repeated map ids),
        # walk left until a unique group is found.
        for rev_idx in range(1, max_groups + 1):
            candidate = []
            valid = True
            for nums in number_groups:
                if len(nums) < rev_idx:
                    valid = False
                    break
                candidate.append(nums[-rev_idx])
            if valid and (len(set(candidate)) == len(files)):
                return candidate

        # Final fallback: preserve order with guaranteed-unique indices.
        return list(range(1, len(files) + 1))

    def _preview_first_file(self):
        if not self._chi_files:
            return
        self._load_file_to_main_plot(0)

    def _load_file_to_main_plot(self, idx):
        if self.base_ptn_ctrl is None:
            return
        if (idx < 0) or (idx >= len(self._chi_files)):
            return
        try:
            self.base_ptn_ctrl._load_a_new_pattern(self._chi_files[idx])
            if self.plot_ctrl is not None:
                self.plot_ctrl.update()
            self._schedule_overlay_refresh()
        except Exception as exc:
            self._set_status(f"Failed to preview file: {exc}")

    def _schedule_overlay_refresh(self):
        if self.plot_ctrl is not None:
            flush = getattr(self.plot_ctrl, "_flush_update_request", None)
            if callable(flush):
                flush()
        self.refresh_current_marker()
        self.refresh_roi_overlays()
        QtCore.QTimer.singleShot(0, self.refresh_current_marker)
        QtCore.QTimer.singleShot(80, self.refresh_current_marker)
        QtCore.QTimer.singleShot(0, self.refresh_roi_overlays)
        QtCore.QTimer.singleShot(80, self.refresh_roi_overlays)

    def _set_default_1d_full_range_roi(self):
        if not self._chi_files:
            return
        try:
            x, __ = self._load_bgsub_xy_if_requested(self._chi_files[0])
            if x.size == 0:
                return
            xmin = float(np.nanmin(x))
            xmax = float(np.nanmax(x))
            if (not np.isfinite(xmin)) or (not np.isfinite(xmax)) or (xmax <= xmin):
                return
            self._roi_1d = (xmin, xmax)
            self._roi_2d = None
            self.widget.lineEdit_SeqRoiSummary.setText(f"1D: 2theta [{xmin:.3f}, {xmax:.3f}]")
        except Exception:
            pass

    def _arm_roi_selection(self):
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Seq:
            self._set_status("Open Seq tab first.")
            self._update_roi_button_state(False)
            return
        if self.is_roi_selection_active():
            self.deactivate_interactions()
            self._set_status("ROI selection canceled.")
            return
        self._disable_roi_selectors()
        self._roi_1d = None
        self._roi_2d = None
        self._seq_x = None
        self._seq_y = None
        self.widget.lineEdit_SeqRoiSummary.setText("")
        self._clear_roi_overlays()
        self._update_roi_button_state(True)
        self._selector_1d = RectangleSelector(
            self.widget.mpl.canvas.ax_pattern,
            self._on_roi_1d_selected,
            useblit=True,
            button=[1],
            interactive=False,
            drag_from_anywhere=False,
        )
        if self.widget.checkBox_ShowCake.isChecked():
            self._selector_2d = RectangleSelector(
                self.widget.mpl.canvas.ax_cake,
                self._on_roi_2d_selected,
                useblit=True,
                button=[1],
                interactive=False,
                drag_from_anywhere=False,
            )
            self._set_status("Draw ROI on 1D pattern or 2D cake plot.")
        else:
            self._set_status("Draw ROI on 1D pattern. Enable Cake view for 2D ROI.")

    def _disable_roi_selectors(self):
        if self._selector_1d is not None:
            try:
                self._selector_1d.set_active(False)
            except Exception:
                pass
            self._release_selector_widgetlock(self._selector_1d)
            try:
                self._selector_1d.disconnect_events()
            except Exception:
                pass
            self._selector_1d = None
        if self._selector_2d is not None:
            try:
                self._selector_2d.set_active(False)
            except Exception:
                pass
            self._release_selector_widgetlock(self._selector_2d)
            try:
                self._selector_2d.disconnect_events()
            except Exception:
                pass
            self._selector_2d = None
        self._update_roi_button_state(False)

    def _release_selector_widgetlock(self, selector):
        try:
            lock = self.widget.mpl.canvas.widgetlock
            if not lock.available(selector):
                lock.release(selector)
        except Exception:
            pass

    def _clear_roi(self):
        self._roi_1d = None
        self._roi_2d = None
        self.deactivate_interactions()
        self._clear_roi_overlays()
        self._seq_x = None
        self._seq_y = None
        self.widget.lineEdit_SeqRoiSummary.setText("")
        self._draw_sequence()
        self._set_status("ROI cleared.")

    def clear_roi_if_event_in_roi(self, event):
        if not self._is_seq_tab_active():
            return False
        if event is None:
            return False
        if self._roi_1d is not None and \
                event.inaxes == self.widget.mpl.canvas.ax_pattern and \
                event.xdata is not None:
            xmin, xmax = self._roi_1d
            if min(xmin, xmax) <= float(event.xdata) <= max(xmin, xmax):
                self._clear_roi()
                return True
        if self._roi_2d is not None and \
                self.widget.checkBox_ShowCake.isChecked() and \
                event.inaxes == self.widget.mpl.canvas.ax_cake and \
                event.xdata is not None and event.ydata is not None:
            xmin, xmax, ymin, ymax = self._roi_2d
            inside_x = min(xmin, xmax) <= float(event.xdata) <= max(xmin, xmax)
            inside_y = min(ymin, ymax) <= float(event.ydata) <= max(ymin, ymax)
            if inside_x and inside_y:
                self._clear_roi()
                return True
        return False

    def _on_roi_1d_selected(self, eclick, erelease):
        if (eclick.xdata is None) or (erelease.xdata is None):
            return
        xmin = min(float(eclick.xdata), float(erelease.xdata))
        xmax = max(float(eclick.xdata), float(erelease.xdata))
        if xmax <= xmin:
            return
        self._roi_1d = (xmin, xmax)
        self._roi_2d = None
        self.widget.lineEdit_SeqRoiSummary.setText(f"1D: 2theta [{xmin:.3f}, {xmax:.3f}]")
        self._set_status("1D ROI selected.")
        self.deactivate_interactions()
        self.refresh_roi_overlays()
        self._compute_sequence()
        if self.mouse_mode_done_cb is not None:
            self.mouse_mode_done_cb("roi")

    def _on_roi_2d_selected(self, eclick, erelease):
        if (eclick.xdata is None) or (erelease.xdata is None) or \
                (eclick.ydata is None) or (erelease.ydata is None):
            return
        xmin = min(float(eclick.xdata), float(erelease.xdata))
        xmax = max(float(eclick.xdata), float(erelease.xdata))
        ymin = min(float(eclick.ydata), float(erelease.ydata))
        ymax = max(float(eclick.ydata), float(erelease.ydata))
        if (xmax <= xmin) or (ymax <= ymin):
            return
        self._roi_2d = (xmin, xmax, ymin, ymax)
        self._roi_1d = None
        self.widget.lineEdit_SeqRoiSummary.setText(
            f"2D: 2theta [{xmin:.3f}, {xmax:.3f}], azi [{ymin:.3f}, {ymax:.3f}]"
        )
        self._set_status("2D ROI selected.")
        self.deactivate_interactions()
        self.refresh_roi_overlays()
        self._compute_sequence()
        if self.mouse_mode_done_cb is not None:
            self.mouse_mode_done_cb("roi")

    def _load_chi_xy(self, chi_path):
        return load_chi_xy(chi_path, self._chi_cache)

    def _load_bgsub_xy_if_requested(self, chi_path):
        use_bgsub = bool(
            getattr(self.widget, "checkBox_BgSub", None) and
            self.widget.checkBox_BgSub.isChecked()
        )
        return load_bgsub_or_raw_xy(chi_path, use_bgsub, self._chi_cache)

    def _find_temp_cake_triplet(self, chi_path):
        return find_temp_cake_triplet(chi_path)

    def _load_cake_data(self, chi_path):
        return load_cake_data(chi_path, self._cake_cache)

    def _current_displayed_chi(self):
        if not getattr(self.model, "base_ptn", None):
            return None
        return getattr(self.model.base_ptn, "fname", None)

    def _normalized_path(self, filename):
        if not filename:
            return None
        try:
            return os.path.normcase(os.path.abspath(os.path.realpath(str(filename))))
        except Exception:
            return os.path.normcase(os.path.abspath(str(filename)))

    def _current_file_idx(self):
        shown = self._current_displayed_chi()
        current = self._normalized_path(shown)
        if current is None:
            return None
        for idx, chi_path in enumerate(self._chi_files):
            if self._normalized_path(chi_path) == current:
                return idx

        shown_base = os.path.basename(str(shown))
        matches = [
            idx for idx, chi_path in enumerate(self._chi_files)
            if os.path.basename(str(chi_path)) == shown_base
        ]
        if len(matches) == 1:
            return int(matches[0])
        return None

    def _preferred_bg_reference_chi(self):
        shown = self._current_displayed_chi()
        if shown and (shown in self._chi_files):
            return shown
        if self._chi_files:
            return self._chi_files[0]
        return None

    def _refresh_temp_bgsub_if_requested(self):
        use_bgsub = bool(
            getattr(self.widget, "checkBox_BgSub", None) and
            self.widget.checkBox_BgSub.isChecked()
        )
        if (not use_bgsub) or (self._roi_1d is None) or (not self._chi_files):
            return

        bg_roi = [
            float(self.widget.doubleSpinBox_Background_ROI_min.value()),
            float(self.widget.doubleSpinBox_Background_ROI_max.value()),
        ]
        bg_params = [
            int(self.widget.spinBox_BGParam0.value()),
            int(self.widget.spinBox_BGParam1.value()),
            int(self.widget.spinBox_BGParam2.value()),
        ]
        result = refresh_temp_bgsub_for_chi_files(
            self._chi_files,
            preferred_chi=self._preferred_bg_reference_chi(),
            bg_roi=bg_roi,
            bg_params=bg_params,
        )
        ref_name = os.path.basename(result["reference"]) if result["reference"] else "N/A"
        if result["updated"] > 0:
            self._set_status(
                f"Temp BG refresh complete: {result['updated']} updated "
                f"(reference: {ref_name}).")
        if result["failed"] > 0:
            first_path, first_err = result["failures"][0]
            first_name = os.path.basename(first_path)
            self._set_status(
                f"Temp BG refresh: {result['updated']} updated, "
                f"{result['failed']} failed. First: {first_name} ({first_err})")

    def _compute_sequence(self):
        if not self._chi_files:
            self._set_status("Load CHI files first.")
            return
        if (self._roi_1d is None) and (self._roi_2d is None):
            self._set_status("Select ROI first.")
            return
        self._refresh_temp_bgsub_if_requested()

        values = np.full(len(self._chi_files), np.nan, dtype=float)
        failures = []
        for i, chi_path in enumerate(self._chi_files):
            try:
                if self._roi_1d is not None:
                    x, y = self._load_bgsub_xy_if_requested(chi_path)
                    xmin, xmax = self._roi_1d
                    m = (x >= xmin) & (x <= xmax)
                    if not np.any(m):
                        values[i] = np.nan
                    else:
                        values[i] = float(np.nansum(y[m]))
                else:
                    cake = self._load_cake_data(chi_path)
                    if cake is None:
                        raise RuntimeError("No cake temp files")
                    tth, azi, intensity = cake
                    xmin, xmax, ymin, ymax = self._roi_2d
                    mt = (tth >= xmin) & (tth <= xmax)
                    ma = (azi >= ymin) & (azi <= ymax)
                    if (not np.any(mt)) or (not np.any(ma)):
                        values[i] = np.nan
                    else:
                        sub = intensity[np.ix_(ma, mt)]
                        values[i] = float(np.nansum(sub))
            except Exception as exc:
                failures.append((chi_path, str(exc)))
                values[i] = np.nan

        self._seq_x = np.asarray(self._file_numbers, dtype=float)
        self._seq_y = values
        self._draw_sequence()

        if failures:
            first_path, first_err = failures[0]
            first_name = os.path.basename(first_path)
            self._set_status(
                f"Sequence computed with {len(failures)} failures. "
                f"First: {first_name} ({first_err})")
        else:
            if self._roi_1d is not None:
                if bool(getattr(self.widget, "checkBox_BgSub", None) and
                        self.widget.checkBox_BgSub.isChecked()):
                    self._set_status("Sequence computed from 1D bg-subtracted intensity in ROI.")
                else:
                    self._set_status("Sequence computed from raw 1D intensity (no bg subtraction).")
            else:
                self._set_status("Sequence computed from raw 2D cake intensity (no bg subtraction).")
        self._schedule_overlay_refresh()

    def _current_title_text(self):
        if self._roi_1d is not None:
            xmin, xmax = self._roi_1d
            return f"2theta [{xmin:.3f}, {xmax:.3f}]"
        if self._roi_2d is not None:
            xmin, xmax, __, __ = self._roi_2d
            return f"2theta [{xmin:.3f}, {xmax:.3f}]"
        return "2theta"

    def _draw_sequence(self):
        if self._seq_ax is None:
            return
        self._clear_hover_file()
        self._seq_ax.clear()
        self._seq_current_marker = None
        self._seq_fig.patch.set_facecolor("black")
        self._seq_ax.set_facecolor("black")
        if (self._seq_x is None) or (self._seq_y is None) or (self._seq_x.size == 0):
            self._seq_ax.set_axis_off()
            self._seq_canvas.draw_idle()
            return
        self._seq_ax.set_axis_on()
        self._seq_line, = self._seq_ax.plot(
            self._seq_x,
            self._seq_y,
            linestyle="-",
            marker="o",
            markersize=5,
            linewidth=1.3,
            color="#1f77b4",
            markerfacecolor="#1f77b4",
            markeredgecolor="white",
            markeredgewidth=0.6,
        )
        self._seq_ax.set_title(self._current_title_text())
        self._seq_ax.set_xlabel("File number")
        self._seq_ax.set_ylabel("Integrated intensity")
        self._seq_ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        self._seq_ax.xaxis.set_major_formatter(FormatStrFormatter("%d"))
        self._seq_ax.grid(True, alpha=0.22, linewidth=0.6)
        self._add_current_marker(draw=False)
        self._seq_fig.tight_layout()
        self._seq_canvas.draw_idle()

    def _clear_current_marker(self):
        if self._seq_current_marker is None:
            return False
        try:
            self._seq_current_marker.remove()
        except Exception:
            pass
        self._seq_current_marker = None
        return True

    def _add_current_marker(self, draw=True):
        self._clear_current_marker()
        if (self._seq_ax is None) or (self._seq_x is None) or (self._seq_y is None):
            return
        idx = self._current_file_idx()
        if idx is None or idx >= len(self._seq_x) or idx >= len(self._seq_y):
            return
        x = float(self._seq_x[idx])
        y = float(self._seq_y[idx])
        if (not np.isfinite(x)) or (not np.isfinite(y)):
            return
        self._seq_current_marker = self._seq_ax.scatter(
            [x],
            [y],
            s=140,
            marker="o",
            facecolors="none",
            edgecolors="#ff3030",
            linewidths=2.0,
            zorder=10,
        )
        if draw and self._seq_canvas is not None:
            self._seq_canvas.draw_idle()

    def refresh_current_marker(self):
        if self._seq_ax is None:
            return
        changed = self._clear_current_marker()
        self._add_current_marker(draw=False)
        if (changed or self._seq_current_marker is not None) and self._seq_canvas is not None:
            self._seq_canvas.draw_idle()

    def _nearest_seq_file_idx(self, event, max_distance_px=20.0):
        if (self._seq_x is None) or (self._seq_y is None):
            return None
        if event.inaxes != self._seq_ax:
            return None
        if event.xdata is None:
            return None
        finite = np.isfinite(self._seq_x) & np.isfinite(self._seq_y)
        if not np.any(finite):
            return None

        x = self._seq_x[finite]
        y = self._seq_y[finite]
        idx_map = np.where(finite)[0]
        ydata = event.ydata if event.ydata is not None else 0.0
        hover_px = self._seq_ax.transData.transform((event.xdata, ydata))
        pts_px = self._seq_ax.transData.transform(np.column_stack([x, y]))
        dist2 = np.sum((pts_px - hover_px) ** 2, axis=1)
        k = int(np.argmin(dist2))
        if dist2[k] > float(max_distance_px) ** 2:
            return None
        return int(idx_map[k])

    def _on_seq_click(self, event):
        file_idx = self._nearest_seq_file_idx(event)
        if file_idx is None:
            return
        self._load_file_to_main_plot(file_idx)
        file_num = int(self._file_numbers[file_idx]) if file_idx < len(self._file_numbers) else file_idx + 1
        self._set_status(f"Selected sequence point: file number {file_num}")

    def _on_seq_hover(self, event):
        file_idx = self._nearest_seq_file_idx(event)
        if file_idx is None or file_idx >= len(self._chi_files):
            self._clear_hover_file()
            return
        self._set_hover_file_text(os.path.basename(self._chi_files[file_idx]))

    def _is_seq_tab_active(self):
        return hasattr(self.widget, "tab_Seq") and \
            (self.widget.tabWidget.currentWidget() == self.widget.tab_Seq)

    def _should_show_roi_overlay(self):
        if (self._seq_y is None) or (self._seq_x is None):
            return False
        if not self._is_seq_tab_active():
            return False
        return (self._roi_1d is not None) or (self._roi_2d is not None)

    def _clear_roi_overlays(self):
        changed = False
        if self._roi_artist_1d is not None:
            try:
                self._roi_artist_1d.remove()
            except Exception:
                pass
            self._roi_artist_1d = None
            changed = True
        if self._roi_artist_2d is not None:
            try:
                self._roi_artist_2d.remove()
            except Exception:
                pass
            self._roi_artist_2d = None
            changed = True
        if changed and hasattr(self.widget, "mpl") and hasattr(self.widget.mpl, "canvas"):
            try:
                self.widget.mpl.canvas.draw_idle()
            except Exception:
                pass

    def refresh_roi_overlays(self):
        self._clear_roi_overlays()
        if not self._should_show_roi_overlay():
            return
        try:
            if self._roi_1d is not None:
                xmin, xmax = self._roi_1d
                ax = self.widget.mpl.canvas.ax_pattern
                self._roi_artist_1d = ax.axvspan(
                    xmin, xmax, ymin=0.0, ymax=1.0,
                    facecolor="red", edgecolor="red", alpha=0.2, linewidth=1.2
                )
            elif self._roi_2d is not None and self.widget.checkBox_ShowCake.isChecked():
                xmin, xmax, ymin, ymax = self._roi_2d
                ax = self.widget.mpl.canvas.ax_cake
                self._roi_artist_2d = mpatches.Rectangle(
                    (xmin, ymin),
                    xmax - xmin,
                    ymax - ymin,
                    fill=False,
                    edgecolor="red",
                    linewidth=1.8,
                )
                ax.add_patch(self._roi_artist_2d)
            self.widget.mpl.canvas.draw_idle()
        except Exception:
            self._roi_artist_1d = None
            self._roi_artist_2d = None

    def _export_image(self):
        if (self._seq_x is None) or (self._seq_y is None):
            self._set_status("No sequence data to export.")
            return
        base = os.path.join(self.model.chi_path, "sequence.png")
        filen, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.widget,
            "Export sequence image",
            base,
            "Image files (*.png *.pdf)",
        )
        if not filen:
            return
        self._seq_fig.savefig(filen, dpi=300, bbox_inches="tight")
        self._set_status("Image exported.")

    def _export_npy(self):
        if (self._seq_x is None) or (self._seq_y is None):
            self._set_status("No sequence data to export.")
            return
        root = self.model.chi_path if str(getattr(self.model, "chi_path", "")).strip() else os.getcwd()
        out_dir = os.path.join(root, "sequence_py")
        os.makedirs(out_dir, exist_ok=True)

        npy_path = os.path.join(out_dir, "sequence.npy")
        py_path = os.path.join(out_dir, "plot_sequence.py")

        data = np.column_stack([self._seq_x, self._seq_y])
        np.save(npy_path, data)

        script = (
            "import numpy as np\n"
            "import matplotlib.pyplot as plt\n\n"
            "from matplotlib.ticker import MaxNLocator, FormatStrFormatter\n\n"
            "def main():\n"
            "    data = np.load('sequence.npy')\n"
            "    file_number = data[:, 0]\n"
            "    intensity = data[:, 1]\n"
            "    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor='white')\n"
            "    ax.set_facecolor('white')\n"
            "    ax.plot(file_number, intensity, '-o', color='tab:blue', markersize=4)\n"
            f"    ax.set_title({self._current_title_text()!r})\n"
            "    ax.set_xlabel('File number')\n"
            "    ax.set_ylabel('Integrated intensity')\n"
            "    ax.xaxis.set_major_locator(MaxNLocator(integer=True))\n"
            "    ax.xaxis.set_major_formatter(FormatStrFormatter('%d'))\n"
            "    ax.grid(True, alpha=0.25)\n"
            "    fig.tight_layout()\n"
            "    plt.show()\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        with open(py_path, "w", encoding="utf-8") as fh:
            fh.write(script)

        self._set_status("Exported sequence_py (sequence.npy + plot_sequence.py).")
