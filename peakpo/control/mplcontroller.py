import os
import time
import datetime
import numpy as np
import numpy.ma as ma
#from matplotlib.widgets import MultiCursor
#import matplotlib.transforms as transforms
#import matplotlib.colors as colors
#import matplotlib.patches as patches
#from matplotlib.textpath import TextPath
#import matplotlib.pyplot as plt
from qtpy import QtWidgets
from qtpy import QtCore
from ..ds_jcpds import convert_tth
from ..model.azimuthal_integration import (
    normalize_range,
    normalize_ranges,
    provenance_for_chi,
)


class MplController(object):

    def __new__(cls, model, widget):
        existing = getattr(widget, "_peakpo_mpl_controller", None)
        if isinstance(existing, cls):
            return existing
        obj = super(MplController, cls).__new__(cls)
        setattr(widget, "_peakpo_mpl_controller", obj)
        return obj

    def __init__(self, model, widget):
        if getattr(self, "_peakpo_initialized", False):
            return
        self._peakpo_initialized = True
        self.model = model
        self.widget = widget
        self.obj_color = 'k'
        self.diff_ctrl = None
        self._cached_title = None
        self._cached_filename = None
        self._is_drawing = False
        self._toolbar_active = False
        self._update_delay_ms = 25
        self._pending_update_args = None
        self._last_auto_cake_filename = None
        self._update_timer = QtCore.QTimer(self.widget)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._flush_update_request)
        self._vcursor_pattern = None
        self._vcursor_cake = None
        self._peak_center_marker_artists = []
        self._selected_peak_marker_artists = []
        self._jcpds_overlay_artists = []
        self._jcpds_hkl_artists = []
        
        # ✅ Wrap toolbar methods to track state
        toolbar = self.widget.mpl.canvas.toolbar
        if toolbar:
            self._original_zoom = toolbar.zoom
            self._original_pan = toolbar.pan
            self._original_home = toolbar.home
            self._original_back = toolbar.back
            self._original_forward = toolbar.forward
            
            def zoom_wrapper(*args, **kwargs):
                result = self._original_zoom(*args, **kwargs)
                self._toolbar_active = False
                # ✅ NEW: Uncheck cursor when zoom is activated
                if toolbar.mode == 'zoom rect':
                    self.widget.checkBox_LongCursor.setChecked(False)
                return result
            
            def pan_wrapper(*args, **kwargs):
                result = self._original_pan(*args, **kwargs)
                self._toolbar_active = False
                # ✅ NEW: Uncheck cursor when pan is activated
                if toolbar.mode == 'pan/zoom':
                    self.widget.checkBox_LongCursor.setChecked(False)
                return result
            
            def home_wrapper(*args, **kwargs):
                self._toolbar_active = True
                result = self._original_home(*args, **kwargs)
                self._toolbar_active = False
                return result
            
            def back_wrapper(*args, **kwargs):
                self._toolbar_active = True
                result = self._original_back(*args, **kwargs)
                self._toolbar_active = False
                return result
            
            def forward_wrapper(*args, **kwargs):
                self._toolbar_active = True
                result = self._original_forward(*args, **kwargs)
                self._toolbar_active = False
                return result
            
            toolbar.zoom = zoom_wrapper
            toolbar.pan = pan_wrapper
            toolbar.home = home_wrapper
            toolbar.back = back_wrapper
            toolbar.forward = forward_wrapper

    def set_diff_controller(self, diff_ctrl):
        self.diff_ctrl = diff_ctrl

    def _clear_vertical_cursor_artists(self):
        for attr in ("_vcursor_pattern", "_vcursor_cake"):
            artist = getattr(self, attr, None)
            if artist is not None:
                try:
                    artist.remove()
                except Exception:
                    pass
            setattr(self, attr, None)

    def _ensure_vertical_cursor_artists(self):
        if not self.widget.checkBox_LongCursor.isChecked():
            self._clear_vertical_cursor_artists()
            return
        try:
            lw_value = float(
                self.widget.comboBox_VertCursorThickness.currentText())
        except Exception:
            lw_value = 1.0
        ax_pattern = self.widget.mpl.canvas.ax_pattern
        if self._vcursor_pattern is None or \
                getattr(self._vcursor_pattern, "axes", None) is not ax_pattern:
            self._vcursor_pattern = ax_pattern.axvline(
                0.0, color='r', lw=lw_value, ls='--', visible=False)
        else:
            self._vcursor_pattern.set_linewidth(lw_value)
        use_cake = hasattr(self.widget.mpl.canvas, 'ax_cake') and \
            self.widget.checkBox_ShowCake.isChecked()
        if use_cake:
            ax_cake = self.widget.mpl.canvas.ax_cake
            if self._vcursor_cake is None or \
                    getattr(self._vcursor_cake, "axes", None) is not ax_cake:
                self._vcursor_cake = ax_cake.axvline(
                    0.0, color='r', lw=lw_value, ls='--', visible=False)
            else:
                self._vcursor_cake.set_linewidth(lw_value)
        else:
            if self._vcursor_cake is not None:
                try:
                    self._vcursor_cake.remove()
                except Exception:
                    pass
                self._vcursor_cake = None

    def update_vertical_cursor_position(self, event):
        if not self.widget.checkBox_LongCursor.isChecked():
            return
        if (event is None) or (event.inaxes is None) or (event.xdata is None):
            self.clear_vertical_cursor_position()
            return
        valid_axes = [self.widget.mpl.canvas.ax_pattern]
        if hasattr(self.widget.mpl.canvas, 'ax_cake') and \
                self.widget.checkBox_ShowCake.isChecked():
            valid_axes.append(self.widget.mpl.canvas.ax_cake)
        if event.inaxes not in valid_axes:
            self.clear_vertical_cursor_position()
            return
        self._ensure_vertical_cursor_artists()
        x = float(event.xdata)
        if self._vcursor_pattern is not None:
            self._vcursor_pattern.set_xdata([x, x])
            self._vcursor_pattern.set_visible(True)
        if self._vcursor_cake is not None:
            self._vcursor_cake.set_xdata([x, x])
            self._vcursor_cake.set_visible(True)
        self.widget.mpl.canvas.draw_idle()

    def clear_vertical_cursor_position(self):
        changed = False
        for artist in (self._vcursor_pattern, self._vcursor_cake):
            if artist is not None and artist.get_visible():
                artist.set_visible(False)
                changed = True
        if changed:
            self.widget.mpl.canvas.draw_idle()

    def _set_nightday_view(self):
        if not self.widget.checkBox_NightView.isChecked():
            self.widget.mpl.canvas.set_toNight(False)
            # reset plot objects with white
            if self.model.base_ptn_exist():
                self.model.base_ptn.color = 'k'
            if self.model.waterfall_exist():
                for pattern in self.model.waterfall_ptn:
                    if (pattern.color == 'white') or \
                            (pattern.color == '#ffffff'):
                        pattern.color = 'k'
            self.obj_color = 'k'
        else:
            self.widget.mpl.canvas.set_toNight(True)
            if self.model.base_ptn_exist():
                self.model.base_ptn.color = 'white'
            if self.model.waterfall_exist():
                for pattern in self.model.waterfall_ptn:
                    if (pattern.color == 'k') or (pattern.color == '#000000'):
                        pattern.color = 'white'
            self.obj_color = 'white'

    def _apply_pattern_background_style(self):
        ax_pattern = self.widget.mpl.canvas.ax_pattern
        face = self.widget.mpl.canvas.bgColor
        if hasattr(self.widget, "checkBox_LightBackground") and \
                self.widget.checkBox_LightBackground.isChecked():
            face = "#66707a"
        ax_pattern.set_facecolor(face)

    def get_cake_range(self):
        if self.widget.checkBox_ShowCake.isChecked():
            return self.widget.mpl.canvas.ax_cake.get_xlim(),\
                self.widget.mpl.canvas.ax_cake.get_ylim()
        else:
            return None, None

    def _read_azilist(self):
        n_row = self.widget.tableWidget_DiffImgAzi.rowCount()
        if n_row == 0:
            return None, None, None
        azi_list = []
        tth_list = []
        note_list = []
        for i in range(n_row):
            parsed = self._read_cake_azi_table_row(i)
            if parsed is None:
                continue
            tth_list.append(parsed["tth"])
            azi_list.append([parsed["azi_min"], parsed["azi_max"]])
            note_list.append(parsed["label"])
        return tth_list, azi_list, note_list

    def _read_cake_azi_table_row(self, row):
        table = self.widget.tableWidget_DiffImgAzi
        item0 = table.item(row, 0)
        if item0 is not None and (item0.flags() & QtCore.Qt.ItemIsUserCheckable):
            if item0.checkState() != QtCore.Qt.Checked:
                return None
            label_item = table.item(row, 1)
            min_item = table.item(row, 2)
            max_item = table.item(row, 3)
            label = "" if label_item is None else label_item.text()
            tth = None
        else:
            label_item = table.item(row, 0)
            min_item = table.item(row, 2)
            max_item = table.item(row, 4)
            tth_min_item = table.item(row, 1)
            tth_max_item = table.item(row, 3)
            label = "" if label_item is None else label_item.text()
            try:
                tth = [
                    float(tth_min_item.text()),
                    float(tth_max_item.text()),
                ]
            except (AttributeError, TypeError, ValueError):
                tth = None
        try:
            azi = normalize_range({
                "label": label,
                "azi_min": float(min_item.text()),
                "azi_max": float(max_item.text()),
            })
        except (AttributeError, TypeError, ValueError):
            return None
        if azi is None:
            return None
        return {
            "label": azi["label"],
            "azi_min": azi["azi_min"],
            "azi_max": azi["azi_max"],
            "tth": tth,
        }

    def _current_pattern_provenance(self):
        getter = getattr(self.model, "get_active_pattern_provenance", None)
        if callable(getter):
            provenance = getter()
            if isinstance(provenance, dict):
                return provenance
        provenance = getattr(self.model, "current_pattern_provenance", None)
        if provenance is None:
            base_ptn = getattr(self.model, "base_ptn", None)
            provenance = getattr(base_ptn, "_pkpo_source_provenance", None)
        if isinstance(provenance, dict):
            return provenance
        try:
            if self.model.base_ptn_exist():
                return provenance_for_chi(self.model.get_base_ptn_filename())
        except Exception:
            pass
        return {}

    def _display_pattern(self):
        getter = getattr(self.model, "get_display_ptn", None)
        if callable(getter):
            pattern = getter()
            if pattern is not None:
                return pattern
        return getattr(self.model, "base_ptn", None)

    def _display_pattern_filename(self):
        getter = getattr(self.model, "get_display_ptn_filename", None)
        if callable(getter):
            filename = getter()
            if filename is not None:
                return filename
        pattern = self._display_pattern()
        return getattr(pattern, "fname", "")

    def _pattern_xy(self, bgsub=None):
        pattern = self._display_pattern()
        if pattern is None:
            return None, None
        if bgsub is None:
            bgsub = self.widget.checkBox_BgSub.isChecked()
        if bgsub:
            x, y = pattern.get_bgsub()
            if x is not None and y is not None:
                return x, y
        return pattern.get_raw()

    def _pattern_background_xy(self):
        pattern = self._display_pattern()
        if pattern is None:
            return None, None
        x_bg, y_bg = pattern.get_background()
        if x_bg is not None and y_bg is not None:
            return x_bg, y_bg
        x_raw, y_raw = pattern.get_raw()
        if x_raw is None or y_raw is None:
            return None, None
        return x_raw, np.zeros_like(y_raw)

    @staticmethod
    def _wrap_angle_to_axis(value, axis_min, span):
        if span <= 0:
            return float(value)
        return ((float(value) - axis_min) % span) + axis_min

    def _shift_azimuth_range_to_current_view(
            self, range_info, saved_shift, axis_min, axis_max):
        span = float(axis_max - axis_min)
        if span <= 0:
            return []
        try:
            current_shift = float(self.widget.spinBox_AziShift.value())
        except Exception:
            current_shift = 0.0
        try:
            saved_shift = float(saved_shift)
        except (TypeError, ValueError):
            saved_shift = current_shift
        width = float(range_info["azi_max"]) - float(range_info["azi_min"])
        if width <= 0:
            return []
        if width >= span:
            return [(axis_min, axis_max)]
        start = self._wrap_angle_to_axis(
            float(range_info["azi_min"]) + current_shift - saved_shift,
            axis_min, span)
        end = start + width
        if end <= axis_max:
            return [(start, end)]
        return [(start, axis_max), (axis_min, end - span)]

    def _derived_azimuth_overlay_ranges(self, axis_min, axis_max):
        provenance = self._current_pattern_provenance()
        if provenance.get("source_kind") != "azimuthal_integration":
            return []
        ranges = normalize_ranges(provenance.get("azimuth_ranges", []))
        saved_shift = provenance.get("azimuth_shift")
        overlay_ranges = []
        for range_info in ranges:
            overlay_ranges.extend(self._shift_azimuth_range_to_current_view(
                range_info, saved_shift, axis_min, axis_max))
        return overlay_ranges

    def _plot_derived_azimuth_overlay(self, tth_min, tth_max, chi_min, chi_max):
        import matplotlib.patches as patches

        ranges = self._derived_azimuth_overlay_ranges(chi_min, chi_max)
        if ranges == []:
            return
        color = "#ffbf47"
        for idx, (azi_min, azi_max) in enumerate(ranges):
            if azi_max <= azi_min:
                continue
            rect = patches.Rectangle(
                (tth_min, azi_min),
                tth_max - tth_min,
                azi_max - azi_min,
                linewidth=1.5,
                edgecolor=color,
                facecolor=color,
                alpha=0.22)
            self.widget.mpl.canvas.ax_cake.add_patch(rect)
            show_labels = getattr(self.widget, "checkBox_ShowCakeLabels", None)
            if idx == 0 and show_labels is not None and show_labels.isChecked():
                self.widget.mpl.canvas.ax_cake.text(
                    tth_max,
                    azi_max,
                    "derived 1D",
                    color=color,
                    horizontalalignment="right",
                    verticalalignment="bottom")

    def zoom_out_graph(self):
        if not self.model.base_ptn_exist():
            return
        data_limits = self._get_data_limits()
        self.update(limits=data_limits,
                    cake_ylimits=(-180, 180))

    def update_to_gsas_style(self):
        if not self.model.base_ptn_exist():
            return
        data_limits = self._get_data_limits(y_margin=0.10)
        self.update(limits=data_limits, gsas_style=True)

    def _get_data_limits(self, y_margin=0.):
        x, y = self._pattern_xy()
        if self.diff_ctrl is not None:
            try:
                x, y = self.diff_ctrl.get_display_pattern(x, y)
            except Exception:
                pass
        return (x.min(), x.max(),
                y.min() - (y.max() - y.min()) * y_margin,
                y.max() + (y.max() - y.min()) * y_margin)


    
    """
    def _plot_ucfit(self):
        i = 0
        for j in self.model.ucfit_lst:
            if j.display:
                i += 1
        if i == 0:
            return
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        bar_scale = 1. / 100. * axisrange[3]
        i = 0
        for phase in self.model.ucfit_lst:
            if phase.display:
                try:
                    phase.cal_dsp()
                except:
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        phase.name+" created issues with pressure calculation.")
                    break
                tth, inten = phase.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                bar_min = np.ones(tth.shape) * axisrange[2]
                intensity = inten
                bar_min = np.ones(tth.shape) * axisrange[2]
                self.widget.tableWidget_UnitCell.removeCellWidget(i, 3)
                Item4 = QtWidgets.QTableWidgetItem(
                    "{:.3f}".format(float(phase.v)))
                Item4.setFlags(
                    QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(i, 3, Item4)
                if self.widget.checkBox_Intensity.isChecked():
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, intensity * bar_scale,
                        colors=phase.color,
                        lw=float(
                            self.widget.comboBox_PtnJCPDSBarThickness.
                            currentText()))
                else:
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, 100. * bar_scale,
                        colors=phase.color,
                        lw=float(
                            self.widget.comboBox_PtnJCPDSBarThickness.
                            currentText()))
            i += 1
    """

    def _plot_cake(self):
        """
        Controls cake viewing as well as mask
        """
        import matplotlib.patches as patches
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        def _coerce_cake_arrays(intensity, tth, chi):
            if intensity is None or tth is None or chi is None:
                return None
            try:
                cake = ma.asarray(intensity, dtype=float)
                tth_arr = np.asarray(tth, dtype=float).ravel()
                chi_arr = np.asarray(chi, dtype=float).ravel()
            except (TypeError, ValueError):
                return None
            if cake.ndim != 2 or cake.size == 0:
                return None
            if tth_arr.size == 0 or chi_arr.size == 0:
                return None
            return cake, tth_arr, chi_arr

        #print(str(datetime.datetime.now())[:-7], ': Num of tth points = {0:.0f}, azi strips = {1:.0f}'.format(len(tth_cake), len(chi_cake)))

        # make a copy of intensity_cake and make sure it also has mask information 
        #intensity_cake_plot = ma.masked_values(intensity_cake, 0.)
        # intensity_cake_plot = ma.masked_equal(intensity_cake, 0.0, copy=False)
        #intensity_cake_plot = ma.array(intensity_cake, mask=self.model.diff_img.mask)

        # Get cake data
        intensity_cake, tth_cake, chi_cake = self.model.diff_img.get_cake()
        coerced = _coerce_cake_arrays(intensity_cake, tth_cake, chi_cake)
        if coerced is None:
            hist_widget = getattr(self.widget, "cake_hist_widget", None)
            if hist_widget is not None:
                if hasattr(hist_widget, "clear"):
                    hist_widget.clear()
                elif hasattr(hist_widget, "_draw_empty_state"):
                    hist_widget._draw_empty_state()
            return
        int_plot, tth_cake, chi_cake = coerced
        int_plot = ma.array(int_plot, copy=True)
        finite_cake = np.asarray(ma.filled(int_plot, np.nan), dtype=float)
        finite_cake = finite_cake[np.isfinite(finite_cake)]
        cake_max = None
        if finite_cake.size > 0:
            cake_max = float(np.nanmax(finite_cake))
            if np.isfinite(cake_max) and cake_max > 0:
                self.widget.spinBox_MaxCakeScale.setValue(int(np.ceil(cake_max)))

        diff_mode = False
        if self.diff_ctrl is not None:
            try:
                diff_int, diff_tth, diff_chi = self.diff_ctrl.get_display_cake(
                    int_plot, tth_cake, chi_cake)
                coerced = _coerce_cake_arrays(diff_int, diff_tth, diff_chi)
                if coerced is not None:
                    int_plot, tth_cake, chi_cake = coerced
                    diff_mode = self.diff_ctrl.is_diff_mode_active()
            except Exception:
                diff_mode = False

        # Apply azimuthal shift after diff subtraction so the same shift is
        # effectively applied to both current and reference cake images.
        mid_angle = self.widget.spinBox_AziShift.value()
        if mid_angle != 0 and int_plot.ndim == 2 and int_plot.shape[0] > 1:
            row_shift = int(round(float(mid_angle) / 360.0 * int_plot.shape[0]))
            int_plot = ma.array(np.roll(int_plot, row_shift, axis=0), copy=False)

        # Get image contrast parameters from UI unless diff mode overrides.
        min_slider_pos = self.widget.horizontalSlider_VMin.value()
        max_slider_pos = self.widget.horizontalSlider_VMax.value()
        if (max_slider_pos <= min_slider_pos):
            self.widget.horizontalSlider_VMin.setValue(5)
            self.widget.horizontalSlider_VMax.setValue(10)
        scale_bar_value = 0
        prefactor = self.widget.spinBox_MaxCakeScale.value() / \
            (10. ** scale_bar_value)
        climits = np.asarray([
            self.widget.horizontalSlider_VMin.value(),
            self.widget.horizontalSlider_VMax.value()]) / \
            100. * prefactor
        hist_widget = getattr(self.widget, "cake_hist_widget", None)

        # Colormap + mask handling.
        if diff_mode and (self.diff_ctrl is not None):
            cfg = self.diff_ctrl.get_cake_render_config(int_plot) or {}
            cmap = plt.get_cmap(cfg.get("cmap", "RdBu_r")).copy()
            climits = np.asarray([cfg.get("vmin", -1.0), cfg.get("vmax", 1.0)])
            norm = None
            if bool(cfg.get("center_zero", False)):
                try:
                    norm = mcolors.TwoSlopeNorm(
                        vmin=float(climits[0]), vcenter=0.0, vmax=float(climits[1]))
                except Exception:
                    norm = None
            zero_mask = np.zeros(np.shape(int_plot), dtype=bool)
            cmap.set_bad(color=(0.0, 0.0, 0.0, 0.0))
        else:
            # Non-diff mode uses user-selected colormap from Plot > Control.
            cmap_name = "gray_r"
            if hasattr(self.widget, "comboBox_CakeColormap"):
                cmap_name = str(self.widget.comboBox_CakeColormap.currentText() or "gray_r")
            cmap = plt.get_cmap(cmap_name).copy()
            norm = None
            # 0-values are typically masked pixels in cake data.
            zero_mask = (int_plot == 0)
            # Opaque pale yellow for masked pixels.
            cmap.set_bad(color=(1.0, 0.97, 0.55, 1.0))
        zero_mask = np.asarray(ma.filled(zero_mask, False), dtype=bool)

        base_mask = ma.getmaskarray(int_plot)
        invalid_mask = ~np.isfinite(ma.filled(int_plot, np.nan))
        combined_mask = zero_mask | base_mask | invalid_mask
        int_new = ma.masked_where(
            combined_mask, ma.filled(int_plot, np.nan), copy=False)

        if hist_widget is not None:
            data_signature = hist_widget.data_signature_for_values(int_new)
            try:
                cake_filename = self.model.get_base_ptn_filename()
            except Exception:
                cake_filename = None
            is_new_cake_file = (
                cake_filename is not None and
                cake_filename != self._last_auto_cake_filename)

            auto_bounds = None
            if (not diff_mode) and is_new_cake_file:
                auto_bounds = hist_widget.auto_edge_bounds_for_values(
                    int_new,
                    self._cake_hist_edge_width_percent(),
                    self._cake_hist_edge_position_percent())
                self._last_auto_cake_filename = cake_filename

            if auto_bounds is not None:
                hist_widget.apply_auto_view(
                    auto_bounds["low_pct"], auto_bounds["high_pct"])
                climits = np.asarray([
                    auto_bounds["vmin"], auto_bounds["vmax"]], dtype=float)
            else:
                exact_bounds = hist_widget.current_bounds(
                    data_signature=data_signature)
                if exact_bounds is not None:
                    climits = np.asarray(exact_bounds, dtype=float)


        imshow_kwargs = {
            "origin": "lower",
            "extent": [tth_cake.min(), tth_cake.max(), chi_cake.min(), chi_cake.max()],
            "aspect": "auto",
            "cmap": cmap,
        }
        if norm is None:
            imshow_kwargs["vmin"] = climits[0]
            imshow_kwargs["vmax"] = climits[1]
        else:
            imshow_kwargs["norm"] = norm
        self.widget.mpl.canvas.ax_cake.imshow(int_new, **imshow_kwargs)
        if hist_widget is not None:
            hist_widget.set_data(
                int_new, vmin=float(climits[0]), vmax=float(climits[1]))

        # get gray scale color map and make sure masked data points are colored red
        """
        if self.widget.checkBox_WhiteForPeak.isChecked():
            #cmap = 'gray'
            cmap = plt.cm.gray.copy()
        else:
            #cmap = 'gray_r'
            cmap = plt.cm.gray_r.copy()
        cmap.set_bad(color='red')
        """

        # plot the data as an image
        """
        self.widget.mpl.canvas.ax_cake.imshow(
            int_new, origin="lower",
            extent=[tth_cake.min(), tth_cake.max(),
                    chi_cake.min(), chi_cake.max()],
            aspect="auto", cmap=cmap, clim=climits)  # gray_r
        """
        #print(str(datetime.datetime.now())[:-7], ': Cake intensity min, max = ', climits)

        # overlay azimuthal sections information
        tth_list, azi_list, note_list = self._read_azilist()
        tth_min = tth_cake.min()
        tth_max = tth_cake.max()
        chi_min = chi_cake.min()
        chi_max = chi_cake.max()
        self._plot_derived_azimuth_overlay(tth_min, tth_max, chi_min, chi_max)
        if azi_list is not None:
            for tth, azi, note in zip(tth_list, azi_list, note_list):
                if tth is None:
                    tth = [tth_min, tth_max]
                rect = patches.Rectangle(
                    (tth_min, azi[0]), (tth_max - tth_min), (azi[1] - azi[0]),
                    linewidth=0, edgecolor='gray', facecolor='gray', alpha=0.2)
                rect1 = patches.Rectangle(
                    (tth[0], azi[0]), (tth[1] - tth[0]), (azi[1] - azi[0]),
                    linewidth=1, edgecolor=self.obj_color, facecolor='None')
                self.widget.mpl.canvas.ax_cake.add_patch(rect)
                self.widget.mpl.canvas.ax_cake.add_patch(rect1)
                if self.widget.checkBox_ShowCakeLabels.isChecked():
                    self.widget.mpl.canvas.ax_cake.text(
                        tth[1], azi[1], note, color=self.obj_color)
        rows = self.widget.tableWidget_DiffImgAzi.selectionModel().\
            selectedRows()
        if rows != []:
            for r in rows:
                parsed = self._read_cake_azi_table_row(r.row())
                if parsed is None:
                    continue
                azi_min = parsed["azi_min"]
                azi_max = parsed["azi_max"]
                rect = patches.Rectangle(
                    (tth_min, azi_min), (tth_max - tth_min),
                    (azi_max - azi_min),
                    linewidth=0, facecolor='r', alpha=0.2)
                self.widget.mpl.canvas.ax_cake.add_patch(rect)

    def _cake_hist_edge_width_percent(self):
        spin = getattr(self.widget, "doubleSpinBox_CakeHistEdgePct", None)
        if spin is None:
            return 30.0
        return float(spin.value())

    def _cake_hist_edge_position_percent(self):
        spin = getattr(self.widget, "doubleSpinBox_CakeHistEdgePositionPct", None)
        if spin is None:
            return 75.0
        return float(spin.value())

    def _track_jcpds_artist(self, artist, hkl=False):
        if artist is not None:
            try:
                artist.set_gid("peakpo_jcpds_hkl" if hkl else "peakpo_jcpds")
            except Exception:
                pass
            artist._peakpo_jcpds_overlay = True
            artist._peakpo_jcpds_hkl = bool(hkl)
            self._jcpds_overlay_artists.append(artist)
            if hkl:
                self._jcpds_hkl_artists.append(artist)
        return artist

    def _artist_is_jcpds_overlay(self, artist, hkl_only=False):
        if getattr(artist, "_peakpo_jcpds_overlay", False):
            return (not hkl_only) or getattr(artist, "_peakpo_jcpds_hkl", False)
        gid = None
        try:
            gid = artist.get_gid()
        except Exception:
            pass
        if gid in ("peakpo_jcpds", "peakpo_jcpds_hkl"):
            return (not hkl_only) or gid == "peakpo_jcpds_hkl"
        if hkl_only:
            return False
        label = ""
        try:
            label = artist.get_label()
        except Exception:
            pass
        return isinstance(label, str) and " A^3" in label

    def _remove_stale_jcpds_artists_from_axes(self, hkl_only=False):
        canvas = self.widget.mpl.canvas
        axes = [getattr(canvas, "ax_pattern", None), getattr(canvas, "ax_cake", None)]
        for ax in axes:
            if ax is None:
                continue
            if not hkl_only:
                legend = ax.get_legend()
                if legend is not None:
                    try:
                        legend.remove()
                    except Exception:
                        pass
            artist_groups = (
                list(getattr(ax, "collections", [])) +
                list(getattr(ax, "lines", [])) +
                list(getattr(ax, "texts", []))
            )
            for artist in artist_groups:
                if self._artist_is_jcpds_overlay(artist, hkl_only=hkl_only):
                    try:
                        artist.remove()
                    except Exception:
                        pass

    def _clear_jcpds_overlay_artists(self):
        for artist in list(self._jcpds_overlay_artists):
            try:
                artist.remove()
            except Exception:
                pass
        self._remove_stale_jcpds_artists_from_axes(hkl_only=False)
        self._jcpds_overlay_artists = []
        self._jcpds_hkl_artists = []

    def _clear_jcpds_hkl_artists(self):
        hkl_artist_ids = {id(artist) for artist in self._jcpds_hkl_artists}
        for artist in list(self._jcpds_hkl_artists):
            try:
                artist.remove()
            except Exception:
                pass
        self._jcpds_overlay_artists = [
            artist for artist in self._jcpds_overlay_artists
            if id(artist) not in hkl_artist_ids]
        self._remove_stale_jcpds_artists_from_axes(hkl_only=True)
        self._jcpds_hkl_artists = []

    def clear_jcpds_hkl_overlay(self):
        self._clear_jcpds_hkl_artists()
        self.widget.mpl.canvas.draw_idle()

    def refresh_jcpds_overlay(self):
        if self._is_drawing or self._toolbar_active:
            self.update()
            return
        canvas = self.widget.mpl.canvas
        if not hasattr(canvas, "ax_pattern"):
            return
        ax_pattern = canvas.ax_pattern
        pattern_xlim = ax_pattern.get_xlim()
        pattern_ylim = ax_pattern.get_ylim()
        cake_xlim = None
        cake_ylim = None
        if hasattr(canvas, "ax_cake"):
            cake_xlim = canvas.ax_cake.get_xlim()
            cake_ylim = canvas.ax_cake.get_ylim()

        self._clear_jcpds_overlay_artists()
        if self.model.jcpds_exist():
            axisrange = ax_pattern.axis()
            self._plot_jcpds(axisrange)
            if self.widget.checkBox_JCPDSinPattern.isChecked() and \
                    (not self.widget.checkBox_Intensity.isChecked()):
                new_low_limit = -1.1 * axisrange[3] * \
                    self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
                ax_pattern.set_ylim(new_low_limit, axisrange[3])
            else:
                ax_pattern.set_ylim(pattern_ylim)
        else:
            ax_pattern.set_ylim(pattern_ylim)

        ax_pattern.set_xlim(pattern_xlim)
        if hasattr(canvas, "ax_cake"):
            if cake_xlim is not None:
                canvas.ax_cake.set_xlim(cake_xlim)
            if cake_ylim is not None:
                canvas.ax_cake.set_ylim(cake_ylim)
        canvas.draw_idle()

    def _plot_jcpds(self, axisrange):
        import matplotlib.transforms as transforms

        # t_start = time.time()
        self._clear_jcpds_overlay_artists()
        if (not self.widget.checkBox_JCPDSinPattern.isChecked()) and \
                (not self.widget.checkBox_JCPDSinCake.isChecked()):
            return
        selected_phases = []
        for phase in self.model.jcpds_lst:
            if phase.display:
                selected_phases.append(phase)
        if selected_phases == []:
            return
        n_displayed_jcpds = len(selected_phases)
        # axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        cakerange = self.widget.mpl.canvas.ax_cake.axis()
        bar_scale = 1. / 100. * axisrange[3] * \
            self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
        bar_pos = self.widget.horizontalSlider_JCPDSBarPosition.value() / 100.
        show_intensity = self.widget.checkBox_Intensity.isChecked()
        if not show_intensity:
            data_limits = self._get_data_limits()
            start_intensity = data_limits[2] + bar_pos * axisrange[3]
        pressure = self.widget.doubleSpinBox_Pressure.value()
        temperature = self.widget.doubleSpinBox_Temperature.value()
        wavelength = self.widget.doubleSpinBox_SetWavelength.value()
        use_table_0gpa = self.widget.checkBox_UseJCPDSTable1bar.isChecked()
        legend_entries = []
        for i, phase in enumerate(selected_phases):
