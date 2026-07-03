import os
import traceback
from qtpy import QtCore
from qtpy import QtWidgets
from .mplcontroller import MplController
from .peakfittablecontroller import PeakfitTableController
from ..utils import make_filename, get_temp_dir, dialog_openfile_hide_param_dirs
from ..compat_pickle import PeakPoCompatDillUnpickler
from ..model.param_session_io import load_section_from_param
from ..ds_section.section import DEFAULT_CENTER_HALF_RANGE, DEFAULT_FWHM_MIN, \
    DEFAULT_FWHM_MAX, DEFAULT_NL_MIN, DEFAULT_NL_MAX, \
    normalize_peak_phase_name


class _TableBackspaceKeyFilter(QtCore.QObject):
    def __init__(self, parent, table, callback):
        super(_TableBackspaceKeyFilter, self).__init__(parent)
        self.table = table
        self.callback = callback

    def eventFilter(self, obj, event):
        if obj != self.table:
            return False
        if event.type() != QtCore.QEvent.KeyPress:
            return False
        if event.key() != QtCore.Qt.Key_Backspace:
            return False
        return bool(self.callback())


class _PeakConstraintsDialog(QtWidgets.QDialog):
    PARAMS = [
        ("Area", "amplitude", "amplitude_vary", "amplitude_min", "amplitude_max", 3),
        ("Position", "center", "center_vary", "center_min", "center_max", 5),
        ("FWHM", "sigma", "sigma_vary", "sigma_min", "sigma_max", 5),
        ("nL", "fraction", "fraction_vary", "fraction_min", "fraction_max", 3),
    ]
    def __init__(self, controller, peak_row):
        super(_PeakConstraintsDialog, self).__init__(controller.widget)
        self.controller = controller
        self.peak_row = peak_row
        self.setWindowTitle("Peak constraints")
        self.setModal(False)
        self.resize(760, 260)
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setRowCount(len(self.PARAMS))
        self.table.setHorizontalHeaderLabels(
            ["Parameter", "Value", "Vary", "Use Min", "Min", "Use Max", "Max"])
        layout.addWidget(self.table)
        button_row = QtWidgets.QHBoxLayout()
        self.button_visual_position = QtWidgets.QPushButton(
            "Set position range from plot", self)
        self.button_visual_fwhm = QtWidgets.QPushButton(
            "Set FWHM max from plot range", self)
        self.button_apply = QtWidgets.QPushButton("Apply", self)
        self.button_close = QtWidgets.QPushButton("Close", self)
        for button in (
                self.button_visual_position, self.button_visual_fwhm,
                self.button_apply, self.button_close):
            button_row.addWidget(button)
        layout.addLayout(button_row)
        self._populate()
        self.button_apply.clicked.connect(self.apply)
        self.button_close.clicked.connect(self.close)
        self.button_visual_position.clicked.connect(self._arm_position_range)
        self.button_visual_fwhm.clicked.connect(self._arm_fwhm_range)

    def _peak(self):
        return self.controller.model.current_section.peaks_in_queue[self.peak_row]

    def _spinbox(self, value, decimals):
        box = QtWidgets.QDoubleSpinBox(self.table)
        box.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                         QtCore.Qt.AlignVCenter)
        box.setDecimals(decimals)
        box.setMinimum(-1000000.0)
        box.setMaximum(1000000.0)
        box.setSingleStep(10 ** (-decimals))
        box.setKeyboardTracking(False)
        box.setValue(float(value))
        return box

    def _checkbox(self, checked):
        box = QtWidgets.QCheckBox(self.table)
        box.setChecked(bool(checked))
        box.setStyleSheet("margin-left:12px; margin-right:12px;")
        return box

    def _suggested_max_value(self, peak, value_key):
        value = abs(float(peak.get(value_key, 0.0)))
        if value_key == "amplitude":
            return 10.0 * value if value > 0.0 else 1.0
        return float(peak.get(value_key, 0.0))

    def _legacy_auto_amplitude_max(self, peak, max_value):
        if "amplitude_max_enabled" in peak:
            return False
        if max_value is None:
            return False
        try:
            amp = float(peak.get("amplitude", 0.0))
            max_value = float(max_value)
        except Exception:
            return False
        return abs(max_value - amp) <= max(1e-12, abs(amp) * 1e-10)

    def _update_suggested_amplitude_max(self, value, use_max_box, max_box):
        if use_max_box.isChecked():
            return
        suggested = 10.0 * abs(float(value)) if float(value) != 0.0 else 1.0
        max_box.setValue(suggested)

    def _populate(self):
        peak = self._peak()
        for row, (label, value_key, vary_key, min_key, max_key, decimals) in \
                enumerate(self.PARAMS):
            item = QtWidgets.QTableWidgetItem(label)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, 0, item)
            value_box = self._spinbox(peak.get(value_key, 0.0), decimals)
            self.table.setCellWidget(row, 1, value_box)
            self.table.setCellWidget(row, 2, self._checkbox(peak.get(vary_key, True)))
            min_value = peak.get(min_key, None)
            max_value = peak.get(max_key, None)
            if value_key == "amplitude":
                if min_value is None:
                    min_value = 0.0
                if not bool(peak.get("amplitude_max_enabled",
                                     max_value is not None)):
                    max_value = None
                if self._legacy_auto_amplitude_max(peak, max_value):
                    max_value = None
            if value_key in ("center", "sigma", "fraction"):
                default_min, default_max = \
                    self.controller.default_bound_values(peak, value_key)
                if min_value is None:
                    min_value = default_min
                if max_value is None:
                    max_value = default_max
            use_min_box = self._checkbox(min_value is not None)
            min_box = self._spinbox(
                0.0 if min_value is None else min_value, decimals)
            use_max_box = self._checkbox(max_value is not None)
            max_display_value = self._suggested_max_value(peak, value_key) \
                if max_value is None else max_value
            max_box = self._spinbox(max_display_value, decimals)
            min_box.setEnabled(use_min_box.isChecked())
            max_box.setEnabled(use_max_box.isChecked())
            use_min_box.toggled.connect(min_box.setEnabled)
            use_max_box.toggled.connect(max_box.setEnabled)
            if value_key == "amplitude":
                value_box.valueChanged.connect(
                    lambda value, use_max_box=use_max_box, max_box=max_box:
                    self._update_suggested_amplitude_max(
                        value, use_max_box, max_box))
            self.table.setCellWidget(row, 3, use_min_box)
            self.table.setCellWidget(row, 4, min_box)
            self.table.setCellWidget(row, 5, use_max_box)
            self.table.setCellWidget(row, 6, max_box)
        self.table.resizeColumnsToContents()

    def apply(self):
        if not self.controller.model.current_section_exist():
            return
        self.controller.model.current_section.invalidate_fit_result()
        peak = self._peak()
        for row, (__label, value_key, vary_key, min_key, max_key, __decimals) in \
                enumerate(self.PARAMS):
            peak[value_key] = float(self.table.cellWidget(row, 1).value())
            peak[vary_key] = bool(self.table.cellWidget(row, 2).isChecked())
            peak[min_key] = float(self.table.cellWidget(row, 4).value()) \
                if self.table.cellWidget(row, 3).isChecked() else None
            use_max = bool(self.table.cellWidget(row, 5).isChecked())
            peak[max_key] = float(self.table.cellWidget(row, 6).value()) \
                if use_max else None
            if value_key == "amplitude":
                peak["amplitude_max_enabled"] = use_max
        self.controller.set_tableWidget_PkParams_unsaved()
        self.controller.peakfit_table_ctrl.update_peak_parameters()
        self.controller.peakfit_table_ctrl.update_peak_constraints()
        self.controller.plot_ctrl.update()

    def _arm_position_range(self):
        if self.controller.plot_interaction_ctrl is None:
            return

        def apply_range(xmin, xmax):
            peak = self._peak()
            peak["center_min"] = float(xmin)
            peak["center_max"] = float(xmax)
            self.table.cellWidget(1, 3).setChecked(True)
            self.table.cellWidget(1, 4).setValue(float(xmin))
            self.table.cellWidget(1, 5).setChecked(True)
            self.table.cellWidget(1, 6).setValue(float(xmax))
            self.apply()

        self.controller.plot_interaction_ctrl.start_range_tool(
            "Set peak position range", apply_range)

    def _arm_fwhm_range(self):
        if self.controller.plot_interaction_ctrl is None:
            return

        def apply_range(xmin, xmax):
            width = abs(float(xmax) - float(xmin))
            peak = self._peak()
            peak["sigma_min"] = 0.0
            peak["sigma_max"] = width
            self.table.cellWidget(2, 3).setChecked(True)
            self.table.cellWidget(2, 4).setValue(0.0)
            self.table.cellWidget(2, 5).setChecked(True)
            self.table.cellWidget(2, 6).setValue(width)
            self.apply()

        self.controller.plot_interaction_ctrl.start_range_tool(
            "Set peak FWHM maximum", apply_range)


