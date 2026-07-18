import os
import time
import datetime
import numpy as np
import numpy.ma as ma
from matplotlib import colors as mcolors
#from matplotlib.widgets import MultiCursor
#import matplotlib.transforms as transforms
#import matplotlib.colors as colors
#import matplotlib.patches as patches
#from matplotlib.textpath import TextPath
#import matplotlib.pyplot as plt
from qtpy import QtWidgets
from qtpy import QtCore
from ..ds_jcpds import convert_tth
from ..ds_section.section import normalize_peak_phase_name
from ..model.azimuthal_integration import (
    normalize_range,
    normalize_ranges,
    provenance_for_chi,
)


def _coordinate_edges(centers):
    """Return pixel edges for a monotonic array of pixel-center coordinates."""
    values = np.asarray(centers, dtype=float).ravel()
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Coordinate centers must be finite and non-empty.")
    if values.size == 1:
        return np.asarray([values[0] - 0.5, values[0] + 0.5])
    deltas = np.diff(values)
    if np.any(deltas == 0) or not (np.all(deltas > 0) or np.all(deltas < 0)):
        raise ValueError("Coordinate centers must be strictly monotonic.")
    edges = np.empty(values.size + 1, dtype=float)
    edges[1:-1] = values[:-1] + 0.5 * deltas
    edges[0] = values[0] - 0.5 * deltas[0]
    edges[-1] = values[-1] + 0.5 * deltas[-1]
    return edges


def _nearest_coordinate_index(centers, value):
    """Find the nearest center index for ascending or descending coordinates."""
    values = np.asarray(centers, dtype=float).ravel()
    if values.size == 0 or not np.isfinite(value):
        return None
    ascending = values[-1] >= values[0]
    search_values = values if ascending else values[::-1]
    pos = int(np.searchsorted(search_values, value, side="left"))
    if pos <= 0:
        index = 0
    elif pos >= search_values.size:
        index = search_values.size - 1
    elif abs(value - search_values[pos - 1]) <= abs(search_values[pos] - value):
        index = pos - 1
    else:
        index = pos
    return index if ascending else values.size - 1 - index


def _coordinates_are_uniform(centers, *, rtol=1e-7, atol=1e-12):
    values = np.asarray(centers, dtype=float).ravel()
    if values.size < 3:
        return True
    deltas = np.diff(values)
    return bool(np.allclose(deltas, deltas[0], rtol=rtol, atol=atol))


def _azimuth_shift_rows(chi_centers, angle_degrees):
    """Convert an angular Cake shift to rows using the actual azimuth spacing."""
    values = np.asarray(chi_centers, dtype=float).ravel()
    if values.size < 2 or not np.isfinite(angle_degrees):
        return 0
    spacing = np.diff(values)
    spacing = np.abs(spacing[np.isfinite(spacing) & (spacing != 0)])
    if spacing.size == 0:
        return 0
    return int(np.rint(float(angle_degrees) / float(np.median(spacing))))