#            try:
            phase.cal_dsp(pressure,
                            temperature,
                            use_table_for_0GPa=use_table_0gpa)
#            except:
#                QtWidgets.QMessageBox.warning(
#                    self.widget, "Warning",
#                    phase.name+" created issues with pressure calculation.")
#                break
            tth, inten = phase.get_tthVSint(
                wavelength)
            if self.widget.checkBox_JCPDSinPattern.isChecked():
                intensity = inten * phase.twk_int
                if show_intensity:
                    bar_min = np.ones_like(tth) * axisrange[2] + \
                        bar_pos * axisrange[3]
                    bar_max = intensity * bar_scale + bar_min
                else:
                    starting_intensity = np.ones_like(tth) * start_intensity
                    bar_max = starting_intensity - \
                        i * 100. * bar_scale / n_displayed_jcpds
                    bar_min = starting_intensity - \
                        (i+0.7) * 100. * bar_scale / n_displayed_jcpds
                if (pressure == 0.) or (phase.symmetry == 'nosymmetry'):
                    volume = phase.v
                else:
                    volume = phase.v.item()
                legend_label = "{0:}, {1:.3f} A^3".format(
                    phase.name, volume)
                jcpds_bars = self.widget.mpl.canvas.ax_pattern.vlines(
                    tth, bar_min, bar_max, colors=phase.color,
                    label=legend_label,
                    lw=float(
                        self.widget.comboBox_PtnJCPDSBarThickness.
                        currentText()),
                    alpha=self.widget.doubleSpinBox_JCPDS_ptn_Alpha.value(),
                    zorder=18)
                self._track_jcpds_artist(jcpds_bars)
                legend_entries.append((jcpds_bars, legend_label, phase.color))
                # hkl
                if self.widget.checkBox_ShowMillerIndices.isChecked():
                    hkl_list = phase.get_hkl_in_text()
                    for j, hkl in enumerate(hkl_list):
                        self._track_jcpds_artist(
                            self.widget.mpl.canvas.ax_pattern.text(
                            tth[j], bar_max[j], hkl, color=phase.color,
                            rotation=90, verticalalignment='bottom',
                            horizontalalignment='center',
                            fontsize=int(
                                self.widget.comboBox_HKLFontSize.currentText()),
                            alpha=self.widget.doubleSpinBox_JCPDS_ptn_Alpha.value(),
                            zorder=19), hkl=True)
                # phase.name, phase.v.item()))
            if self.widget.checkBox_ShowCake.isChecked() and \
                    self.widget.checkBox_JCPDSinCake.isChecked():
                self._track_jcpds_artist(
                    self.widget.mpl.canvas.ax_cake.vlines(
                    tth, np.ones_like(tth) * cakerange[2],
                    np.ones_like(tth) * cakerange[3], colors=phase.color,
                    lw=float(
                        self.widget.comboBox_CakeJCPDSBarThickness.currentText()),
                    alpha=self.widget.doubleSpinBox_JCPDS_cake_Alpha.value(),
                    zorder=18))
                if self.widget.checkBox_ShowMillerIndices_Cake.isChecked():
                    hkl_list = phase.get_hkl_in_text()
                    trans = transforms.blended_transform_factory(
                        self.widget.mpl.canvas.ax_cake.transData,
                        self.widget.mpl.canvas.ax_cake.transAxes)
                    for j, hkl in enumerate(hkl_list):
                        self._track_jcpds_artist(
                            self.widget.mpl.canvas.ax_cake.text(
                            tth[j], 0.99, hkl, color=phase.color,
                            rotation=90, verticalalignment='top',
                            transform=trans, horizontalalignment='right',
                            fontsize=int(
                                self.widget.comboBox_HKLFontSize.currentText()),
                            alpha=self.widget.doubleSpinBox_JCPDS_cake_Alpha.value(),
                            zorder=19), hkl=True)
        if self.widget.checkBox_JCPDSinPattern.isChecked():
            legend_fontsize = 14
            if hasattr(self.widget, "comboBox_LegendFontSize"):
                try:
                    legend_fontsize = int(
                        self.widget.comboBox_LegendFontSize.currentText())
                except Exception:
                    pass
            unique_entries = []
            seen_labels = set()
            for handle, label, color in legend_entries:
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                unique_entries.append((handle, label, color))
            if unique_entries:
                handles = [entry[0] for entry in unique_entries]
                labels = [entry[1] for entry in unique_entries]
                leg_jcpds = self.widget.mpl.canvas.ax_pattern.legend(
                    handles, labels, loc=1, framealpha=0.,
                    fontsize=legend_fontsize,
                    handlelength=1)
                self._track_jcpds_artist(leg_jcpds)
                for (__handle, __label, color), txt in zip(
                        unique_entries, leg_jcpds.get_texts()):
                    txt.set_color(color)
        # print("JCPDS update takes {0:.2f}s at".format(time.time() - t_start),
        #      str(datetime.datetime.now())[:-7])

    def _plot_waterfallpatterns(self):
        if not self.widget.checkBox_ShowWaterfall.isChecked():
            return
        # t_start = time.time()
        # count how many are dispaly
        i = 0
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                i += 1
        if i == 0:
            return
        n_display = i
        j = 0  # this is needed for waterfall gaps
        # get y_max
        for pattern in self.model.waterfall_ptn[::-1]:
            if pattern.display:
                j += 1
                """
                self.widget.mpl.canvas.ax_pattern.text(
                    0.01, 0.97 - n_display * 0.05 + j * 0.05,
                    os.path.basename(pattern.fname),
                    transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                    color=pattern.color)
                """
                if self.widget.checkBox_BgSub.isChecked():
                    ygap = self.widget.horizontalSlider_WaterfallGaps.value() * \
                        self.model.base_ptn.y_bgsub.max() * float(j) / 100.
                    y_bgsub = pattern.y_bgsub
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = y_bgsub / y_bgsub.max() * \
                            self.model.base_ptn.y_bgsub.max()
                    else:
                        y = y_bgsub
                    x_t = pattern.x_bgsub
                else:
                    ygap = self.widget.horizontalSlider_WaterfallGaps.value() * \
                        self.model.base_ptn.y_raw.max() * float(j) / 100.
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = pattern.y_raw / pattern.y_raw.max() *\
                            self.model.base_ptn.y_raw.max()
                    else:
                        y = pattern.y_raw
                    x_t = pattern.x_raw
                if self.widget.checkBox_SetToBasePtnLambda.isChecked():
                    x = convert_tth(x_t, pattern.wavelength,
                                    self.model.base_ptn.wavelength)
                else:
                    x = x_t
                self.widget.mpl.canvas.ax_pattern.plot(
                    x, y + ygap, c=pattern.color, lw=float(
                        self.widget.comboBox_WaterfallLineThickness.
                        currentText()))
                if self.widget.checkBox_ShowWaterfallLabels.isChecked():
                    wf_fontsize = 12
                    if hasattr(self.widget, "comboBox_WaterfallFontSize"):
                        try:
                            wf_fontsize = int(
                                self.widget.comboBox_WaterfallFontSize.currentText())
                        except Exception:
                            pass
                    self.widget.mpl.canvas.ax_pattern.text(
                        (x[-1] - x[0]) * 0.01 + x[0], y[0] + ygap,
                        os.path.basename(pattern.fname),
                        verticalalignment='bottom', horizontalalignment='left',
                        color=pattern.color, fontsize=wf_fontsize)
        """
        self.widget.mpl.canvas.ax_pattern.text(
            0.01, 0.97 - n_display * 0.05,
            os.path.basename(self.model.base_ptn.fname),
            transform=self.widget.mpl.canvas.ax_pattern.transAxes,
            color=self.model.base_ptn.color)
        """

    def _plot_diffpattern(self, gsas_style=False):
        x, y = self._pattern_xy()
        color = getattr(getattr(self.model, "base_ptn", None), "color", "white")
        if self.diff_ctrl is not None:
            try:
                x, y = self.diff_ctrl.get_display_pattern(x, y)
            except Exception:
                pass
        if gsas_style:
            self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=color, marker='o',
                linestyle='None', ms=1.5)
        else:
            self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=color,
                lw=float(
                    self.widget.comboBox_BasePtnLineThickness.
                    currentText()))
        if self.diff_ctrl is not None and self.diff_ctrl.is_diff_mode_active():
            self.widget.mpl.canvas.ax_pattern.axhline(
                0.0, ls='--', c='tab:red', lw=0.8)
            return
        if not self.widget.checkBox_BgSub.isChecked():
            x_bg, y_bg = self._pattern_background_xy()
            self.widget.mpl.canvas.ax_pattern.plot(
                x_bg, y_bg, c=color, ls='--',
                lw=float(
                    self.widget.comboBox_BkgnLineThickness.
                    currentText()))

    def _plot_peakfit(self):
        self._peak_center_marker_artists = []
        self._selected_peak_marker_artists = []
        if not self.model.current_section_exist():
            return
        if self.model.current_section.peaks_exist():
            selected_row = self._get_selected_peak_parameter_row()
            for row, x_c in enumerate(self.model.current_section.get_peak_positions()):
                self._plot_peak_center_marker(x_c)
                if row == selected_row:
                    self._plot_selected_peak_marker(x_c)
        if self.model.current_section.fitted():
            bgsub = self.widget.checkBox_BgSub.isChecked()
            x_plot = self.model.current_section.x
            profiles = self.model.current_section.get_individual_profiles(
                bgsub=bgsub)
            for key, value in profiles.items():
                self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, value, ls='-', c=self.obj_color, lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))
            total_profile = self.model.current_section.get_fit_profile(
                bgsub=bgsub)
            residue = self.model.current_section.get_fit_residue(bgsub=bgsub)
            self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, total_profile, 'r-', lw=float(
                    self.widget.comboBox_BasePtnLineThickness.
                    currentText()))
            y_range = self.model.current_section.get_yrange(bgsub=bgsub)
            y_shift = y_range[0] - (y_range[1] - y_range[0]) * 0.05
            #(y_range[1] - y_range[0]) * 1.05
            self.widget.mpl.canvas.ax_pattern.fill_between(
                x_plot, self.model.current_section.get_fit_residue_baseline(
                    bgsub=bgsub) + y_shift, residue + y_shift, facecolor='r')
            """
            self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, residue + y_shift, 'r-')
            self.widget.mpl.canvas.ax_pattern.axhline(
                self.model.current_section.get_fit_residue_baseline(
                    bgsub=bgsub) + y_shift, c='r', ls='-', lw=0.5)
            """
        else:
            pass

    def _get_selected_peak_parameter_row(self):
        tables = [
            getattr(self.widget, "tableWidget_PkParams", None),
            getattr(self.widget, "tableWidget_PeakConstraints", None),
        ]
        if hasattr(self.widget, "tabWidget_PeakFit"):
            current_tab = self.widget.tabWidget_PeakFit.currentWidget()
            if current_tab == getattr(self.widget, "tab_PeakFitConstraints", None):
                tables.reverse()
        row = self._get_selected_row_from_table(tables[0])
        if row is not None:
            return row
        return self._get_selected_row_from_table(tables[1])

    def _get_selected_row_from_table(self, table):
        if table is None:
            return None
        rows = set()
        selection_model = table.selectionModel()
        if selection_model is not None:
            for index in selection_model.selectedRows():
                rows.add(index.row())
            if not rows:
                for index in selection_model.selectedIndexes():
                    rows.add(index.row())
        current_item = table.currentItem()
        current_row = table.currentRow()
        if current_item is not None and current_item.isSelected() and \
                current_row >= 0:
            rows.add(current_row)
        if len(rows) != 1:
            return None
        row = rows.pop()
        if row < 0:
            return None
        if not self.model.current_section_exist():
            return None
        if row >= self.model.current_section.get_number_of_peaks_in_queue():
            return None
        return row

    def _clear_selected_peak_marker(self):
        for artist in getattr(self, "_selected_peak_marker_artists", []):
            try:
                artist.remove()
            except Exception:
                pass
        self._selected_peak_marker_artists = []

    def _clear_peak_center_markers(self):
        for artist in getattr(self, "_peak_center_marker_artists", []):
            try:
                artist.remove()
            except Exception:
                pass
        self._peak_center_marker_artists = []

    def refresh_peakfit_markers(self):
        if not self.model.current_section_exist():
            return False
        self._clear_selected_peak_marker()
        self._clear_peak_center_markers()
        if not self.model.current_section.peaks_exist():
            self.widget.mpl.canvas.draw_idle()
            return True
        selected_row = self._get_selected_peak_parameter_row()
        for row, x_c in enumerate(self.model.current_section.get_peak_positions()):
            self._plot_peak_center_marker(x_c)
            if row == selected_row:
                self._plot_selected_peak_marker(x_c)
        self.widget.mpl.canvas.draw_idle()
        return True

    def refresh_selected_peak_marker(self):
        if not self.model.current_section_exist():
            return False
        if not self.model.current_section.peaks_exist():
            self._clear_selected_peak_marker()
            self.widget.mpl.canvas.draw_idle()
            return True
        selected_row = self._get_selected_peak_parameter_row()
        self._clear_selected_peak_marker()
        if selected_row is None:
            self.widget.mpl.canvas.draw_idle()
            return True
        positions = self.model.current_section.get_peak_positions()
        if selected_row >= len(positions):
            self.widget.mpl.canvas.draw_idle()
            return True
        self._plot_selected_peak_marker(positions[selected_row])
        self.widget.mpl.canvas.draw_idle()
        return True

    def _plot_selected_peak_marker(self, x_center):
        fitted = self.model.current_section.fitted()
        color = 'tab:cyan' if fitted else 'tab:orange'
        linestyle = '-' if fitted else '-'
        self._selected_peak_marker_artists = []
        line = self.widget.mpl.canvas.ax_pattern.axvline(
            x_center, c=color, ls=linestyle, lw=1.4, zorder=20)
        self._selected_peak_marker_artists.append(line)
        marker = self.widget.mpl.canvas.ax_pattern.plot(
            [x_center], [0.02], marker='^', markersize=7,
            color=color, linestyle='None',
            transform=self.widget.mpl.canvas.ax_pattern.get_xaxis_transform(),
            zorder=21, clip_on=False)[0]
        self._selected_peak_marker_artists.append(marker)
        if hasattr(self.widget.mpl.canvas, 'ax_cake') and \
                self.widget.checkBox_ShowCake.isChecked():
            line = self.widget.mpl.canvas.ax_cake.axvline(
                x_center, c=color, ls=linestyle, lw=1.2, zorder=20)
            self._selected_peak_marker_artists.append(line)
            marker = self.widget.mpl.canvas.ax_cake.plot(
                [x_center], [0.02], marker='^', markersize=7,
                color=color, linestyle='None',
                transform=self.widget.mpl.canvas.ax_cake.get_xaxis_transform(),
                zorder=21, clip_on=False)[0]
            self._selected_peak_marker_artists.append(marker)

    def update_dragged_peak_marker(self, x_center):
        artists = [
            artist for artist in getattr(
                self, "_selected_peak_marker_artists", [])
            if artist is not None
        ]
        if artists == []:
            try:
                self._plot_selected_peak_marker(x_center)
                self.widget.mpl.canvas.draw_idle()
                return True
            except Exception:
                return False
        for artist in artists:
            try:
                xdata = artist.get_xdata()
                if len(xdata) == 1:
                    artist.set_xdata([x_center])
                else:
                    artist.set_xdata([x_center, x_center])
            except Exception:
                return False
        self.widget.mpl.canvas.draw_idle()
        return True

    def _plot_peak_center_marker(self, x_center):
        line = self.widget.mpl.canvas.ax_pattern.axvline(
            x_center, c=self.obj_color, ls='-', lw=0.6, alpha=0.35,
            zorder=8)
        self._peak_center_marker_artists.append(line)
        if hasattr(self.widget.mpl.canvas, 'ax_cake') and \
                self.widget.checkBox_ShowCake.isChecked():
            line = self.widget.mpl.canvas.ax_cake.axvline(
                x_center, c=self._cake_peak_center_line_color(),
                ls='-', lw=0.6, alpha=0.35, zorder=8)
            self._peak_center_marker_artists.append(line)

    def _cake_peak_center_line_color(self):
        ax_cake = getattr(self.widget.mpl.canvas, "ax_cake", None)
        if ax_cake is None or not getattr(ax_cake, "images", None):
            return self.obj_color
        image = ax_cake.images[0]
        values = image.get_array()
        if values is None:
            return self.obj_color
        try:
            values = np.ma.masked_invalid(values)
            if np.ma.count(values) == 0:
                return self.obj_color
            sample_value = float(np.ma.median(values))
            rgba = image.cmap(image.norm(sample_value))
            luminance = (
                0.2126 * float(rgba[0]) +
                0.7152 * float(rgba[1]) +
                0.0722 * float(rgba[2]))
            return 'k' if luminance > 0.5 else 'white'
        except Exception:
            return self.obj_color

    def _plot_peakfit_in_gsas_style(self):
        # get all the highlights
        # iteratively run plot
        rows = self.widget.tableWidget_PkFtSections.selectionModel().\
            selectedRows()
        if rows == []:
            return
        else:
            selected_rows = [r.row() for r in rows]
        bgsub = self.widget.checkBox_BgSub.isChecked()
        data_limits = self._get_data_limits()
        y_shift = data_limits[2] - (data_limits[3] - data_limits[2]) * 0.05
        i = 0
        for section in self.model.section_lst:
            if i in selected_rows:
                x_plot = section.x
                total_profile = section.get_fit_profile(bgsub=bgsub)
                residue = section.get_fit_residue(bgsub=bgsub)
                self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, total_profile, 'r-', lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))
                self.widget.mpl.canvas.ax_pattern.fill_between(
                    x_plot, section.get_fit_residue_baseline(bgsub=bgsub) +
                    y_shift, residue + y_shift, facecolor='r')
            i += 1

    def _fits_tab_active(self):
        """
        Determine if the Fits tab is currently active.
        Avoid hardcoded tab indices because UI tab order can change.
        """
        if hasattr(self.widget, "tab_PkFt"):
            try:
                return self.widget.tabWidget.currentWidget() == self.widget.tab_PkFt
            except Exception:
                pass
        # Backward-compatible fallback.
        return self.widget.tabWidget.currentIndex() in (4, 5)

    def update(self, limits=None, gsas_style=False, cake_ylimits=None):
        if limits is not None:
            limits = tuple(limits)
        if cake_ylimits is not None:
            cake_ylimits = tuple(cake_ylimits)
        self._pending_update_args = (limits, bool(gsas_style), cake_ylimits)
        self._update_timer.start(self._update_delay_ms)

    def _flush_update_request(self):
        if self._pending_update_args is None:
            return
        if self._is_drawing or self._toolbar_active:
            self._update_timer.start(self._update_delay_ms)
            return
        limits, gsas_style, cake_ylimits = self._pending_update_args
        self._pending_update_args = None
        self._update_impl(limits=limits, gsas_style=gsas_style, cake_ylimits=cake_ylimits)
        if self._pending_update_args is not None:
            self._update_timer.start(self._update_delay_ms)

    def _update_impl(self, limits=None, gsas_style=False, cake_ylimits=None):
        """Updates the graph"""
        # ✅ Block updates during drawing OR toolbar interaction
        if self._is_drawing or self._toolbar_active:
            return
        
        # ✅ Pre-check conditions BEFORE setting flag
        if (not self.model.base_ptn_exist()) and \
                (not self.model.jcpds_exist()):
            self.widget.mpl.canvas.show_empty_state()
            return
        
        t_start = time.time()
        self.widget.setCursor(QtCore.Qt.WaitCursor)
        
        # ✅ Set drawing flag AFTER pre-checks
        self._is_drawing = True
        
        try:
            if limits is None:
                limits = self.widget.mpl.canvas.ax_pattern.axis()
            if cake_ylimits is None:
                # ✅ Check if ax_cake exists before accessing
                if hasattr(self.widget.mpl.canvas, 'ax_cake'):
                    c_limits = self.widget.mpl.canvas.ax_cake.axis()
                    cake_ylimits = c_limits[2:4]
                else:
                    cake_ylimits = (-180, 180)
            
            if self.widget.checkBox_ShowCake.isChecked() and \
                    self.model.diff_img_exist():
                new_height = self.widget.horizontalSlider_CakeAxisSize.value()
                self.widget.mpl.canvas.resize_axes(new_height)
                self._plot_cake()
            else:
                self.widget.mpl.canvas.resize_axes(1)
            
            self._set_nightday_view()
            self._apply_pattern_background_style()
            
            if self.model.base_ptn_exist():
                title_font_size = 12
                if hasattr(self.widget, "spinBox_TitleFontSize"):
                    try:
                        title_font_size = int(self.widget.spinBox_TitleFontSize.value())
                    except Exception:
                        title_font_size = 12
                max_title_chars = 140
                if hasattr(self.widget, "spinBox_TitleMaxLength"):
                    try:
                        max_title_chars = int(self.widget.spinBox_TitleMaxLength.value())
                    except Exception:
                        max_title_chars = 140

                if self.widget.checkBox_ShortPlotTitle.isChecked():
                    raw_title = os.path.basename(self._display_pattern_filename())
                else:
                    raw_title = self._display_pattern_filename()

                truncate_middle = True
                if hasattr(self.widget, "checkBox_TitleTruncateMiddle"):
                    truncate_middle = bool(
                        self.widget.checkBox_TitleTruncateMiddle.isChecked())
                title = truncate_title_by_chars(
                    raw_title, max_title_chars, truncate_middle=truncate_middle)
                fig_width_pixels = \
                    self.widget.mpl.canvas.fig.get_size_inches()[0] * \
                    self.widget.mpl.canvas.fig.dpi
                max_width = 0.85 * fig_width_pixels
                title = truncate_title(title, title_font_size, max_width)
                
                self.widget.mpl.canvas.fig.suptitle(
                    title, color=self.obj_color, fontsize=title_font_size)
                
                self._plot_diffpattern(gsas_style)
                
                if self.model.waterfall_exist():
                    self._plot_waterfallpatterns()
            
            if self._fits_tab_active():
                if gsas_style:
                    self._plot_peakfit_in_gsas_style()
                else:
                    self._plot_peakfit()
            
            self.widget.mpl.canvas.ax_pattern.set_xlim(limits[0], limits[1])
            if hasattr(self.widget.mpl.canvas, 'ax_cake'):
                self.widget.mpl.canvas.ax_cake.set_xlim(limits[0], limits[1])
            
            if not self.widget.checkBox_AutoY.isChecked():
                self.widget.mpl.canvas.ax_pattern.set_ylim(limits[2], limits[3])
            
            # ✅ Check if ax_cake exists before setting ylim
            if hasattr(self.widget.mpl.canvas, 'ax_cake'):
                self.widget.mpl.canvas.ax_cake.set_ylim(cake_ylimits)
            
            if self.model.jcpds_exist():
                self._plot_jcpds(limits)
                if not self.widget.checkBox_Intensity.isChecked():
                    new_low_limit = -1.1 * limits[3] * \
                        self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
                    self.widget.mpl.canvas.ax_pattern.set_ylim(
                        new_low_limit, limits[3])
            
            if self.widget.checkBox_ShowLargePnT.isChecked():
                label_p_t = "{0: 5.1f} GPa\n{1: 4.0f} K".\
                    format(self.widget.doubleSpinBox_Pressure.value(),
                        self.widget.doubleSpinBox_Temperature.value())
                self.widget.mpl.canvas.ax_pattern.text(
                    0.01, 0.98, label_p_t, horizontalalignment='left',
                    verticalalignment='top',
                    transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                    fontsize=int(
                        self.widget.comboBox_PnTFontSize.currentText()))
            
            xlabel = "Two Theta (degrees), {:6.4f} \u212B".\
                format(self.widget.doubleSpinBox_SetWavelength.value())
            self.widget.mpl.canvas.ax_pattern.set_xlabel(xlabel)
            
            self.widget.mpl.canvas.ax_pattern.format_coord = \
                lambda x, y: \
                "\n 2\u03B8={0:.3f}\u00B0, I={1:.4e}, d-sp={2:.4f}\u212B".\
                format(x, y,
                    self.widget.doubleSpinBox_SetWavelength.value()
                    / 2. / np.sin(np.radians(x / 2.)))
            
            # ✅ Only set cake format_coord if ax_cake exists
            if hasattr(self.widget.mpl.canvas, 'ax_cake'):
                """
                self.widget.mpl.canvas.ax_cake.format_coord = \
                    lambda x, y: \
                    "\n 2\u03B8={0:.3f}\u00B0, azi={1:.1f}, d-sp={2:.4f}\u212B".\
                    format(x, y,  
                        self.widget.doubleSpinBox_SetWavelength.value()
                        / 2. / np.sin(np.radians(x / 2.)))
                """
                self.widget.mpl.canvas.ax_cake.format_coord = self._format_coord_x_y_z_dsp
            
            self._ensure_vertical_cursor_artists()
            if not self.widget.checkBox_LongCursor.isChecked():
                self.clear_vertical_cursor_position()
            
            # ✅ Draw canvas (deferred to Qt event loop)
            QtCore.QTimer.singleShot(0, self.widget.mpl.canvas.draw)
            
            print(str(datetime.datetime.now())[:-7], 
                ": Plot takes {0:.2f}s".format(time.time() - t_start))
        
        except Exception as e:
            print(f"Error during plot update: {e}")
            import traceback
            traceback.print_exc()
        
        # ✅ Always clear flag and restore cursor
        finally:
            self._is_drawing = False
            self.widget.unsetCursor()
            if self._pending_update_args is not None:
                self._update_timer.start(0)

    def _format_coord_x_y_z_dsp(self, x, y):
        """
        Read 2theta, azimuthal angle, intensity, and d-spacing from the image
        
        :param x: 2 theta angle
        :param y: azimuthal angle
        """
        ax = self.widget.mpl.canvas.ax_cake

        # compute d-spacing from x (2-theta)
        try:
            dsp = (self.widget.doubleSpinBox_SetWavelength.value()
                   / 2.0 / np.sin(np.radians(x / 2.0)))
        except Exception:
            dsp = None

        # If no image on the axis, return x,y,dsp only
        if not ax.images:
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)

        img = ax.images[0]
        data = img.get_array()
        if data is None:
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)

        # extent -> map data coords to pixel indices
        xmin, xmax, ymin, ymax = img.get_extent()
        if xmax == xmin or ymax == ymin:
            # degenerate extent
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)

        # ensure 2D image
        try:
            ny, nx = data.shape
        except Exception:
            # not a 2D image
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)

        # fractional positions (0..nx-1, 0..ny-1)
        fx = (x - xmin) / (xmax - xmin) * (nx - 1)
        fy = (y - ymin) / (ymax - ymin) * (ny - 1)

        # nearest-neighbor
        col = int(round(fx))
        row = int(round(fy))

        # handle origin
        origin = getattr(img, 'origin', None)
        if origin == 'upper':
            row = (ny - 1) - row

        # clamp & check bounds
        if col < 0 or col >= nx or row < 0 or row >= ny:
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)

        # read intensity, handle masked/invalid
        try:
            if np.ma.isMaskedArray(data):
                mask = data.mask
                if mask is not None and mask.shape == data.shape and mask[row, col]:
                    z_text = "NA"
                else:
                    z_val = data.data[row, col]
                    if np.isnan(z_val) or np.isinf(z_val):
                        z_text = "(invalid)"
                    else:
                        z_text = "{:.0f}".format(float(z_val))
            else:
                z_val = data[row, col]
                if isinstance(z_val, (float, np.floating)) and (np.isnan(z_val) or np.isinf(z_val)):
                    z_text = "(invalid)"
                else:
                    z_text = "{:.0f}".format(float(z_val))
        except Exception:
            z_text = "NA"

        # format final string: x, y, z, d-sp
        if dsp is None:
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I={}, d-sp=NA".format(x, y, z_text)
        return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I={}, d-sp={:.4f}\u212B".format(x, y, z_text, dsp)