class _DefaultPeakBoundsDialog(QtWidgets.QDialog):
    def __init__(self, controller):
        super(_DefaultPeakBoundsDialog, self).__init__(controller.widget)
        self.controller = controller
        self.setWindowTitle("Default peak bounds")
        self.setModal(False)
        self.resize(430, 210)
        defaults = controller.default_peak_bounds()

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.spin_center_half_range = self._spinbox(
            defaults["center_half_range"], 5, 0.0, 1000000.0)
        self.spin_fwhm_min = self._spinbox(
            defaults["fwhm_min"], 5, 0.0, 1000000.0)
        self.spin_fwhm_max = self._spinbox(
            defaults["fwhm_max"], 5, 0.0, 1000000.0)
        form.addRow("Position +/- (degrees)", self.spin_center_half_range)
        form.addRow("FWHM min", self.spin_fwhm_min)
        form.addRow("FWHM max", self.spin_fwhm_max)
        layout.addLayout(form)

        self.check_apply_existing = QtWidgets.QCheckBox(
            "Apply to all peaks currently in the list", self)
        self.check_apply_existing.setChecked(True)
        layout.addWidget(self.check_apply_existing)

        buttons = QtWidgets.QHBoxLayout()
        self.button_apply = QtWidgets.QPushButton("Apply", self)
        self.button_close = QtWidgets.QPushButton("Close", self)
        buttons.addStretch(1)
        buttons.addWidget(self.button_apply)
        buttons.addWidget(self.button_close)
        layout.addLayout(buttons)

        self.button_apply.clicked.connect(self.apply)
        self.button_close.clicked.connect(self.close)

    def _spinbox(self, value, decimals, minimum, maximum):
        box = QtWidgets.QDoubleSpinBox(self)
        box.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                         QtCore.Qt.AlignVCenter)
        box.setDecimals(decimals)
        box.setMinimum(float(minimum))
        box.setMaximum(float(maximum))
        box.setSingleStep(10 ** (-decimals))
        box.setKeyboardTracking(False)
        box.setValue(float(value))
        return box

    def apply(self):
        fwhm_min = float(self.spin_fwhm_min.value())
        fwhm_max = float(self.spin_fwhm_max.value())
        if fwhm_max < fwhm_min:
            QtWidgets.QMessageBox.warning(
                self, "Warning", "FWHM max must be greater than or equal to FWHM min.")
            return
        self.controller.set_default_peak_bounds_values(
            center_half_range=float(self.spin_center_half_range.value()),
            fwhm_min=fwhm_min,
            fwhm_max=fwhm_max,
        )
        if self.check_apply_existing.isChecked():
            self.controller.apply_default_peak_bounds_to_all_peaks()
        self.close()