def _bragg_dspacing(two_theta_degrees, wavelength):
    """Return d spacing for a physically valid two-theta coordinate."""
    try:
        two_theta = float(two_theta_degrees)
        wavelength = float(wavelength)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(two_theta) or not np.isfinite(wavelength) or wavelength <= 0:
        return None
    if two_theta <= 0.0 or two_theta > 180.0:
        return None
    sine = float(np.sin(np.deg2rad(two_theta / 2.0)))
    if not np.isfinite(sine) or sine <= np.finfo(float).eps:
        return None
    return wavelength / (2.0 * sine)


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
        self._canvas_draw_scheduled = False
        self._pending_draw_profile = None
        self._after_draw_callbacks = []
        self._last_auto_cake_filename = None
        self._update_timer = QtCore.QTimer(self.widget)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._flush_update_request)
        self._vcursor_pattern = None
        self._vcursor_cake = None
        self._peak_center_marker_artists = []
        self._selected_peak_marker_artists = []
        self._peakfit_overlay_artists = []
        self._jcpds_overlay_artists = []
        self._jcpds_hkl_artists = []
        self._section_selection_artists = []
        self._background_selection_artists = []
        self._cake_overlay_artists = []
        self._waterfall_artists = []
        self._pnt_artist = None
        self._derived_label_visible = False
        self._cake_tth_centers = None
        self._cake_chi_centers = None
        self._cake_artist = None
        self._cake_display_data = None
        self._cake_data_cache_key = None
        self._cake_data_cache = None
        self._cake_source_stats_key = None
        self._cake_source_max = None
        self._waterfall_transform_cache = {}
        
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

    def shutdown(self):
        if getattr(self, "_shutdown_done", False):
            return
        self._shutdown_done = True

        try:
            if self._update_timer is not None:
                self._update_timer.stop()
        except Exception:
            pass

        self._pending_update_args = None
        self._canvas_draw_scheduled = False
        self._pending_draw_profile = None
        self._after_draw_callbacks = []
        self._cached_title = None
        self._cached_filename = None
        self._pnt_artist = None
        self._vcursor_pattern = None
        self._vcursor_cake = None
        self._peak_center_marker_artists = []
        self._selected_peak_marker_artists = []
        self._peakfit_overlay_artists = []
        self._jcpds_overlay_artists = []
        self._jcpds_hkl_artists = []
        self._section_selection_artists = []
        self._background_selection_artists = []
        self._cake_overlay_artists = []
        self._waterfall_artists = []
        self._cake_artist = None
        self._cake_display_data = None
        self._cake_data_cache = None
        self._waterfall_transform_cache = {}

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
                getattr(self._vcursor_pattern, "axes", None) is not ax_pattern or \
                self._vcursor_pattern not in ax_pattern.lines:
            self._vcursor_pattern = ax_pattern.axvline(
                0.0, color='r', lw=lw_value, ls='--', visible=False)
        else:
            self._vcursor_pattern.set_linewidth(lw_value)
        use_cake = hasattr(self.widget.mpl.canvas, 'ax_cake') and \
            self.widget.checkBox_ShowCake.isChecked()
        if use_cake:
            ax_cake = self.widget.mpl.canvas.ax_cake
            if self._vcursor_cake is None or \
                    getattr(self._vcursor_cake, "axes", None) is not ax_cake or \
                    self._vcursor_cake not in ax_cake.lines:
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
        if changed and not self._is_drawing:
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

    def _display_pattern_is_azimuth_derived(self):
        provenance = self._current_pattern_provenance()
        return provenance.get("source_kind") == "azimuthal_integration"

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
            self._track_cake_overlay_artist(
                self.widget.mpl.canvas.ax_cake.add_patch(rect))
            show_labels = getattr(self.widget, "checkBox_ShowCakeLabels", None)
            if idx == 0 and show_labels is not None and show_labels.isChecked():
                self._track_cake_overlay_artist(
                    self.widget.mpl.canvas.ax_cake.text(
                    tth_max,
                    azi_max,
                    "derived 1D",
                    color=color,
                    horizontalalignment="right",
                    verticalalignment="bottom"))

    def _plot_derived_pattern_label(self):
        if not self._display_pattern_is_azimuth_derived():
            return False
        ax_pattern = self.widget.mpl.canvas.ax_pattern
        ax_pattern.text(
            0.015, 0.985, "Azi-derived",
            transform=ax_pattern.transAxes,
            ha='left', va='top',
            fontsize=11,
            color='white',
            bbox=dict(
                boxstyle='round,pad=0.25',
                facecolor='#b22222',
                edgecolor='#8f1b1b',
                linewidth=1.0,
                alpha=0.95,
            ),
            zorder=20,
        )
        return True

    def _plot_selected_derived_chi_preview_overlay(
            self, tth_min, tth_max, chi_min, chi_max):
        import matplotlib.patches as patches

        ranges = getattr(self.widget, "_cake_azi_selected_rois", None)
        chi_path = getattr(self.widget, "_cake_azi_selected_derived_chi_path", None)
        saved_shift = getattr(self.widget, "_cake_azi_selected_derived_chi_shift", None)
        if not ranges or not chi_path:
            return
        if hasattr(self.widget, "tab_Cake1") and \
                self.widget.tabWidget.currentWidget() != self.widget.tab_Cake1:
            return
        try:
            current_filename = self._display_pattern_filename()
        except Exception:
            current_filename = None
        if current_filename and chi_path:
            try:
                same_path = os.path.normcase(os.path.abspath(current_filename)) == \
                    os.path.normcase(os.path.abspath(chi_path))
            except Exception:
                same_path = False
            if same_path:
                return
        if saved_shift is None:
            try:
                saved_shift = float(self.widget.spinBox_AziShift.value())
            except Exception:
                saved_shift = 0.0
        color = "#ff9f1a"
        for idx, range_info in enumerate(normalize_ranges(ranges)):
            overlay_ranges = self._shift_azimuth_range_to_current_view(
                range_info, saved_shift, chi_min, chi_max)
            for jdx, (azi_min, azi_max) in enumerate(overlay_ranges):
                if azi_max <= azi_min:
                    continue
                rect = patches.Rectangle(
                    (tth_min, azi_min),
                    tth_max - tth_min,
                    azi_max - azi_min,
                    linewidth=1.8,
                    edgecolor=color,
                    facecolor=color,
                    alpha=0.30,
                )
                self.widget.mpl.canvas.ax_cake.add_patch(rect)
                if idx == 0 and jdx == 0:
                    show_labels = getattr(self.widget, "checkBox_ShowCakeLabels", None)
                    if show_labels is not None and show_labels.isChecked():
                        self.widget.mpl.canvas.ax_cake.text(
                            tth_max,
                            azi_max,
                            "selected ROI preview",
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
        y_min = y.min()
        y_max = y.max()

        if (hasattr(self.model, "waterfall_exist")
                and self.model.waterfall_exist()
                and hasattr(self.widget, "checkBox_ShowWaterfall")
                and self.widget.checkBox_ShowWaterfall.isChecked()):
            j = 0
            for pattern in self.model.waterfall_ptn[::-1]:
                if pattern.display:
                    j += 1
                    if self.widget.checkBox_BgSub.isChecked():
                        y_base_ref = self.model.base_ptn.y_bgsub
                        y_pattern = pattern.y_bgsub
                    else:
                        y_base_ref = self.model.base_ptn.y_raw
                        y_pattern = pattern.y_raw
                    ygap = self.widget.horizontalSlider_WaterfallGaps.value() * \
                        y_base_ref.max() * float(j) / 100.
                    if self.widget.checkBox_IntNorm.isChecked():
                        y_scaled = y_pattern / y_pattern.max() * y_base_ref.max()
                    else:
                        y_scaled = y_pattern
                    y_min = min(y_min, (y_scaled + ygap).min())
                    y_max = max(y_max, (y_scaled + ygap).max())

        return (x.min(), x.max(),
                y_min - (y_max - y_min) * y_margin,
                y_max + (y_max - y_min) * y_margin)


    
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

        def _clear_failed_cake_state():
            self._cake_artist = None
            self._cake_display_data = None
            self._clear_cake_overlay_artists()
            hist_widget = getattr(self.widget, "cake_hist_widget", None)
            if hist_widget is not None:
                if hasattr(hist_widget, "clear"):
                    hist_widget.clear()
                elif hasattr(hist_widget, "_draw_empty_state"):
                    hist_widget._draw_empty_state()

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
            if cake.shape != (chi_arr.size, tth_arr.size):
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
            _clear_failed_cake_state()
            return False
        int_plot, tth_cake, chi_cake = coerced
        self._clear_cake_overlay_artists()
        int_plot = ma.array(int_plot, copy=False)
        source_stats_key = (
            id(intensity_cake), id(ma.getdata(int_plot)),
            id(ma.getmask(int_plot)), tuple(int_plot.shape))
        if source_stats_key != self._cake_source_stats_key:
            finite_source = np.asarray(
                ma.filled(int_plot, np.nan), dtype=float).ravel()
            finite_source = finite_source[np.isfinite(finite_source)]
            self._cake_source_max = (
                float(finite_source.max()) if finite_source.size else None)
            self._cake_source_stats_key = source_stats_key
        cake_max = self._cake_source_max
        if cake_max is not None and np.isfinite(cake_max) and cake_max > 0:
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

        # Keep image rows/columns aligned with ascending physical coordinates.
        reverse_tth = bool(tth_cake.size > 1 and tth_cake[-1] < tth_cake[0])
        reverse_chi = bool(chi_cake.size > 1 and chi_cake[-1] < chi_cake[0])
        if reverse_tth:
            tth_cake = tth_cake[::-1]
            int_plot = int_plot[:, ::-1]
        if reverse_chi:
            chi_cake = chi_cake[::-1]
            int_plot = int_plot[::-1, :]

        # Apply azimuthal shift after diff subtraction so the same shift is
        # effectively applied to both current and reference cake images.
        mid_angle = self.widget.spinBox_AziShift.value()
        row_shift = 0
        if mid_angle != 0 and int_plot.ndim == 2 and int_plot.shape[0] > 1:
            row_shift = _azimuth_shift_rows(chi_cake, mid_angle)
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
        cache_key = None
        if not diff_mode:
            cache_key = (
                source_stats_key, reverse_tth, reverse_chi, row_shift)
        if cache_key is not None and cache_key == self._cake_data_cache_key:
            int_new, finite_values, data_signature = self._cake_data_cache
        else:
            zero_mask = np.asarray(ma.filled(zero_mask, False), dtype=bool)
            filled_plot = np.asarray(ma.filled(int_plot, np.nan), dtype=float)
            base_mask = ma.getmaskarray(int_plot)
            invalid_mask = ~np.isfinite(filled_plot)
            combined_mask = zero_mask | base_mask | invalid_mask
            int_new = ma.masked_where(
                combined_mask, filled_plot, copy=False)
            finite_values = np.asarray(int_new.compressed(), dtype=float)
            data_signature = None
            if finite_values.size:
                data_signature = (
                    int(finite_values.size), float(finite_values.min()),
                    float(finite_values.max()), float(finite_values.mean()))
            if cache_key is not None:
                self._cake_data_cache_key = cache_key
                self._cake_data_cache = (
                    int_new, finite_values, data_signature)

        if hist_widget is not None:
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


        try:
            tth_edges = _coordinate_edges(tth_cake)
            chi_edges = _coordinate_edges(chi_cake)
        except ValueError:
            _clear_failed_cake_state()
            return False
        self._cake_tth_centers = np.asarray(tth_cake, dtype=float)
        self._cake_chi_centers = np.asarray(chi_cake, dtype=float)
        imshow_kwargs = {
            "origin": "lower",
            "extent": [tth_edges[0], tth_edges[-1],
                       chi_edges[0], chi_edges[-1]],
            "aspect": "auto",
            "cmap": cmap,
            "interpolation": "nearest",
        }
        if norm is None:
            imshow_kwargs["vmin"] = climits[0]
            imshow_kwargs["vmax"] = climits[1]
        else:
            imshow_kwargs["norm"] = norm
        ax_cake = self.widget.mpl.canvas.ax_cake
        if _coordinates_are_uniform(tth_cake) and \
                _coordinates_are_uniform(chi_cake):
            self._cake_artist = ax_cake.imshow(int_new, **imshow_kwargs)
        else:
            mesh_kwargs = {
                "cmap": cmap,
                "shading": "flat",
                "rasterized": True,
            }
            if norm is None:
                mesh_kwargs["vmin"] = climits[0]
                mesh_kwargs["vmax"] = climits[1]
            else:
                mesh_kwargs["norm"] = norm
            self._cake_artist = ax_cake.pcolormesh(
                tth_edges, chi_edges, int_new, **mesh_kwargs)
        self._cake_display_data = int_new
        if hist_widget is not None:
            hist_widget.set_data(
                int_new, vmin=float(climits[0]), vmax=float(climits[1]),
                data_token=cache_key, finite_values=finite_values,
                data_signature=data_signature)

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
                self._track_cake_overlay_artist(
                    self.widget.mpl.canvas.ax_cake.add_patch(rect))
                self._track_cake_overlay_artist(
                    self.widget.mpl.canvas.ax_cake.add_patch(rect1))
                if self.widget.checkBox_ShowCakeLabels.isChecked():
                    self._track_cake_overlay_artist(
                        self.widget.mpl.canvas.ax_cake.text(
                            tth[1], azi[1], note, color=self.obj_color))
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
                self._track_cake_overlay_artist(
                    self.widget.mpl.canvas.ax_cake.add_patch(rect))
        self._plot_selected_derived_chi_preview_overlay(
            tth_min, tth_max, chi_min, chi_max)
        return True

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

    def _track_jcpds_artist(self, artist, hkl=False, phase_index=None,
                            base_alpha=None, base_color=None):
        if artist is not None:
            try:
                artist.set_gid("peakpo_jcpds_hkl" if hkl else "peakpo_jcpds")
            except Exception:
                pass
            artist._peakpo_jcpds_overlay = True
            artist._peakpo_jcpds_hkl = bool(hkl)
            artist._peakpo_jcpds_phase_index = phase_index
            artist._peakpo_jcpds_base_alpha = base_alpha
            artist._peakpo_jcpds_base_color = base_color
            self._jcpds_overlay_artists.append(artist)
            if hkl:
                self._jcpds_hkl_artists.append(artist)
        return artist

    def _get_selected_jcpds_rows(self):
        table = getattr(self.widget, "tableWidget_JCPDS", None)
        if table is None:
            return set()
        selection_model = table.selectionModel()
        if selection_model is None:
            return set()
        rows = {index.row() for index in selection_model.selectedRows()}
        if not rows:
            for index in selection_model.selectedIndexes():
                rows.add(index.row())
        return rows

    def _get_active_cellfit_jcpds_rows(self):
        combo = getattr(self.widget, "comboBox_PeakFitLabels", None)
        if combo is None:
            return set()
        if not hasattr(self.widget, "tabWidget_4") or \
                not hasattr(self.widget, "tabWidget_4Page2"):
            return set()
        try:
            if self.widget.tabWidget_4.currentWidget() != self.widget.tabWidget_4Page2:
                return set()
        except Exception:
            return set()
        phase_name = normalize_peak_phase_name(combo.currentText())
        if not phase_name:
            return set()
        rows = set()
        for idx, phase in enumerate(getattr(self.model, "jcpds_lst", [])):
            if normalize_peak_phase_name(getattr(phase, "name", "")) == phase_name:
                rows.add(idx)
        return rows

    def _get_jcpds_emphasis_rows(self):
        selected_rows = self._get_selected_jcpds_rows()
        if selected_rows:
            return selected_rows
        return self._get_active_cellfit_jcpds_rows()

    def _get_selected_waterfall_rows(self):
        table = getattr(self.widget, "tableWidget_wfPatterns", None)
        if table is None:
            return set()
        selection_model = table.selectionModel()
        if selection_model is None:
            return set()
        rows = {index.row() for index in selection_model.selectedRows()}
        if not rows:
            for index in selection_model.selectedIndexes():
                rows.add(index.row())
        return rows

    def _get_waterfall_emphasis_rows(self):
        selected_rows = self._get_selected_waterfall_rows()
        if not selected_rows:
            return set()
        emphasis_rows = set()
        for row in selected_rows:
            if 0 <= row < len(self.model.waterfall_ptn):
                pattern = self.model.waterfall_ptn[row]
                if getattr(pattern, "display", False):
                    emphasis_rows.add(row)
        return emphasis_rows

    def _jcpds_bar_alphas(self):
        """Return independent base alpha values for Pattern and Cake bars."""
        pattern = 1.0
        cake = 0.6
        if hasattr(self.widget, "doubleSpinBox_JCPDS_ptn_Alpha"):
            try:
                pattern = float(self.widget.doubleSpinBox_JCPDS_ptn_Alpha.value())
            except Exception:
                pass
        if hasattr(self.widget, "doubleSpinBox_JCPDS_CakeBarAlpha"):
            try:
                cake = float(self.widget.doubleSpinBox_JCPDS_CakeBarAlpha.value())
            except Exception:
                pass
        return (min(1.0, max(0.0, pattern)),
                min(1.0, max(0.0, cake)))

    def _jcpds_dimming_factor(self):
        value = 0.2
        if hasattr(self.widget, "doubleSpinBox_JCPDS_cake_Alpha"):
            try:
                value = float(self.widget.doubleSpinBox_JCPDS_cake_Alpha.value())
            except Exception:
                pass
        return min(1.0, max(0.0, value))

    def _get_jcpds_plot_alpha(self, phase_index, emphasis_rows,
                              base_alpha=1.0):
        """Apply phase dimming on top of a Pattern or Cake bar alpha."""
        alpha = min(1.0, max(0.0, float(base_alpha)))
        if not emphasis_rows:
            return alpha
        phase = None
        if 0 <= phase_index < len(self.model.jcpds_lst):
            phase = self.model.jcpds_lst[phase_index]
        if phase is None or not getattr(phase, "display", False):
            return alpha
        if phase_index in emphasis_rows:
            return alpha
        return alpha * self._jcpds_dimming_factor()

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

    def clear_jcpds_overlay(self):
        self._clear_jcpds_overlay_artists()
        self.widget.mpl.canvas.draw_idle()

    def rebuild_jcpds_overlay(self):
        self._clear_jcpds_overlay_artists()
        self.refresh_jcpds_overlay()

    def _clear_section_selection_artists(self):
        for artist in list(self._section_selection_artists):
            try:
                artist.remove()
            except Exception:
                pass
        self._section_selection_artists = []

    def _clear_background_selection_artists(self):
        for artist in list(self._background_selection_artists):
            try:
                artist.remove()
            except Exception:
                pass
        self._background_selection_artists = []

    def _track_cake_overlay_artist(self, artist):
        if artist is not None:
            self._cake_overlay_artists.append(artist)
        return artist

    def _clear_cake_overlay_artists(self):
        for artist in list(self._cake_overlay_artists):
            try:
                artist.remove()
            except Exception:
                pass
        self._cake_overlay_artists = []

    def _get_selected_section_rows(self):
        table = getattr(self.widget, "tableWidget_PkFtSections", None)
        if table is None:
            return []
        selection_model = table.selectionModel()
        if selection_model is None:
            return []
        rows = [index.row() for index in selection_model.selectedRows()]
        if not rows:
            rows = [index.row() for index in selection_model.selectedIndexes()]
        return sorted(set(r for r in rows if r is not None and r >= 0))

    def _peakfit_sections_tab_active(self):
        if not hasattr(self.widget, "tabWidget_PeakFit"):
            return False
        try:
            return self.widget.tabWidget_PeakFit.currentWidget() == \
                getattr(self.widget, "tab_PeakFitSection", None)
        except Exception:
            return False

    def _sync_overlay_rectangles(self, artists, specs):
        import matplotlib.patches as patches
        reusable = (
            len(artists) == len(specs) and
            all(
                artist is not None and artist.axes == spec["axes"]
                for artist, spec in zip(artists, specs)
            )
        )
        if reusable:
            for artist, spec in zip(artists, specs):
                artist.set_xy((spec["xmin"], spec["ymin"]))
                artist.set_width(spec["xmax"] - spec["xmin"])
                artist.set_height(spec["ymax"] - spec["ymin"])
                artist.set_linewidth(spec["linewidth"])
                artist.set_edgecolor(spec["edgecolor"])
                artist.set_facecolor(spec["facecolor"])
                artist.set_alpha(spec["alpha"])
                artist.set_zorder(spec["zorder"])
            return artists
        for artist in list(artists):
            try:
                artist.remove()
            except Exception:
                pass
        new_artists = []
        for spec in specs:
            rect = patches.Rectangle(
                (spec["xmin"], spec["ymin"]),
                spec["xmax"] - spec["xmin"],
                spec["ymax"] - spec["ymin"],
                linewidth=spec["linewidth"],
                edgecolor=spec["edgecolor"],
                facecolor=spec["facecolor"],
                alpha=spec["alpha"],
                zorder=spec["zorder"],
            )
            spec["axes"].add_patch(rect)
            new_artists.append(rect)
        return new_artists

    def _plot_selected_section_overlays(self):
        if not self._peakfit_sections_tab_active():
            self._clear_section_selection_artists()
            return
        if self.model.current_section_exist() and \
                self.model.current_section.get_number_of_peaks_in_queue() > 0:
            self._clear_section_selection_artists()
            return
        selected_rows = self._get_selected_section_rows()
        if not selected_rows:
            self._clear_section_selection_artists()
            return
        if not hasattr(self.widget.mpl.canvas, "ax_pattern"):
            self._clear_section_selection_artists()
            return
        pattern_ax = self.widget.mpl.canvas.ax_pattern
        pattern_ylim = pattern_ax.get_ylim()
        specs = []
        for row in selected_rows:
            if row >= len(self.model.section_lst):
                continue
            section = self.model.section_lst[row]
            x = getattr(section, "x", None)
            if x is None or len(x) == 0:
                continue
            xmin = float(np.min(x))
            xmax = float(np.max(x))
            specs.append({
                "axes": pattern_ax,
                "xmin": xmin,
                "xmax": xmax,
                "ymin": pattern_ylim[0],
                "ymax": pattern_ylim[1],
                "linewidth": 1.2,
                "edgecolor": "#ff6f00",
                "facecolor": "#ff9800",
                "alpha": 0.25,
                "zorder": 6,
            })
        if hasattr(self.widget.mpl.canvas, "ax_cake"):
            cake_ax = self.widget.mpl.canvas.ax_cake
            cake_ylim = cake_ax.get_ylim()
            for row in selected_rows:
                if row >= len(self.model.section_lst):
                    continue
                section = self.model.section_lst[row]
                x = getattr(section, "x", None)
                if x is None or len(x) == 0:
                    continue
                xmin = float(np.min(x))
                xmax = float(np.max(x))
                specs.append({
                    "axes": cake_ax,
                    "xmin": xmin,
                    "xmax": xmax,
                    "ymin": cake_ylim[0],
                    "ymax": cake_ylim[1],
                    "linewidth": 1.2,
                    "edgecolor": "#ff6f00",
                    "facecolor": "#ff9800",
                    "alpha": 0.25,
                    "zorder": 6,
                })
        self._section_selection_artists = self._sync_overlay_rectangles(
            self._section_selection_artists, specs)

    def refresh_section_selection_overlay(self):
        if not self._peakfit_sections_tab_active():
            self._clear_section_selection_artists()
            self.widget.mpl.canvas.draw_idle()
            return
        if self._is_drawing or self._toolbar_active:
            self.update()
            return
        self._clear_section_selection_artists()
        self._plot_selected_section_overlays()
        self.widget.mpl.canvas.draw_idle()

    def _get_selected_background_rows(self):
        table = getattr(self.widget, "tableWidget_BGAnchorRanges", None)
        if table is None:
            return []
        selection_model = table.selectionModel()
        if selection_model is None:
            return []
        rows = [index.row() for index in selection_model.selectedRows()]
        if not rows:
            rows = [index.row() for index in selection_model.selectedIndexes()]
        return sorted(set(r for r in rows if r is not None and r >= 0))

    def _plot_selected_background_overlays(self):
        if not self.model.current_section_exist():
            self._clear_background_selection_artists()
            return
        anchors = getattr(self.model.current_section, "background_anchor_ranges", [])
        if not anchors:
            self._clear_background_selection_artists()
            return
        selected_rows = self._get_selected_background_rows()
        if not selected_rows:
            self._clear_background_selection_artists()
            return
        if not hasattr(self.widget.mpl.canvas, "ax_pattern"):
            self._clear_background_selection_artists()
            return
        pattern_ax = self.widget.mpl.canvas.ax_pattern
        pattern_ylim = pattern_ax.get_ylim()
        specs = []
        for row in selected_rows:
            if row >= len(anchors):
                continue
            anchor = anchors[row]
            xmin = float(anchor.get("xmin", 0.0))
            xmax = float(anchor.get("xmax", xmin))
            if xmax < xmin:
                xmin, xmax = xmax, xmin
            specs.append({
                "axes": pattern_ax,
                "xmin": xmin,
                "xmax": xmax,
                "ymin": pattern_ylim[0],
                "ymax": pattern_ylim[1],
                "linewidth": 1.0,
                "edgecolor": "#d32f2f",
                "facecolor": "#f44336",
                "alpha": 0.22,
                "zorder": 6,
            })
        self._background_selection_artists = self._sync_overlay_rectangles(
            self._background_selection_artists, specs)

    def refresh_background_selection_overlay(self):
        if self._is_drawing or self._toolbar_active:
            self.update()
            return
        self._clear_background_selection_artists()
        self._plot_selected_background_overlays()
        self.widget.mpl.canvas.draw_idle()

    def refresh_jcpds_overlay(self):
        if self._is_drawing or self._toolbar_active:
            self.update()
            return
        emphasis_rows = self._get_jcpds_emphasis_rows()
        artists = [
            artist for artist in self._jcpds_overlay_artists
            if artist is not None
        ]
        if artists:
            for artist in artists:
                phase_index = getattr(artist, "_peakpo_jcpds_phase_index", None)
                if phase_index is None:
                    continue
                alpha = self._get_jcpds_plot_alpha(
                    phase_index, emphasis_rows,
                    getattr(artist, "_peakpo_jcpds_base_alpha", 1.0))
                try:
                    artist.set_alpha(alpha)
                except Exception:
                    pass
                base_color = getattr(artist, "_peakpo_jcpds_base_color", None)
                if base_color is not None:
                    try:
                        artist.set_color(mcolors.to_rgba(base_color, alpha))
                    except Exception:
                        pass
            self.widget.mpl.canvas.draw_idle()
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

    def _update_pnt_artist(self, derived_label_visible=None):
        artist = getattr(self, "_pnt_artist", None)
        if artist is not None:
            try:
                artist.remove()
            except Exception:
                pass
        self._pnt_artist = None
        if not self.widget.checkBox_ShowLargePnT.isChecked():
            return
        if derived_label_visible is None:
            derived_label_visible = self._derived_label_visible
        pnt_y = 0.90 if derived_label_visible else 0.985
        label = "{0: 5.1f} GPa\n{1: 4.0f} K".format(
            self.widget.doubleSpinBox_Pressure.value(),
            self.widget.doubleSpinBox_Temperature.value())
        self._pnt_artist = self.widget.mpl.canvas.ax_pattern.text(
            0.01, pnt_y, label,
            horizontalalignment="left", verticalalignment="top",
            transform=self.widget.mpl.canvas.ax_pattern.transAxes,
            fontsize=int(self.widget.comboBox_PnTFontSize.currentText()),
            gid="peakpo_pnt")

    def update_jcpds_only(self, update_xlabel=False):
        """Rebuild JCPDS/P-T overlays without clearing and replotting axes."""
        if self._is_drawing or self._toolbar_active or \
                self._pending_update_args is not None:
            self.update()
            return
        canvas = self.widget.mpl.canvas
        if not hasattr(canvas, "ax_pattern"):
            self.update()
            return

        started_at = time.perf_counter()
        ax_pattern = canvas.ax_pattern
        pattern_xlim = ax_pattern.get_xlim()
        pattern_ylim = ax_pattern.get_ylim()
        cake_xlim = canvas.ax_cake.get_xlim() if hasattr(canvas, "ax_cake") else None
        cake_ylim = canvas.ax_cake.get_ylim() if hasattr(canvas, "ax_cake") else None

        self.widget.setCursor(QtCore.Qt.WaitCursor)
        self._is_drawing = True
        try:
            self._clear_jcpds_overlay_artists()
            if self.model.jcpds_exist():
                axisrange = ax_pattern.axis()
                self._plot_jcpds(axisrange)
                if self.widget.checkBox_JCPDSinPattern.isChecked() and \
                        not self.widget.checkBox_Intensity.isChecked():
                    new_low = -1.1 * pattern_ylim[1] * \
                        self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
                    ax_pattern.set_ylim(new_low, pattern_ylim[1])
                else:
                    ax_pattern.set_ylim(pattern_ylim)
            else:
                ax_pattern.set_ylim(pattern_ylim)
            ax_pattern.set_xlim(pattern_xlim)
            if hasattr(canvas, "ax_cake"):
                canvas.ax_cake.set_xlim(cake_xlim)
                canvas.ax_cake.set_ylim(cake_ylim)
            self._update_pnt_artist()
            if update_xlabel:
                ax_pattern.set_xlabel(
                    "Two Theta (degrees), {:6.4f} \u212B".format(
                        self.widget.doubleSpinBox_SetWavelength.value()))
        finally:
            self._is_drawing = False
            self.widget.unsetCursor()

        build_seconds = time.perf_counter() - started_at
        self._schedule_canvas_draw(
            started_at, build_seconds, {"JCPDS/P-T": build_seconds})

    def refresh_cake_style(self):
        """Update an existing Cake image's colormap and limits in place."""
        if self._is_drawing or self._toolbar_active or \
                self._pending_update_args is not None:
            self.update()
            return
        if self.diff_ctrl is not None and self.diff_ctrl.is_diff_mode_active():
            self.update()
            return
        canvas = self.widget.mpl.canvas
        cake_artist = self._cake_artist
        if not hasattr(canvas, "ax_cake") or cake_artist is None or \
                getattr(cake_artist, "axes", None) is not canvas.ax_cake:
            self.update()
            return

        started_at = time.perf_counter()
        prefactor = float(self.widget.spinBox_MaxCakeScale.value())
        climits = np.asarray([
            self.widget.horizontalSlider_VMin.value(),
            self.widget.horizontalSlider_VMax.value()], dtype=float) / 100. * prefactor
        hist_widget = getattr(self.widget, "cake_hist_widget", None)
        if hist_widget is not None:
            signature = None
            if self._cake_data_cache is not None:
                signature = self._cake_data_cache[2]
            if signature is None and self._cake_display_data is not None:
                signature = hist_widget.data_signature_for_values(
                    self._cake_display_data)
            exact_bounds = hist_widget.current_bounds(data_signature=signature)
            if exact_bounds is not None:
                climits = np.asarray(exact_bounds, dtype=float)
        if climits[1] <= climits[0]:
            self.update()
            return
        cmap_name = "gray_r"
        if hasattr(self.widget, "comboBox_CakeColormap"):
            cmap_name = str(
                self.widget.comboBox_CakeColormap.currentText() or "gray_r")
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(color=(1.0, 0.97, 0.55, 1.0))
        cake_artist.set_cmap(cmap)
        cake_artist.set_clim(float(climits[0]), float(climits[1]))

        if hist_widget is not None:
            finite_values = None
            data_signature = None
            if self._cake_data_cache is not None:
                _cached_image, finite_values, data_signature = \
                    self._cake_data_cache
            hist_widget.set_data(
                self._cake_display_data, vmin=float(climits[0]),
                vmax=float(climits[1]),
                data_token=self._cake_data_cache_key,
                finite_values=finite_values,
                data_signature=data_signature)
        build_seconds = time.perf_counter() - started_at
        self._schedule_canvas_draw(
            started_at, build_seconds, {"Cake style": build_seconds})

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
        cake_hkl_transform = None
        if self.widget.checkBox_ShowCake.isChecked() and \
                self.widget.checkBox_ShowMillerIndices_Cake.isChecked():
            cake_hkl_transform = transforms.blended_transform_factory(
                self.widget.mpl.canvas.ax_cake.transData,
                self.widget.mpl.canvas.ax_cake.transAxes)
        emphasis_rows = self._get_jcpds_emphasis_rows()
        emphasis_rows = {
            idx for idx in emphasis_rows
            if 0 <= idx < len(self.model.jcpds_lst) and
            getattr(self.model.jcpds_lst[idx], "display", False)
        }
        pattern_bar_alpha, cake_bar_alpha = self._jcpds_bar_alphas()
        display_index = -1
        for row_idx, phase in enumerate(self.model.jcpds_lst):
            if not phase.display:
                continue
            display_index += 1
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
            tth = np.asarray(tth, dtype=float)
            inten = np.asarray(inten, dtype=float)
            valid_reflections = np.isfinite(tth) & np.isfinite(inten) & \
                (tth > 0.0) & (tth <= 180.0)
            valid_indices = np.flatnonzero(valid_reflections)
            tth = tth[valid_reflections]
            inten = inten[valid_reflections]
            if tth.size == 0:
                continue
            if self.widget.checkBox_JCPDSinPattern.isChecked():
                intensity = inten * phase.twk_int
                if show_intensity:
                    bar_min = np.ones_like(tth) * axisrange[2] + \
                        bar_pos * axisrange[3]
                    bar_max = intensity * bar_scale + bar_min
                else:
                    starting_intensity = np.ones_like(tth) * start_intensity
                    bar_max = starting_intensity - \
                        display_index * 100. * bar_scale / n_displayed_jcpds
                    bar_min = starting_intensity - \
                        (display_index + 0.7) * 100. * bar_scale / n_displayed_jcpds
                if (pressure == 0.) or (phase.symmetry == 'nosymmetry'):
                    volume = phase.v
                else:
                    volume = phase.v.item()
                legend_label = "{0:}, {1:.3f} A^3".format(
                    phase.name, volume)
                phase_alpha = self._get_jcpds_plot_alpha(
                    row_idx, emphasis_rows, pattern_bar_alpha)
                jcpds_bars = self.widget.mpl.canvas.ax_pattern.vlines(
                    tth, bar_min, bar_max, colors=phase.color,
                    label=legend_label,
                    lw=float(
                        self.widget.comboBox_PtnJCPDSBarThickness.
                        currentText()),
                    alpha=phase_alpha,
                    zorder=18)
                self._track_jcpds_artist(
                    jcpds_bars, phase_index=row_idx,
                    base_alpha=pattern_bar_alpha)
                legend_entries.append(
                    (jcpds_bars, legend_label, phase.color, row_idx))
                # hkl
                if self.widget.checkBox_ShowMillerIndices.isChecked():
                    all_hkl = phase.get_hkl_in_text()
                    hkl_list = [all_hkl[index] for index in valid_indices]
                    for j, hkl in enumerate(hkl_list):
                        self._track_jcpds_artist(
                            self.widget.mpl.canvas.ax_pattern.text(
                            tth[j], bar_max[j], hkl, color=phase.color,
                            rotation=90, verticalalignment='bottom',
                            horizontalalignment='center',
                            fontsize=int(
                                self.widget.comboBox_HKLFontSize.currentText()),
                            alpha=self._get_jcpds_plot_alpha(
                                row_idx, emphasis_rows),
                            zorder=19), hkl=True,
                            phase_index=row_idx, base_alpha=1.0)
                # phase.name, phase.v.item()))
            if self.widget.checkBox_ShowCake.isChecked() and \
                    self.widget.checkBox_JCPDSinCake.isChecked():
                phase_alpha = self._get_jcpds_plot_alpha(
                    row_idx, emphasis_rows, cake_bar_alpha)
                self._track_jcpds_artist(
                    self.widget.mpl.canvas.ax_cake.vlines(
                    tth, np.ones_like(tth) * cakerange[2],
                    np.ones_like(tth) * cakerange[3], colors=phase.color,
                    lw=float(
                        self.widget.comboBox_CakeJCPDSBarThickness.currentText()),
                    alpha=phase_alpha,
                    zorder=18),
                    phase_index=row_idx, base_alpha=cake_bar_alpha)
                if self.widget.checkBox_ShowMillerIndices_Cake.isChecked():
                    all_hkl = phase.get_hkl_in_text()
                    hkl_list = [all_hkl[index] for index in valid_indices]
                    for j, hkl in enumerate(hkl_list):
                        self._track_jcpds_artist(
                            self.widget.mpl.canvas.ax_cake.text(
                            tth[j], 0.99, hkl, color=phase.color,
                            rotation=90, verticalalignment='top',
                            transform=cake_hkl_transform,
                            horizontalalignment='right',
                            fontsize=int(
                                self.widget.comboBox_HKLFontSize.currentText()),
                            alpha=self._get_jcpds_plot_alpha(
                                row_idx, emphasis_rows),
                            zorder=19), hkl=True,
                            phase_index=row_idx,
                            base_alpha=1.0)
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
            for handle, label, color, phase_index in legend_entries:
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                unique_entries.append((handle, label, color, phase_index))
            if unique_entries:
                handles = [entry[0] for entry in unique_entries]
                labels = [entry[1] for entry in unique_entries]
                leg_jcpds = self.widget.mpl.canvas.ax_pattern.legend(
                    handles, labels, loc=1, framealpha=0.,
                    fontsize=legend_fontsize,
                    handlelength=0,
                    handletextpad=0.0)
                self._track_jcpds_artist(leg_jcpds)
                legend_handles = getattr(leg_jcpds, "legend_handles", None)
                if legend_handles is None:
                    legend_handles = getattr(leg_jcpds, "legendHandles", [])
                for handle in legend_handles:
                    try:
                        handle.set_visible(False)
                    except Exception:
                        pass
                for (__handle, __label, color, phase_index), txt in zip(
                        unique_entries, leg_jcpds.get_texts()):
                    alpha = self._get_jcpds_plot_alpha(
                        phase_index, emphasis_rows)
                    txt.set_color(mcolors.to_rgba(color, alpha))
                    self._track_jcpds_artist(
                        txt, phase_index=phase_index, base_alpha=1.0,
                        base_color=color)
        # print("JCPDS update takes {0:.2f}s at".format(time.time() - t_start),
        #      str(datetime.datetime.now())[:-7])

    def _waterfall_plot_data(self, pattern, *, bgsub, normalize,
                             convert_wavelength, base_max, base_wavelength):
        x_source = pattern.x_bgsub if bgsub else pattern.x_raw
        y_source = pattern.y_bgsub if bgsub else pattern.y_raw
        x_source = np.asarray(x_source)
        y_source = np.asarray(y_source)
        source_max = float(np.nanmax(y_source)) if y_source.size else 0.0
        key = (
            id(pattern), id(x_source), id(y_source), tuple(x_source.shape),
            tuple(y_source.shape), source_max, bool(bgsub), bool(normalize),
            bool(convert_wavelength), float(pattern.wavelength),
            float(base_wavelength), float(base_max))
        cached = self._waterfall_transform_cache.get(key)
        if cached is not None:
            return cached
        if normalize and np.isfinite(source_max) and source_max != 0.0:
            y = y_source / source_max * base_max
        else:
            y = y_source
        if convert_wavelength:
            # Preserve PeakPo's established conversion behavior.  Its numerical
            # definition is intentionally outside this optimization change.
            x = convert_tth(
                x_source, pattern.wavelength, base_wavelength)
        else:
            x = x_source
        cached = (x, y)
        if len(self._waterfall_transform_cache) >= 256:
            self._waterfall_transform_cache.clear()
        self._waterfall_transform_cache[key] = cached
        return cached

    def _track_waterfall_artist(self, artist):
        if artist is not None:
            self._waterfall_artists.append(artist)
        return artist

    def _clear_waterfall_artists(self):
        for artist in list(self._waterfall_artists):
            try:
                artist.remove()
            except Exception:
                pass
        self._waterfall_artists = []

    def refresh_waterfall_overlay(self):
        """Rebuild only waterfall lines and labels, preserving all other artists."""
        if self._is_drawing or self._toolbar_active or \
                self._pending_update_args is not None:
            self.update()
            return
        ax = getattr(self.widget.mpl.canvas, "ax_pattern", None)
        if ax is None:
            self.update()
            return
        started_at = time.perf_counter()
        limits = ax.axis()
        self._clear_waterfall_artists()
        if self.model.waterfall_exist():
            self._plot_waterfallpatterns()
        ax.axis(limits)
        build_seconds = time.perf_counter() - started_at
        self._schedule_canvas_draw(
            started_at, build_seconds, {"waterfall": build_seconds})

    def _plot_waterfallpatterns(self):
        self._clear_waterfall_artists()
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
        emphasis_rows = self._get_waterfall_emphasis_rows()
        dim_alpha = 0.25
        highlight_alpha = 1.0
        bgsub = self.widget.checkBox_BgSub.isChecked()
        normalize = self.widget.checkBox_IntNorm.isChecked()
        convert_wavelength = self.widget.checkBox_SetToBasePtnLambda.isChecked()
        base_y = self.model.base_ptn.y_bgsub if bgsub else \
            self.model.base_ptn.y_raw
        base_max = float(np.nanmax(base_y)) if np.size(base_y) else 0.0
        gap_fraction = self.widget.horizontalSlider_WaterfallGaps.value() / 100.0
        j = 0  # this is needed for waterfall gaps
        # get y_max
        for reverse_idx, pattern in enumerate(self.model.waterfall_ptn[::-1]):
            if pattern.display:
                j += 1
                """
                self.widget.mpl.canvas.ax_pattern.text(
                    0.01, 0.97 - n_display * 0.05 + j * 0.05,
                    os.path.basename(pattern.fname),
                    transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                    color=pattern.color)
                """
                ygap = gap_fraction * base_max * float(j)
                x, y = self._waterfall_plot_data(
                    pattern, bgsub=bgsub, normalize=normalize,
                    convert_wavelength=convert_wavelength,
                    base_max=base_max,
                    base_wavelength=self.model.base_ptn.wavelength)
                alpha = highlight_alpha
                if emphasis_rows:
                    row_idx = len(self.model.waterfall_ptn) - 1 - reverse_idx
                    if row_idx not in emphasis_rows:
                        alpha = dim_alpha
                line = self.widget.mpl.canvas.ax_pattern.plot(
                    x, y + ygap, c=pattern.color, lw=float(
                        self.widget.comboBox_WaterfallLineThickness.
                        currentText()), alpha=alpha)[0]
                self._track_waterfall_artist(line)
                if self.widget.checkBox_ShowWaterfallLabels.isChecked():
                    wf_fontsize = 12
                    if hasattr(self.widget, "comboBox_WaterfallFontSize"):
                        try:
                            wf_fontsize = int(
                                self.widget.comboBox_WaterfallFontSize.currentText())
                        except Exception:
                            pass
                    self._track_waterfall_artist(
                        self.widget.mpl.canvas.ax_pattern.text(
                        (x[-1] - x[0]) * 0.01 + x[0], y[0] + ygap,
                        os.path.basename(pattern.fname),
                        verticalalignment='bottom', horizontalalignment='left',
                        color=mcolors.to_rgba(pattern.color, alpha),
                        fontsize=wf_fontsize))
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
            pattern_line = self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=color, marker='o',
                linestyle='None', ms=1.5)[0]
        else:
            pattern_line = self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=color,
                lw=float(
                    self.widget.comboBox_BasePtnLineThickness.
                    currentText()))[0]
        pattern_line.set_gid("peakpo_base_pattern")
        if self.diff_ctrl is not None and self.diff_ctrl.is_diff_mode_active():
            zero_line = self.widget.mpl.canvas.ax_pattern.axhline(
                0.0, ls='--', c='tab:red', lw=0.8)
            zero_line.set_gid("peakpo_diff_zero")
            return
        if not self.widget.checkBox_BgSub.isChecked():
            x_bg, y_bg = self._pattern_background_xy()
            background_line = self.widget.mpl.canvas.ax_pattern.plot(
                x_bg, y_bg, c=color, ls='--',
                lw=float(
                    self.widget.comboBox_BkgnLineThickness.
                    currentText()))[0]
            background_line.set_gid("peakpo_pattern_background")

    @staticmethod
    def _artist_with_gid(artists, gid):
        for artist in artists:
            try:
                if artist.get_gid() == gid:
                    return artist
            except Exception:
                continue
        return None

    def refresh_pattern_data(self, limits=None):
        """Update the base/background lines without rebuilding either axis."""
        if self.model.waterfall_exist() or self._fits_tab_active() or \
                self._is_drawing or self._toolbar_active or \
                self._pending_update_args is not None:
            self.update(limits=limits)
            return
        ax = self.widget.mpl.canvas.ax_pattern
        pattern_line = self._artist_with_gid(ax.lines, "peakpo_base_pattern")
        if pattern_line is None:
            self.update(limits=limits)
            return

        started_at = time.perf_counter()
        x, y = self._pattern_xy()
        if self.diff_ctrl is not None:
            try:
                x, y = self.diff_ctrl.get_display_pattern(x, y)
            except Exception:
                pass
        pattern_line.set_data(x, y)

        background_line = self._artist_with_gid(
            ax.lines, "peakpo_pattern_background")
        show_background = not self.widget.checkBox_BgSub.isChecked() and not (
            self.diff_ctrl is not None and self.diff_ctrl.is_diff_mode_active())
        if show_background:
            x_bg, y_bg = self._pattern_background_xy()
            if background_line is None:
                background_line = ax.plot(
                    x_bg, y_bg,
                    c=pattern_line.get_color(), ls="--",
                    lw=float(self.widget.comboBox_BkgnLineThickness.currentText()))[0]
                background_line.set_gid("peakpo_pattern_background")
            else:
                background_line.set_data(x_bg, y_bg)
                background_line.set_visible(True)
        elif background_line is not None:
            background_line.set_visible(False)

        if limits is not None:
            ax.set_xlim(limits[0], limits[1])
            ax.set_ylim(limits[2], limits[3])
            if hasattr(self.widget.mpl.canvas, "ax_cake"):
                self.widget.mpl.canvas.ax_cake.set_xlim(limits[0], limits[1])
        build_seconds = time.perf_counter() - started_at
        self._schedule_canvas_draw(
            started_at, build_seconds, {"pattern data": build_seconds})

    def _track_peakfit_artist(self, artist):
        if artist is not None:
            self._peakfit_overlay_artists.append(artist)
        return artist

    def _clear_peakfit_overlay_artists(self):
        for artist in list(getattr(self, "_peakfit_overlay_artists", [])):
            try:
                artist.remove()
            except Exception:
                pass
        self._peakfit_overlay_artists = []

    def _plot_peakfit(self):
        self._clear_peakfit_overlay_artists()
        self._clear_selected_peak_marker()
        self._clear_peak_center_markers()
        self._peak_center_marker_artists = []
        self._selected_peak_marker_artists = []
        if not self.model.current_section_exist():
            return
        fitted = self.model.current_section.fitted()
        if self.model.current_section.peaks_exist():
            selected_row = self._get_selected_peak_parameter_row()
            peaks = self.model.current_section.peaks_in_queue
            for row, x_c in enumerate(self.model.current_section.get_peak_positions()):
                self._plot_peak_center_marker(x_c)
                if row == selected_row:
                    peak = peaks[row] if row < len(peaks) else None
                    self._plot_selected_peak_marker(x_c, peak=peak)
            if not fitted:
                self._plot_initial_peak_profiles()
        if fitted:
            bgsub = self.widget.checkBox_BgSub.isChecked()
            x_plot = self.model.current_section.x
            profiles = self.model.current_section.get_individual_profiles(
                bgsub=bgsub)
            for key, value in profiles.items():
                line = self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, value, ls='-',
                    c='yellow' if str(key).startswith('p') else self.obj_color,
                    lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))[0]
                self._track_peakfit_artist(line)
            total_profile = self.model.current_section.get_fit_profile(
                bgsub=bgsub)
            residue = self.model.current_section.get_fit_residue(bgsub=bgsub)
            total_line = self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, total_profile, 'r-', lw=float(
                    self.widget.comboBox_BasePtnLineThickness.
                    currentText()))[0]
            self._track_peakfit_artist(total_line)
            y_range = self.model.current_section.get_yrange(bgsub=bgsub)
            y_shift = y_range[0] - (y_range[1] - y_range[0]) * 0.05
            #(y_range[1] - y_range[0]) * 1.05
            fill = self.widget.mpl.canvas.ax_pattern.fill_between(
                x_plot, self.model.current_section.get_fit_residue_baseline(
                    bgsub=bgsub) + y_shift, residue + y_shift, facecolor='r')
            self._track_peakfit_artist(fill)
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
        peaks = self.model.current_section.peaks_in_queue
        for row, x_c in enumerate(self.model.current_section.get_peak_positions()):
            self._plot_peak_center_marker(x_c)
            if row == selected_row:
                peak = peaks[row] if row < len(peaks) else None
                self._plot_selected_peak_marker(x_c, peak=peak)
        if not self.model.current_section.fitted():
            self._plot_initial_peak_profiles()
        self.widget.mpl.canvas.draw_idle()
        return True

    def _plot_initial_peak_profiles(self):
        bgsub = self.widget.checkBox_BgSub.isChecked()
        profiles = self.model.current_section.get_initial_peak_profiles(
            bgsub=bgsub)
        x_plot = self.model.current_section.x
        linewidth = float(
            self.widget.comboBox_BasePtnLineThickness.currentText())
        for value in profiles.values():
            line = self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, value, ls='-', c='yellow', lw=linewidth, zorder=9)[0]
            self._peak_center_marker_artists.append(line)

    def _get_selected_peak(self):
        selected_row = self._get_selected_peak_parameter_row()
        if selected_row is None:
            return None
        if not self.model.current_section.peaks_exist():
            return None
        peaks = self.model.current_section.peaks_in_queue
        if selected_row >= len(peaks):
            return None
        return peaks[selected_row]

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
        peak = self._get_selected_peak()
        self._plot_selected_peak_marker(positions[selected_row], peak=peak)
        self.widget.mpl.canvas.draw_idle()
        return True

    def _get_peak_marker_color(self, peak):
        phase_name = peak.get('phasename', 'unknown')
        if phase_name.lower() == 'unknown':
            return self.obj_color
        for phase in self.model.jcpds_lst:
            if phase.name.lower() == phase_name.lower():
                return phase.color
        return self.obj_color

    def _get_peak_hkl_label(self, peak):
        h = int(peak.get('h', 0))
        k = int(peak.get('k', 0))
        l = int(peak.get('l', 0))
        phase = peak.get('phasename', 'unknown')
        return f"{phase} ({h},{k},{l})"

    def _nearest_observed_peak_intensity(self, x_center):
        """Return the displayed observed intensity nearest a peak center."""
        section = getattr(self.model, "current_section", None)
        if section is None or section.x is None or section.y_bgsub is None:
            return None
        try:
            x = np.asarray(section.x, dtype=float)
            y = np.asarray(section.y_bgsub, dtype=float)
            if not self.widget.checkBox_BgSub.isChecked() and section.y_bg is not None:
                y = y + np.asarray(section.y_bg, dtype=float)
            valid = np.isfinite(x) & np.isfinite(y)
            if not np.any(valid):
                return None
            x = x[valid]
            y = y[valid]
            index = int(np.abs(x - float(x_center)).argmin())
            return float(y[index])
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _active_peak_triangle_y(axis, observed_y):
        """Place the downward triangle just above the observed intensity."""
        y_min, y_max = axis.get_ylim()
        y_span = y_max - y_min
        if not np.isfinite(y_span) or y_span <= 0.0:
            return float(observed_y)
        offset = 0.02 * y_span
        return min(y_max - 0.01 * y_span,
                   max(y_min + 0.01 * y_span, float(observed_y) + offset))

    def _plot_selected_peak_marker(self, x_center, peak=None):
        fitted = self.model.current_section.fitted()
        if peak is not None:
            color = self._get_peak_marker_color(peak)
        else:
            color = 'tab:cyan' if fitted else 'tab:orange'
        linestyle = '-' if fitted else '-'
        self._selected_peak_marker_artists = []
        pattern_axis = self.widget.mpl.canvas.ax_pattern
        observed_y = self._nearest_observed_peak_intensity(x_center)
        marker_y = None
        if observed_y is not None:
            _, y_max = pattern_axis.get_ylim()
            marker_y = self._active_peak_triangle_y(pattern_axis, observed_y)
            line = pattern_axis.plot(
                [x_center, x_center], [marker_y, y_max],
                color=color, linestyle=linestyle, linewidth=1.4,
                zorder=20)[0]
            line._peakpo_active_peak_guide = True
            self._selected_peak_marker_artists.append(line)
        if marker_y is None:
            marker_y = pattern_axis.get_ylim()[1]
        marker = pattern_axis.plot(
            [x_center], [marker_y], marker='v', markersize=8,
            color=color, linestyle='None', zorder=21, clip_on=False)[0]
        marker._peakpo_active_peak_triangle = True
        self._selected_peak_marker_artists.append(marker)
        if peak is not None:
            label_text = self._get_peak_hkl_label(peak)
            y_pos = 0.94
            text_artist = self.widget.mpl.canvas.ax_pattern.text(
                x_center, y_pos, label_text,
                color='black', fontsize=9, fontweight='bold',
                horizontalalignment='center', verticalalignment='top',
                transform=self.widget.mpl.canvas.ax_pattern.get_xaxis_transform(),
                zorder=22, clip_on=False,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor=color, alpha=0.85))
            self._selected_peak_marker_artists.append(text_artist)
        if hasattr(self.widget.mpl.canvas, 'ax_cake') and \
                self.widget.checkBox_ShowCake.isChecked():
            line = self.widget.mpl.canvas.ax_cake.axvline(
                x_center, c=color, ls=linestyle, lw=1.2, zorder=20)
            self._selected_peak_marker_artists.append(line)
            marker = self.widget.mpl.canvas.ax_cake.plot(
                [x_center], [0.985], marker='v', markersize=8,
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
                if hasattr(artist, 'get_xdata'):
                    xdata = artist.get_xdata()
                    if len(xdata) == 1:
                        artist.set_xdata([x_center])
                        if getattr(artist, "_peakpo_active_peak_triangle", False):
                            observed_y = self._nearest_observed_peak_intensity(
                                x_center)
                            if observed_y is not None:
                                artist.set_ydata([
                                    self._active_peak_triangle_y(
                                        artist.axes, observed_y)])
                    else:
                        artist.set_xdata([x_center, x_center])
                        if getattr(artist, "_peakpo_active_peak_guide", False):
                            observed_y = self._nearest_observed_peak_intensity(
                                x_center)
                            if observed_y is not None:
                                _, y_max = artist.axes.get_ylim()
                                marker_y = self._active_peak_triangle_y(
                                    artist.axes, observed_y)
                                artist.set_ydata([marker_y, y_max])
                elif hasattr(artist, 'set_position'):
                    x, y = artist.get_position()
                    artist.set_position((x_center, y))
            except Exception:
                pass
        self.widget.mpl.canvas.draw_idle()
        return True

    def _plot_peak_center_marker(self, x_center):
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
        self._clear_peakfit_overlay_artists()
        self._clear_selected_peak_marker()
        self._clear_peak_center_markers()
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
                total_line = self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, total_profile, 'r-', lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))[0]
                self._track_peakfit_artist(total_line)
                fill = self.widget.mpl.canvas.ax_pattern.fill_between(
                    x_plot, section.get_fit_residue_baseline(bgsub=bgsub) +
                    y_shift, residue + y_shift, facecolor='r')
                self._track_peakfit_artist(fill)
            i += 1

    def refresh_current_section_view(self, limits=None, cake_ylimits=None,
                                     gsas_style=False):
        if self._is_drawing or self._toolbar_active:
            self.update(
                limits=limits, gsas_style=gsas_style,
                cake_ylimits=cake_ylimits)
            return
        canvas = self.widget.mpl.canvas
        ax_pattern = getattr(canvas, "ax_pattern", None)
        if ax_pattern is None:
            self.update(
                limits=limits, gsas_style=gsas_style,
                cake_ylimits=cake_ylimits)
            return
        if limits is None:
            limits = ax_pattern.axis()
        if cake_ylimits is None and hasattr(canvas, "ax_cake"):
            cake_ylimits = canvas.ax_cake.get_ylim()
        if self.model.jcpds_exist():
            self._plot_jcpds(limits)
        if self._fits_tab_active():
            if gsas_style:
                self._plot_peakfit_in_gsas_style()
            else:
                self._plot_peakfit()
            self._plot_selected_section_overlays()
            self._plot_selected_background_overlays()
        ax_pattern.set_xlim(limits[0], limits[1])
        if not self.widget.checkBox_AutoY.isChecked():
            ax_pattern.set_ylim(limits[2], limits[3])
        if hasattr(canvas, "ax_cake"):
            canvas.ax_cake.set_xlim(limits[0], limits[1])
            if cake_ylimits is not None:
                canvas.ax_cake.set_ylim(cake_ylimits)
        if self.model.jcpds_exist() and \
                (not self.widget.checkBox_Intensity.isChecked()):
            new_low_limit = -1.1 * limits[3] * \
                self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
            ax_pattern.set_ylim(new_low_limit, limits[3])
        canvas.draw_idle()

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

    def _schedule_canvas_draw(self, update_started_at, build_seconds,
                              stage_seconds):
        """Coalesce full canvas renders and report build + render timing."""
        self._pending_draw_profile = (
            float(update_started_at), float(build_seconds), dict(stage_seconds))
        if self._canvas_draw_scheduled:
            return
        self._canvas_draw_scheduled = True
        QtCore.QTimer.singleShot(0, self._flush_canvas_draw)

    def call_after_next_draw(self, callback):
        if not callable(callback):
            return
        if callback not in self._after_draw_callbacks:
            self._after_draw_callbacks.append(callback)

    def _flush_canvas_draw(self):
        profile = self._pending_draw_profile
        self._pending_draw_profile = None
        if profile is None:
            self._canvas_draw_scheduled = False
            return
        if self._is_drawing or self._toolbar_active:
            self._pending_draw_profile = profile
            QtCore.QTimer.singleShot(self._update_delay_ms, self._flush_canvas_draw)
            return

        update_started_at, build_seconds, stage_seconds = profile
        render_started_at = time.perf_counter()
        self._is_drawing = True
        try:
            self.widget.mpl.canvas.draw()
        finally:
            self._is_drawing = False
            self._canvas_draw_scheduled = False

        render_seconds = time.perf_counter() - render_started_at
        total_seconds = time.perf_counter() - update_started_at
        if total_seconds > 1.0:
            stage_text = ", ".join(
                f"{name} {seconds:.2f}s"
                for name, seconds in stage_seconds.items()
                if seconds >= 0.01)
            details = (
                f"build {build_seconds:.2f}s, render {render_seconds:.2f}s")
            if stage_text:
                details += f"; {stage_text}"
            print(
                str(datetime.datetime.now())[:-7],
                f": Plot takes {total_seconds:.2f}s ({details})")

        callbacks = self._after_draw_callbacks
        self._after_draw_callbacks = []
        for callback in callbacks:
            try:
                callback()
            except Exception:
                pass

        if self._pending_draw_profile is not None:
            self._schedule_canvas_draw(*self._pending_draw_profile)
        if self._pending_update_args is not None:
            self._update_timer.start(0)

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
        
        t_start = time.perf_counter()
        stage_started_at = t_start
        stage_seconds = {}
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
                if not self._plot_cake():
                    self.widget.checkBox_ShowCake.setChecked(False)
                    self.widget.mpl.canvas.resize_axes(1)
            else:
                if self.widget.checkBox_ShowCake.isChecked():
                    self.widget.checkBox_ShowCake.setChecked(False)
                self.widget.mpl.canvas.resize_axes(1)
            stage_seconds["axes/cake"] = time.perf_counter() - stage_started_at
            stage_started_at = time.perf_counter()
            
            self._set_nightday_view()
            self._apply_pattern_background_style()
            
            derived_label_visible = False
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
                derived_label_visible = self._plot_derived_pattern_label()
                
                if self.model.waterfall_exist():
                    self._plot_waterfallpatterns()
            self._derived_label_visible = bool(derived_label_visible)
            stage_seconds["pattern"] = time.perf_counter() - stage_started_at
            stage_started_at = time.perf_counter()
            
            if self._fits_tab_active():
                if gsas_style:
                    self._plot_peakfit_in_gsas_style()
                else:
                    self._plot_peakfit()
            stage_seconds["fits"] = time.perf_counter() - stage_started_at
            stage_started_at = time.perf_counter()
            
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
            stage_seconds["JCPDS"] = time.perf_counter() - stage_started_at
            stage_started_at = time.perf_counter()

            if self._fits_tab_active():
                self._plot_selected_section_overlays()
                self._plot_selected_background_overlays()
            
            self._update_pnt_artist(derived_label_visible)
            
            xlabel = "Two Theta (degrees), {:6.4f} \u212B".\
                format(self.widget.doubleSpinBox_SetWavelength.value())
            self.widget.mpl.canvas.ax_pattern.set_xlabel(xlabel)
            
            self.widget.mpl.canvas.ax_pattern.format_coord = \
                self._format_pattern_coord
            
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
            
            stage_seconds["decorations"] = time.perf_counter() - stage_started_at
            build_seconds = time.perf_counter() - t_start
            self._schedule_canvas_draw(t_start, build_seconds, stage_seconds)
        
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

    def _format_pattern_coord(self, x, y):
        dsp = _bragg_dspacing(
            x, self.widget.doubleSpinBox_SetWavelength.value())
        dsp_text = "NA" if dsp is None else f"{dsp:.4f}\u212B"
        return f"\n 2\u03B8={x:.3f}\u00B0, I={y:.4e}, d-sp={dsp_text}"

    def _format_coord_x_y_z_dsp(self, x, y):
        """
        Read 2theta, azimuthal angle, intensity, and d-spacing from the image
        
        :param x: 2 theta angle
        :param y: azimuthal angle
        """
        ax = self.widget.mpl.canvas.ax_cake

        dsp = _bragg_dspacing(
            x, self.widget.doubleSpinBox_SetWavelength.value())

        cake_artist = self._cake_artist
        # If no Cake artist is available, return x,y,dsp only.
        if cake_artist is None or getattr(cake_artist, "axes", None) is not ax:
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)

        data = self._cake_display_data
        if data is None:
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

        tth_centers = self._cake_tth_centers
        chi_centers = self._cake_chi_centers
        if tth_centers is None or chi_centers is None or \
                len(tth_centers) != nx or len(chi_centers) != ny:
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)
        try:
            tth_edges = _coordinate_edges(tth_centers)
            chi_edges = _coordinate_edges(chi_centers)
        except ValueError:
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
        if not (tth_edges[0] <= x <= tth_edges[-1]) or \
                not (chi_edges[0] <= y <= chi_edges[-1]):
            if dsp is None:
                return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp=NA".format(x, y)
            return "2\u03B8={:.3f}\u00B0, azi={:.1f}, I=NA, d-sp={:.4f}\u212B".format(x, y, dsp)
        col = _nearest_coordinate_index(tth_centers, x)
        row = _nearest_coordinate_index(chi_centers, y)

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
