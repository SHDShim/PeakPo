import os
import glob
import math
import re
import numpy as np
from qtpy import QtWidgets, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.widgets import RectangleSelector
from matplotlib import colors as mcolors
from matplotlib.gridspec import GridSpec
import matplotlib.patches as mpatches

from ..utils import get_temp_dir, readchi


class MapController(object):
    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.base_ptn_ctrl = None
        self.plot_ctrl = None

        self._map_canvas = None
        self._map_toolbar = None
        self._map_ax = None
        self._map_cax = None
        self._map_cbar = None
        self._map_im = None

        self._selector_1d = None
        self._selector_2d = None
        self._roi_artist_1d = None
        self._roi_artist_2d = None

        self._chi_files = []
        self._pos_idx = []
        self._lin_to_file = {}
        self._chi_cache = {}
        self._cake_cache = {}
        self._grid = (1, 1)
        self._roi_1d = None
        self._roi_2d = None
        self._map_data = None

        self._sync_ui_from_roi = False

        self._build_canvas()
        self._connect_channel()

    def set_helpers(self, base_ptn_ctrl=None, plot_ctrl=None):
        self.base_ptn_ctrl = base_ptn_ctrl
        self.plot_ctrl = plot_ctrl

    def _build_canvas(self):
        if not hasattr(self.widget, "verticalLayout_MapCanvas"):
            return
        self._map_fig = Figure()
        self._map_fig.subplots_adjust(left=0.08, right=0.92, top=0.93, bottom=0.1, wspace=0.04)
        self._recreate_map_axes()
        self._map_canvas = FigureCanvasQTAgg(self._map_fig)
        self._map_toolbar = NavigationToolbar2QT(self._map_canvas, self.widget.groupBox_MapCanvas)
        self.widget.verticalLayout_MapCanvas.addWidget(self._map_toolbar)
        self.widget.verticalLayout_MapCanvas.addWidget(self._map_canvas, 1)
        self._map_canvas.mpl_connect("button_press_event", self._on_map_click)

    def _recreate_map_axes(self):
        if getattr(self, "_map_fig", None) is None:
            return
        self._map_fig.clf()
        gs = GridSpec(1, 2, width_ratios=[20, 1], figure=self._map_fig)
        self._map_ax = self._map_fig.add_subplot(gs[0, 0])
        self._map_cax = self._map_fig.add_subplot(gs[0, 1])
        self._map_cbar = None

    def _ensure_map_axes(self):
        if (self._map_ax is None) or (self._map_cax is None):
            self._recreate_map_axes()
            return
        # Axes can become detached after colorbar removal in some mpl states.
        ax_fig = getattr(self._map_ax, "figure", None)
        cax_fig = getattr(self._map_cax, "figure", None)
        if (ax_fig is None) or (cax_fig is None) or (ax_fig is not self._map_fig) or (cax_fig is not self._map_fig):
            self._recreate_map_axes()

    def _connect_channel(self):
        if not hasattr(self.widget, "tabWidget"):
            return
        self.widget.tabWidget.currentChanged.connect(self._on_main_tab_changed)

        self.widget.pushButton_MapLoadChi.clicked.connect(self._load_chi_files)
        self.widget.spinBox_MapNx.valueChanged.connect(self._on_grid_changed)
        self.widget.spinBox_MapNy.valueChanged.connect(self._on_grid_changed)
        self.widget.comboBox_MapOrder.currentIndexChanged.connect(self._on_grid_changed)

        self.widget.pushButton_MapSetRoi1D.clicked.connect(self._arm_roi_1d)
        self.widget.pushButton_MapSetRoi2D.clicked.connect(self._arm_roi_2d)
        self.widget.pushButton_MapClearRoi.clicked.connect(self._clear_roi)
        self.widget.pushButton_MapCompute.clicked.connect(self._compute_map)

        self.widget.comboBox_MapCmap.currentIndexChanged.connect(self._draw_map)
        self.widget.checkBox_MapReverseCmap.stateChanged.connect(self._draw_map)
        self.widget.doubleSpinBox_MapVmin.valueChanged.connect(self._draw_map)
        self.widget.doubleSpinBox_MapVmax.valueChanged.connect(self._draw_map)
        self.widget.checkBox_MapLog.stateChanged.connect(self._draw_map)

        self.widget.pushButton_MapScaleAuto.clicked.connect(self._auto_scale)
        self.widget.pushButton_MapScalePercentile.clicked.connect(self._scale_percentile)
        self.widget.pushButton_MapScaleReset.clicked.connect(self._scale_reset)

        self.widget.pushButton_MapExportImage.clicked.connect(self._export_image)
        self.widget.pushButton_MapExportNpy.clicked.connect(self._export_npy)

    def _on_main_tab_changed(self, _idx):
        if not hasattr(self.widget, "tab_Map"):
            return
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Map:
            self.deactivate_interactions()
            self._clear_roi_overlays()
        else:
            self.refresh_roi_overlays()

    def deactivate_interactions(self):
        self._disable_roi_selectors()
        if hasattr(self.widget, "pushButton_MapSetRoi1D"):
            self.widget.pushButton_MapSetRoi1D.setChecked(False)
        if hasattr(self.widget, "pushButton_MapSetRoi2D"):
            self.widget.pushButton_MapSetRoi2D.setChecked(False)

    def is_roi_selection_active(self):
        sel_1d_active = (self._selector_1d is not None) and \
            bool(getattr(self._selector_1d, "active", False))
        sel_2d_active = (self._selector_2d is not None) and \
            bool(getattr(self._selector_2d, "active", False))
        return bool(sel_1d_active or sel_2d_active)

    def _set_status(self, msg):
        if hasattr(self.widget, "label_MapStatus"):
            self.widget.label_MapStatus.setText(str(msg))

    def _set_loaded_count(self):
        if hasattr(self.widget, "label_MapLoaded"):
            self.widget.label_MapLoaded.setText(f"Loaded: {len(self._chi_files)}")

    def _load_chi_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self.widget,
            "Select CHI files for map",
            self.model.chi_path,
            "CHI files (*.chi)",
        )
        if not files:
            return

        self._chi_files = sorted(list(files), key=self._filename_sort_key)
        self._pos_idx = self._derive_position_indices(self._chi_files)
        self._rebuild_linear_lookup()
        self._chi_cache = {}
        self._cake_cache = {}
        self._roi_1d = None
        self._roi_2d = None
        self._map_data = None

        nx, ny = self._guess_grid_dims(len(self._chi_files))
        self._sync_ui_from_roi = True
        self.widget.spinBox_MapNx.setValue(nx)
        self.widget.spinBox_MapNy.setValue(ny)
        self._sync_ui_from_roi = False
        self._grid = (nx, ny)
        self._set_loaded_count()
        self._set_status(f"Loaded {len(self._chi_files)} CHI files. Guessed grid: {nx} x {ny}")

        self._preview_center_file()
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

    def _derive_position_indices(self, files):
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
        self._preview_center_file()
        self._draw_map()

    def _preview_center_file(self):
        if not self._chi_files:
            return
        nx, ny = self._grid
        n = len(self._chi_files)
        if nx * ny != n:
            self._set_status(f"Grid mismatch: {nx} x {ny} != {n}")
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
        self.refresh_roi_overlays()
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

    def _arm_roi_1d(self):
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Map:
            self._set_status("Open Map tab first.")
            return
        self._disable_roi_selectors()
        self.widget.pushButton_MapSetRoi2D.setChecked(False)
        self.widget.pushButton_MapSetRoi1D.setChecked(True)
        self._selector_1d = RectangleSelector(
            self.widget.mpl.canvas.ax_pattern,
            self._on_roi_1d_selected,
            useblit=True,
            button=[1],
            interactive=False,
            drag_from_anywhere=False,
        )
        self._set_status("Draw ROI on 1D pattern (main plot).")

    def _arm_roi_2d(self):
        if self.widget.tabWidget.currentWidget() != self.widget.tab_Map:
            self._set_status("Open Map tab first.")
            return
        if not self.widget.checkBox_ShowCake.isChecked():
            self._set_status("Enable Cake view to select 2D ROI.")
            return
        self._disable_roi_selectors()
        self.widget.pushButton_MapSetRoi1D.setChecked(False)
        self.widget.pushButton_MapSetRoi2D.setChecked(True)
        self._selector_2d = RectangleSelector(
            self.widget.mpl.canvas.ax_cake,
            self._on_roi_2d_selected,
            useblit=True,
            button=[1],
            interactive=False,
            drag_from_anywhere=False,
        )
        self._set_status("Draw ROI on cake plot (main plot).")

    def _disable_roi_selectors(self):
        if self._selector_1d is not None:
            try:
                self._selector_1d.set_active(False)
            except Exception:
                pass
            self._selector_1d = None
        if self._selector_2d is not None:
            try:
                self._selector_2d.set_active(False)
            except Exception:
                pass
            self._selector_2d = None

    def _clear_roi(self):
        self._roi_1d = None
        self._roi_2d = None
        self.widget.lineEdit_MapRoiSummary.setText("")
        self._set_status("ROI cleared.")
        self.deactivate_interactions()
        self._clear_roi_overlays()

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

    def _load_chi_xy(self, chi_path):
        if chi_path in self._chi_cache:
            return self._chi_cache[chi_path]
        __, __, x, y = readchi(chi_path)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        self._chi_cache[chi_path] = (x, y)
        return x, y

    def _load_bgsub_xy_if_requested(self, chi_path):
        use_bgsub = bool(getattr(self.widget, "checkBox_BgSub", None) and
                         self.widget.checkBox_BgSub.isChecked())
        if not use_bgsub:
            return self._load_chi_xy(chi_path)
        # Priority 1: temp bgsub file under <chi>-param/
        try:
            temp_dir = get_temp_dir(chi_path)
            base = os.path.splitext(os.path.basename(chi_path))[0]
            temp_bgsub = os.path.join(temp_dir, f"{base}.bgsub.chi")
            if os.path.exists(temp_bgsub):
                __, __, x, y = readchi(temp_bgsub)
                return np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        except Exception:
            pass
        # Priority 2: sibling bgsub file next to chi
        sibling_bgsub = os.path.splitext(chi_path)[0] + ".bgsub.chi"
        if os.path.exists(sibling_bgsub):
            __, __, x, y = readchi(sibling_bgsub)
            return np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        # Fallback: raw chi if bgsub file is unavailable.
        return self._load_chi_xy(chi_path)

    def _find_temp_cake_triplet(self, chi_path):
        temp_dir = get_temp_dir(chi_path)
        tth_files = sorted(glob.glob(os.path.join(temp_dir, "*.tth.cake.npy")))
        if not tth_files:
            return None
        stem_map = {}
        for tth_f in tth_files:
            stem = tth_f[: -len(".tth.cake.npy")]
            azi_f = stem + ".azi.cake.npy"
            int_f = stem + ".int.cake.npy"
            if os.path.exists(azi_f) and os.path.exists(int_f):
                stem_map[stem] = (tth_f, azi_f, int_f)
        if not stem_map:
            return None
        # Most recent triplet first.
        triplets = sorted(stem_map.values(), key=lambda t: os.path.getmtime(t[2]), reverse=True)
        return triplets[0]

    def _load_cake_data(self, chi_path):
        if chi_path in self._cake_cache:
            return self._cake_cache[chi_path]
        triplet = self._find_temp_cake_triplet(chi_path)
        if triplet is None:
            return None
        tth = np.load(triplet[0])
        azi = np.load(triplet[1])
        intensity = np.load(triplet[2])
        payload = (np.asarray(tth, dtype=float), np.asarray(azi, dtype=float), np.asarray(intensity, dtype=float))
        self._cake_cache[chi_path] = payload
        return payload

    def _compute_map(self):
        if not self._chi_files:
            self._set_status("Load CHI files first.")
            return
        nx, ny = self._grid
        n = len(self._chi_files)
        if nx * ny != n:
            self._set_status(f"Grid mismatch: {nx} x {ny} != {n}")
            return
        if (self._roi_1d is None) and (self._roi_2d is None):
            self._set_status("Select ROI first.")
            return

        values = np.full(n, np.nan, dtype=float)
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

        grid = np.full((ny, nx), np.nan, dtype=float)
        for i, val in enumerate(values):
            lin_pos = self._pos_idx[i] if i < len(self._pos_idx) else i
            x, y = self._linear_to_grid(lin_pos)
            if (y < ny) and (x < nx):
                grid[y, x] = val
        self._map_data = grid

        # Recomputing map should always refresh Min/Max from new data.
        self._scale_reset()
        self._draw_map()

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
        cmap = str(self.widget.comboBox_MapCmap.currentText())
        if self.widget.checkBox_MapReverseCmap.isChecked() and (not cmap.endswith("_r")):
            cmap = cmap + "_r"
        return cmap

    def _current_vrange(self, data):
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            return None
        return float(np.nanmin(finite)), float(np.nanmax(finite))

    def _scale_reset(self):
        if self._map_data is None:
            return
        vr = self._current_vrange(self._map_data)
        if vr is None:
            return
        self.widget.doubleSpinBox_MapVmin.setValue(vr[0])
        self.widget.doubleSpinBox_MapVmax.setValue(vr[1])

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

    def _draw_map(self):
        self._ensure_map_axes()
        if self._map_ax is None:
            return
        self._map_ax.clear()
        if self._map_cax is not None:
            self._map_cax.clear()
        self._map_cbar = None
        if self._map_data is None:
            self._map_ax.set_title("Map")
            self._map_ax.set_xlabel("X")
            self._map_ax.set_ylabel("Y")
            self._map_ax.set_aspect("equal", adjustable="box")
            self._map_canvas.draw_idle()
            return

        data = np.array(self._map_data, copy=True)
        vmin = float(self.widget.doubleSpinBox_MapVmin.value())
        vmax = float(self.widget.doubleSpinBox_MapVmax.value())

        norm = None
        label = "Integrated intensity"
        if self.widget.checkBox_MapLog.isChecked():
            finite = data[np.isfinite(data)]
            if finite.size == 0 or np.nanmax(finite) <= 0:
                self._set_status("Log scale disabled: map has no positive values.")
                self.widget.checkBox_MapLog.setChecked(False)
            else:
                min_pos = np.nanmin(finite[finite > 0]) if np.any(finite > 0) else np.nan
                if (not np.isfinite(min_pos)):
                    self._set_status("Log scale disabled: map has no positive values.")
                    self.widget.checkBox_MapLog.setChecked(False)
                else:
                    data[data <= 0] = np.nan
                    if vmin <= 0:
                        vmin = min_pos
                    vmax = max(vmax, vmin * 1.001)
                    norm = mcolors.LogNorm(vmin=vmin, vmax=vmax)
                    label = "log10(Integrated intensity)"

        im_kwargs = {
            "origin": "lower",
            "cmap": self._effective_cmap(),
            "extent": [-0.5, data.shape[1] - 0.5, -0.5, data.shape[0] - 0.5],
            "interpolation": "nearest",
        }
        if norm is None:
            im_kwargs["vmin"] = vmin
            im_kwargs["vmax"] = vmax
        else:
            im_kwargs["norm"] = norm
        self._map_im = self._map_ax.imshow(data, **im_kwargs)
        self._map_cbar = self._map_fig.colorbar(self._map_im, cax=self._map_cax)
        self._map_cbar.set_label(label)

        self._map_ax.set_title("Map")
        self._map_ax.set_xlabel("X index")
        self._map_ax.set_ylabel("Y index")
        self._map_ax.set_aspect("equal", adjustable="box")
        self._map_ax.set_xlim(-0.5, data.shape[1] - 0.5)
        self._map_ax.set_ylim(-0.5, data.shape[0] - 0.5)
        self._map_canvas.draw_idle()

    def _on_map_click(self, event):
        if self._map_data is None:
            return
        if event.inaxes != self._map_ax:
            return
        if (event.xdata is None) or (event.ydata is None):
            return
        x = int(round(event.xdata))
        y = int(round(event.ydata))
        lin = self._grid_to_linear(x, y)
        if lin is None:
            return
        file_idx = self._lin_to_file.get(lin, None)
        if file_idx is None:
            self._set_status(f"No file for map pixel ({x}, {y})")
            return
        self._load_file_to_main_plot(file_idx)
        self._set_status(f"Selected map pixel ({x}, {y})")

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
        self._set_status(f"Saved image: {filen}")

    def _export_npy(self):
        if self._map_data is None:
            self._set_status("No map data to export.")
            return
        base = os.path.join(self.model.chi_path, "map.npy")
        filen, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.widget,
            "Export map data",
            base,
            "NumPy files (*.npy)",
        )
        if not filen:
            return
        if not filen.lower().endswith(".npy"):
            filen = filen + ".npy"
        np.save(filen, self._map_data)
        self._set_status(f"Saved NPY: {filen}")
