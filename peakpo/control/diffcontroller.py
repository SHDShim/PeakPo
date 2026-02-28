import os
import numpy as np
from qtpy import QtWidgets

from ..model import PeakPoModel8
from ..model.diff_state import DiffState
from ..model.param_session_io import load_model_from_param
from ..utils import readchi, writechi, get_temp_dir


class DiffController(object):
    """Controller for 1D/2D reference subtraction (Diff mode)."""

    _CMAPS = [
        "RdBu_r",
        "seismic",
        "coolwarm",
        "PiYG",
        "PRGn",
        "BrBG",
        "gray",
        "gray_r",
    ]

    def __init__(self, model, widget, plot_ctrl=None):
        self.model = model
        self.widget = widget
        self.plot_ctrl = plot_ctrl
        if not hasattr(self.model, "diff_state") or (self.model.diff_state is None):
            self.model.diff_state = DiffState()
        self._connect_channel()
        self._init_ui_from_state()

    def _connect_channel(self):
        if not hasattr(self.widget, "checkBox_UseDiffMode"):
            return
        self.widget.pushButton_DiffRefBrowse.clicked.connect(self._browse_ref_chi)
        self.widget.pushButton_DiffRefClear.clicked.connect(self._clear_reference)
        self.widget.checkBox_UseDiffMode.toggled.connect(self._on_toggled)
        self.widget.lineEdit_DiffRefChi.editingFinished.connect(
            self._on_ref_path_changed_from_ui)
        self.widget.comboBox_DiffCmap.currentTextChanged.connect(self._on_cmap_changed)
        self.widget.comboBox_DiffPositiveSide.currentIndexChanged.connect(
            self._on_polarity_changed)
        self.widget.checkBox_DiffAutoRange.toggled.connect(self._on_auto_range_changed)
        self.widget.doubleSpinBox_DiffVmin.valueChanged.connect(self._on_manual_range_changed)
        self.widget.doubleSpinBox_DiffVmax.valueChanged.connect(self._on_manual_range_changed)
        self.widget.pushButton_ExportDiffChi.clicked.connect(self.export_diff_chi)
        self.widget.pushButton_ExportDiffCakeNpy.clicked.connect(self.export_diff_cake_npy)

    def _init_ui_from_state(self):
        if not hasattr(self.widget, "checkBox_UseDiffMode"):
            return
        st = self.model.diff_state
        self.widget.lineEdit_DiffRefChi.setText(str(st.ref_chi_path or ""))
        self.widget.checkBox_UseDiffMode.setChecked(bool(st.enabled))
        self.widget.comboBox_DiffCmap.clear()
        self.widget.comboBox_DiffCmap.addItems(self._CMAPS)
        cmap = st.cmap_2d if st.cmap_2d in self._CMAPS else "RdBu_r"
        self.widget.comboBox_DiffCmap.setCurrentText(cmap)
        self.widget.comboBox_DiffPositiveSide.setCurrentIndex(
            0 if st.positive_side != "blue_cool" else 1)
        self.widget.checkBox_DiffAutoRange.setChecked(bool(st.auto_range_2d))
        self.widget.doubleSpinBox_DiffVmin.setValue(float(st.vmin_2d))
        self.widget.doubleSpinBox_DiffVmax.setValue(float(st.vmax_2d))
        self._set_manual_range_enabled(not st.auto_range_2d)
        if st.ref_chi_path not in (None, ""):
            self._reload_reference_data(show_errors=False)
        self._set_status()

    def sync_state_from_ui(self):
        if not hasattr(self.widget, "checkBox_UseDiffMode"):
            return
        st = self.model.diff_state
        st.enabled = bool(self.widget.checkBox_UseDiffMode.isChecked())
        st.ref_chi_path = str(self.widget.lineEdit_DiffRefChi.text()).strip()
        st.cmap_2d = str(self.widget.comboBox_DiffCmap.currentText())
        st.positive_side = "blue_cool" \
            if (self.widget.comboBox_DiffPositiveSide.currentIndex() == 1) \
            else "red_warm"
        st.auto_range_2d = bool(self.widget.checkBox_DiffAutoRange.isChecked())
        st.vmin_2d = float(self.widget.doubleSpinBox_DiffVmin.value())
        st.vmax_2d = float(self.widget.doubleSpinBox_DiffVmax.value())

    def _sync_ui_from_state(self):
        if not hasattr(self.widget, "checkBox_UseDiffMode"):
            return
        st = self.model.diff_state
        self.widget.checkBox_UseDiffMode.setChecked(bool(st.enabled))
        self.widget.lineEdit_DiffRefChi.setText(str(st.ref_chi_path or ""))
        if self.widget.comboBox_DiffCmap.findText(str(st.cmap_2d)) >= 0:
            self.widget.comboBox_DiffCmap.setCurrentText(str(st.cmap_2d))
        self.widget.comboBox_DiffPositiveSide.setCurrentIndex(
            0 if st.positive_side != "blue_cool" else 1)
        self.widget.checkBox_DiffAutoRange.setChecked(bool(st.auto_range_2d))
        self.widget.doubleSpinBox_DiffVmin.setValue(float(st.vmin_2d))
        self.widget.doubleSpinBox_DiffVmax.setValue(float(st.vmax_2d))
        self._set_manual_range_enabled(not st.auto_range_2d)
        self._set_status()

    def apply_ui_state_dict(self, diff_dict):
        if not hasattr(self.model, "diff_state") or (self.model.diff_state is None):
            self.model.diff_state = DiffState()
        self.model.diff_state.apply_ui_dict(diff_dict or {})
        self._sync_ui_from_state()
        if self.model.diff_state.ref_chi_path not in (None, ""):
            self._reload_reference_data(show_errors=False)
        else:
            self.model.diff_state.clear_reference_data()

    def to_ui_state_dict(self):
        self.sync_state_from_ui()
        return self.model.diff_state.to_ui_dict()

    def is_diff_mode_active(self):
        st = self.model.diff_state
        return bool(st.enabled) and st.has_ref_1d()

    def _browse_ref_chi(self):
        start_dir = self.model.chi_path if self.model.chi_path else ""
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget,
            "Choose Reference CHI",
            start_dir,
            "CHI files (*.chi)",
        )[0]
        if filen == "":
            return
        self.widget.lineEdit_DiffRefChi.setText(str(filen))
        self._on_ref_path_changed_from_ui()

    def _clear_reference(self):
        self.widget.lineEdit_DiffRefChi.setText("")
        self.model.diff_state.ref_chi_path = ""
        self.model.diff_state.clear_reference_data()
        self._set_status("Reference cleared")
        self._trigger_plot_update()

    def _on_toggled(self, _checked):
        self.sync_state_from_ui()
        if self.model.diff_state.enabled and (self.model.diff_state.ref_chi_path != ""):
            self._reload_reference_data(show_errors=True)
        self._set_status()
        self._trigger_plot_update()

    def _on_ref_path_changed_from_ui(self):
        self.sync_state_from_ui()
        self._reload_reference_data(show_errors=True)
        self._set_status()
        self._trigger_plot_update()

    def _on_cmap_changed(self, _text):
        self.sync_state_from_ui()
        self._trigger_plot_update()

    def _on_polarity_changed(self, _index):
        self.sync_state_from_ui()
        self._trigger_plot_update()

    def _on_auto_range_changed(self, checked):
        self.sync_state_from_ui()
        self._set_manual_range_enabled(not checked)
        self._trigger_plot_update()

    def _on_manual_range_changed(self, _value):
        self.sync_state_from_ui()
        if self.model.diff_state.auto_range_2d:
            return
        self._trigger_plot_update()

    def _set_manual_range_enabled(self, enabled):
        self.widget.doubleSpinBox_DiffVmin.setEnabled(bool(enabled))
        self.widget.doubleSpinBox_DiffVmax.setEnabled(bool(enabled))

    def _reload_reference_data(self, show_errors=False):
        st = self.model.diff_state
        ref_path = str(st.ref_chi_path or "")
        st.clear_reference_data()
        if ref_path == "":
            return
        if not os.path.exists(ref_path):
            if show_errors:
                QtWidgets.QMessageBox.warning(
                    self.widget,
                    "Reference Not Found",
                    "Reference CHI file was not found:\n" + ref_path,
                )
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

    def _set_status(self, explicit=""):
        if not hasattr(self.widget, "label_DiffStatus"):
            return
        if explicit != "":
            self.widget.label_DiffStatus.setText(explicit)
            return
        st = self.model.diff_state
        if st.ref_chi_path in (None, ""):
            self.widget.label_DiffStatus.setText("No reference selected")
            return
        ref_name = os.path.basename(st.ref_chi_path)
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
        x = np.asarray(x_cur, dtype=float)
        y = np.asarray(y_cur, dtype=float)
        if not self.is_diff_mode_active():
            return x, y
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

        order_t = np.argsort(ref_tth)
        ref_tth = ref_tth[order_t]
        ref_int = ref_int[:, order_t]

        order_c = np.argsort(ref_chi)
        ref_chi = ref_chi[order_c]
        ref_int = ref_int[order_c, :]

        tth_cur = np.asarray(tth_cur, dtype=float)
        chi_cur = np.asarray(chi_cur, dtype=float)

        tmp = np.empty((ref_int.shape[0], tth_cur.size), dtype=float)
        for i in range(ref_int.shape[0]):
            tmp[i, :] = np.interp(tth_cur, ref_tth, ref_int[i, :], left=np.nan, right=np.nan)

        out = np.empty((chi_cur.size, tth_cur.size), dtype=float)
        for j in range(tth_cur.size):
            out[:, j] = np.interp(chi_cur, ref_chi, tmp[:, j], left=np.nan, right=np.nan)
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
        cmap = st.cmap_2d if st.cmap_2d in self._CMAPS else "RdBu_r"
        if st.positive_side == "blue_cool":
            if cmap.endswith("_r"):
                cmap = cmap[:-2]
            else:
                cmap = cmap + "_r"
        data = np.asarray(cake_arr, dtype=float)
        finite = data[np.isfinite(data)]
        if (finite.size == 0) or st.auto_range_2d:
            if finite.size == 0:
                vmin, vmax = -1.0, 1.0
            else:
                lo = np.percentile(finite, 1.0)
                hi = np.percentile(finite, 99.0)
                if lo == hi:
                    lo = float(np.min(finite))
                    hi = float(np.max(finite))
                if lo == hi:
                    lo -= 1.0
                    hi += 1.0
                vmin, vmax = float(lo), float(hi)
        else:
            vmin, vmax = float(st.vmin_2d), float(st.vmax_2d)
            if vmin >= vmax:
                vmax = vmin + 1.0
        return {"cmap": cmap, "vmin": vmin, "vmax": vmax}

    def export_diff_chi(self):
        if not self.model.base_ptn_exist():
            return
        if self.widget.checkBox_BgSub.isChecked():
            x_cur, y_cur = self.model.base_ptn.get_bgsub()
        else:
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