class _BackgroundSetupDialog(QtWidgets.QDialog):
    def __init__(self, controller):
        super(_BackgroundSetupDialog, self).__init__(controller.widget)
        self.controller = controller
        self._coeffs = [
            dict(coeff)
            for coeff in getattr(self._section(), "baseline_in_queue", [])
        ]
        self.setWindowTitle("Background setup")
        self.setModal(False)
        self.resize(760, 520)
        layout = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Polynomial order", self))
        self.spin_order = QtWidgets.QSpinBox(self)
        self.spin_order.setMinimum(0)
        self.spin_order.setMaximum(20)
        self.spin_order.setValue(max(0, self._section().get_order_of_baseline_in_queue()))
        top.addWidget(self.spin_order)
        top.addStretch(1)
        layout.addLayout(top)

        layout.addWidget(QtWidgets.QLabel("Polynomial coefficients", self))
        self.table_coeff = QtWidgets.QTableWidget(self)
        self.table_coeff.setColumnCount(2)
        self.table_coeff.setHorizontalHeaderLabels(["Value", "Vary"])
        layout.addWidget(self.table_coeff)

        layout.addWidget(QtWidgets.QLabel("Background anchor ranges", self))
        self.table_anchor = QtWidgets.QTableWidget(self)
        self.table_anchor.setColumnCount(3)
        self.table_anchor.setHorizontalHeaderLabels(["xmin", "xmax", "Weight"])
        layout.addWidget(self.table_anchor)

        anchor_buttons = QtWidgets.QHBoxLayout()
        self.button_add_anchor = QtWidgets.QPushButton("Add current view", self)
        self.button_visual_anchor = QtWidgets.QPushButton("Add range from plot", self)
        self.button_remove_anchor = QtWidgets.QPushButton("Remove range", self)
        self.button_visual_anchor.setCheckable(True)
        self.button_add_anchor.setToolTip(
            "Add the currently visible 2-theta range as a background anchor range.")
        self.button_visual_anchor.setToolTip(
            "Click once, then drag one or more ranges on the plot. Right-click to finish.")
        self.button_remove_anchor.setToolTip(
            "Remove the selected background anchor range rows.")
        for button in (
                self.button_add_anchor, self.button_visual_anchor,
                self.button_remove_anchor):
            anchor_buttons.addWidget(button)
        layout.addLayout(anchor_buttons)

        buttons = QtWidgets.QHBoxLayout()
        self.button_apply = QtWidgets.QPushButton("Apply", self)
        self.button_close = QtWidgets.QPushButton("Close", self)
        buttons.addStretch(1)
        buttons.addWidget(self.button_apply)
        buttons.addWidget(self.button_close)
        layout.addLayout(buttons)

        self._populate()
        self.spin_order.valueChanged.connect(self._rebuild_coeff_table)
        self.button_add_anchor.clicked.connect(self._add_current_view_anchor)
        self.button_visual_anchor.clicked.connect(self._arm_anchor_range)
        self.button_remove_anchor.clicked.connect(self._remove_anchor_rows)
        self.button_apply.clicked.connect(self.apply)
        self.button_close.clicked.connect(self.close)

    def closeEvent(self, event):
        if self.controller.plot_interaction_ctrl is not None:
            self.controller.plot_interaction_ctrl.cancel_range_tool()
        super(_BackgroundSetupDialog, self).closeEvent(event)

    def _section(self):
        return self.controller.model.current_section

    def _spinbox(self, value, decimals=5):
        box = QtWidgets.QDoubleSpinBox(self)
        box.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                         QtCore.Qt.AlignVCenter)
        box.setDecimals(decimals)
        box.setMinimum(-1000000.0)
        box.setMaximum(1000000.0)
        box.setSingleStep(10 ** (-decimals))
        box.setKeyboardTracking(False)
        box.setValue(float(value))
        return box

    def _checkbox(self, checked):
        box = QtWidgets.QCheckBox(self)
        box.setChecked(bool(checked))
        box.setStyleSheet("margin-left:12px; margin-right:12px;")
        return box

    def _populate(self):
        self._rebuild_coeff_table()
        anchors = getattr(self._section(), "background_anchor_ranges", [])
        self.table_anchor.setRowCount(0)
        for anchor in anchors:
            self._add_anchor_row(anchor)

    def _read_coeff_table(self):
        coeffs = []
        for row in range(self.table_coeff.rowCount()):
            value_widget = self.table_coeff.cellWidget(row, 0)
            vary_widget = self.table_coeff.cellWidget(row, 1)
            if value_widget is None or vary_widget is None:
                continue
            coeffs.append({
                "value": float(value_widget.value()),
                "vary": bool(vary_widget.isChecked()),
            })
        return coeffs

    def _coeffs_for_order(self):
        n_coeff = int(self.spin_order.value()) + 1
        coeffs = [dict(coeff) for coeff in self._coeffs[:n_coeff]]
        while len(coeffs) < n_coeff:
            coeffs.append({"value": 0.0, "vary": True})
        return coeffs

    def _rebuild_coeff_table(self):
        if self.table_coeff.rowCount() > 0:
            self._coeffs = self._read_coeff_table()
        coeffs = self._coeffs_for_order()
        self.table_coeff.setRowCount(len(coeffs))
        for row, coeff in enumerate(coeffs):
            self.table_coeff.setCellWidget(
                row, 0, self._spinbox(coeff.get("value", 0.0), 5))
            self.table_coeff.setCellWidget(
                row, 1, self._checkbox(coeff.get("vary", True)))
        self.table_coeff.resizeColumnsToContents()

    def _add_anchor_row(self, anchor=None):
        if not isinstance(anchor, dict):
            anchor = None
        row = self.table_anchor.rowCount()
        self.table_anchor.insertRow(row)
        if anchor is None:
            x0, x1 = self.controller.widget.mpl.canvas.ax_pattern.get_xlim()
            anchor = {"xmin": min(x0, x1), "xmax": max(x0, x1), "weight": 10.0}
        for col, key in enumerate(("xmin", "xmax", "weight")):
            value = anchor.get(key, 10.0 if key == "weight" else 0.0)
            self.table_anchor.setCellWidget(row, col, self._spinbox(value, 5))
        self.table_anchor.resizeColumnsToContents()
        return row

    def _read_anchor_rows(self):
        anchors = []
        for row in range(self.table_anchor.rowCount()):
            xmin_widget = self.table_anchor.cellWidget(row, 0)
            xmax_widget = self.table_anchor.cellWidget(row, 1)
            weight_widget = self.table_anchor.cellWidget(row, 2)
            if xmin_widget is None or xmax_widget is None or weight_widget is None:
                continue
            xmin = float(xmin_widget.value())
            xmax = float(xmax_widget.value())
            weight = float(weight_widget.value())
            anchors.append({
                "xmin": min(xmin, xmax),
                "xmax": max(xmin, xmax),
                "weight": max(1.0, weight),
            })
        return anchors

    def _sync_anchor_rows_to_section(self):
        self._section().background_anchor_ranges = self._read_anchor_rows()
        self.controller.set_tableWidget_PkParams_unsaved()

    def _add_current_view_anchor(self, checked=False):
        del checked
        self._add_anchor_row()
        self._sync_anchor_rows_to_section()
        label = getattr(self.controller.widget, "label_PlotHelp", None)
        if label is not None:
            label.setText(
                "Background anchor range added from the current plot view.")

    def _remove_anchor_rows(self, checked=False):
        del checked
        rows = set()
        selection_model = self.table_anchor.selectionModel()
        if selection_model is not None:
            rows = {index.row() for index in selection_model.selectedRows()}
            if not rows:
                rows = {index.row() for index in selection_model.selectedIndexes()}
        if not rows and self.table_anchor.currentRow() >= 0:
            rows.add(self.table_anchor.currentRow())
        for row in sorted(rows, reverse=True):
            self.table_anchor.removeRow(row)
        self._sync_anchor_rows_to_section()

    def _arm_anchor_range(self, checked=False):
        if self.controller.plot_interaction_ctrl is None:
            return
        if not checked:
            self.controller.plot_interaction_ctrl.cancel_range_tool()
            return

        def add_range(xmin, xmax):
            self._add_anchor_row(
                {"xmin": float(xmin), "xmax": float(xmax), "weight": 10.0})
            self._sync_anchor_rows_to_section()
            old_state = self.button_visual_anchor.blockSignals(True)
            self.button_visual_anchor.setChecked(True)
            self.button_visual_anchor.blockSignals(old_state)
            self.button_visual_anchor.setText("Stop picking ranges")

        def deactivate_button():
            old_state = self.button_visual_anchor.blockSignals(True)
            self.button_visual_anchor.setChecked(False)
            self.button_visual_anchor.blockSignals(old_state)
            self.button_visual_anchor.setText("Add range from plot")
            self.button_visual_anchor.setToolTip(
                "Click once, then drag one or more ranges on the plot. Right-click to finish.")

        self.controller.plot_interaction_ctrl.start_range_tool(
            "Add background anchor range", add_range, repeat=True,
            cancel_callback=deactivate_button)
        self.button_visual_anchor.setText("Stop picking ranges")
        self.button_visual_anchor.setToolTip(
            "Drag one or more ranges on the plot. Click again or right-click on the plot to finish.")

    def apply(self):
        if self.controller.plot_interaction_ctrl is not None:
            self.controller.plot_interaction_ctrl.cancel_range_tool()
        section = self._section()
        section.set_baseline(int(self.spin_order.value()))
        for row in range(self.table_coeff.rowCount()):
            section.baseline_in_queue[row]["value"] = \
                float(self.table_coeff.cellWidget(row, 0).value())
            section.baseline_in_queue[row]["vary"] = \
                bool(self.table_coeff.cellWidget(row, 1).isChecked())
        section.background_anchor_ranges = self._read_anchor_rows()
        self.controller.widget.spinBox_BGPolyOrder.setValue(
            int(self.spin_order.value()))
        self.controller.set_tableWidget_PkParams_unsaved()
        self.controller.peakfit_table_ctrl.update_baseline_constraints()
        self.controller.plot_ctrl.update()


