import os
import traceback
import numpy as np
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from .mplcontroller import MplController
from .peakfittablecontroller import PeakfitTableController
from ..view.ui_policy import apply_raised_toggle_style
from ..utils import make_filename, get_temp_dir, dialog_openfile_hide_param_dirs
from ..compat_pickle import PeakPoCompatDillUnpickler
from ..model.param_session_io import load_section_from_param
from ..ds_section.section import DEFAULT_CENTER_HALF_RANGE, DEFAULT_FWHM_MIN, \
    DEFAULT_FWHM_MAX, DEFAULT_NL_MIN, DEFAULT_NL_MAX, \
    MAX_BACKGROUND_ANCHOR_WEIGHT, normalize_peak_phase_name


def _set_toggle_button_style(button, checked):
    apply_raised_toggle_style(button, checked=checked)


class _TableBackspaceKeyFilter(QtCore.QObject):
    def __init__(self, parent, table, callback):
        super(_TableBackspaceKeyFilter, self).__init__(parent)
        self.table = table
        self.callback = callback

    def eventFilter(self, obj, event):
        table = getattr(self, "table", None)
        callback = getattr(self, "callback", None)
        if table is None or callback is None or obj != table:
            return False
        if event.type() != QtCore.QEvent.KeyPress:
            return False
        if event.key() != QtCore.Qt.Key_Backspace:
            return False
        return bool(callback())


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
        self._active_editor = None
        self._position_toggle_off_text = "Set position range from plot"
        self._position_toggle_on_text = "Set position range from plot (ON)"
        self._fwhm_toggle_off_text = "Set FWHM max from plot"
        self._fwhm_toggle_on_text = "Set FWHM max from plot (ON)"
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
            self._position_toggle_off_text, self)
        self.button_visual_fwhm = QtWidgets.QPushButton(
            self._fwhm_toggle_off_text, self)
        self.button_visual_position.setCheckable(True)
        self.button_visual_fwhm.setCheckable(True)
        apply_raised_toggle_style(self.button_visual_position, checked=False)
        apply_raised_toggle_style(self.button_visual_fwhm, checked=False)
        self._update_visual_toggle_style(self.button_visual_position, False)
        self._update_visual_toggle_style(self.button_visual_fwhm, False)
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
        self.button_visual_position.toggled.connect(self._arm_position_range)
        self.button_visual_fwhm.toggled.connect(self._arm_fwhm_range)

    def _peak(self):
        section = self.controller.model.current_section
        if section is None:
            return None
        if self.peak_row < 0 or self.peak_row >= section.get_number_of_peaks_in_queue():
            return None
        return section.peaks_in_queue[self.peak_row]

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
        if peak is None:
            self.close()
            return
        for row, (label, value_key, vary_key, min_key, max_key, decimals) in \
                enumerate(self.PARAMS):
            item = QtWidgets.QTableWidgetItem(label)
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.table.setItem(row, 0, item)
            value_box = self._spinbox(peak.get(value_key, 0.0), decimals)
            self.table.setCellWidget(row, 1, value_box)
            self.table.setCellWidget(row, 2, self._checkbox(peak.get(vary_key, True)))
            min_value, max_value, use_min, use_max = \
                self.controller._peak_constraint_state(peak, value_key)
            use_min_box = self._checkbox(use_min)
            min_box = self._spinbox(0.0 if min_value is None else min_value, decimals)
            use_max_box = self._checkbox(use_max)
            max_display_value = self._suggested_max_value(peak, value_key) \
                if max_value is None else max_value
            max_box = self._spinbox(max_display_value, decimals)
            min_box.setEnabled(use_min_box.isChecked())
            max_box.setEnabled(use_max_box.isChecked())
            use_min_box.toggled.connect(min_box.setEnabled)
            use_max_box.toggled.connect(max_box.setEnabled)
            if value_key == "amplitude":
                use_max_box.setChecked(False)
                use_max_box.setEnabled(False)
                max_box.setEnabled(False)
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
        if self.controller.plot_interaction_ctrl is not None:
            self.controller.plot_interaction_ctrl.cancel_editable_xrange()
        self.controller.model.current_section.invalidate_fit_result()
        peak = self._peak()
        if peak is None:
            self.close()
            return
        for row, (__label, value_key, vary_key, min_key, max_key, __decimals) in \
                enumerate(self.PARAMS):
            peak[value_key] = float(self.table.cellWidget(row, 1).value())
            peak[vary_key] = bool(self.table.cellWidget(row, 2).isChecked())
            use_min = bool(self.table.cellWidget(row, 3).isChecked())
            peak[f"{value_key}_min_enabled"] = use_min
            if value_key == "amplitude":
                peak[min_key] = float(self.table.cellWidget(row, 4).value()) \
                    if use_min else None
                peak[max_key] = None
                peak["amplitude_max_enabled"] = False
            else:
                peak[min_key] = float(self.table.cellWidget(row, 4).value()) \
                    if use_min else None
                use_max = bool(self.table.cellWidget(row, 5).isChecked())
                peak[f"{value_key}_max_enabled"] = use_max
                peak[max_key] = float(self.table.cellWidget(row, 6).value()) \
                    if use_max else None
        self.controller.set_tableWidget_PkParams_unsaved()
        self.controller.peakfit_table_ctrl.update_peak_parameters()
        self.controller.peakfit_table_ctrl.update_peak_constraints()
        self.controller.plot_ctrl.update()

    def _set_toggle_button(self, button, checked, on_text, off_text):
        old_state = button.blockSignals(True)
        button.setChecked(bool(checked))
        button.setDown(bool(checked))
        button.setText(on_text if checked else off_text)
        self._update_visual_toggle_style(button, checked)
        button.blockSignals(old_state)

    def _update_visual_toggle_style(self, button, checked):
        apply_raised_toggle_style(button, checked=checked)

    def _cancel_other_visual_toggle(self, active_button):
        if active_button is self.button_visual_position:
            other_button = self.button_visual_fwhm
            other_on_text = self._fwhm_toggle_on_text
            other_off_text = self._fwhm_toggle_off_text
        else:
            other_button = self.button_visual_position
            other_on_text = self._position_toggle_on_text
            other_off_text = self._position_toggle_off_text
        if other_button.isChecked():
            self._set_toggle_button(
                other_button, False, other_on_text, other_off_text)
        if self.controller.plot_interaction_ctrl is not None:
            self.controller.plot_interaction_ctrl.cancel_editable_xrange()

    def _arm_position_range(self, checked):
        if self.controller.plot_interaction_ctrl is None:
            return
        if not checked:
            self._active_editor = None
            self._set_toggle_button(
                self.button_visual_position, False,
                self._position_toggle_on_text, self._position_toggle_off_text)
            self.controller.plot_interaction_ctrl.cancel_editable_xrange()
            return
        self._cancel_other_visual_toggle(self.button_visual_position)
        self._active_editor = "center"
        xmin = float(self.table.cellWidget(1, 4).value())
        xmax = float(self.table.cellWidget(1, 6).value())

        def preview_range(xmin, xmax):
            self.table.cellWidget(1, 3).setChecked(True)
            self.table.cellWidget(1, 4).setValue(float(xmin))
            self.table.cellWidget(1, 5).setChecked(True)
            self.table.cellWidget(1, 6).setValue(float(xmax))

        def deactivate_button():
            self._active_editor = None
            self._set_toggle_button(
                self.button_visual_position, False,
                self._position_toggle_on_text, self._position_toggle_off_text)

        self._set_toggle_button(
            self.button_visual_position, True,
            self._position_toggle_on_text, self._position_toggle_off_text)
        self.controller.plot_interaction_ctrl.start_editable_xrange_tool(
            "Adjust peak position range", xmin, xmax, preview_range,
            cancel_callback=deactivate_button)

    def _arm_fwhm_range(self, checked):
        if self.controller.plot_interaction_ctrl is None:
            return
        if not checked:
            self._active_editor = None
            self._set_toggle_button(
                self.button_visual_fwhm, False,
                self._fwhm_toggle_on_text, self._fwhm_toggle_off_text)
            self.controller.plot_interaction_ctrl.cancel_editable_xrange()
            return
        self._cancel_other_visual_toggle(self.button_visual_fwhm)
        self._active_editor = "sigma"
        peak = self._peak()
        center = float(self.table.cellWidget(1, 1).value())
        current_max = float(self.table.cellWidget(2, 6).value())
        if current_max <= 0.0:
            current_max = float(peak.get("sigma", 0.05)) if peak else 0.05
        half = 0.5 * float(current_max)
        xmin = center - half
        xmax = center + half

        def preview_range(xmin, xmax):
            width = abs(float(xmax) - float(xmin))
            self.table.cellWidget(2, 3).setChecked(True)
            self.table.cellWidget(2, 4).setValue(0.0)
            self.table.cellWidget(2, 5).setChecked(True)
            self.table.cellWidget(2, 6).setValue(width)

        def deactivate_button():
            self._active_editor = None
            self._set_toggle_button(
                self.button_visual_fwhm, False,
                self._fwhm_toggle_on_text, self._fwhm_toggle_off_text)

        self._set_toggle_button(
            self.button_visual_fwhm, True,
            self._fwhm_toggle_on_text, self._fwhm_toggle_off_text)
        self.controller.plot_interaction_ctrl.start_editable_xrange_tool(
            "Adjust peak FWHM maximum", xmin, xmax, preview_range,
            cancel_callback=deactivate_button)

    def closeEvent(self, event):
        if self.controller.plot_interaction_ctrl is not None:
            self.controller.plot_interaction_ctrl.cancel_editable_xrange()
            self._set_toggle_button(
                self.button_visual_position, False,
                self._position_toggle_on_text, self._position_toggle_off_text)
            self._set_toggle_button(
                self.button_visual_fwhm, False,
                self._fwhm_toggle_on_text, self._fwhm_toggle_off_text)
        super(_PeakConstraintsDialog, self).closeEvent(event)


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
        order = self._section().get_order_of_baseline_in_queue()
        self.spin_order.setValue(order if order >= 0 else 1)
        top.addWidget(self.spin_order)
        top.addStretch(1)
        layout.addLayout(top)

        layout.addWidget(QtWidgets.QLabel("Polynomial coefficients", self))
        self.table_coeff = QtWidgets.QTableWidget(self)
        self.table_coeff.setColumnCount(2)
        self.table_coeff.setHorizontalHeaderLabels(["Value", "Vary"])
        self._widen_row_header(self.table_coeff)
        layout.addWidget(self.table_coeff)

        layout.addWidget(QtWidgets.QLabel("Background anchor ranges", self))
        self.table_anchor = QtWidgets.QTableWidget(self)
        self.table_anchor.setColumnCount(3)
        self.table_anchor.setHorizontalHeaderLabels(["xmin", "xmax", "Weight"])
        self._widen_row_header(self.table_anchor)
        layout.addWidget(self.table_anchor)

        anchor_buttons = QtWidgets.QHBoxLayout()
        self.button_add_anchor = QtWidgets.QPushButton("Add current view", self)
        self.button_visual_anchor = QtWidgets.QPushButton("Add range from plot", self)
        self.button_remove_anchor = QtWidgets.QPushButton("Remove range", self)
        self.button_visual_anchor.setCheckable(True)
        apply_raised_toggle_style(self.button_visual_anchor, checked=False)
        for button in (self.button_add_anchor, self.button_visual_anchor,
                       self.button_remove_anchor):
            button.setMinimumHeight(25)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
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
            self.controller.plot_interaction_ctrl.cancel_editable_xrange()
            self.controller.plot_interaction_ctrl.cancel_range_tool()
        super(_BackgroundSetupDialog, self).closeEvent(event)

    def _section(self):
        return self.controller.model.current_section

    def _spinbox(self, value, decimals=5, minimum=-1000000.0,
                 maximum=1000000.0):
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

    def _checkbox(self, checked):
        box = QtWidgets.QCheckBox(self)
        box.setChecked(bool(checked))
        box.setStyleSheet("margin-left:12px; margin-right:12px;")
        return box

    def _widen_row_header(self, table):
        header = table.verticalHeader()
        header.setVisible(True)
        header.setDefaultAlignment(QtCore.Qt.AlignCenter)
        header.setMinimumWidth(68)
        header.setFixedWidth(68)

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
            if key == "weight":
                box = self._spinbox(
                    value, 2, minimum=1.0,
                    maximum=MAX_BACKGROUND_ANCHOR_WEIGHT)
                box.setToolTip(
                    "Relative anchor strength. Values are capped to avoid "
                    "unstable or slow fitting.")
            else:
                box = self._spinbox(value, 5)
            self.table_anchor.setCellWidget(row, col, box)
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
            weight = max(1.0, min(MAX_BACKGROUND_ANCHOR_WEIGHT, weight))
            anchors.append({
                "xmin": min(xmin, xmax),
                "xmax": max(xmin, xmax),
                "weight": weight,
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
            _set_toggle_button_style(self.button_visual_anchor, False)
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
            _set_toggle_button_style(self.button_visual_anchor, False)

        self.controller.plot_interaction_ctrl.start_range_tool(
            "Add background anchor range", add_range, repeat=True,
            cancel_callback=deactivate_button)
        self.button_visual_anchor.setText("Stop picking ranges")
        self.button_visual_anchor.setToolTip(
            "Drag one or more ranges on the plot. Click again or right-click on the plot to finish.")
        _set_toggle_button_style(self.button_visual_anchor, True)

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
        self._constraints_tab_current_row = None
        self._last_peakfit_tab = None
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
        self.base_ptn_ctrl = None
        self.connect_channel()

    def set_ucfit_controller(self, ucfit_ctrl):
        self.ucfit_ctrl = ucfit_ctrl

    def set_base_pattern_controller(self, base_ptn_ctrl):
        self.base_ptn_ctrl = base_ptn_ctrl

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
        self._install_table_backspace_key_filters()
        self._connect_sections_tab_widgets()
        self._connect_constraints_tab_widgets()
        self._connect_background_tab_widgets()
        if hasattr(self.widget, "tabWidget_PeakFit"):
            self.widget.tabWidget_PeakFit.currentChanged.connect(
                self._on_peakfit_tab_changed)
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

    def _connect_sections_tab_widgets(self):
        if not hasattr(self.widget, "tableWidget_PkFtSections"):
            return
        if not hasattr(self, "_sections_table_selection_connected"):
            sel_model = self.widget.tableWidget_PkFtSections.selectionModel()
            if sel_model:
                sel_model.selectionChanged.connect(
                    self._on_section_table_selection_changed)
                self._sections_table_selection_connected = True

    def _connect_constraints_tab_widgets(self):
        if not hasattr(self.widget, "pushButton_SetPosRange"):
            return
        self._setup_constraints_peak_selector()
        self.widget.pushButton_SetPosRange.setCheckable(True)
        self.widget.pushButton_SetFwhmMax.setCheckable(True)
        self.widget.pushButton_SetPosRange.setAutoDefault(False)
        self.widget.pushButton_SetFwhmMax.setAutoDefault(False)
        self.widget.pushButton_SetPosRange.toggled.connect(
            self._arm_constraints_position_range)
        self.widget.pushButton_SetFwhmMax.toggled.connect(
            self._arm_constraints_fwhm_range)
        self._update_visual_toggle_style(self.widget.pushButton_SetPosRange, False)
        self._update_visual_toggle_style(self.widget.pushButton_SetFwhmMax, False)
        self.widget.pushButton_SetPosRange.setText("Constrain position from plot…")
        self.widget.pushButton_SetPosRange.setToolTip(
            "Set optional lower and upper position limits for the selected peak.")
        self.widget.pushButton_SetFwhmMax.setText("Constrain FWHM range from plot…")
        self.widget.pushButton_SetFwhmMax.setToolTip(
            "Set optional lower and upper FWHM limits for the selected peak.")
        if hasattr(self.widget, "groupBox_DefaultBounds"):
            self.widget.groupBox_DefaultBounds.setTitle("Constraint templates (optional)")
            self.widget.groupBox_DefaultBounds.setToolTip(
                "These values are templates only. Editing them does not "
                "constrain any peak until you explicitly apply a template.")
            template_labels = {
                "Position +/- (degrees)": "Position window ± (template)",
                "Initial FWHM": "Initial FWHM for new peaks",
                "FWHM min": "FWHM lower limit (template)",
                "FWHM max": "FWHM upper limit (template)",
            }
            for label in self.widget.groupBox_DefaultBounds.findChildren(
                    QtWidgets.QLabel):
                if label.text() in template_labels:
                    label.setText(template_labels[label.text()])
        if hasattr(self.widget, "groupBox_PeakConstraintEditor"):
            self.widget.groupBox_PeakConstraintEditor.setTitle(
                "Optional constraints for selected peak")
        self.widget.spinBox_CenterHalfRange.valueChanged.connect(
            self._on_default_bounds_changed)
        self.widget.spinBox_DefaultFwhmMin.valueChanged.connect(
            self._on_default_bounds_changed)
        self.widget.spinBox_DefaultFwhmMax.valueChanged.connect(
            self._on_default_bounds_changed)
        if hasattr(self.widget, "tableWidget_PkParams"):
            if not hasattr(self, "_peak_table_selection_connected"):
                sel_model = self.widget.tableWidget_PkParams.selectionModel()
                if sel_model:
                    sel_model.selectionChanged.connect(
                        self._on_peak_table_selection_changed)
                    self._peak_table_selection_connected = True

    def _apply_peak_constraints_enabled(self):
        box = getattr(self.widget, "checkBox_ApplyPeakConstraints", None)
        if box is None:
            return False
        return bool(box.isChecked())

    def _set_apply_peak_constraints_checked(self, checked=True):
        box = getattr(self.widget, "checkBox_ApplyPeakConstraints", None)
        if box is not None:
            box.setChecked(bool(checked))

    def _setup_constraints_peak_selector(self):
        """Add a Constraints-tab selector backed by the Peaks table rows."""
        if hasattr(self.widget, "comboBox_ConstraintPeak"):
            return
        layout = getattr(
            self.widget, "verticalLayout_ConstraintsContent", None)
        constraint_box = getattr(
            self.widget, "groupBox_PeakConstraintEditor", None)
        if layout is None or constraint_box is None:
            return

        combo = QtWidgets.QComboBox(self.widget.scrollAreaWidgetContents_Constraints)
        combo.setObjectName("comboBox_ConstraintPeak")
        combo.setMinimumHeight(28)
        combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        combo.setToolTip(
            "Choose the peak whose constraints are being edited. "
            "Selection also highlights that peak in the 1D pattern.")

        index = layout.indexOf(constraint_box)
        if index < 0:
            layout.addWidget(combo)
        else:
            layout.insertWidget(index, combo)
        self.widget.comboBox_ConstraintPeak = combo
        combo.currentIndexChanged.connect(
            self._on_constraints_peak_selector_changed)

    @staticmethod
    def _constraints_peak_label(peak):
        phase = normalize_peak_phase_name(peak.get("phasename", "Unknown"))
        h = int(peak.get("h", 0))
        k = int(peak.get("k", 0))
        l = int(peak.get("l", 0))
        area = float(peak.get("amplitude", 0.0))
        center = float(peak.get("center", 0.0))
        return (
            f"{phase} ({h} {k} {l}) | Area {area:.5g} | "
            f"Position {center:.5f}\N{DEGREE SIGN}")

    def _refresh_constraints_peak_selector(self, selected_row=None):
        combo = getattr(self.widget, "comboBox_ConstraintPeak", None)
        if combo is None:
            return
        if selected_row is None:
            selected_row = self._constraints_tab_current_row
        if selected_row is None:
            selected_row = self._single_selected_peak_row()

        blocker = QtCore.QSignalBlocker(combo)
        combo.clear()
        combo.addItem("Select a peak…", None)
        has_peaks = False
        if self.model.current_section_exist():
            for row, peak in enumerate(self.model.current_section.peaks_in_queue):
                combo.addItem(self._constraints_peak_label(peak), row)
                has_peaks = True
        if selected_row is None:
            combo.setCurrentIndex(0)
        elif has_peaks:
            row = min(max(int(selected_row), 0), combo.count() - 2)
            combo.setCurrentIndex(row + 1)
        del blocker
        combo.setEnabled(has_peaks)

    def _sync_constraints_peak_selector_to_selected_row(self):
        combo = getattr(self.widget, "comboBox_ConstraintPeak", None)
        if combo is None:
            return
        row = self._single_selected_peak_row()
        if row is None or combo.count() == 0:
            return
        for index in range(combo.count()):
            if combo.itemData(index) == row:
                blocker = QtCore.QSignalBlocker(combo)
                combo.setCurrentIndex(index)
                del blocker
                return

    def _on_constraints_peak_selector_changed(self, index):
        combo = getattr(self.widget, "comboBox_ConstraintPeak", None)
        table = getattr(self.widget, "tableWidget_PkParams", None)
        if combo is None or table is None or index < 0:
            return
        row = combo.itemData(index)
        if row is None:
            return
        row = int(row)
        if row < 0 or row >= table.rowCount():
            return
        selection_model = table.selectionModel()
        model_index = table.model().index(row, 0)
        if selection_model is not None:
            selection_model.setCurrentIndex(
                model_index,
                QtCore.QItemSelectionModel.ClearAndSelect |
                QtCore.QItemSelectionModel.Rows)
        else:
            table.selectRow(row)
        table.scrollTo(model_index)
        self._update_constraints_tab_state()
        if self.plot_ctrl is not None:
            self.plot_ctrl.refresh_selected_peak_marker()

    def _set_constraints_toggle_button(self, button, checked, on_text, off_text):
        old_state = button.blockSignals(True)
        button.setChecked(bool(checked))
        button.setDown(bool(checked))
        button.setText(on_text if checked else off_text)
        apply_raised_toggle_style(button, checked=checked)
        button.blockSignals(old_state)

    def _update_visual_toggle_style(self, button, checked):
        apply_raised_toggle_style(button, checked=checked)

    def _clear_constraints_toggle_buttons(self, except_button=None):
        pairs = [
            (self.widget.pushButton_SetPosRange,
             "Set position range from plot (ON)",
             "Set position range from plot"),
            (self.widget.pushButton_SetFwhmMax,
             "Set FWHM max from plot (ON)",
             "Set FWHM max from plot"),
        ]
        for button, on_text, off_text in pairs:
            if button is except_button:
                continue
            if button.isChecked():
                self._set_constraints_toggle_button(button, False, on_text, off_text)

    def _connect_background_tab_widgets(self):
        if not hasattr(self.widget, "pushButton_AddCurrentView"):
            return
        self.widget.pushButton_AddCurrentView.clicked.connect(
            self._add_bg_anchor_from_view)
        self.widget.pushButton_AddRangeFromPlot.toggled.connect(
            self._arm_bg_anchor_range)
        self._set_bg_toggle_button_style(self.widget.pushButton_AddRangeFromPlot, False)
        self.widget.pushButton_RemoveBGAnchor.clicked.connect(
            self._remove_bg_anchor_rows)
        self.widget.spinBox_BGPolyOrder.valueChanged.connect(
            self._on_bg_poly_order_changed)
        if hasattr(self.widget, "tableWidget_BGAnchorRanges"):
            sel_model = self.widget.tableWidget_BGAnchorRanges.selectionModel()
            if sel_model and not hasattr(self, "_bg_anchor_selection_connected"):
                sel_model.selectionChanged.connect(
                    self._on_bg_anchor_table_selection_changed)
                self._bg_anchor_selection_connected = True

    def _on_peak_table_selection_changed(self):
        self._sync_constraints_peak_selector_to_selected_row()
        self._update_constraints_tab_state()

    def _on_section_table_selection_changed(self, _selected, _deselected):
        if hasattr(self, "plot_ctrl") and (self.plot_ctrl is not None):
            self.plot_ctrl.refresh_section_selection_overlay()

    def _on_bg_anchor_table_selection_changed(self, _selected, _deselected):
        if hasattr(self, "plot_ctrl") and (self.plot_ctrl is not None):
            self.plot_ctrl.refresh_background_selection_overlay()

    def _update_constraints_tab_state(self):
        if not hasattr(self.widget, "label_PeakStatus"):
            return
        table = self.widget.tableWidget_PkParams
        selected_rows = set()
        if table.selectionModel():
            selected_rows = {r.row() for r in table.selectionModel().selectedRows()}
            if not selected_rows:
                selected_rows = {idx.row() for idx in table.selectionModel().selectedIndexes()}
        if len(selected_rows) != 1:
            self.widget.label_PeakStatus.setStyleSheet(
                "QLineEdit { background-color: #ffcccc; color: #cc0000; font-weight: bold; }")
            self.widget.label_PeakStatus.setText(
                "Please select exactly one peak in the Peaks table or dropdown menu")
            self._clear_peak_constraints_table()
            self._constraints_tab_current_row = None
            return
        row = selected_rows.pop()
        if not self.model.current_section_exist():
            return
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        if row < 0 or row >= n_peaks:
            return
        peak = self.model.current_section.peaks_in_queue[row]
        phase = peak.get("phasename", "Unknown")
        h, k, l = int(peak.get("h", 0)), int(peak.get("k", 0)), int(peak.get("l", 0))
        amplitude = peak.get("amplitude", 0.0)
        self.widget.label_PeakStatus.setStyleSheet(
            "QLineEdit { background-color: #ccffcc; color: #006600; font-weight: bold; }")
        self.widget.label_PeakStatus.setText(
            f"Phase: {phase} ({h} {k} {l}) | Intensity: {amplitude:.3f}")
        if (self._constraints_tab_current_row is not None and
                self._constraints_tab_current_row != row):
            self._sync_constraints_tab_row_to_model()
        if row == self._constraints_tab_current_row:
            return
        self._constraints_tab_current_row = row
        self._sync_constraints_peak_selector_to_selected_row()
        self._clear_peak_constraints_table()
        self._populate_peak_constraints_table(row)

    def _clear_peak_constraints_table(self):
        if not hasattr(self.widget, "tableWidget_PeakConstraintDetail"):
            return
        table = self.widget.tableWidget_PeakConstraintDetail
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                w = table.cellWidget(r, c)
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
        table.clearContents()
        table.setRowCount(0)
        table.setColumnCount(0)

    def _populate_peak_constraints_table(self, peak_row):
        if not hasattr(self.widget, "tableWidget_PeakConstraintDetail"):
            return
        table = self.widget.tableWidget_PeakConstraintDetail
        table.clearContents()
        table.setRowCount(0)
        table.setColumnCount(0)
        PARAMS = [
            ("Area", "amplitude", "amplitude_vary", "amplitude_min", "amplitude_max", 3),
            ("Position", "center", "center_vary", "center_min", "center_max", 5),
            ("FWHM", "sigma", "sigma_vary", "sigma_min", "sigma_max", 5),
            ("nL", "fraction", "fraction_vary", "fraction_min", "fraction_max", 3),
        ]
        peak = self.model.current_section.peaks_in_queue[peak_row]
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(
            ["Parameter", "Initial value", "Refine", "Lower limit", "Value",
             "Upper limit", "Value"])
        table.setRowCount(len(PARAMS))
        table.horizontalHeader().setVisible(True)
        for row, (label, value_key, vary_key, min_key, max_key, decimals) in enumerate(PARAMS):
            lbl = QtWidgets.QLabel(label)
            lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            table.setCellWidget(row, 0, lbl)
            val_box = self._make_spinbox(peak.get(value_key, 0.0), decimals)
            if value_key in ("amplitude", "center", "sigma"):
                val_box.setMinimum(1e-15)
            elif value_key == "fraction":
                val_box.setMinimum(DEFAULT_NL_MIN)
                val_box.setMaximum(DEFAULT_NL_MAX)
            table.setCellWidget(row, 1, val_box)
            vary_box = self._make_checkbox(peak.get(vary_key, True))
            table.setCellWidget(row, 2, vary_box)
            min_val, max_val, use_min_state, use_max_state = \
                self._peak_constraint_state(peak, value_key)
            use_min = self._make_checkbox(use_min_state)
            min_box = self._make_spinbox(0.0 if min_val is None else min_val, decimals)
            min_box.setEnabled(use_min.isChecked())
            use_min.toggled.connect(min_box.setEnabled)
            use_max = self._make_checkbox(use_max_state)
            max_box = self._make_spinbox(0.0 if max_val is None else max_val, decimals)
            max_box.setEnabled(use_max.isChecked())
            use_max.toggled.connect(max_box.setEnabled)
            if value_key == "amplitude":
                use_min.setChecked(True)
                use_min.setEnabled(False)
                use_min.setToolTip("Physical domain: area must be greater than zero.")
                min_box.setValue(0.0)
                min_box.setEnabled(False)
                use_max.setChecked(False)
                use_max.setEnabled(False)
                max_box.setEnabled(False)
            elif value_key == "fraction":
                for box in (use_min, use_max):
                    box.setChecked(True)
                    box.setEnabled(False)
                    box.setToolTip("Physical domain: 0 ≤ nL ≤ 1.")
                min_box.setValue(DEFAULT_NL_MIN)
                max_box.setValue(DEFAULT_NL_MAX)
                min_box.setEnabled(False)
                max_box.setEnabled(False)
            table.setCellWidget(row, 3, use_min)
            table.setCellWidget(row, 4, min_box)
            table.setCellWidget(row, 5, use_max)
            table.setCellWidget(row, 6, max_box)
            val_box.valueChanged.connect(
                lambda v, pr=peak_row, vr_key=value_key: self._on_peak_param_changed(pr, vr_key, "value", v))
            vary_box.toggled.connect(
                lambda s, pr=peak_row, vr_key=value_key: self._on_peak_param_changed(pr, vr_key, "vary", s))
            use_min.toggled.connect(
                lambda s, pr=peak_row, vr_key=value_key: self._on_peak_param_changed(pr, vr_key, "use_min", s))
            min_box.valueChanged.connect(
                lambda v, pr=peak_row, vr_key=value_key: self._on_peak_param_changed(pr, vr_key, "min", v))
            use_max.toggled.connect(
                lambda s, pr=peak_row, vr_key=value_key: self._on_peak_param_changed(pr, vr_key, "use_max", s))
            max_box.valueChanged.connect(
                lambda v, pr=peak_row, vr_key=value_key: self._on_peak_param_changed(pr, vr_key, "max", v))
        table.resizeColumnsToContents()

    def _make_spinbox(self, value, decimals=5):
        box = QtWidgets.QDoubleSpinBox()
        box.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        box.setDecimals(decimals)
        box.setMinimum(-1000000.0)
        box.setMaximum(1000000.0)
        box.setSingleStep(10 ** (-decimals))
        box.setKeyboardTracking(False)
        box.setValue(float(value))
        return box

    def _make_checkbox(self, checked):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(checked))
        box.setStyleSheet("margin-left:12px; margin-right:12px;")
        return box

    def _peak_constraint_state(self, peak, value_key):
        """
        Priority:
        1. Use peak-specific user-entered bounds when explicitly enabled.
        2. Otherwise seed from the live default-bounds UI.
        3. Never seed an amplitude max bound.
        """
        defaults = self.default_peak_bounds()
        min_key = f"{value_key}_min"
        max_key = f"{value_key}_max"
        min_enabled_key = f"{value_key}_min_enabled"
        max_enabled_key = f"{value_key}_max_enabled"
        min_val = peak.get(min_key, None)
        max_val = peak.get(max_key, None)
        min_enabled = peak.get(min_enabled_key, None)
        max_enabled = peak.get(max_enabled_key, None)
        if value_key == "amplitude":
            if min_enabled is None:
                min_enabled = min_val is not None if min_key in peak else True
            if min_val is None and min_key not in peak:
                min_val = 0.0
            return min_val, None, True, False
        if value_key == "center":
            center = float(peak.get("center", 0.0))
            if min_enabled is None:
                min_enabled = min_val is not None if min_key in peak else True
            if max_enabled is None:
                max_enabled = max_val is not None if max_key in peak else True
            if min_val is None and min_key not in peak:
                min_val = center - defaults["center_half_range"]
            if max_val is None and max_key not in peak:
                max_val = center + defaults["center_half_range"]
        elif value_key == "sigma":
            if min_enabled is None:
                min_enabled = min_val is not None if min_key in peak else False
            if max_enabled is None:
                max_enabled = max_val is not None if max_key in peak else False
            if min_val is None and min_key not in peak:
                min_val = defaults["fwhm_min"]
            if max_val is None and max_key not in peak:
                max_val = defaults["fwhm_max"]
        elif value_key == "fraction":
            # nL's inclusive 0–1 range is an intrinsic physical domain, not
            # an optional user constraint.
            min_val = DEFAULT_NL_MIN
            max_val = DEFAULT_NL_MAX
            min_enabled = True
            max_enabled = True
        if min_enabled is None:
            min_enabled = min_val is not None
        if value_key == "amplitude":
            max_enabled = False
        elif max_enabled is None:
            max_enabled = max_val is not None
        return min_val, max_val, bool(min_enabled), bool(max_enabled)

    def _update_peak_constraint_min_max_widgets(self, row, value_key):
        if not hasattr(self.widget, "tableWidget_PeakConstraintDetail"):
            return
        table = self.widget.tableWidget_PeakConstraintDetail
        param_map = {
            "amplitude": 0,
            "center": 1,
            "sigma": 2,
            "fraction": 3,
        }
        if value_key not in param_map:
            return
        table_row = param_map[value_key]
        peak = self.model.current_section.peaks_in_queue[row]
        min_val, max_val, use_min_enabled, use_max_enabled = \
            self._peak_constraint_state(peak, value_key)
        use_min_box = table.cellWidget(table_row, 3)
        min_box = table.cellWidget(table_row, 4)
        use_max_box = table.cellWidget(table_row, 5)
        max_box = table.cellWidget(table_row, 6)
        if use_min_box and min_box:
            use_min_box.blockSignals(True)
            min_box.blockSignals(True)
            use_min_box.setChecked(use_min_enabled)
            min_box.setValue(0.0 if min_val is None else min_val)
            use_min_box.blockSignals(False)
            min_box.blockSignals(False)
            min_box.setEnabled(use_min_box.isChecked())
        if use_max_box and max_box:
            use_max_box.blockSignals(True)
            max_box.blockSignals(True)
            use_max_box.setChecked(use_max_enabled)
            max_box.setValue(0.0 if max_val is None else max_val)
            use_max_box.blockSignals(False)
            max_box.blockSignals(False)
            max_box.setEnabled(False if value_key == "amplitude" else use_max_box.isChecked())

    def _update_peak_constraint_value_widgets(self, row, value_key, value):
        """
        Keep the live constraints editors in sync with plot/table edits.
        If these widgets stay stale, changing to another row can write old
        values back into the model.
        """
        param_map = {
            "amplitude": 0,
            "center": 1,
            "sigma": 2,
            "fraction": 3,
        }
        if value_key not in param_map:
            return
        table_row = param_map[value_key]
        # Sync the docked/tabbed constraints table.
        table = getattr(self.widget, "tableWidget_PeakConstraintDetail", None)
        if (table is not None and table.rowCount() > table_row and
                getattr(self, "_constraints_tab_current_row", None) == row):
            widget = table.cellWidget(table_row, 1)
            if widget is not None:
                old_state = widget.blockSignals(True)
                widget.setValue(float(value))
                widget.blockSignals(old_state)
        # Sync the popup dialog if it is editing this row.
        dialog = getattr(self, "_constraints_dialog", None)
        if dialog is not None and getattr(dialog, "peak_row", None) == row:
            try:
                dlg_widget = dialog.table.cellWidget(table_row, 1)
                if dlg_widget is not None:
                    old_state = dlg_widget.blockSignals(True)
                    dlg_widget.setValue(float(value))
                    dlg_widget.blockSignals(old_state)
            except Exception:
                pass

    def _on_peak_param_changed(self, row, param_key, change_type, value):
        if not self.model.current_section_exist():
            return
        if row < 0 or row >= self.model.current_section.get_number_of_peaks_in_queue():
            return
        self.model.current_section.invalidate_fit_result()
        peak = self.model.current_section.peaks_in_queue[row]
        min_key = f"{param_key}_min"
        max_key = f"{param_key}_max"
        if change_type == "value":
            peak[param_key] = float(value)
        elif change_type == "vary":
            peak[f"{param_key}_vary"] = bool(value)
        elif change_type == "use_min":
            peak[f"{param_key}_min_enabled"] = bool(value)
            if not bool(value):
                peak[min_key] = None
            else:
                if param_key == "center":
                    peak[min_key] = (
                        float(peak.get("center", 0.0)) -
                        float(self.default_peak_bounds()["center_half_range"]))
                elif param_key == "sigma":
                    peak[min_key] = DEFAULT_FWHM_MIN
                elif param_key == "fraction":
                    peak[min_key] = DEFAULT_NL_MIN
                elif param_key == "amplitude":
                    peak[min_key] = 0.0
                else:
                    peak[min_key] = 0.0
        elif change_type == "min":
            peak[f"{param_key}_min_enabled"] = True
            peak[min_key] = float(value)
        elif change_type == "use_max":
            if param_key == "amplitude":
                peak[max_key] = None
                peak["amplitude_max_enabled"] = False
                peak[f"{param_key}_max_enabled"] = False
            elif not bool(value):
                peak[f"{param_key}_max_enabled"] = False
                peak[max_key] = None
            else:
                peak[f"{param_key}_max_enabled"] = True
                if param_key == "center":
                    peak[max_key] = (
                        float(peak.get("center", 0.0)) +
                        float(self.default_peak_bounds()["center_half_range"]))
                elif param_key == "sigma":
                    peak[max_key] = DEFAULT_FWHM_MAX
                elif param_key == "fraction":
                    peak[max_key] = DEFAULT_NL_MAX
                else:
                    peak[max_key] = 0.0
        elif change_type == "max":
            if param_key == "amplitude":
                peak[max_key] = None
                peak["amplitude_max_enabled"] = False
                peak[f"{param_key}_max_enabled"] = False
            else:
                peak[f"{param_key}_max_enabled"] = True
                peak[max_key] = float(value)
        if param_key == "center" and change_type == "value":
            if hasattr(self.widget, "tableWidget_PkParams"):
                table = self.widget.tableWidget_PkParams
                item = table.item(row, 5)
                if item is not None:
                    old_state = table.blockSignals(True)
                    item.setText("{:.5e}".format(float(value)))
                    table.blockSignals(old_state)
            self._update_peak_constraint_value_widgets(row, "center", value)
        if change_type == "value" and param_key in ("amplitude", "center"):
            self._refresh_constraints_peak_selector(selected_row=row)
        if change_type == "value" and hasattr(self, "plot_ctrl") and \
                self.plot_ctrl is not None:
            self.plot_ctrl.refresh_peakfit_markers()
        self.set_tableWidget_PkParams_unsaved()

    def _sync_constraints_tab_row_to_model(self):
        if not self.model.current_section_exist():
            return
        table = getattr(self.widget, "tableWidget_PeakConstraintDetail", None)
        if table is None:
            return
        row = self._constraints_tab_current_row
        if row is None:
            return
        if row < 0 or row >= self.model.current_section.get_number_of_peaks_in_queue():
            return
        peak = self.model.current_section.peaks_in_queue[row]
        param_map = [
            ("amplitude", 0),
            ("center", 1),
            ("sigma", 2),
            ("fraction", 3),
        ]
        for param_key, table_row in param_map:
            value_widget = table.cellWidget(table_row, 1)
            vary_widget = table.cellWidget(table_row, 2)
            use_min_widget = table.cellWidget(table_row, 3)
            min_widget = table.cellWidget(table_row, 4)
            use_max_widget = table.cellWidget(table_row, 5)
            max_widget = table.cellWidget(table_row, 6)
            if value_widget is None or vary_widget is None:
                continue
            peak[param_key] = float(value_widget.value())
            peak[f"{param_key}_vary"] = bool(vary_widget.isChecked())
            if use_min_widget is not None and min_widget is not None:
                use_min = bool(use_min_widget.isChecked())
                peak[f"{param_key}_min_enabled"] = use_min
                peak[f"{param_key}_min"] = (
                    float(min_widget.value()) if use_min else None)
            if param_key == "amplitude":
                peak[f"{param_key}_max"] = None
                peak[f"{param_key}_max_enabled"] = False
            elif use_max_widget is not None and max_widget is not None:
                use_max = bool(use_max_widget.isChecked())
                peak[f"{param_key}_max_enabled"] = use_max
                peak[f"{param_key}_max"] = (
                    float(max_widget.value()) if use_max else None)
        self.model.current_section.invalidate_fit_result()

    def _sync_background_tab_to_model(self):
        if not self.model.current_section_exist():
            return
        table_coeff = getattr(self.widget, "tableWidget_BGCoefficients", None)
        table_anchor = getattr(self.widget, "tableWidget_BGAnchorRanges", None)
        if table_coeff is not None:
            coeffs = []
            for row in range(table_coeff.rowCount()):
                value_widget = table_coeff.cellWidget(row, 0)
                vary_widget = table_coeff.cellWidget(row, 1)
                if value_widget is None or vary_widget is None:
                    continue
                coeffs.append({
                    "value": float(value_widget.value()),
                    "vary": bool(vary_widget.isChecked()),
                })
            self.model.current_section.baseline_in_queue = coeffs
        if table_anchor is not None:
            anchors = []
            for row in range(table_anchor.rowCount()):
                xmin_widget = table_anchor.cellWidget(row, 0)
                xmax_widget = table_anchor.cellWidget(row, 1)
                weight_widget = table_anchor.cellWidget(row, 2)
                if xmin_widget is None or xmax_widget is None or weight_widget is None:
                    continue
                xmin = float(xmin_widget.value())
                xmax = float(xmax_widget.value())
                weight = float(weight_widget.value())
                weight = max(1.0, min(MAX_BACKGROUND_ANCHOR_WEIGHT, weight))
                anchors.append({
                    "xmin": min(xmin, xmax),
                    "xmax": max(xmin, xmax),
                    "weight": weight,
                })
            self.model.current_section.background_anchor_ranges = anchors
        self.model.current_section.invalidate_fit_result()

    def _arm_constraints_position_range(self):
        if self.plot_interaction_ctrl is None:
            return
        button = self.widget.pushButton_SetPosRange
        if not button.isChecked():
            self.plot_interaction_ctrl.cancel_editable_xrange()
            self._set_constraints_toggle_button(
                button, False,
                "Constrain position from plot… (ON)",
                "Constrain position from plot…")
            return
        table = self.widget.tableWidget_PkParams
        selected_rows = {r.row() for r in table.selectionModel().selectedRows()} if table.selectionModel() else set()
        if not selected_rows:
            selected_rows = {idx.row() for idx in table.selectionModel().selectedIndexes()} if table.selectionModel() else set()
        if len(selected_rows) != 1:
            self._set_constraints_toggle_button(
                button, False,
                "Constrain position from plot… (ON)",
                "Constrain position from plot…")
            return
        row = selected_rows.pop()
        if not self.model.current_section_exist():
            self._set_constraints_toggle_button(
                button, False,
                "Constrain position from plot… (ON)",
                "Constrain position from plot…")
            return
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        if row < 0 or row >= n_peaks:
            self._set_constraints_toggle_button(
                button, False,
                "Constrain position from plot… (ON)",
                "Constrain position from plot…")
            return
        self._clear_constraints_toggle_buttons(except_button=button)
        def apply_range(xmin, xmax):
            peak = self.model.current_section.peaks_in_queue[row]
            peak["center_min"] = float(xmin)
            peak["center_max"] = float(xmax)
            peak["center_min_enabled"] = True
            peak["center_max_enabled"] = True
            self._update_peak_constraint_min_max_widgets(row, "center")
            self.set_tableWidget_PkParams_unsaved()
        def cancel_button():
            self._set_constraints_toggle_button(
                button, False,
                "Constrain position from plot… (ON)",
                "Constrain position from plot…")
        peak = self.model.current_section.peaks_in_queue[row]
        default_xmin, default_xmax = self.default_bound_values(peak, "center")
        xmin = self._optional_bound_or_default(
            peak.get("center_min"), default_xmin)
        xmax = self._optional_bound_or_default(
            peak.get("center_max"), default_xmax)
        if xmax <= xmin:
            xmin, xmax = self.default_bound_values(peak, "center")
        self._set_constraints_toggle_button(
            button, True,
            "Constrain position from plot… (ON)",
            "Constrain position from plot…")
        self.plot_interaction_ctrl.start_editable_xrange_tool(
            "Set peak position range", xmin, xmax, apply_range,
            cancel_callback=cancel_button)

    def _arm_constraints_fwhm_range(self):
        if self.plot_interaction_ctrl is None:
            return
        button = self.widget.pushButton_SetFwhmMax
        if not button.isChecked():
            self.plot_interaction_ctrl.cancel_editable_xrange()
            self._set_constraints_toggle_button(
                button, False,
                "Constrain FWHM range from plot… (ON)",
                "Constrain FWHM range from plot…")
            return
        table = self.widget.tableWidget_PkParams
        selected_rows = {r.row() for r in table.selectionModel().selectedRows()} if table.selectionModel() else set()
        if not selected_rows:
            selected_rows = {idx.row() for idx in table.selectionModel().selectedIndexes()} if table.selectionModel() else set()
        if len(selected_rows) != 1:
            self._set_constraints_toggle_button(
                button, False,
                "Constrain FWHM range from plot… (ON)",
                "Constrain FWHM range from plot…")
            return
        row = selected_rows.pop()
        if not self.model.current_section_exist():
            self._set_constraints_toggle_button(
                button, False,
                "Constrain FWHM range from plot… (ON)",
                "Constrain FWHM range from plot…")
            return
        n_peaks = self.model.current_section.get_number_of_peaks_in_queue()
        if row < 0 or row >= n_peaks:
            self._set_constraints_toggle_button(
                button, False,
                "Constrain FWHM range from plot… (ON)",
                "Constrain FWHM range from plot…")
            return
        self._clear_constraints_toggle_buttons(except_button=button)
        def apply_range(xmin, xmax):
            peak = self.model.current_section.peaks_in_queue[row]
            self._apply_fwhm_bounds_from_plot_range(peak, xmin, xmax)
            self._update_peak_constraint_min_max_widgets(row, "sigma")
            self.set_tableWidget_PkParams_unsaved()
        def cancel_button():
            self._set_constraints_toggle_button(
                button, False,
                "Constrain FWHM range from plot… (ON)",
                "Constrain FWHM range from plot…")
        peak = self.model.current_section.peaks_in_queue[row]
        detail_table = getattr(self.widget, "tableWidget_PeakConstraintDetail", None)
        if detail_table is not None and detail_table.rowCount() > 2:
            max_widget = detail_table.cellWidget(2, 6)
            if max_widget is not None:
                current_max = float(max_widget.value())
            else:
                current_max = self._optional_bound_or_default(
                    peak.get("sigma_max"), peak.get("sigma", 0.05))
        else:
            current_max = self._optional_bound_or_default(
                peak.get("sigma_max"), peak.get("sigma", 0.05))
        center = float(peak.get("center", 0.0))
        if current_max <= 0.0:
            current_max = float(peak.get("sigma", 0.05)) if peak else 0.05
        half = 0.5 * float(current_max)
        xmin = center - half
        xmax = center + half
        self._set_constraints_toggle_button(
            button, True,
            "Constrain FWHM range from plot… (ON)",
            "Constrain FWHM range from plot…")
        self.plot_interaction_ctrl.start_editable_xrange_tool(
            "Set peak FWHM maximum", xmin, xmax, apply_range,
            cancel_callback=cancel_button)

    @staticmethod
    def _optional_bound_or_default(value, default):
        """Return a finite optional bound or the supplied template value."""
        try:
            bound = float(value)
        except (TypeError, ValueError):
            bound = float(default)
        return bound if np.isfinite(bound) else float(default)

    @staticmethod
    def _apply_fwhm_bounds_from_plot_range(peak, xmin, xmax):
        peak["sigma_min"] = 0.0
        peak["sigma_max"] = abs(float(xmax) - float(xmin))
        peak["sigma_min_enabled"] = True
        peak["sigma_max_enabled"] = True

    def _on_default_bounds_changed(self):
        self._default_peak_bounds = {
            "center_half_range": float(self.widget.spinBox_CenterHalfRange.value()),
            "fwhm_min": float(self.widget.spinBox_DefaultFwhmMin.value()),
            "fwhm_max": float(self.widget.spinBox_DefaultFwhmMax.value()),
        }

    def _current_default_peak_bounds(self):
        if (hasattr(self.widget, "spinBox_CenterHalfRange") and
                hasattr(self.widget, "spinBox_DefaultFwhmMin") and
                hasattr(self.widget, "spinBox_DefaultFwhmMax")):
            return {
                "center_half_range": float(self.widget.spinBox_CenterHalfRange.value()),
                "fwhm_min": float(self.widget.spinBox_DefaultFwhmMin.value()),
                "fwhm_max": float(self.widget.spinBox_DefaultFwhmMax.value()),
            }
        return dict(self._default_peak_bounds)

    def default_peak_bounds(self):
        return self._current_default_peak_bounds()

    def initial_peak_fwhm(self):
        if hasattr(self.widget, "doubleSpinBox_InitialFWHM"):
            try:
                return float(self.widget.doubleSpinBox_InitialFWHM.value())
            except Exception:
                pass
        return 0.01

    def _add_bg_anchor_from_view(self):
        if not self.model.current_section_exist():
            return
        x0, x1 = self.widget.mpl.canvas.ax_pattern.get_xlim()
        self._add_bg_anchor_row({"xmin": min(x0, x1), "xmax": max(x0, x1), "weight": 10.0}, append_to_model=True)
        label = getattr(self.widget, "label_PlotHelp", None)
        if label:
            label.setText("Background anchor range added from the current plot view.")

    def _remove_bg_anchor_rows(self):
        if not self.model.current_section_exist():
            return
        table = self.widget.tableWidget_BGAnchorRanges
        rows = set()
        if table.selectionModel():
            rows = {index.row() for index in table.selectionModel().selectedRows()}
            if not rows:
                rows = {index.row() for index in table.selectionModel().selectedIndexes()}
        if not rows and table.currentRow() >= 0:
            rows.add(table.currentRow())
        for row in sorted(rows, reverse=True):
            table.removeRow(row)
        anchors = []
        for r in range(table.rowCount()):
            xmin_w = table.cellWidget(r, 0)
            xmax_w = table.cellWidget(r, 1)
            weight_w = table.cellWidget(r, 2)
            if xmin_w and xmax_w and weight_w:
                anchors.append({
                    "xmin": min(float(xmin_w.value()), float(xmax_w.value())),
                    "xmax": max(float(xmin_w.value()), float(xmax_w.value())),
                    "weight": float(weight_w.value()),
                })
        self.model.current_section.background_anchor_ranges = anchors
        self.set_tableWidget_PkParams_unsaved()

    def _remove_bg_anchor_range(self, checked=False):
        if self.plot_interaction_ctrl is None:
            return
        if not checked:
            self.plot_interaction_ctrl.cancel_range_tool()
            if hasattr(self.widget, "pushButton_RemoveBGAnchor"):
                self.widget.pushButton_RemoveBGAnchor.setText("Remove range")
                _set_toggle_button_style(self.widget.pushButton_RemoveBGAnchor, False)
            return

        def remove_range(xmin, xmax):
            table = self.widget.tableWidget_BGAnchorRanges
            to_remove = []
            for r in range(table.rowCount()):
                xmin_w = table.cellWidget(r, 0)
                xmax_w = table.cellWidget(r, 1)
                if xmin_w and xmax_w:
                    row_xmin = float(xmin_w.value())
                    row_xmax = float(xmax_w.value())
                    if abs(row_xmin - xmin) < 0.001 and abs(row_xmax - xmax) < 0.001:
                        to_remove.append(r)
            for row in sorted(to_remove, reverse=True):
                table.removeRow(row)
            self._sync_anchor_rows_to_section()
            if hasattr(self.widget, "pushButton_RemoveBGAnchor"):
                self.widget.pushButton_RemoveBGAnchor.setText("Stop picking ranges")
                _set_toggle_button_style(self.widget.pushButton_RemoveBGAnchor, True)

        def deactivate():
            if hasattr(self.widget, "pushButton_RemoveBGAnchor"):
                self.widget.pushButton_RemoveBGAnchor.setChecked(False)
                self.widget.pushButton_RemoveBGAnchor.setText("Remove range")
                _set_toggle_button_style(self.widget.pushButton_RemoveBGAnchor, False)

        self.plot_interaction_ctrl.start_range_tool(
            "Remove background anchor range", remove_range, repeat=True, cancel_callback=deactivate)
        if hasattr(self.widget, "pushButton_RemoveBGAnchor"):
            self.widget.pushButton_RemoveBGAnchor.setText("Stop picking ranges")
            _set_toggle_button_style(self.widget.pushButton_RemoveBGAnchor, True)

    def _set_bg_toggle_button_style(self, button, checked):
        apply_raised_toggle_style(button, checked=checked)

    def _arm_bg_anchor_range(self, checked=False):
        if self.plot_interaction_ctrl is None:
            return
        if not checked:
            self.plot_interaction_ctrl.cancel_range_tool()
            if hasattr(self.widget, "pushButton_AddRangeFromPlot"):
                self.widget.pushButton_AddRangeFromPlot.setText("Add range from plot")
                self._set_bg_toggle_button_style(self.widget.pushButton_AddRangeFromPlot, False)
            return
        def add_range(xmin, xmax):
            self._add_bg_anchor_row({"xmin": float(xmin), "xmax": float(xmax), "weight": 10.0}, append_to_model=True)
            if hasattr(self.widget, "pushButton_AddRangeFromPlot"):
                self.widget.pushButton_AddRangeFromPlot.setText("Stop picking ranges")
                self._set_bg_toggle_button_style(self.widget.pushButton_AddRangeFromPlot, True)
        def deactivate():
            if hasattr(self.widget, "pushButton_AddRangeFromPlot"):
                self.widget.pushButton_AddRangeFromPlot.setChecked(False)
                self.widget.pushButton_AddRangeFromPlot.setText("Add range from plot")
                self._set_bg_toggle_button_style(self.widget.pushButton_AddRangeFromPlot, False)
        self.plot_interaction_ctrl.start_range_tool(
            "Add background anchor range", add_range, repeat=True, cancel_callback=deactivate)
        if hasattr(self.widget, "pushButton_AddRangeFromPlot"):
            self.widget.pushButton_AddRangeFromPlot.setText("Stop picking ranges")
            self._set_bg_toggle_button_style(self.widget.pushButton_AddRangeFromPlot, True)

    def _add_bg_anchor_row(self, anchor=None, append_to_model=False):
        if not hasattr(self.widget, "tableWidget_BGAnchorRanges"):
            return
        table = self.widget.tableWidget_BGAnchorRanges
        if anchor is None:
            x0, x1 = self.widget.mpl.canvas.ax_pattern.get_xlim()
            anchor = {"xmin": min(x0, x1), "xmax": max(x0, x1), "weight": 10.0}
        row = table.rowCount()
        table.insertRow(row)
        for col, key in enumerate(("xmin", "xmax", "weight")):
            value = anchor.get(key, 10.0 if key == "weight" else 0.0)
            decimals = 2 if key == "weight" else 5
            box = self._make_spinbox(value, decimals)
            if key == "weight":
                box.setMinimum(1.0)
                box.setMaximum(MAX_BACKGROUND_ANCHOR_WEIGHT)
                box.setToolTip("Relative anchor strength. Values are capped to avoid unstable or slow fitting.")
            table.setCellWidget(row, col, box)
        table.resizeColumnsToContents()
        if append_to_model:
            anchors = getattr(self.model.current_section, "background_anchor_ranges", [])
            anchors.append({
                "xmin": min(float(anchor["xmin"]), float(anchor["xmax"])),
                "xmax": max(float(anchor["xmin"]), float(anchor["xmax"])),
                "weight": float(anchor["weight"]),
            })
            self.model.current_section.background_anchor_ranges = anchors
            self.set_tableWidget_PkParams_unsaved()

    def _on_bg_poly_order_changed(self):
        if not self.model.current_section_exist():
            return
        order = int(self.widget.spinBox_BGPolyOrder.value())
        self.model.current_section.set_baseline(order)
        self._populate_bg_coeff_table()
        self.set_tableWidget_PkParams_unsaved()

    def _on_peakfit_tab_changed(self, index):
        if not hasattr(self.widget, "tabWidget_PeakFit"):
            return
        previous = self._last_peakfit_tab
        current = self.widget.tabWidget_PeakFit.widget(index)
        if previous == getattr(self.widget, "tab_PeakFitConstraints", None):
            self._sync_constraints_tab_row_to_model()
        elif previous == getattr(self.widget, "tab_PeakFitBackground", None):
            self._sync_background_tab_to_model()
        if current == getattr(self.widget, "tab_PeakFitPeaks", None):
            self.peakfit_table_ctrl.update_peak_parameters()
        elif current == getattr(self.widget, "tab_PeakFitSection", None):
            self.peakfit_table_ctrl.update_sections()
        if current == getattr(self.widget, "tab_PeakFitConstraints", None):
            self.peakfit_table_ctrl.update_peak_constraints()
            self._populate_constraints_tab_from_model()
            self._refresh_constraints_peak_selector()
            self._update_constraints_tab_state()
        elif current == getattr(self.widget, "tab_PeakFitBackground", None):
            self.peakfit_table_ctrl.update_baseline_constraints()
            self._populate_background_tab_from_model()
        self._last_peakfit_tab = current

    def _populate_constraints_tab_from_model(self):
        if not hasattr(self.widget, "spinBox_CenterHalfRange"):
            return
        defaults = self.default_peak_bounds()
        self.widget.spinBox_CenterHalfRange.setValue(defaults["center_half_range"])
        self.widget.spinBox_DefaultFwhmMin.setValue(defaults["fwhm_min"])
        self.widget.spinBox_DefaultFwhmMax.setValue(defaults["fwhm_max"])

    def _populate_background_tab_from_model(self):
        if not self.model.current_section_exist():
            return
        if not hasattr(self.widget, "spinBox_BGPolyOrder"):
            return
        order = self.model.current_section.get_order_of_baseline_in_queue()
        self.widget.spinBox_BGPolyOrder.blockSignals(True)
        self.widget.spinBox_BGPolyOrder.setValue(order if order >= 0 else 1)
        self.widget.spinBox_BGPolyOrder.blockSignals(False)
        self._populate_bg_coeff_table()
        self._populate_bg_anchor_table()

    def _populate_bg_coeff_table(self):
        if not hasattr(self.widget, "tableWidget_BGCoefficients"):
            return
        if not self.model.current_section_exist():
            return
        table = self.widget.tableWidget_BGCoefficients
        order = int(self.widget.spinBox_BGPolyOrder.value())
        coeffs = getattr(self.model.current_section, "baseline_in_queue", [])
        table.setRowCount(order + 1)
        for row in range(order + 1):
            coeff = coeffs[row] if row < len(coeffs) else {"value": 0.0, "vary": True}
            val_box = self._make_spinbox(coeff.get("value", 0.0), 5)
            val_box.valueChanged.connect(self._on_bg_coeff_changed)
            table.setCellWidget(row, 0, val_box)
            vary_box = self._make_checkbox(coeff.get("vary", True))
            vary_box.toggled.connect(self._on_bg_coeff_changed)
            table.setCellWidget(row, 1, vary_box)
        table.resizeColumnsToContents()

    def _on_bg_coeff_changed(self):
        if not self.model.current_section_exist():
            return
        table = self.widget.tableWidget_BGCoefficients
        coeffs = []
        for row in range(table.rowCount()):
            val_w = table.cellWidget(row, 0)
            vary_w = table.cellWidget(row, 1)
            if val_w and vary_w:
                coeffs.append({"value": float(val_w.value()), "vary": bool(vary_w.isChecked())})
        self.model.current_section.baseline_in_queue = coeffs
        self.set_tableWidget_PkParams_unsaved()

    def _populate_bg_anchor_table(self):
        if not hasattr(self.widget, "tableWidget_BGAnchorRanges"):
            return
        if not self.model.current_section_exist():
            return
        table = self.widget.tableWidget_BGAnchorRanges
        anchors = getattr(self.model.current_section, "background_anchor_ranges", [])
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["xmin", "xmax", "weight"])
        table.setRowCount(0)
        for anchor in anchors:
            row = table.rowCount()
            table.insertRow(row)
            for col, key in enumerate(("xmin", "xmax", "weight")):
                value = anchor.get(key, 10.0 if key == "weight" else 0.0)
                decimals = 2 if key == "weight" else 5
                box = self._make_spinbox(value, decimals)
                if key == "weight":
                    box.setMinimum(1.0)
                    box.setMaximum(MAX_BACKGROUND_ANCHOR_WEIGHT)
                table.setCellWidget(row, col, box)
            table.resizeColumnsToContents()

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
        if hasattr(self.widget, "spinBox_CenterHalfRange"):
            self.widget.spinBox_CenterHalfRange.blockSignals(True)
            self.widget.spinBox_CenterHalfRange.setValue(float(center_half_range))
            self.widget.spinBox_CenterHalfRange.blockSignals(False)
        if hasattr(self.widget, "spinBox_DefaultFwhmMin"):
            self.widget.spinBox_DefaultFwhmMin.blockSignals(True)
            self.widget.spinBox_DefaultFwhmMin.setValue(float(fwhm_min))
            self.widget.spinBox_DefaultFwhmMin.blockSignals(False)
        if hasattr(self.widget, "spinBox_DefaultFwhmMax"):
            self.widget.spinBox_DefaultFwhmMax.blockSignals(True)
            self.widget.spinBox_DefaultFwhmMax.setValue(float(fwhm_max))
            self.widget.spinBox_DefaultFwhmMax.blockSignals(False)

    def _apply_default_bounds_to_peak(self, peak):
        center = float(peak.get("center", 0.0))
        defaults = self.default_peak_bounds()
        center_half_range = defaults["center_half_range"]
        peak["center_min"] = center - center_half_range
        peak["center_max"] = center + center_half_range
        peak["center_min_enabled"] = True
        peak["center_max_enabled"] = True
        peak["sigma_min"] = defaults["fwhm_min"]
        peak["sigma_max"] = defaults["fwhm_max"]
        peak["sigma_min_enabled"] = True
        peak["sigma_max_enabled"] = True
        peak["fraction_min"] = DEFAULT_NL_MIN
        peak["fraction_max"] = DEFAULT_NL_MAX
        peak["fraction_min_enabled"] = True
        peak["fraction_max_enabled"] = True

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

    def zoom_to_section(self, lightweight=False, gsas_style=False):
        if not self.model.current_section_exist():
            return
        x_range = self.model.current_section.get_xrange()
        y_range = self.model.current_section.get_yrange(
            bgsub=self.widget.checkBox_BgSub.isChecked())
        margin = 0.1 * (y_range[1] - y_range[0])
        limits = (
            x_range[0], x_range[1],
            y_range[0] - margin, y_range[1] + margin)
        if lightweight and hasattr(self.plot_ctrl, "refresh_current_section_view"):
            self.plot_ctrl.refresh_current_section_view(
                limits=limits, gsas_style=gsas_style)
            return
        self.plot_ctrl.update(limits=limits, gsas_style=gsas_style)
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
        width = self.initial_peak_fwhm()
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
        self.lineEdit_PkParamsStatus.setStyleSheet("")
        self._set_status_text(
            self.lineEdit_PkParamsStatus,
            "Peaks table status: current peak settings were saved to Sections.")

    def set_tableWidget_PkParams_unsaved(self):
        self.widget.tableWidget_PkParams.setStyleSheet("")
        self.lineEdit_PkParamsStatus.setStyleSheet("background-color: red;")
        self._set_status_text(
            self.lineEdit_PkParamsStatus,
            "Peaks table status: unsaved peak settings. Click Save to store them in Sections.")

    def set_tableWidget_PkFtSections_saved(self):
        self.widget.tableWidget_PkFtSections.setStyleSheet("")
        self.lineEdit_PkFtSectionsStatus.setStyleSheet("")
        self._set_status_text(
            self.lineEdit_PkFtSectionsStatus,
            "Sections table status: no unsaved section-list changes.")

    def set_tableWidget_PkFtSections_unsaved(self):
        self.widget.tableWidget_PkFtSections.setStyleSheet("")
        self.lineEdit_PkFtSectionsStatus.setStyleSheet("background-color: red;")
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
        if idx < 0 or idx >= len(self.model.section_lst):
            return
        selected_section = self.model.section_lst[idx]
        selected_timestamp = selected_section.get_timestamp()
        source_switched = False
        if not self._activate_pattern_for_section(selected_section):
            return
        source_switched = bool(
            getattr(self, "_last_section_source_switched", False))
        idx = self._section_index_for_timestamp(selected_timestamp, idx)
        if idx is None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The selected fitting section could not be found after "
                "switching the 1D pattern.")
            return
        # Reload selected section from PARAM CSV on demand so graph updates
        # reflect persisted section data (not stale in-memory copies).
        if self.model.base_ptn_exist():
            in_memory_section = self.model.section_lst[idx]
            section_has_data = (
                in_memory_section is not None and
                getattr(in_memory_section, "x", None) is not None and
                len(in_memory_section.x) > 0 and
                getattr(in_memory_section, "y_bgsub", None) is not None
            )
            should_reload_from_param = source_switched or (not section_has_data)
            try:
                section_disk = load_section_from_param(
                    self.model.get_base_ptn_filename(), idx) \
                    if should_reload_from_param else None
            except Exception:
                section_disk = None
            section_has_data = section_disk is not None and \
                getattr(section_disk, "x", None) is not None and \
                len(section_disk.x) > 0 and \
                getattr(section_disk, "y_bgsub", None) is not None
            if section_has_data:
                self.model.section_lst[idx] = section_disk
            elif should_reload_from_param and \
                    not self.model.section_lst[idx].get_number_of_peaks_in_queue():
                QtWidgets.QMessageBox.warning(
                    self.widget, "Missing Section Data",
                    "Saved section data for the selected row was not found.\n"
                    "Using in-memory section data instead.")
        self.model.set_this_section_current(idx)
        self.peakfit_table_ctrl.update_sections()
        current_peakfit_tab = None
        if hasattr(self.widget, "tabWidget_PeakFit"):
            current_peakfit_tab = self.widget.tabWidget_PeakFit.currentWidget()
        if current_peakfit_tab == getattr(self.widget, "tab_PeakFitPeaks", None):
            self.peakfit_table_ctrl.update_peak_parameters()
        elif current_peakfit_tab == getattr(self.widget, "tab_PeakFitConstraints", None):
            self.peakfit_table_ctrl.update_peak_constraints()
            self._update_constraints_tab_state()
        elif current_peakfit_tab == getattr(self.widget, "tab_PeakFitBackground", None):
            self.peakfit_table_ctrl.update_baseline_constraints()
        """
        self._list_peaks()
        self._list_localbg()
        self._update_config
        """
        gsas_style = bool(
            hasattr(self.widget, "pushButton_PlotSelectedPkFtResults") and
            self.widget.pushButton_PlotSelectedPkFtResults.isChecked())
        self.zoom_to_section(
            lightweight=(not source_switched), gsas_style=gsas_style)

    def _same_path(self, path_a, path_b):
        if not path_a or not path_b:
            return False
        return os.path.normcase(os.path.abspath(path_a)) == \
            os.path.normcase(os.path.abspath(path_b))

    def _section_index_for_timestamp(self, timestamp, fallback_idx):
        if timestamp not in (None, ""):
            for row, section in enumerate(self.model.section_lst):
                if section.get_timestamp() == timestamp:
                    return row
        if 0 <= fallback_idx < len(self.model.section_lst):
            return fallback_idx
        return None

    def _activate_pattern_for_section(self, section):
        self._last_section_source_switched = False
        provenance = getattr(section, "source_provenance", {}) or {}
        source_kind = provenance.get("source_kind", "full_chi")
        if source_kind == "azimuthal_integration":
            target_chi = provenance.get("derived_chi", "")
            display_derived = True
            missing_text = "azimuth-derived CHI"
        else:
            target_chi = provenance.get("source_chi", "")
            display_derived = False
            missing_text = "full-azimuth CHI"

        if not target_chi:
            # Older sections did not store provenance; they belong to the
            # current source CHI.
            if not display_derived:
                return True
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "This section was fitted from a derived CHI, but the saved "
                "derived CHI path is missing.")
            return False

        target_chi = os.path.abspath(target_chi)
        if not os.path.exists(target_chi):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Cannot switch the 1D pattern for this section because the "
                f"{missing_text} was not found:\n{target_chi}")
            return False

        current_display = None
        getter = getattr(self.model, "get_display_ptn_filename", None)
        if callable(getter):
            current_display = getter()
        if self._same_path(current_display, target_chi):
            return True

        if self.base_ptn_ctrl is None:
            if display_derived:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Cannot switch to the derived CHI because the pattern "
                    "loader is unavailable.")
                return False
            clear_display = getattr(self.model, "clear_display_ptn", None)
            if callable(clear_display):
                clear_display()
            return True

        self.base_ptn_ctrl._setshow_new_base_ptn(
            target_chi, display_derived=display_derived)
        self._last_section_source_switched = True
        return True

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
        if hasattr(self.widget, "tableWidget_BGCoefficients"):
            self.widget.tableWidget_BGCoefficients.clearContents()
        if hasattr(self.widget, "tableWidget_PeakConstraints"):
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
        if hasattr(self.widget, "tableWidget_PeakConstraints"):
            self.widget.tableWidget_PeakConstraints.clearContents()
        if hasattr(self.widget, "tableWidget_BGCoefficients"):
            self.widget.tableWidget_BGCoefficients.clearContents()
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
                self.initial_peak_fwhm(),
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
        self._sync_constraints_tab_row_to_model()
        self._sync_background_tab_to_model()
        order = self.widget.spinBox_BGPolyOrder.value()
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
                order, 0.0, 0.0,
                apply_peak_constraints=self._apply_peak_constraints_enabled())
            progress.setLabelText("Optimizing peak parameters...")
            QtWidgets.QApplication.processEvents()
            success, converged = self.model.current_section.conduct_fitting()
        finally:
            progress.close()
        if success:
            self.zoom_to_section()
            self.peakfit_table_ctrl.update_peak_parameters()
            self.peakfit_table_ctrl.update_baseline_constraints()
            self.peakfit_table_ctrl.update_peak_constraints()
            self.set_tableWidget_PkParams_unsaved()
            QtWidgets.QApplication.processEvents()
            self._show_fit_result_dialog(converged)
            self._warn_zero_intensity_peaks()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Fitting Result",
                                          'Fitting failed.')

    @staticmethod
    def _format_fit_statistic(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "Not available"
        if not np.isfinite(value):
            return "Not available"
        return f"{value:.6g}"

    def _show_fit_result_dialog(self, converged):
        """Show convergence state and fit-quality statistics after fitting."""
        statistics = self.model.current_section.get_fit_quality_statistics()
        iterations = statistics.get("iterations")
        evaluations = statistics.get("function_evaluations")
        if iterations is not None:
            iteration_label = "Iterations"
            iteration_value = self._format_fit_statistic(iterations)
        else:
            iteration_label = "Function evaluations"
            iteration_value = self._format_fit_statistic(evaluations)

        if converged:
            status = "<b>Fitting converged successfully.</b>"
            icon = QtWidgets.QMessageBox.Information
        else:
            status = (
                '<span style="color: #cc0000; font-weight: bold;">'
                "Fitting finished but did not converge."
                "</span>")
            icon = QtWidgets.QMessageBox.Warning
        message = (
            f"{status}<br><br>"
            f"{iteration_label}: {iteration_value}<br>"
            f"Chi-square: {self._format_fit_statistic(statistics.get('chi_square'))}<br>"
            f"Rp: {self._format_fit_statistic(statistics.get('rp'))}<br>"
            f"Rwp (unit weights): {self._format_fit_statistic(statistics.get('rwp'))}")
        dialog = QtWidgets.QMessageBox(self.widget)
        dialog.setWindowTitle("Fitting Result")
        dialog.setIcon(icon)
        dialog.setTextFormat(QtCore.Qt.RichText)
        dialog.setText(message)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        dialog.exec()

    def _warn_zero_intensity_peaks(self):
        section = self.model.current_section
        if section is None or not section.peaks_exist():
            return
        amplitudes = []
        for peak in section.peaks_in_queue:
            try:
                amplitudes.append(float(peak.get('amplitude', 0.0)))
            except Exception:
                amplitudes.append(0.0)
        if amplitudes == []:
            return
        max_abs = max(abs(value) for value in amplitudes)
        zero_tol = max(1e-12, max_abs * 1e-8)
        zero_rows = []
        for row, (peak, amplitude) in enumerate(
                zip(section.peaks_in_queue, amplitudes), start=1):
            if amplitude <= zero_tol:
                hkl = (
                    int(peak.get('h', 0)),
                    int(peak.get('k', 0)),
                    int(peak.get('l', 0)),
                )
                try:
                    pos = float(peak.get('center', 0.0))
                    pos_text = f"{pos:.5g}"
                except Exception:
                    pos_text = "unknown"
                zero_rows.append(
                    f"Row {row}: {peak.get('phasename', '')} "
                    f"({hkl[0]} {hkl[1]} {hkl[2]}), Pos {pos_text}")
        if zero_rows == []:
            return
        QtWidgets.QMessageBox.warning(
            self.widget,
            "Zero Intensity Peaks",
            "The fitting result contains peak(s) with zero fitted intensity.\n\n"
            + "\n".join(zero_rows) +
            "\n\nYou may remove these peaks if they are not meaningful.")

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
