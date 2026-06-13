import os
import numpy as np
from qtpy import QtWidgets
from scipy.interpolate import interp1d

from ..model import PeakPoModel8
from ..model.diff_state import DiffState
from ..model.param_session_io import load_model_from_param
from ..utils import readchi, writechi, get_temp_dir, dialog_openfile_hide_param_dirs


class DiffController(object):
    """Controller for 1D/2D reference subtraction (Diff mode)."""

    _CMAPS = [
        "coolwarm",
        "RdBu_r",
        "seismic",
        "PiYG",
        "PRGn",
        "BrBG",
        "gray",
        "gray_r",
    ]
    _SCALE_MODE_ITEMS = [
        "0 Centered",
        "Free range",
    ]
    _SCALE_MODE_TO_ID = {
        "0 centered": "asymmetric_centered",
        "0 Centered": "asymmetric_centered",
        "Symmetric (0 centered)": "asymmetric_centered",
        "Asymmetric (0 centered)": "asymmetric_centered",
        "Positive only (0 as min)": "free_range",
        "Negative only (0 as max)": "free_range",
        "Cake-like free range": "free_range",
        "Free range": "free_range",
    }
    _SCALE_ID_TO_MODE = {
        "asymmetric_centered": "0 Centered",
        "free_range": "Free range",
    }

    def __init__(self, model, widget, plot_ctrl=None):
        self.model = model
        self.widget = widget
        self.plot_ctrl = plot_ctrl
        self._in_ref_reload = False
        self._ref2d_sort_cache = {}
        self._ref2d_interp_cache = {}
        if not hasattr(self.model, "diff_state") or (self.model.diff_state is None):
            self.model.diff_state = DiffState()
        self._connect_channel()
        self._init_ui_from_state()

    def _clear_interp_cache(self):
        self._ref2d_sort_cache = {}
        self._ref2d_interp_cache = {}

    def _connect_channel(self):
        if (not hasattr(self.widget, "checkBox_Diff")) and \
                (not hasattr(self.widget, "checkBox_UseDiffMode")):
            return
        self.widget.pushButton_DiffRefBrowse.clicked.connect(self._browse_ref_chi)
        self.widget.pushButton_DiffRefClear.clicked.connect(self._clear_reference)
        if hasattr(self.widget, "checkBox_Diff"):
            self.widget.checkBox_Diff.toggled.connect(self._on_toggled)
        if hasattr(self.widget, "checkBox_UseDiffMode"):
            self.widget.checkBox_UseDiffMode.toggled.connect(self._on_toggled)
        self.widget.lineEdit_DiffRefChi.editingFinished.connect(
            self._on_ref_path_changed_from_ui)
        self.widget.lineEdit_DiffRefChi.textChanged.connect(
            self._on_ref_path_text_changed)
        self.widget.comboBox_DiffCmap.currentTextChanged.connect(self._on_cmap_changed)
        self.widget.comboBox_DiffScaleMode.currentTextChanged.connect(
            self._on_scale_mode_changed)
        self.widget.doubleSpinBox_DiffVmin.valueChanged.connect(self._on_manual_range_changed)
        self.widget.doubleSpinBox_DiffVmax.valueChanged.connect(self._on_manual_range_changed)
        if hasattr(self.widget, "pushButton_ExportDiffChi"):
            self.widget.pushButton_ExportDiffChi.clicked.connect(self.export_diff_chi)
        if hasattr(self.widget, "pushButton_ExportDiffCakeNpy"):
            self.widget.pushButton_ExportDiffCakeNpy.clicked.connect(self.export_diff_cake_npy)

    def _init_ui_from_state(self):
        if (not hasattr(self.widget, "checkBox_Diff")) and \
                (not hasattr(self.widget, "checkBox_UseDiffMode")):
            return
        st = self.model.diff_state
        # Always start with Diff unchecked on app launch.
        st.enabled = False
        self.widget.lineEdit_DiffRefChi.setText(str(st.ref_chi_path or ""))
        self._set_enabled_ui(False)
        self.widget.comboBox_DiffCmap.clear()
        self.widget.comboBox_DiffCmap.addItems(self._CMAPS)
        self.widget.comboBox_DiffScaleMode.clear()
        self.widget.comboBox_DiffScaleMode.addItems(self._SCALE_MODE_ITEMS)
        cmap = st.cmap_2d if st.cmap_2d in self._CMAPS else "coolwarm"
        self.widget.comboBox_DiffCmap.setCurrentText(cmap)
        mode_text = self._SCALE_ID_TO_MODE.get(
            str(st.scale_mode_2d), "0 Centered")
        self.widget.comboBox_DiffScaleMode.setCurrentText(mode_text)
        self.widget.doubleSpinBox_DiffVmin.setValue(float(st.vmin_2d))
        self.widget.doubleSpinBox_DiffVmax.setValue(float(st.vmax_2d))
        self._refresh_scale_mode_ui()
        self._set_gray_scale_controls_enabled(not self.is_diff_mode_active())
        self._set_diff_scale_controls_enabled(self.is_diff_mode_active())
        self._set_toolbar_controls_enabled(not self.is_diff_mode_active())
        if st.ref_chi_path not in (None, ""):
            self._reload_reference_data(show_errors=False)
        self._refresh_toggle_enabled_state()
        self._set_status()
        self._update_diff_minmax_labels()

    def sync_state_from_ui(self):
        if (not hasattr(self.widget, "checkBox_Diff")) and \
                (not hasattr(self.widget, "checkBox_UseDiffMode")):
            return
        st = self.model.diff_state
        st.enabled = self._is_enabled_ui()
        st.ref_chi_path = str(self.widget.lineEdit_DiffRefChi.text()).strip()
        st.cmap_2d = str(self.widget.comboBox_DiffCmap.currentText())
        st.positive_side = "red_warm"
        st.scale_mode_2d = self._SCALE_MODE_TO_ID.get(
            str(self.widget.comboBox_DiffScaleMode.currentText()),
            "asymmetric_centered",
        )
        st.vmin_2d = float(self.widget.doubleSpinBox_DiffVmin.value())
        st.vmax_2d = float(self.widget.doubleSpinBox_DiffVmax.value())

    def _sync_ui_from_state(self):
        if (not hasattr(self.widget, "checkBox_Diff")) and \
                (not hasattr(self.widget, "checkBox_UseDiffMode")):
            return
        st = self.model.diff_state
        self._set_enabled_ui(bool(st.enabled))
        self.widget.lineEdit_DiffRefChi.setText(str(st.ref_chi_path or ""))
        if self.widget.comboBox_DiffCmap.findText(str(st.cmap_2d)) >= 0:
            self.widget.comboBox_DiffCmap.setCurrentText(str(st.cmap_2d))
        mode_text = self._SCALE_ID_TO_MODE.get(
            str(st.scale_mode_2d), "0 Centered")
        if self.widget.comboBox_DiffScaleMode.findText(mode_text) >= 0:
            self.widget.comboBox_DiffScaleMode.setCurrentText(mode_text)
        self.widget.doubleSpinBox_DiffVmin.setValue(float(st.vmin_2d))
        self.widget.doubleSpinBox_DiffVmax.setValue(float(st.vmax_2d))
        self._refresh_scale_mode_ui()
        self._set_gray_scale_controls_enabled(not self.is_diff_mode_active())
        self._set_diff_scale_controls_enabled(self.is_diff_mode_active())
        self._set_toolbar_controls_enabled(not self.is_diff_mode_active())
        self._refresh_toggle_enabled_state()
        self._set_status()
        self._update_diff_minmax_labels()

    def apply_ui_state_dict(self, diff_dict):
        if not hasattr(self.model, "diff_state") or (self.model.diff_state is None):
            self.model.diff_state = DiffState()
        self.model.diff_state.apply_ui_dict(diff_dict or {})
        self._sync_ui_from_state()
        if self.model.diff_state.ref_chi_path not in (None, ""):
            self._reload_reference_data(show_errors=False)
        else:
            self.model.diff_state.clear_reference_data()
        self._refresh_toggle_enabled_state()

    def to_ui_state_dict(self):
        self.sync_state_from_ui()
        return self.model.diff_state.to_ui_dict()

    def is_diff_mode_active(self):
        st = self.model.diff_state
        return bool(st.enabled) and st.has_ref_1d()

    def _browse_ref_chi(self):
        start_dir = self.model.chi_path if self.model.chi_path else ""
        filen = dialog_openfile_hide_param_dirs(
            self.widget,
            "Choose Reference CHI",
            start_dir,
            "CHI files (*.chi)",
            default_hide_param_dirs=True,
        )[0]
        if filen == "":
            return
        self.widget.lineEdit_DiffRefChi.setText(str(filen))
        self._on_ref_path_changed_from_ui()

    def _clear_reference(self):
        self.widget.lineEdit_DiffRefChi.setText("")
        self.model.diff_state.ref_chi_path = ""
        self.model.diff_state.clear_reference_data()
        self._clear_interp_cache()
        self.model.diff_state.enabled = False
        self._set_enabled_ui(False)
        self._refresh_toggle_enabled_state()
        self._set_gray_scale_controls_enabled(True)
        self._set_diff_scale_controls_enabled(False)
        self._set_toolbar_controls_enabled(True)
        self._set_status("Reference cleared")
        self._update_diff_minmax_labels()
        self._trigger_plot_update()

    def _on_toggled(self, _checked):
        self.sync_state_from_ui()
        if self.model.diff_state.enabled and (self.model.diff_state.ref_chi_path != ""):
            self._reload_reference_data(show_errors=True)
        self._refresh_toggle_enabled_state()
        self._set_gray_scale_controls_enabled(not self.is_diff_mode_active())
        self._set_diff_scale_controls_enabled(self.is_diff_mode_active())
        self._set_toolbar_controls_enabled(not self.is_diff_mode_active())
        self._set_status()
        self._update_diff_minmax_labels()
        self._trigger_plot_update()

    def _is_enabled_ui(self):
        if hasattr(self.widget, "checkBox_Diff"):
            return bool(self.widget.checkBox_Diff.isChecked())
        if hasattr(self.widget, "checkBox_UseDiffMode"):
            return bool(self.widget.checkBox_UseDiffMode.isChecked())
        return False

    def _set_enabled_ui(self, enabled):
        if hasattr(self.widget, "checkBox_Diff"):
            old = self.widget.checkBox_Diff.blockSignals(True)
            self.widget.checkBox_Diff.setChecked(bool(enabled))
            self.widget.checkBox_Diff.blockSignals(old)
        if hasattr(self.widget, "checkBox_UseDiffMode"):
            old = self.widget.checkBox_UseDiffMode.blockSignals(True)
            self.widget.checkBox_UseDiffMode.setChecked(bool(enabled))
            self.widget.checkBox_UseDiffMode.blockSignals(old)

    def _set_toggle_enabled_ui(self, enabled):
        if hasattr(self.widget, "checkBox_Diff"):
            self.widget.checkBox_Diff.setEnabled(bool(enabled))
        if hasattr(self.widget, "checkBox_UseDiffMode"):
            self.widget.checkBox_UseDiffMode.setEnabled(bool(enabled))

    def _refresh_toggle_enabled_state(self):
        has_ref = bool(self.model.diff_state.has_ref_1d())
        ref_path = str(self.model.diff_state.ref_chi_path or "").strip()
        if ref_path == "":
            ref_path = str(self.widget.lineEdit_DiffRefChi.text() or "").strip()
            if ref_path != "":
                self.model.diff_state.ref_chi_path = ref_path
        if (not has_ref) and (not self._in_ref_reload):
            if ref_path != "" and os.path.exists(ref_path):
                self._reload_reference_data(show_errors=False)
                has_ref = bool(self.model.diff_state.has_ref_1d())
        # Enable Diff toggle whenever reference path field has data.
        # Actual activation still requires a valid loaded reference.
        self._set_toggle_enabled_ui(bool(has_ref or (ref_path != "")))
        if not has_ref:
            self.model.diff_state.enabled = False
            self._set_enabled_ui(False)
        diff_active = self.is_diff_mode_active()
        self._set_gray_scale_controls_enabled(not diff_active)
        self._set_diff_scale_controls_enabled(diff_active)
        self._set_toolbar_controls_enabled(not diff_active)

    def _on_ref_path_changed_from_ui(self):
        self.sync_state_from_ui()
        self._reload_reference_data(show_errors=True)
        self._refresh_toggle_enabled_state()
        self._set_status()
        self._update_diff_minmax_labels()
        self._trigger_plot_update()

    def _on_ref_path_text_changed(self, _text):
        # Keep status and enable-state synchronized when path is set
        # programmatically (e.g., loading PARAM JSON).
        self.sync_state_from_ui()
        self._refresh_toggle_enabled_state()
        self._set_status()

    def _on_cmap_changed(self, _text):
        self.sync_state_from_ui()
        self._trigger_plot_update()

    def _on_scale_mode_changed(self, _text):
        self.sync_state_from_ui()
        self._refresh_scale_mode_ui()
        self._update_diff_minmax_labels()
        self._trigger_plot_update()

    def _on_manual_range_changed(self, _value):
        self.sync_state_from_ui()
        self._update_diff_minmax_labels()
        self._trigger_plot_update()

    def _refresh_scale_mode_ui(self):
        self.widget.label_DiffVmin.setEnabled(True)
        self.widget.doubleSpinBox_DiffVmin.setEnabled(True)
        self.widget.label_DiffVmax.setEnabled(True)
        self.widget.doubleSpinBox_DiffVmax.setEnabled(True)

    def _set_gray_scale_controls_enabled(self, enabled):
        if hasattr(self.widget, "groupBox_29"):
            self.widget.groupBox_29.setEnabled(bool(enabled))
        if hasattr(self.widget, "groupBox_CakeColormap"):
            self.widget.groupBox_CakeColormap.setEnabled(bool(enabled))

    def _set_diff_scale_controls_enabled(self, enabled):
        if hasattr(self.widget, "groupBox_DiffCake"):
            self.widget.groupBox_DiffCake.setEnabled(bool(enabled))

    def _set_toolbar_controls_enabled(self, enabled):
        # Keep Night, ptn always user-controllable.
        if hasattr(self.widget, "checkBox_NightView"):
            self.widget.checkBox_NightView.setEnabled(True)

    def _format_value_for_label(self, value):
        v = float(value)
        if np.isfinite(v) and np.isclose(v, round(v), atol=1e-6):
            return str(int(round(v)))
        return "{:.2f}".format(v)

    def _update_diff_minmax_labels(self):
        if not (hasattr(self.widget, "label_DiffVmin") and hasattr(self.widget, "label_DiffVmax")):
            return
        self.widget.label_DiffVmin.setText("Min")
        self.widget.label_DiffVmax.setText("Max")
        if (not self.model.diff_img_exist()) or (not self.model.diff_state.has_ref_2d()):
            return
        try:
            int_cur, tth_cur, chi_cur = self.model.diff_img.get_cake()
            int_cur = np.asarray(int_cur, dtype=float)
            ref_interp = self._interp_ref_cake_to_current(tth_cur, chi_cur)
            if ref_interp is None:
                return
            diff_arr = int_cur - ref_interp
            finite = diff_arr[np.isfinite(diff_arr)]
            if finite.size == 0:
                return
            mn = np.min(finite)
            mx = np.max(finite)
            self.widget.label_DiffVmin.setText(
                "Min ({})".format(self._format_value_for_label(mn)))
            self.widget.label_DiffVmax.setText(
                "Max ({})".format(self._format_value_for_label(mx)))
        except Exception:
            return

    def _reload_reference_data(self, show_errors=False):
        st = self.model.diff_state
        self._in_ref_reload = True
        self._clear_interp_cache()
        ref_path = str(st.ref_chi_path or "")
        st.clear_reference_data()
        if ref_path == "":
            self._refresh_toggle_enabled_state()
            self._in_ref_reload = False
            return
        if not os.path.exists(ref_path):
            if show_errors:
                QtWidgets.QMessageBox.warning(
                    self.widget,
                    "Reference Not Found",
                    "Reference CHI file was not found:\n" + ref_path,
                )
            self._refresh_toggle_enabled_state()
            self._in_ref_reload = False
            return

        try:
            __, __, x_ref, y_ref = readchi(ref_path)
            st.ref_x = np.asarray(x_ref, dtype=float)
            st.ref_y = np.asarray(y_ref, dtype=float)
        except Exception as exc:
            st.clear_reference_data()
            if show_errors:
                QtWidgets.QMessageBox.warning(
                    self.widget,
                    "Reference Load Failed",
                    "Failed to read reference CHI:\n{}\n\n{}".format(ref_path, str(exc)),
                )
            self._refresh_toggle_enabled_state()
            self._in_ref_reload = False
            return

        try:
            temp_model = PeakPoModel8()
            ok, __meta = load_model_from_param(temp_model, ref_path)
            if ok and temp_model.diff_img_exist():
                int_ref, tth_ref, chi_ref = temp_model.diff_img.get_cake()
                st.ref_cake_int = np.asarray(int_ref, dtype=float)
                st.ref_cake_tth = np.asarray(tth_ref, dtype=float)
                st.ref_cake_chi = np.asarray(chi_ref, dtype=float)
        except Exception:
            # 2D reference is optional.
            pass
        self._refresh_toggle_enabled_state()
        self._in_ref_reload = False
        self._update_diff_minmax_labels()

    def _ref2d_token(self, ref_int, ref_tth, ref_chi):
        return (
            id(ref_int),
            id(ref_tth),
            id(ref_chi),
            ref_int.shape,
            ref_tth.shape,
            ref_chi.shape,
        )

    def _curve_token(self, arr):
        if arr.size == 0:
            return (id(arr), 0, None, None)
        return (id(arr), int(arr.size), float(arr[0]), float(arr[-1]))

    def _set_status(self, explicit=""):
        if not hasattr(self.widget, "label_DiffStatus"):
            return
        if explicit != "":
            self.widget.label_DiffStatus.setText(explicit)
            return
        st = self.model.diff_state
        ref_path = str(st.ref_chi_path or "").strip()
        if ref_path == "":
            ref_path = str(self.widget.lineEdit_DiffRefChi.text() or "").strip()
            if ref_path != "":
                st.ref_chi_path = ref_path
        if ref_path == "":
            self.widget.label_DiffStatus.setText("No reference selected")
            return
        ref_name = os.path.basename(ref_path)
        if not st.has_ref_1d():
            self.widget.label_DiffStatus.setText("Reference unavailable: {}".format(ref_name))
            return
        if st.has_ref_2d():
            self.widget.label_DiffStatus.setText("Reference loaded: {} (1D+2D)".format(ref_name))
        else:
            self.widget.label_DiffStatus.setText("Reference loaded: {} (1D only)".format(ref_name))

    def _trigger_plot_update(self):
        if self.plot_ctrl is not None:
            try:
                self.plot_ctrl.update()
            except Exception:
                pass

    def _prepare_ref_1d(self, x_target):
        st = self.model.diff_state
        if not st.has_ref_1d():
            if st.ref_chi_path not in (None, ""):
                self._reload_reference_data(show_errors=False)
        if not st.has_ref_1d():
            return None
        xr = np.asarray(st.ref_x, dtype=float)
        yr = np.asarray(st.ref_y, dtype=float)
        if xr.size < 2:
            return None
        order = np.argsort(xr)
        xr = xr[order]
        yr = yr[order]
        return np.interp(np.asarray(x_target, dtype=float), xr, yr)

    def get_display_pattern(self, x_cur, y_cur):
        """Return x/y to be displayed on the pattern plot."""
        if not self.is_diff_mode_active():
            x = np.asarray(x_cur, dtype=float)
            y = np.asarray(y_cur, dtype=float)
            return x, y
        # In Diff mode, always use raw pattern regardless of Bg checkbox.
        x_raw, y_raw = self.model.base_ptn.get_raw()
        x = np.asarray(x_raw, dtype=float)
        y = np.asarray(y_raw, dtype=float)
        y_ref = self._prepare_ref_1d(x)
        if y_ref is None:
            return x, y
        return x, y - y_ref

    def _interp_ref_cake_to_current(self, tth_cur, chi_cur):
        st = self.model.diff_state
        if not st.has_ref_2d():
            if st.ref_chi_path not in (None, ""):
                self._reload_reference_data(show_errors=False)
        if not st.has_ref_2d():
            return None

        ref_int = np.asarray(st.ref_cake_int, dtype=float)
        ref_tth = np.asarray(st.ref_cake_tth, dtype=float)
        ref_chi = np.asarray(st.ref_cake_chi, dtype=float)
        if ref_int.ndim != 2:
            return None

        tth_cur = np.asarray(tth_cur, dtype=float)
        chi_cur = np.asarray(chi_cur, dtype=float)
        ref_token = self._ref2d_token(ref_int, ref_tth, ref_chi)
        sorted_ref = self._ref2d_sort_cache.get(ref_token)
        if sorted_ref is None:
            order_t = np.argsort(ref_tth)
            ref_tth_sorted = ref_tth[order_t]
            ref_int_sorted = ref_int[:, order_t]
            order_c = np.argsort(ref_chi)
            ref_chi_sorted = ref_chi[order_c]
            ref_int_sorted = ref_int_sorted[order_c, :]
            sorted_ref = (ref_tth_sorted, ref_chi_sorted, ref_int_sorted)
            self._ref2d_sort_cache = {ref_token: sorted_ref}
            self._ref2d_interp_cache = {}
        ref_tth_sorted, ref_chi_sorted, ref_int_sorted = sorted_ref
        interp_key = (ref_token, self._curve_token(tth_cur), self._curve_token(chi_cur))
        cached = self._ref2d_interp_cache.get(interp_key)
        if cached is not None:
            return cached
        interp_t = interp1d(
            ref_tth_sorted,
            ref_int_sorted,
            axis=1,
            bounds_error=False,
            fill_value=np.nan,
            assume_sorted=True,
        )
        tmp = interp_t(tth_cur)
        interp_c = interp1d(
            ref_chi_sorted,
            tmp,
            axis=0,
            bounds_error=False,
            fill_value=np.nan,
            assume_sorted=True,
        )
        out = interp_c(chi_cur)
        self._ref2d_interp_cache = {interp_key: out}
        return out

    def get_display_cake(self, int_cur, tth_cur, chi_cur):
        """Return intensity, tth, chi for display (diff or normal)."""
        inten = np.asarray(int_cur, dtype=float)
        tth = np.asarray(tth_cur, dtype=float)
        chi = np.asarray(chi_cur, dtype=float)
        if not self.is_diff_mode_active():
            return inten, tth, chi
        ref_interp = self._interp_ref_cake_to_current(tth, chi)
        if ref_interp is None:
            return inten, tth, chi
        return inten - ref_interp, tth, chi

    def get_cake_render_config(self, cake_arr):
        st = self.model.diff_state
        if not self.is_diff_mode_active():
            return None
        cmap = st.cmap_2d if st.cmap_2d in self._CMAPS else "coolwarm"
        mode_id = str(st.scale_mode_2d or "asymmetric_centered")
        raw_vmin = float(st.vmin_2d)
        raw_vmax = float(st.vmax_2d)
        center_zero = False
        if mode_id == "asymmetric_centered":
            vmin = raw_vmin if raw_vmin < 0.0 else -max(abs(raw_vmin), 1.0)
            vmax = raw_vmax if raw_vmax > 0.0 else max(abs(raw_vmax), 1.0)
            center_zero = True
        else:  # free_range
            vmin, vmax = raw_vmin, raw_vmax
            if vmin >= vmax:
                vmax = vmin + 1.0
        return {
            "cmap": cmap,
            "vmin": vmin,
            "vmax": vmax,
            "center_zero": center_zero,
        }

    def export_diff_chi(self):
        if not self.model.base_ptn_exist():
            return
        # Diff export is defined against raw patterns even if Bg is checked.
        x_cur, y_cur = self.model.base_ptn.get_raw()
        x_out, y_out = self.get_display_pattern(x_cur, y_cur)
        if (x_out is None) or (y_out is None):
            QtWidgets.QMessageBox.warning(self.widget, "Warning", "No diff data to export.")
            return
        param_dir = get_temp_dir(self.model.get_base_ptn_filename(), branch="-param")
        os.makedirs(param_dir, exist_ok=True)
        base_name = "diff_" + os.path.splitext(os.path.basename(self.model.base_ptn.fname))[0] + ".chi"
        default_path = os.path.join(param_dir, base_name)
        fsave = QtWidgets.QFileDialog.getSaveFileName(
            self.widget,
            "Save Diff CHI",
            default_path,
            "CHI files (*.chi)",
        )[0]
        if fsave == "":
            return
        writechi(fsave, x_out, y_out)

    def export_diff_cake_npy(self):
        if (not self.model.diff_img_exist()) or (not self.model.base_ptn_exist()):
            QtWidgets.QMessageBox.warning(
                self.widget,
                "Warning",
                "No cake data available for export.",
            )
            return
        int_cur, tth_cur, chi_cur = self.model.diff_img.get_cake()
        int_out, __, __ = self.get_display_cake(int_cur, tth_cur, chi_cur)
        if int_out is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning", "No diff cake data to export.")
            return
        param_dir = get_temp_dir(self.model.get_base_ptn_filename(), branch="-param")
        os.makedirs(param_dir, exist_ok=True)
        base_name = "diff_" + os.path.splitext(os.path.basename(self.model.base_ptn.fname))[0] + "_cake.npy"
        default_path = os.path.join(param_dir, base_name)
        fsave = QtWidgets.QFileDialog.getSaveFileName(
            self.widget,
            "Save Diff Cake NPY",
            default_path,
            "NumPy files (*.npy)",
        )[0]
        if fsave == "":
            return
        np.save(fsave, np.asarray(int_out, dtype=float))