class PeakFitController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.peakfit_table_ctrl = PeakfitTableController(
            self.model, self.widget)
        self._setup_table_status_fields()
        self._table_backspace_key_filters = []
        self._constraints_dialog = None
        self._background_dialog = None
        self._default_bounds_dialog = None
        self._default_peak_bounds = {
            "center_half_range": DEFAULT_CENTER_HALF_RANGE,
            "fwhm_min": DEFAULT_FWHM_MIN,
            "fwhm_max": DEFAULT_FWHM_MAX,
        }
        self.plot_interaction_ctrl = None
        self.ucfit_ctrl = None
        self.connect_channel()

    def set_ucfit_controller(self, ucfit_ctrl):
        self.ucfit_ctrl = ucfit_ctrl

    def _clear_collected_ucfit_results(self):
        clear_results = getattr(
            self.ucfit_ctrl, "clear_collected_peakfit_results", None)
        if callable(clear_results):
            clear_results()

    def connect_channel(self):
        self.widget.pushButton_SetFitSection.clicked.connect(
            self.set_fit_section)
        self.widget.pushButton_ConductFitting.clicked.connect(
            self.conduct_fitting)
        self.widget.pushButton_PkSave.clicked.connect(
            self.save_to_section)
        self.widget.pushButton_ClearSection.clicked.connect(
            self.clear_this_section)
        self.widget.pushButton_PkFtSectionRemove.clicked.connect(
            self.remove_section)
        self.widget.pushButton_PkFtSectionSetToCurrent.clicked.\
            connect(self.set_section_to_current)
        self.widget.pushButton_AddRemoveFromJlist.clicked.connect(
            self.get_peaks_from_jcpds)
        self.widget.pushButton_RestoreMissingJcpdsPeaks.clicked.connect(
            self.restore_missing_jcpds_peaks)
        self.widget.pushButton_ZoomToSection.clicked.connect(
            self.zoom_to_section)
        self.widget.pushButton_PkFtSectionSavetoXLS.clicked.\
            connect(self.save_to_xls)
        self.widget.pushButton_PkFtSectionImport.clicked.connect(
            self.import_section_from_dpp)
        self.widget.pushButton_PlotSelectedPkFtResults.clicked.connect(
            self._plot_selected_fitting)
        if hasattr(self.widget, "pushButton_PkRemoveSelectedPeaks"):
            self.widget.pushButton_PkRemoveSelectedPeaks.clicked.connect(
                self.remove_selected_peak_from_table)
        if hasattr(self.widget, "pushButton_PkConstraintsPopup"):
            self.widget.pushButton_PkConstraintsPopup.clicked.connect(
                self.open_peak_constraints_dialog)
        if hasattr(self.widget, "pushButton_PkDefaultBounds"):
            self.widget.pushButton_PkDefaultBounds.clicked.connect(
                self.open_default_peak_bounds_dialog)
        if hasattr(self.widget, "pushButton_PkBackgroundPopup"):
            self.widget.pushButton_PkBackgroundPopup.clicked.connect(
                self.open_background_setup_dialog)
        self._install_table_backspace_key_filters()
        # The line below exist in session_ctrl
        # self.widget.pushButton_PkFtSectionSavetoDPP.clicked.coonect

    def _install_table_backspace_key_filters(self):
        bindings = [
            ("tableWidget_PkParams", self.remove_selected_peak_from_table),
            ("tableWidget_PkFtSections", self.remove_section),
        ]
        for table_name, callback in bindings:
            if not hasattr(self.widget, table_name):
                continue
            table = getattr(self.widget, table_name)
            key_filter = _TableBackspaceKeyFilter(
                self.widget, table, callback)
            table.installEventFilter(key_filter)
            self._table_backspace_key_filters.append(key_filter)

    def remove_selected_peak_from_table(self):
        if not self.model.current_section_exist():
            return False
        table = self.widget.tableWidget_PkParams
        rows = set()
        selection_model = table.selectionModel()
        if selection_model is not None:
            rows = {index.row() for index in selection_model.selectedRows()}
            if not rows:
                rows = {
                    index.row()
                    for index in selection_model.selectedIndexes()
                }
        if not rows and table.currentRow() >= 0:
            rows.add(table.currentRow())
        valid_rows = [
            row for row in rows
            if 0 <= row < self.model.current_section.get_number_of_peaks_in_queue()
        ]
        if valid_rows == []:
            return False
        reply = QtWidgets.QMessageBox.question(
            self.widget, "Message",
            "Are you sure you want to delete the selected peaks?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No:
            return True
        for row in sorted(valid_rows, reverse=True):
            self.model.current_section.peaks_in_queue.pop(row)
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        next_row = min(min(valid_rows), table.rowCount() - 1)
        if next_row >= 0:
            table.selectRow(next_row)
        self.plot_ctrl.update()
        return True

    def _single_selected_peak_row(self):
        table = self.widget.tableWidget_PkParams
        rows = set()
        selection_model = table.selectionModel()
        if selection_model is not None:
            rows = {index.row() for index in selection_model.selectedRows()}
            if not rows:
                rows = {index.row() for index in selection_model.selectedIndexes()}
        if not rows and table.currentRow() >= 0:
            rows.add(table.currentRow())
        if len(rows) != 1:
            return None
        row = rows.pop()
        if not self.model.current_section_exist():
            return None
        if row < 0 or row >= self.model.current_section.get_number_of_peaks_in_queue():
            return None
        return row

    def _single_selected_or_default_peak_row(self):
        if not self.model.current_section_exist():
            return None
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        if n_peaks <= 0:
            return None
        row = self._single_selected_peak_row()
        if row is not None:
            return row
        table = self.widget.tableWidget_PkParams
        selection_model = table.selectionModel()
        if selection_model is not None:
            selected_rows = {index.row() for index in selection_model.selectedRows()}
            selected_cells = {index.row() for index in selection_model.selectedIndexes()}
            if len(selected_rows) > 1 or len(selected_cells) > 1:
                return None
        current_row = table.currentRow()
        if 0 <= current_row < n_peaks:
            table.selectRow(current_row)
            return current_row
        table.selectRow(0)
        return 0

    def _selected_peak_rows_or_all(self):
        if not self.model.current_section_exist():
            return []
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        table = self.widget.tableWidget_PkParams
        rows = set()
        selection_model = table.selectionModel()
        if selection_model is not None:
            rows = {index.row() for index in selection_model.selectedRows()}
            if not rows:
                rows = {index.row() for index in selection_model.selectedIndexes()}
        if not rows and 0 <= table.currentRow() < n_peaks:
            rows.add(table.currentRow())
        if not rows:
            rows = set(range(n_peaks))
        return sorted(row for row in rows if 0 <= row < n_peaks)

    def _apply_default_bounds_to_peak(self, peak):
        center = float(peak.get("center", 0.0))
        defaults = self.default_peak_bounds()
        center_half_range = defaults["center_half_range"]
        peak["center_min"] = center - center_half_range
        peak["center_max"] = center + center_half_range
        peak["sigma_min"] = defaults["fwhm_min"]
        peak["sigma_max"] = defaults["fwhm_max"]
        peak["fraction_min"] = DEFAULT_NL_MIN
        peak["fraction_max"] = DEFAULT_NL_MAX

    def default_peak_bounds(self):
        return dict(self._default_peak_bounds)

    def default_bound_values(self, peak, value_key):
        defaults = self.default_peak_bounds()
        if value_key == "center":
            center = float(peak.get("center", 0.0))
            return (
                center - defaults["center_half_range"],
                center + defaults["center_half_range"],
            )
        if value_key == "sigma":
            return defaults["fwhm_min"], defaults["fwhm_max"]
        if value_key == "fraction":
            return DEFAULT_NL_MIN, DEFAULT_NL_MAX
        return None, None

    def set_default_peak_bounds_values(self, center_half_range, fwhm_min, fwhm_max):
        self._default_peak_bounds = {
            "center_half_range": float(center_half_range),
            "fwhm_min": float(fwhm_min),
            "fwhm_max": float(fwhm_max),
        }

    def apply_default_peak_bounds_to_all_peaks(self):
        if not self.model.current_section_exist():
            return
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        if n_peaks <= 0:
            return
        peaks = self.model.current_section.peaks_in_queue
        for peak in peaks:
            self._apply_default_bounds_to_peak(peak)
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_constraints()
        if self._constraints_dialog is not None:
            try:
                self._constraints_dialog.close()
            except Exception:
                pass
            self._constraints_dialog = None
        self.plot_ctrl.update()

    def open_default_peak_bounds_dialog(self):
        self._default_bounds_dialog = _DefaultPeakBoundsDialog(self)
        self._default_bounds_dialog.show()
        self._default_bounds_dialog.raise_()

    def open_peak_constraints_dialog(self):
        row = self._single_selected_or_default_peak_row()
        if row is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Select one peak row before opening constraints.")
            return
        self._constraints_dialog = _PeakConstraintsDialog(self, row)
        self._constraints_dialog.show()
        self._constraints_dialog.raise_()

    def open_background_setup_dialog(self):
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Set a section first.")
            return
        self._background_dialog = _BackgroundSetupDialog(self)
        self._background_dialog.show()
        self._background_dialog.raise_()

    def _plot_selected_fitting(self):
        button = self.widget.pushButton_PlotSelectedPkFtResults
        if button.isChecked():
            button.setText("GSAS style ON")
            self.plot_ctrl.update_to_gsas_style()
        else:
            button.setText("GSAS style OFF")
            self.plot_ctrl.update()

    def import_section_from_dpp(self):
        fn = dialog_openfile_hide_param_dirs(
            self.widget, "Choose A Session File",
            self.model.chi_path, "(*.dpp)")[0]
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        success = self._load_from_dpp(fn)
        if success:
            self.peakfit_table_ctrl.update_sections()

    def _load_from_dpp(self, filen_dpp):
        '''
        internal method for reading dilled dpp file
        '''
        if (not os.path.exists(filen_dpp)) or (os.path.getsize(filen_dpp) == 0):
            QtWidgets.QMessageBox.warning(
                self.widget,
                "Warning",
                "DPP file is empty or missing.\n\n"
                f"File: {filen_dpp}\n"
                f"Size: {os.path.getsize(filen_dpp) if os.path.exists(filen_dpp) else 0} bytes",
            )
            return False
        try:
            with open(filen_dpp, 'rb') as f:
                model_dpp = PeakPoCompatDillUnpickler(f).load()
        except EOFError:
            QtWidgets.QMessageBox.warning(
                self.widget,
                "Warning",
                "DPP file appears truncated or corrupted (unexpected end of file).\n\n"
                f"File: {filen_dpp}\n"
                f"Size: {os.path.getsize(filen_dpp)} bytes",
            )
            return False
        except Exception as inst:
            err = traceback.format_exc()
            print(err)
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", str(inst) + "\n\n" + err)
            return False
        self.model.import_section_list(model_dpp)
        return True

    def zoom_to_section(self):
        if not self.model.current_section_exist():
            return
        x_range = self.model.current_section.get_xrange()
        y_range = self.model.current_section.get_yrange(
            bgsub=self.widget.checkBox_BgSub.isChecked())
        margin = 0.1 * (y_range[1] - y_range[0])
        self.plot_ctrl.update(
            limits=(x_range[0], x_range[1],
                    y_range[0] - margin, y_range[1] + margin))
        flush = getattr(self.plot_ctrl, "_flush_update_request", None)
        if callable(flush):
            flush()

    def get_peaks_from_jcpds(self):
        selected_phases = self._get_selected_jcpds_phases_for_peakfit()
        if selected_phases is None:
            return
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Set a section first.")
            return
        else:
            if self.model.current_section.fitted():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, "Question",
                    "Are you OK with clearing any unsaved results?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.No:
                    return
                else:
                    self.clear_this_section()
            else:
                pass
        self._normalize_current_peak_phase_names()
        self._remove_peaks_outside_current_section()
        candidates = self._get_jcpds_peak_candidates_for_current_section(
            selected_phases)
        for candidate in candidates:
            self.model.current_section.set_single_peak(
                candidate["tth"],
                candidate["width"],
                hkl=candidate["hkl"],
                phase_name=candidate["phase"],
                constraint_defaults=self.default_peak_bounds())
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        self.plot_ctrl.update()

    def restore_missing_jcpds_peaks(self):
        selected_phases = self._get_selected_jcpds_phases_for_peakfit()
        if selected_phases is None:
            return
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Set a section first.")
            return
        names_changed = self._normalize_current_peak_phase_names()
        candidates = self._get_jcpds_peak_candidates_for_current_section(
            selected_phases)
        existing_keys = self._existing_peak_phase_hkl_keys()
        n_added = 0
        for candidate in candidates:
            key = self._peak_phase_hkl_key(
                candidate["phase"], candidate["hkl"])
            if key in existing_keys:
                continue
            success = self.model.current_section.set_single_peak(
                candidate["tth"],
                candidate["width"],
                hkl=candidate["hkl"],
                phase_name=candidate["phase"],
                constraint_defaults=self.default_peak_bounds())
            if success:
                existing_keys.add(key)
                n_added += 1
        if n_added == 0:
            if names_changed:
                self.set_tableWidget_PkParams_unsaved()
                self.peakfit_table_ctrl.update_peak_parameters()
                self.peakfit_table_ctrl.update_peak_constraints()
                self.plot_ctrl.update()
                return
            QtWidgets.QMessageBox.information(
                self.widget, "Restore missing",
                "No missing JCPDS peaks were found for the current section.")
            return
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        self.plot_ctrl.update()

    def _get_selected_jcpds_phases_for_peakfit(self):
        if not self.model.jcpds_exist():
            return None
        self._sync_jcpds_display_from_table()
        selected_phases = [j for j in self.model.jcpds_lst if j.display]
        if selected_phases == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "No JCPDS phase is selected for display.\n\n"
                "Check the JCPDS phase checkbox for each phase you want to "
                "import.")
            return None
        return selected_phases

    def _remove_peaks_outside_current_section(self):
        x_range = self.model.current_section.get_xrange()
        x_min, x_max = min(x_range), max(x_range)
        self.model.current_section.peaks_in_queue = [
            p for p in self.model.current_section.peaks_in_queue
            if (p.get('center', x_min) >= x_min) and (p.get('center', x_max) <= x_max)
        ]

    def _normalize_current_peak_phase_names(self):
        changed = False
        for peak in self.model.current_section.peaks_in_queue:
            old_name = str(peak.get("phasename", ""))
            new_name = self._normalize_peakfit_phase_name(old_name)
            if new_name != old_name:
                peak["phasename"] = new_name
                changed = True
        return changed

    def _get_jcpds_peak_candidates_for_current_section(self, selected_phases):
        x_range = self.model.current_section.get_xrange()
        x_min, x_max = min(x_range), max(x_range)
        int_threshold = float(
            self.widget.spinBox_PeaksFromJlistIntensity.value())
        width = self.widget.doubleSpinBox_InitialFWHM.value()
        candidates = []
        for j in selected_phases:
            tths, intensities = j.get_tthVSint(
                self.widget.doubleSpinBox_SetWavelength.value())
            phasename = self._phase_name_from_jcpds_for_peakfit(j)
            for ii in range(tths.__len__()):
                tth = float(tths[ii])
                if (tth < x_min) or (tth > x_max):
                    continue
                if intensities[ii] < int_threshold:
                    continue
                hkl = [j.DiffLines[ii].h, j.DiffLines[ii].k,
                       j.DiffLines[ii].l]
                candidates.append({
                    "phase": phasename,
                    "hkl": hkl,
                    "tth": tth,
                    "width": width,
                })
        return candidates

    def _existing_peak_phase_hkl_keys(self):
        keys = set()
        for peak in self.model.current_section.peaks_in_queue:
            keys.add(self._peak_phase_hkl_key(
                peak.get("phasename", ""),
                [peak.get("h", 0), peak.get("k", 0), peak.get("l", 0)]))
        return keys

    def _peak_phase_hkl_key(self, phase, hkl):
        return (
            self._normalize_peakfit_phase_name(str(phase)),
            int(round(float(hkl[0]))),
            int(round(float(hkl[1]))),
            int(round(float(hkl[2]))),
        )

    def _phase_name_from_jcpds_for_peakfit(self, jcpds):
        name = str(getattr(jcpds, "name", ""))
        name = self._normalize_peakfit_phase_name(name)
        if name != "":
            return name
        filename = os.path.basename(str(getattr(jcpds, "file", "")))
        filename = self._normalize_peakfit_phase_name(filename)
        if filename.endswith(".jcpds"):
            return filename[:-len(".jcpds")]
        return filename

    def _normalize_peakfit_phase_name(self, name):
        return normalize_peak_phase_name(str(name))

    def _sync_jcpds_display_from_table(self):
        if not hasattr(self.widget, "tableWidget_JCPDS"):
            return
        table = self.widget.tableWidget_JCPDS
        n_rows = min(table.rowCount(), len(self.model.jcpds_lst))
        for row in range(n_rows):
            item = table.item(row, 0)
            if item is None:
                continue
            self.model.jcpds_lst[row].display = (
                item.checkState() == QtCore.Qt.Checked)

    def _setup_table_status_fields(self):
        self.lineEdit_PkFtSectionsStatus = self._ensure_status_field(
            "lineEdit_PkFtSectionsStatus",
            getattr(self.widget, "verticalLayout_39", None),
            getattr(self.widget, "tableWidget_PkFtSections", None),
            "Sections table status: no unsaved section-list changes.")
        self.lineEdit_PkParamsStatus = self._ensure_status_field(
            "lineEdit_PkParamsStatus",
            getattr(self.widget, "verticalLayout_40", None),
            getattr(self.widget, "tableWidget_PkParams", None),
            "Peaks table status: no active peak settings.")

    def _ensure_status_field(self, name, layout, before_widget, text):
        field = getattr(self.widget, name, None)
        if field is not None:
            field.setText(text)
            return field
        if layout is None or before_widget is None:
            return None
        field = QtWidgets.QLineEdit(self.widget)
        field.setObjectName(name)
        field.setReadOnly(True)
        field.setFocusPolicy(QtCore.Qt.NoFocus)
        field.setText(text)
        field.setToolTip(text)
        field.setStyleSheet(
            "QLineEdit {"
            "background-color: #2f2f2f;"
            "color: #f0f0f0;"
            "border: 1px solid #666666;"
            "padding: 4px 6px;"
            "}")
        idx = layout.indexOf(before_widget)
        if idx < 0:
            layout.addWidget(field)
        else:
            layout.insertWidget(idx, field)
        setattr(self.widget, name, field)
        return field

    def _set_status_text(self, field, text):
        if field is None:
            return
        field.setText(text)
        field.setToolTip(text)

    def set_tableWidget_PkParams_saved(self):
        self.widget.tableWidget_PkParams.setStyleSheet("")
        self._set_status_text(
            self.lineEdit_PkParamsStatus,
            "Peaks table status: current peak settings were saved to Sections.")

    def set_tableWidget_PkParams_unsaved(self):
        self.widget.tableWidget_PkParams.setStyleSheet("")
        self._set_status_text(
            self.lineEdit_PkParamsStatus,
            "Peaks table status: unsaved peak settings. Click Save to store them in Sections.")

    def set_tableWidget_PkFtSections_saved(self):
        self.widget.tableWidget_PkFtSections.setStyleSheet("")
        self._set_status_text(
            self.lineEdit_PkFtSectionsStatus,
            "Sections table status: no unsaved section-list changes.")

    def set_tableWidget_PkFtSections_unsaved(self):
        self.widget.tableWidget_PkFtSections.setStyleSheet("")
        self._set_status_text(
            self.lineEdit_PkFtSectionsStatus,
            "Sections table status: section list changed. Save the session to keep these changes.")

    def set_section_to_current(self):
        if self.widget.tableWidget_PkFtSections.selectionModel().\
                selectedRows().__len__() != 1:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'Select one whole row to make current.\n\n'
                'Make sure the row header is selected, not just a cell.')
            return
        if self.model.current_section_exist():
            if not self.model.current_section_saved():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Message',
                    'Are you OK to loose current section information?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.No:
                    return
                else:
                    pass
            else:
                pass
        else:
            pass
        idx = self.widget.tableWidget_PkFtSections.selectionModel().\
            selectedRows()[0].row()
        # Reload selected section from PARAM CSV on demand so graph updates
        # reflect persisted section data (not stale in-memory copies).
        if self.model.base_ptn_exist():
            try:
                section_disk = load_section_from_param(
                    self.model.get_base_ptn_filename(), idx)
            except Exception:
                section_disk = None
            section_has_data = section_disk is not None and \
                getattr(section_disk, "x", None) is not None and \
                len(section_disk.x) > 0 and \
                getattr(section_disk, "y_bgsub", None) is not None
            if section_has_data:
                self.model.section_lst[idx] = section_disk
            elif not self.model.section_lst[idx].get_number_of_peaks_in_queue():
                QtWidgets.QMessageBox.warning(
                    self.widget, "Missing Section Data",
                    "Saved section data for the selected row was not found.\n"
                    "Using in-memory section data instead.")
        self.model.set_this_section_current(idx)
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_sections()
        self.peakfit_table_ctrl.update_baseline_constraints()
        self.peakfit_table_ctrl.update_peak_constraints()
        """
        self._list_peaks()
        self._list_localbg()
        self._update_config
        """
        self.zoom_to_section()

    def clear_section_list(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Any unsaved sections will be erased. Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        self._clear_all_sections()

    def _clear_all_sections(self):
        '''clean both sections and currentSection'''
        self.model.clear_section_list()
        self.widget.tableWidget_PkFtSections.clearContents()
        self._clear_current_section()
        self._clear_collected_ucfit_results()

    def remove_section(self):
        idx_checked = []
        selection_model = self.widget.tableWidget_PkFtSections.selectionModel()
        if selection_model is not None:
            idx_checked = [item.row() for item in selection_model.selectedRows()]
            if idx_checked == []:
                idx_checked = sorted(
                    {item.row() for item in selection_model.selectedIndexes()})
        if idx_checked == []:
            return False
        idx_checked = [
            idx for idx in idx_checked
            if 0 <= idx < len(self.model.section_lst)
        ]
        if idx_checked == []:
            return False
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Are you sure you want to delete the selected sections?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.No:
            return True
        # remove checked ones
        for idx in sorted(idx_checked, reverse=True):
            self.model.section_lst.pop(idx)
            self.widget.tableWidget_PkFtSections.removeRow(idx)
        self.set_tableWidget_PkFtSections_unsaved()
        self._clear_collected_ucfit_results()
        return True

    def clear_this_section(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Any unsaved fitting result will be discarded.  Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        limits = self.widget.mpl.canvas.ax_pattern.axis()
        if reply == QtWidgets.QMessageBox.No:
            return
        else:
            self._clear_current_section()
            # self.plot_ctrl.update(limits, False)
            self.plot_ctrl.update()

    def _clear_current_section(self):
        '''erase only current section'''
        self.widget.tableWidget_BackgroundConstraints.clearContents()
        self.widget.tableWidget_PeakConstraints.clearContents()
        self.widget.tableWidget_PkParams.clearContents()
        self.model.initialize_current_section()

    def save_to_section(self):
        if not self.model.current_section_exist():
            return
        self.model.save_current_section()
        self.set_tableWidget_PkParams_saved()
        self.set_tableWidget_PkFtSections_unsaved()
        # self._list_sections()
        self.model.initialize_current_section()
        self.widget.tableWidget_PkParams.clearContents()
        self.widget.tableWidget_PeakConstraints.clearContents()
        self.widget.tableWidget_BackgroundConstraints.clearContents()
        self.peakfit_table_ctrl.update_sections()
        self.plot_ctrl.update()

    def set_fit_section(self):
        # if there is unsaved section, ask if it needs to be saved,
        # this can be checked by looking at timestamp
        if self.model.current_section_exist():
            if not self.model.current_section_saved():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Message',
                    'Do you want to save the unsaved section?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.Yes:
                    self.model.save_current_section()
        self.model.initialize_current_section()
        # Warn the users about what is going to happen
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'I will set current plot range as current section. OK?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        # get X range from the current view
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        self.model.set_current_section([axisrange[0], axisrange[1]])
        # This button itself should activate the mouse for peak picking model
        self.widget.pushButton_AddRemoveFromMouse.setChecked(True)
        self.set_tableWidget_PkParams_unsaved()

    def set_mouse_for_peak_input(self):
        if self.widget.pushButton_AddRemoveFromMouse.isChecked():
            self.release_mouse_from_peak_input()
        else:
            self.widget.pushButton_AddRemoveFromMouse.setChecked(True)

    def release_mouse_from_peak_input(self):
        if self.widget.mpl.ntb._active == 'PAN':
            self.widget.mpl.ntb.pan()
        if self.widget.mpl.ntb._active == 'ZOOM':
            self.widget.mpl.ntb.zoom()
        self.widget.pushButton_AddRemoveFromMouse.setChecked(False)
        return
    '''
    def pick_peak(self, mouse_button, xdata, ydata):
        """
        """
        if mouse_button == 'left':  # left click
            success = self.model.current_section.set_single_peak(
                float(xdata),
                self.widget.doubleSpinBox_InitialFWHM.value(),
                constraint_defaults=self.default_peak_bounds())
            if not success:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You picked outside of the current section.")
                return
        elif mouse_button == 'right':  # right button for removal
            if not self.model.current_section.peaks_exist():
                return
            self.model.current_section.remove_single_peak_nearby(xdata)
        else:
            return
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        self.plot_ctrl.update()
    '''

    def conduct_fitting(self):
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No section is defined")
            return
        if self.model.current_section.get_number_of_peaks_in_queue() == 0:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No pick exists in the section.")
            return
        width = self.widget.doubleSpinBox_InitialFWHM.value()
        order = self.widget.spinBox_BGPolyOrder.value()
        maxwidth = self.widget.doubleSpinBox_MaxFWHM.value()
        centerrange = self.widget.doubleSpinBox_PeakCenterRange.value()
        progress = QtWidgets.QProgressDialog(self.widget)
        progress.setLabelText("Fitting peak profiles...")
        progress.setRange(0, 0)
        progress.setWindowTitle("Peak fitting")
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()
        try:
            self.model.current_section.prepare_for_fitting(
                order, maxwidth, centerrange)
            progress.setLabelText("Optimizing peak parameters...")
            QtWidgets.QApplication.processEvents()
            success = self.model.current_section.conduct_fitting()
        finally:
            progress.close()
        if success:
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          'Fitting finished.')
            self.zoom_to_section()
            self.peakfit_table_ctrl.update_peak_parameters()
            self.peakfit_table_ctrl.update_baseline_constraints()
            self.peakfit_table_ctrl.update_peak_constraints()
            self.set_tableWidget_PkParams_unsaved()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          'Fitting failed.')

    def save_to_xls(self):
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        filen_xls = make_filename(self.model.get_base_ptn_filename(),
                      'peakfit.xls', temp_dir=temp_dir)
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Question',
            'Do you want to save in default filename, %s ?' % filen_xls,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            filen_xls = QtWidgets.QFileDialog.getSaveFileName(
                self.widget, "Save an Excel File", filen_xls, "(*.xls)")
        else:
            if os.path.exists(filen_xls):
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Question',
                    'The file already exist.  Overwrite?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.No:
                    return
        self.model.save_peak_fit_results_to_xls(filen_xls)