from matplotlib.textpath import TextPath

def truncate_title_by_chars(title, max_chars, truncate_middle=True):
    if title is None:
        return ""
    title = str(title)
    try:
        max_chars = int(max_chars)
    except Exception:
        max_chars = 140
    if max_chars < 20:
        max_chars = 20
    if len(title) <= max_chars:
        return title
    if not truncate_middle:
        tail_len = max_chars - 4
        if tail_len < 1:
            tail_len = 1
        return "... " + title[-tail_len:]
    head = int(max_chars * 0.45)
    tail = max_chars - head - 5
    if tail < 1:
        tail = 1
    return title[:head] + " ... " + title[-tail:]

def truncate_title(title, font_size, max_width):
    """Fast truncation without expensive TextPath calculations"""
    # ✅ Simple character-based truncation
    # Approximate: average character is ~7 pixels at size 12
    if isinstance(font_size, str):
        font_size = 12  # Default
    else:
        font_size = float(font_size)
    
    # Rough estimate of characters that fit
    approx_chars = int(max_width / (font_size * 0.6))
    
    if len(title) <= approx_chars:
        return title
    
    # Keep first 30% and last 50% of available space
    first_chars = int(approx_chars * 0.3)
    last_chars = int(approx_chars * 0.5)
    
    if first_chars + last_chars + 5 >= len(title):
        return title
    
    return title[:first_chars] + " ... " + title[-last_chars:]
