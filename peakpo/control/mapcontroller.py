import os
import math
import re
import numpy as np
from qtpy import QtWidgets, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.widgets import RectangleSelector
from matplotlib import colormaps
import matplotlib.patches as mpatches

from .xrdiohelpers import (
    DioptasMetadataCollection,
    MapPointInfo,
    build_coordinate_grid,
    extract_scan_coordinates,
    load_chi_xy,
    load_bgsub_or_raw_xy,
    refresh_temp_bgsub_for_chi_files,
    find_temp_cake_triplet,
    load_cake_data,
)
from ..utils import get_temp_dir
from ..utils.dialogs import dialog_openfiles_hide_param_dirs


class MapController(object):
    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.base_ptn_ctrl = None
        self.plot_ctrl = None
        self.mouse_mode_done_cb = None
        self.export_current_view_cb = None

        self._map_canvas = None
        self._map_ax = None
        self._map_cax = None
        self._map_cbar = None
        self._map_im = None
        self._map_current_pixel_artist = None

        self._selector_1d = None
        self._selector_2d = None
        self._roi_artist_1d = None
        self._roi_artist_2d = None

        self._chi_files = []
        self._chi_input_files = []
        self._pos_idx = []
        self._lin_to_file = {}
        self._chi_cache = {}
        self._cake_cache = {}
        self._grid = (1, 1)
        self._roi_1d = None
        self._roi_2d = None
        self._map_data = None
        self._map_points = []
        self._coord_x = []
        self._coord_y = []
        self._coord_to_file = {}
        self._map_coordinate_mode = False

        self._sync_ui_from_roi = False
        self._progress_dialog = None

        self._build_canvas()
        self._connect_channel()

    def set_helpers(self, base_ptn_ctrl=None, plot_ctrl=None,
                    mouse_mode_done_cb=None, export_current_view_cb=None):
        self.base_ptn_ctrl = base_ptn_ctrl
        self.plot_ctrl = plot_ctrl
        self.mouse_mode_done_cb = mouse_mode_done_cb
        self.export_current_view_cb = export_current_view_cb

    def _build_canvas(self):
        if not hasattr(self.widget, "verticalLayout_MapCanvas"):
            return
        self._map_fig = Figure()
        self._map_fig.patch.set_facecolor("black")
        self._map_fig.subplots_adjust(left=0.005, right=0.94, top=0.985, bottom=0.03)
        self._recreate_map_axes()
        self._map_canvas = FigureCanvasQTAgg(self._map_fig)
        self.widget.verticalLayout_MapCanvas.addWidget(self._map_canvas, 1)
        self._map_canvas.mpl_connect("button_press_event", self._on_map_click)
        self._map_canvas.mpl_connect("motion_notify_event", self._on_map_hover)
        self._map_canvas.mpl_connect("figure_leave_event", self._clear_hover_file)
        self._draw_map()

    def _recreate_map_axes(self):
        if getattr(self, "_map_fig", None) is None:
            return
        self._map_fig.clf()
        self._map_fig.patch.set_facecolor("black")
        self._map_ax = self._map_fig.add_subplot(111)
        self._map_ax.set_facecolor("black")
        self._map_cax = None
        self._map_cbar = None
        self._map_current_pixel_artist = None

    def _ensure_map_axes(self):
        if self._map_ax is None:
            self._recreate_map_axes()
            return
        # Axes can become detached after colorbar removal in some mpl states.
        ax_fig = getattr(self._map_ax, "figure", None)
        if (ax_fig is None) or (ax_fig is not self._map_fig):
            self._recreate_map_axes()

    def _connect_channel(self):
        if not hasattr(self.widget, "tabWidget"):
            return
        self.widget.tabWidget.currentChanged.connect(self._on_main_tab_changed)

        self.widget.pushButton_MapLoadChi.clicked.connect(self._load_chi_files)
        self.widget.spinBox_MapNx.valueChanged.connect(self._on_grid_changed)
        self.widget.spinBox_MapNy.valueChanged.connect(self._on_grid_changed)
        self.widget.comboBox_MapOrder.currentIndexChanged.connect(self._on_grid_changed)


        self.widget.pushButton_MapSetRoi.clicked.connect(self._arm_roi_selection)
        self.widget.pushButton_MapClearRoi.clicked.connect(self._clear_roi)
        self.widget.pushButton_MapCompute.clicked.connect(self._compute_map)

        self.widget.comboBox_MapCmap.currentIndexChanged.connect(self._draw_map)
        self.widget.doubleSpinBox_MapVmin.valueChanged.connect(self._draw_map)
        self.widget.doubleSpinBox_MapVmax.valueChanged.connect(self._draw_map)
        self.widget.checkBox_MapLog.stateChanged.connect(self._on_map_log_changed)
        self.widget.doubleSpinBox_MapPctLow.valueChanged.connect(
            self._set_map_hist_view_percentages)
        self.widget.doubleSpinBox_MapPctHigh.valueChanged.connect(
            self._set_map_hist_view_percentages)

        self.widget.pushButton_MapScaleAuto.clicked.connect(self._auto_scale)
        self.widget.pushButton_MapScalePercentile.clicked.connect(self._scale_percentile)
        self.widget.pushButton_MapScaleReset.clicked.connect(self._scale_reset)
        if hasattr(self.widget, "map_hist_widget"):
            self.widget.map_hist_widget.boundChanged.connect(
                self._set_map_bound_from_hist)
            self.widget.map_hist_widget.rangeChanged.connect(
                self._set_map_range_from_hist)

        if hasattr(self.widget, "pushButton_MapExportImage"):
            self.widget.pushButton_MapExportImage.clicked.connect(self._export_image)
        if hasattr(self.widget, "pushButton_MapExportNpy"):
            self.widget.pushButton_MapExportNpy.clicked.connect(self._export_current_view)

    def _export_current_view(self):
        if self._map_fig is None:
            self._set_status("No map view to export.")
            return
        if self.export_current_view_cb is None:
            self._set_status("Export view is not available.")
            return
        self.export_current_view_cb(
            fig=self._map_fig,
            folder_prefix="map-pkpo-export",
        )

    def _on_main_tab_changed(self, _idx):
        if not hasattr(self.widget, "tab_Map"):
            return
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Map:
            self.deactivate_interactions()
            self._clear_roi_overlays()
        else:
            self.refresh_current_marker()
            self.refresh_roi_overlays()

    def deactivate_interactions(self):
        self._disable_roi_selectors()
        if hasattr(self.widget, "pushButton_MapSetRoi"):
            self.widget.pushButton_MapSetRoi.setChecked(False)
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
        button = getattr(self.widget, "pushButton_MapSetRoi", None)
        if button is None:
            return
        button.setChecked(bool(active))
        if active:
            button.setText("ROI ON")
            button.setStyleSheet(
                "QPushButton { background-color: #d6a800; color: #1f1f1f; "
                "border: 1px solid #b8860b; }")
            button.setToolTip("ROI selection is active. Click again to cancel.")
        else:
            button.setText("Set ROI")
            button.setStyleSheet(
                "QPushButton { background-color: #444444; color: #f0f0f0; "
                "border: 1px solid #d6a800; }"
                "QPushButton:hover { background-color: #505050; }"
                "QPushButton:pressed { background-color: #383838; }")
            button.setToolTip("Click to draw an ROI on the 1D or Cake plot.")

    def _set_status(self, msg):
        text = str(msg or "")
        if hasattr(self.widget, "lineEdit_MapStatus"):
            self.widget.lineEdit_MapStatus.setText(text)
            self.widget.lineEdit_MapStatus.setToolTip(text)

    def _open_progress(self, title, label, maximum):
        dlg = QtWidgets.QProgressDialog(label, "", 0, max(1, int(maximum)), self.widget)
        dlg.setWindowTitle(title)
        dlg.setCancelButton(None)
        dlg.setWindowModality(QtCore.Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)
        dlg.show()
        QtWidgets.QApplication.processEvents()
        self._progress_dialog = dlg
        return dlg

    def _update_progress(self, value, label=None, maximum=None):
        dlg = self._progress_dialog
        if dlg is None:
            return
        if maximum is not None:
            dlg.setMaximum(max(1, int(maximum)))
        if label is not None:
            dlg.setLabelText(str(label))
        dlg.setValue(min(max(0, int(value)), dlg.maximum()))
        QtWidgets.QApplication.processEvents()

    def _close_progress(self):
        dlg = self._progress_dialog
        self._progress_dialog = None
        if dlg is None:
            return
        dlg.setValue(dlg.maximum())
        dlg.close()
        dlg.deleteLater()
        QtWidgets.QApplication.processEvents()

    def _default_hover_text(self):
        if not self._chi_files:
            return "Load CHI files to start."
        return "Hover over a map pixel to see its file name"

    def _set_hover_file_text(self, text):
        if hasattr(self.widget, "lineEdit_MapHoverFile"):
            self.widget.lineEdit_MapHoverFile.setText(str(text))

    def _clear_hover_file(self, _event=None):
        if hasattr(self.widget, "lineEdit_MapHoverFile"):
            self.widget.lineEdit_MapHoverFile.setPlaceholderText(
                self._default_hover_text()
            )
        self._set_hover_file_text("")

    def _set_loaded_count(self):
        if hasattr(self.widget, "label_MapLoaded"):
            self.widget.label_MapLoaded.setText(f"Loaded: {len(self._chi_files)}")

    def _load_chi_files(self):
        files, _ = dialog_openfiles_hide_param_dirs(
            self.widget,
            "Select CHI files for map",
            self.model.chi_path,
            "CHI files (*.chi)",
            default_hide_param_dirs=True,
        )
        if not files:
            return

        self._chi_input_files = list(files)
        self._roi_1d = None
        self._roi_2d = None
        self._open_progress("Map Loading", "Preparing selected CHI files...", 4)
        try:
            self._refresh_loaded_files(reset_grid=True, progress=True)
            nx, ny = self._grid
            order_text = "input order" if self._ignore_file_numbers() else "filename order"
            coord_source = "metadata" if self._has_complete_coordinate_assignment() else "guessed"
            self._set_status(
                f"Loaded {len(self._chi_files)} CHI files using {order_text}. "
                f"Grid ({coord_source}): {nx} x {ny}"
            )
            self._update_progress(3, "Selecting full-pattern ROI...")
            self._set_default_1d_full_range_roi()
        finally:
            self._close_progress()
        if self._roi_1d is not None:
            self._compute_map()
        else:
            self._draw_map()

    def _guess_grid_dims(self, n_files):
        if n_files <= 0:
            return 1, 1
        best = (n_files, 1)
        best_score = abs(n_files - 1)
        root = int(math.sqrt(n_files))
        for a in range(1, root + 1):
            if (n_files % a) != 0:
                continue
            b = n_files // a
            score = abs(b - a)
            if score < best_score:
                best = (b, a)
                best_score = score
        return int(best[0]), int(best[1])

    def _filename_sort_key(self, filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        name_lower = name.lower()
        map_match = re.search(r"map_(\d+)", name_lower)
        if map_match:
            return (
                0,
                name_lower[:map_match.start()],
                int(map_match.group(1)),
                name_lower[map_match.end():],
            )
        tail_match = re.search(r"(\d+)$", name_lower)
        if tail_match:
            return (1, name_lower[:tail_match.start()], int(tail_match.group(1)))
        return (2, name_lower)

    def _ignore_file_numbers(self):
        return self._ignore_metadata()

    def _ignore_metadata(self):
        # Automatically decide: use metadata positions if available, otherwise use input file order
        return not self._has_complete_coordinate_assignment()

    def _h5_candidates_for_chi(self, chi_path):
        folder = os.path.dirname(chi_path)
        stem = os.path.splitext(os.path.basename(chi_path))[0]
        candidates = [
            os.path.join(folder, stem + ".h5"),
            os.path.join(folder, stem + ".hdf5"),
        ]
        return [c for c in candidates if os.path.exists(c)]

    def _has_complete_coordinate_assignment(self):
        if len(self._map_points) != len(self._chi_files):
            return False
        if not self._map_points:
            return False
        if not all(p.x_pos is not None and p.y_pos is not None for p in self._map_points):
            return False
        test_values = np.arange(len(self._map_points), dtype=float)
        nx, ny = self._grid
        return build_coordinate_grid(
            test_values,
            [p.x_pos for p in self._map_points],
            [p.y_pos for p in self._map_points],
            target_shape=(ny, nx),
        ) is not None

    def _detect_scan_coordinates(self, progress=False):
        points = []
        total = len(self._chi_files)
        metadata_cache = {}
        # Always try to extract metadata coordinates during initial detection.
        # The _ignore_metadata() check cannot be used here because
        # _has_complete_coordinate_assignment() depends on _map_points being
        # populated, which only happens AFTER this loop completes.
        # Metadata is never skipped — the automatic decision via _ignore_metadata()
        # happens later after _map_points is populated.
        for i, chi_path in enumerate(self._chi_files):
            if progress:
                self._update_progress(
                    2,
                    f"Checking metadata: {os.path.basename(chi_path)}",
                )
            x_pos = None
            y_pos = None
            param_dir = get_temp_dir(chi_path)
            if param_dir not in metadata_cache:
                metadata_cache[param_dir] = DioptasMetadataCollection.from_param_dir(param_dir)
            metadata = metadata_cache[param_dir]
            coords = metadata.get_coordinates(filename=chi_path, frame_index=None)
            if coords is not None:
                x_pos, y_pos = coords
            else:
                for h5_path in self._h5_candidates_for_chi(chi_path):
                    coords = extract_scan_coordinates(h5_path, frame_index=None)
                    if coords is not None:
                        x_pos, y_pos = coords
                        break
            points.append(MapPointInfo(
                filepath=chi_path,
                filename=os.path.basename(chi_path),
                frame_index=None,
                x_pos=x_pos,
                y_pos=y_pos,
            ))
            if progress and total > 0:
                QtWidgets.QApplication.processEvents()
        self._map_points = points
        valid_coords = self._has_complete_coordinate_assignment()
        return valid_coords

    def _derive_grid_dims_from_coordinates(self):
        """Derive grid dimensions (Nx, Ny) from metadata coordinates if available.

        Returns:
            tuple or None: (nx, ny) if coordinates are complete and valid, None otherwise.
        """
        if not self._map_points:
            return None
        if not self._has_complete_coordinate_assignment():
            return None
        x_positions = [p.x_pos for p in self._map_points]
        y_positions = [p.y_pos for p in self._map_points]
        values = np.arange(len(self._map_points), dtype=float)
        result = build_coordinate_grid(values, x_positions, y_positions)
        if result is None:
            return None
        grid, unique_x, unique_y, __ = result
        nx = len(unique_x)
        ny = len(unique_y)
        return nx, ny

    def _ordered_chi_files(self, files):
        ordered = list(files)
        if self._ignore_file_numbers():
            return ordered
        return sorted(ordered, key=self._filename_sort_key)

    def _refresh_loaded_files(self, reset_grid=False, preferred_chi=None, progress=False):
        if progress:
            self._update_progress(1, "Sorting files and building map grid...")
        self._chi_files = self._ordered_chi_files(self._chi_input_files)
        self._pos_idx = self._derive_position_indices(self._chi_files)
        self._rebuild_linear_lookup()
        self._chi_cache = {}
        self._cake_cache = {}
        self._map_data = None
        self._map_coordinate_mode = False
        self._coord_x = []
        self._coord_y = []
        self._coord_to_file = {}
        self._clear_hover_file()

        if reset_grid:
            # First detect coordinates from metadata before guessing grid dimensions
            self._detect_scan_coordinates(progress=False)
            grid_from_metadata = self._derive_grid_dims_from_coordinates()
            if grid_from_metadata is not None:
                nx, ny = grid_from_metadata
            else:
                nx, ny = self._guess_grid_dims(len(self._chi_files))
            self._sync_ui_from_roi = True
            self.widget.spinBox_MapNx.setValue(nx)
            self.widget.spinBox_MapNy.setValue(ny)
            self._sync_ui_from_roi = False
            self._grid = (nx, ny)
        else:
            self._grid = (
                int(self.widget.spinBox_MapNx.value()),
                int(self.widget.spinBox_MapNy.value()),
            )

        self._set_loaded_count()
        if progress:
            self._update_progress(2, "Previewing map center file...")
        if preferred_chi and (preferred_chi in self._chi_files):
            self._load_file_to_main_plot(self._chi_files.index(preferred_chi))
        else:
            self._preview_center_file()
        # Only run full coordinate detection with progress if not already done above
        if not reset_grid:
            self._detect_scan_coordinates(progress=progress)

    def _on_file_order_mode_changed(self):
        if not self._chi_input_files:
            return
        preferred_chi = self._current_displayed_chi()
        self._refresh_loaded_files(reset_grid=False, preferred_chi=preferred_chi)
        if (self._roi_1d is not None) or (self._roi_2d is not None):
            self._compute_map()
        else:
            self._draw_map()

    def _on_metadata_mode_changed(self):
        if not self._chi_files:
            return
        preferred_chi = self._current_displayed_chi()
        self._refresh_loaded_files(
            reset_grid=False,
            preferred_chi=preferred_chi,
            progress=False,
        )
        if (self._roi_1d is not None) or (self._roi_2d is not None):
            self._compute_map()
        else:
            self._draw_map()

    def _derive_position_indices(self, files):
        if self._ignore_file_numbers():
            return list(range(len(files)))
        nums = []
        ok = True
        for f in files:
            b = os.path.basename(f).lower()
            m = re.search(r"map_(\d+)", b)
            if m is None:
                ok = False
                break
            nums.append(int(m.group(1)))
        if not ok:
            return list(range(len(files)))
        min_num = min(nums)
        return [n - min_num for n in nums]

    def _rebuild_linear_lookup(self):
        self._lin_to_file = {}
        for i, lin in enumerate(self._pos_idx):
            if lin not in self._lin_to_file:
                self._lin_to_file[lin] = i

    def _on_grid_changed(self):
        if self._sync_ui_from_roi:
            return
        nx = int(self.widget.spinBox_MapNx.value())
        ny = int(self.widget.spinBox_MapNy.value())
        self._grid = (nx, ny)
        n = len(self._chi_files)
        coordinate_ready = (
            (not self._ignore_metadata()) and
            self._has_complete_coordinate_assignment()
        )
        if n > 0 and (not coordinate_ready) and (nx * ny != n):
            self._set_status(
                f"Grid mismatch: Nx*Ny ({nx}x{ny}={nx * ny}) must equal loaded files ({n})."
            )
            self._map_data = None
            self._draw_map()
            return
        self._preview_center_file()
        if (self._roi_1d is not None) or (self._roi_2d is not None):
            self._compute_map()
        else:
            self._map_data = None
            self._draw_map()

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
            self.widget.lineEdit_MapRoiSummary.setText(f"1D: 2theta [{xmin:.3f}, {xmax:.3f}]")
        except Exception:
            pass

    def _preview_center_file(self):
        if not self._chi_files:
            return
        nx, ny = self._grid
        n = len(self._chi_files)
        if nx * ny != n:
            self._set_status(
                f"Grid mismatch: Nx*Ny ({nx}x{ny}={nx * ny}) must equal loaded files ({n})."
            )
            return
        cx = nx // 2
        cy = ny // 2
        idx = self._grid_to_linear(cx, cy)
        if idx is None:
            return
        file_idx = self._lin_to_file.get(idx, None)
        if file_idx is None:
            return
        self._load_file_to_main_plot(file_idx)

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
        # Some redraw paths are deferred; refresh twice to survive delayed clears.
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

    def _grid_to_linear(self, x, y):
        nx, ny = self._grid
        if (x < 0) or (y < 0) or (x >= nx) or (y >= ny):
            return None
        order = self.widget.comboBox_MapOrder.currentText()
        if order == "Snake":
            if (y % 2) == 0:
                i = y * nx + x
            else:
                i = y * nx + (nx - 1 - x)
        else:
            i = y * nx + x
        return int(i)

    def _linear_to_grid(self, idx):
        nx, _ny = self._grid
        order = self.widget.comboBox_MapOrder.currentText()
        y = idx // nx
        x = idx % nx
        if order == "Snake" and ((y % 2) == 1):
            x = nx - 1 - x
        return int(x), int(y)

    def _file_idx_from_map_coords(self, xdata, ydata):
        if self._map_data is None:
            return None
        if (xdata is None) or (ydata is None):
            return None
        x = int(round(xdata))
        y = int(round(ydata))
        if self._map_coordinate_mode:
            return self._coord_to_file.get((x, y), None)
        lin = self._grid_to_linear(x, y)
        if lin is None:
            return None
        return self._lin_to_file.get(lin, None)

    def _hover_filename_for_event(self, event):
        if event.inaxes != self._map_ax:
            return ""
        file_idx = self._file_idx_from_map_coords(event.xdata, event.ydata)
        if file_idx is None:
            if self._map_coordinate_mode and event.inaxes == self._map_ax:
                return "No diffraction pattern available"
            return ""
        if (file_idx < 0) or (file_idx >= len(self._chi_files)):
            return ""
        base = os.path.basename(self._chi_files[file_idx])
        x = int(round(event.xdata))
        y = int(round(event.ydata))
        if self._map_coordinate_mode:
            if 0 <= x < len(self._coord_x) and 0 <= y < len(self._coord_y):
                return (
                    f"{base} | Horizontal={self._coord_x[x]:.6g}, "
                    f"Vertical={self._coord_y[y]:.6g}"
                )
        else:
            # No metadata coordinates: show generic pixel position (column, row)
            # with origin (0, 0) at top-left
            return f"{base} | Pixel=({x}, {y})"
        return base

    def _arm_roi_selection(self):
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Map:
            self._set_status("Open Map tab first.")
            self._update_roi_button_state(False)
            return
        if self.is_roi_selection_active():
            self.deactivate_interactions()
            self._set_status("ROI selection canceled.")
            return
        self._disable_roi_selectors()
        self._roi_1d = None
        self._roi_2d = None
        self._map_data = None
        self.widget.lineEdit_MapRoiSummary.setText("")
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
        self._map_data = None
        self.widget.lineEdit_MapRoiSummary.setText("")
        self._draw_map()
        self._set_status("ROI cleared.")

    def clear_roi_if_event_in_roi(self, event):
        if not self._is_map_tab_active():
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
        self.widget.lineEdit_MapRoiSummary.setText(f"1D: 2theta [{xmin:.3f}, {xmax:.3f}]")
        self._set_status("1D ROI selected.")
        self.deactivate_interactions()
        self.refresh_roi_overlays()
        self._compute_map()
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
        self.widget.lineEdit_MapRoiSummary.setText(
            f"2D: 2theta [{xmin:.3f}, {xmax:.3f}], azi [{ymin:.3f}, {ymax:.3f}]"
        )
        self._set_status("2D ROI selected.")
        self.deactivate_interactions()
        self.refresh_roi_overlays()
        self._compute_map()
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

    def _refresh_temp_bgsub_if_requested(self, progress_offset=0, progress_span=None):
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

        def on_bg_progress(i, total, chi_path):
            if progress_span is None:
                return
            value = progress_offset + min(int(i), int(total))
            label = "Refreshing temporary background files..."
            if chi_path:
                label = f"Refreshing background: {os.path.basename(chi_path)}"
            self._update_progress(value, label)

        result = refresh_temp_bgsub_for_chi_files(
            self._chi_files,
            preferred_chi=self._preferred_bg_reference_chi(),
            bg_roi=bg_roi,
            bg_params=bg_params,
            progress_callback=on_bg_progress,
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

    def _compute_map(self):
        if not self._chi_files:
            self._set_status("Load CHI files first.")
            return
        nx, ny = self._grid
        n = len(self._chi_files)
        coordinate_requested = not self._ignore_metadata()
        coordinate_ready = (
            coordinate_requested and
            self._has_complete_coordinate_assignment()
        )
        if (not coordinate_ready) and nx * ny != n:
            self._set_status(
                f"Grid mismatch: Nx*Ny ({nx}x{ny}={nx * ny}) must equal loaded files ({n})."
            )
            return
        if (self._roi_1d is None) and (self._roi_2d is None):
            self._set_status("Select ROI first.")
            return

        use_bgsub = bool(
            getattr(self.widget, "checkBox_BgSub", None) and
            self.widget.checkBox_BgSub.isChecked() and
            self._roi_1d is not None
        )
        progress_max = n + (n if use_bgsub else 0) + 2
        self._open_progress("Map Processing", "Preparing map computation...", progress_max)

        try:
            self._refresh_temp_bgsub_if_requested(
                progress_offset=0,
                progress_span=n if use_bgsub else None,
            )
            compute_offset = n if use_bgsub else 0

            values = np.full(n, np.nan, dtype=float)
            failures = []
            for i, chi_path in enumerate(self._chi_files):
                self._update_progress(
                    compute_offset + i,
                    f"Integrating ROI: {os.path.basename(chi_path)}",
                )
                try:
                    if self._roi_1d is not None:
                        x, y = self._load_bgsub_xy_if_requested(chi_path)
                        xmin, xmax = self._roi_1d
                        m = (x >= xmin) & (x <= xmax)
                        if not np.any(m):
                            values[i] = np.nan
                        else:
                            # Requested behavior: add all intensities in ROI range.
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

            self._update_progress(compute_offset + n, "Building map grid...")
            self._map_coordinate_mode = False
            self._coord_x = []
            self._coord_y = []
            self._coord_to_file = {}
            coord_grid = None
            if coordinate_ready:
                coord_grid = build_coordinate_grid(
                    values,
                    [p.x_pos for p in self._map_points],
                    [p.y_pos for p in self._map_points],
                    target_shape=(ny, nx),
                )
            if coord_grid is not None:
                grid, x_vals, y_vals, coord_to_index = coord_grid
                self._map_data = grid
                self._coord_x = x_vals
                self._coord_y = y_vals
                x_to_col = {float(x): i for i, x in enumerate(x_vals)}
                y_to_row = {float(y): i for i, y in enumerate(y_vals)}
                self._coord_to_file = {
                    (x_to_col[float(key[0])], y_to_row[float(key[1])]): idx
                    for key, idx in coord_to_index.items()
                }
                self._map_coordinate_mode = True
            else:
                grid = np.full((ny, nx), np.nan, dtype=float)
                for i, val in enumerate(values):
                    if self._ignore_metadata():
                        x = i % nx
                        y = i // nx
                    else:
                        lin_pos = self._pos_idx[i] if i < len(self._pos_idx) else i
                        x, y = self._linear_to_grid(lin_pos)
                    if (y < ny) and (x < nx):
                        grid[y, x] = val
                self._map_data = grid

            self._update_progress(compute_offset + n + 1, "Drawing map...")

            # Recomputing map should always refresh Min/Max from new data.
            self._scale_reset()
            self._draw_map()
        finally:
            self._close_progress()

        if failures:
            first_path, first_err = failures[0]
            first_name = os.path.basename(first_path)
            self._set_status(
                f"Map computed with {len(failures)} failures. "
                f"First: {first_name} ({first_err})")
        else:
            if self._roi_1d is not None:
                if bool(getattr(self.widget, "checkBox_BgSub", None) and
                        self.widget.checkBox_BgSub.isChecked()):
                    self._set_status("Map computed from 1D bg-subtracted intensity in ROI.")
                else:
                    self._set_status("Map computed from raw 1D intensity (no bg subtraction).")
            else:
                self._set_status("Map computed from raw 2D cake intensity (no bg subtraction).")
        self._schedule_overlay_refresh()

    def _effective_cmap(self):
        return str(self.widget.comboBox_MapCmap.currentText())

    def _map_cmap_for_plot(self):
        cmap = colormaps[self._effective_cmap()].copy()
        cmap.set_bad((0.0, 0.0, 0.0, 0.0))
        return cmap

    def _current_vrange(self, data):
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            return None
        return float(np.nanmin(finite)), float(np.nanmax(finite))

    def _display_map_data(self):
        if self._map_data is None:
            return None
        data = np.array(self._map_data, copy=True, dtype=float)
        if not self.widget.checkBox_MapLog.isChecked():
            return data
        finite = data[np.isfinite(data)]
        if finite.size == 0 or np.nanmax(finite) <= 0:
            self._set_status("Log scale disabled: map has no positive values.")
            self.widget.checkBox_MapLog.setChecked(False)
            return data
        data[data <= 0] = np.nan
        return np.log10(data)

    def _scale_reset(self):
        if self._map_data is None:
            return
        data = self._display_map_data()
        if data is None:
            return
        vr = self._current_vrange(data)
        if vr is None:
            return
        self.widget.doubleSpinBox_MapVmin.setValue(vr[0])
        self.widget.doubleSpinBox_MapVmax.setValue(vr[1])

    def _on_map_log_changed(self):
        self._scale_reset()
        self._draw_map()

    def _auto_scale(self):
        self._scale_reset()
        self._draw_map()

    def _scale_percentile(self):
        if self._map_data is None:
            return
        finite = self._map_data[np.isfinite(self._map_data)]
        if finite.size == 0:
            return
        p_low = float(self.widget.doubleSpinBox_MapPctLow.value())
        p_high = float(self.widget.doubleSpinBox_MapPctHigh.value())
        if p_high <= p_low:
            self._set_status("Percentile high must be larger than low.")
            return
        vmin = float(np.nanpercentile(finite, p_low))
        vmax = float(np.nanpercentile(finite, p_high))
        self.widget.doubleSpinBox_MapVmin.setValue(vmin)
        self.widget.doubleSpinBox_MapVmax.setValue(vmax)
        self._draw_map()

    def _set_map_bound_from_hist(self, bound_type, intensity_value):
        value = float(intensity_value)
        current_min = float(self.widget.doubleSpinBox_MapVmin.value())
        current_max = float(self.widget.doubleSpinBox_MapVmax.value())
        min_gap = max(1e-12, abs(current_max - current_min) * 1e-9)
        if bound_type == "min":
            if value >= current_max:
                value = current_max - min_gap
            self.widget.doubleSpinBox_MapVmin.setValue(value)
        elif bound_type == "max":
            if value <= current_min:
                value = current_min + min_gap
            self.widget.doubleSpinBox_MapVmax.setValue(value)

    def _set_map_range_from_hist(self, vmin, vmax):
        vmin = float(vmin)
        vmax = float(vmax)
        if vmax < vmin:
            vmin, vmax = vmax, vmin
        blocker_min = QtCore.QSignalBlocker(self.widget.doubleSpinBox_MapVmin)
        blocker_max = QtCore.QSignalBlocker(self.widget.doubleSpinBox_MapVmax)
        try:
            self.widget.doubleSpinBox_MapVmin.setValue(vmin)
            self.widget.doubleSpinBox_MapVmax.setValue(vmax)
        finally:
            del blocker_max
            del blocker_min
        self._draw_map()

    def _set_map_hist_view_percentages(self):
        if not hasattr(self.widget, "map_hist_widget"):
            return
        self.widget.map_hist_widget.set_view_percentages(
            self.widget.doubleSpinBox_MapPctLow.value(),
            self.widget.doubleSpinBox_MapPctHigh.value(),
        )

    def _draw_map(self):
        # Recreate axes each draw so colorbar layout adjustments do not accumulate.
        self._recreate_map_axes()
        self._clear_hover_file()
        if self._map_ax is None:
            return
        self._map_ax.clear()
        self._map_fig.patch.set_facecolor("black")
        self._map_ax.set_facecolor("black")
        self._map_cbar = None
        if self._map_data is None:
            self._map_ax.set_axis_off()
            if hasattr(self.widget, "map_hist_widget"):
                self.widget.map_hist_widget.clear()
            self._map_canvas.draw_idle()
            return

        data = self._display_map_data()
        if data is None:
            return
        vmin = float(self.widget.doubleSpinBox_MapVmin.value())
        vmax = float(self.widget.doubleSpinBox_MapVmax.value())

        norm = None
        if vmax <= vmin:
            vr = self._current_vrange(data)
            if vr is not None:
                vmin, vmax = vr

        im_kwargs = {
            "origin": "upper",
            "cmap": self._map_cmap_for_plot(),
            "extent": [-0.5, data.shape[1] - 0.5, data.shape[0] - 0.5, -0.5],
            "interpolation": "nearest",
        }
        if norm is None:
            im_kwargs["vmin"] = vmin
            im_kwargs["vmax"] = vmax
        else:
            im_kwargs["norm"] = norm
        self._map_im = self._map_ax.imshow(data, **im_kwargs)
        self._map_cbar = self._map_fig.colorbar(
            self._map_im, ax=self._map_ax, pad=0.0075, fraction=0.046
        )
        self._map_cbar.set_label("")
        self._map_cbar.set_ticks([])
        self._map_cbar.ax.tick_params(
            left=False, right=False, labelleft=False, labelright=False,
            bottom=False, top=False, labelbottom=False, labeltop=False
        )
        if hasattr(self.widget, "map_hist_widget"):
            self.widget.map_hist_widget.set_view_percentages(
                self.widget.doubleSpinBox_MapPctLow.value(),
                self.widget.doubleSpinBox_MapPctHigh.value(),
            )
            self.widget.map_hist_widget.set_data(data, vmin=vmin, vmax=vmax)

        self._map_ax.set_aspect("equal", adjustable="box")
        self._map_ax.set_anchor("C")
        self._map_ax.set_xlim(-0.5, data.shape[1] - 0.5)
        self._map_ax.set_ylim(data.shape[0] - 0.5, -0.5)
        self._map_ax.set_axis_off()
        self._add_current_marker(draw=False)
        self._map_canvas.draw_idle()

    def _current_pixel_xy(self):
        file_idx = self._current_file_idx()
        if file_idx is None:
            return None

        if self._map_coordinate_mode:
            for (x, y), idx in self._coord_to_file.items():
                if idx == file_idx:
                    return int(x), int(y)
            return None

        lin_pos = self._pos_idx[file_idx] if file_idx < len(self._pos_idx) else file_idx
        xy = self._linear_to_grid(lin_pos)
        if xy is None:
            return None
        return int(xy[0]), int(xy[1])

    def _clear_current_marker(self):
        if self._map_current_pixel_artist is None:
            return False
        try:
            self._map_current_pixel_artist.remove()
        except Exception:
            pass
        self._map_current_pixel_artist = None
        return True

    def _add_current_marker(self, draw=True):
        self._clear_current_marker()
        if self._map_ax is None or self._map_data is None:
            return
        xy = self._current_pixel_xy()
        if xy is None:
            return
        x, y = xy
        rows, cols = self._map_data.shape
        if (x < 0) or (y < 0) or (x >= cols) or (y >= rows):
            return
        self._map_current_pixel_artist = mpatches.Rectangle(
            (x - 0.5, y - 0.5),
            1.0,
            1.0,
            fill=False,
            edgecolor="#ff3030",
            linewidth=2.0,
            zorder=10,
            clip_on=False,
        )
        self._map_ax.add_patch(self._map_current_pixel_artist)
        if draw and self._map_canvas is not None:
            self._map_canvas.draw_idle()

    def refresh_current_marker(self):
        if self._map_ax is None:
            return
        changed = self._clear_current_marker()
        self._add_current_marker(draw=False)
        if (changed or self._map_current_pixel_artist is not None) and \
                self._map_canvas is not None:
            self._map_canvas.draw_idle()

    def _on_map_click(self, event):
        file_idx = self._file_idx_from_map_coords(event.xdata, event.ydata)
        if file_idx is None:
            if self._map_coordinate_mode and event.inaxes == self._map_ax:
                self._set_status("No diffraction pattern available.")
                return
            if event.inaxes == self._map_ax:
                x = "NA" if event.xdata is None else int(round(event.xdata))
                y = "NA" if event.ydata is None else int(round(event.ydata))
                self._set_status(f"No file for map pixel ({x}, {y})")
            return
        x = int(round(event.xdata))
        y = int(round(event.ydata))
        self._load_file_to_main_plot(file_idx)
        self._set_status(f"Selected map pixel ({x}, {y})")

    def _on_map_hover(self, event):
        self._set_hover_file_text(self._hover_filename_for_event(event))

    def _is_map_tab_active(self):
        return hasattr(self.widget, "tab_Map") and \
            (self.widget.tabWidget.currentWidget() == self.widget.tab_Map)

    def _should_show_roi_overlay(self):
        if self._map_data is None:
            return False
        if not self._is_map_tab_active():
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
            # Keep map functionality robust even if overlay draw fails.
            self._roi_artist_1d = None
            self._roi_artist_2d = None

    def _export_image(self):
        if self._map_data is None:
            self._set_status("No map data to export.")
            return
        base = os.path.join(self.model.chi_path, "map.png")
        filen, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.widget,
            "Export map image",
            base,
            "Image files (*.png *.pdf)",
        )
        if not filen:
            return
        self._map_fig.savefig(filen, dpi=300, bbox_inches="tight")
        self._set_status("Image exported.")

    def _export_npy(self):
        if self._map_data is None:
            self._set_status("No map data to export.")
            return
        root = self.model.chi_path if str(getattr(self.model, "chi_path", "")).strip() else os.getcwd()
        out_dir = os.path.join(root, "map_py")
        os.makedirs(out_dir, exist_ok=True)

        npy_path = os.path.join(out_dir, "map.npy")
        py_path = os.path.join(out_dir, "plot_map.py")

        np.save(npy_path, self._map_data)

        script = (
            "import numpy as np\n"
            "import matplotlib.pyplot as plt\n\n"
            "def main():\n"
            "    data = np.load('map.npy')\n"
            "    fig, ax = plt.subplots(figsize=(7, 5), facecolor='white')\n"
            "    ax.set_facecolor('white')\n"
            "    im = ax.imshow(data, origin='lower', cmap='viridis', interpolation='nearest', aspect='equal')\n"
            "    cbar = fig.colorbar(im, ax=ax)\n"
            "    cbar.set_label('Integrated intensity')\n"
            "    ax.set_title('Map')\n"
            "    ax.set_xticks([])\n"
            "    ax.set_yticks([])\n"
            "    ax.set_xlabel('')\n"
            "    ax.set_ylabel('')\n"
            "    fig.tight_layout()\n"
            "    plt.show()\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        with open(py_path, "w", encoding="utf-8") as fh:
            fh.write(script)

        self._set_status("Exported map_py (map.npy + plot_map.py).")
