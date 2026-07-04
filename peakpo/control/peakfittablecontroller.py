from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from ..ds_section.section import normalize_peak_phase_name
from ..model.azimuthal_integration import source_label, source_ranges_label
# from .mplcontroller import MplController


class PeakfitTableController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self._row_header_width = 52

    def _widen_row_header(self, table):
        if table is None:
            return
        header = table.verticalHeader()
        header.setVisible(True)
        header.setDefaultAlignment(QtCore.Qt.AlignCenter)
        header.setMinimumWidth(self._row_header_width)
        header.setFixedWidth(self._row_header_width)

    def _style_peak_parameter_item(self, item, peak, vary_key):
        if bool(peak.get(vary_key, True)):
            return item
        item.setBackground(QtGui.QBrush(QtGui.QColor("#8b0000")))
        item.setForeground(QtGui.QBrush(QtGui.QColor("#ffd54f")))
        item.setToolTip("Fixed during fitting; this parameter is not varied.")
        font = item.font()
        font.setBold(True)
        font.setItalic(True)
        item.setFont(font)
        return item

    def update_peak_parameters(self):
        '''
        show a list of peaks in the list window of tab 2
        '''
        if not self.model.current_section_exist():
            self.widget.tableWidget_PkParams.clearContents()
            self.widget.tableWidget_PkParams.setRowCount(0)
            self.widget.tableWidget_PkParams.setColumnCount(0)
            return
        """
        if not self.model.current_section.fitted():
            print('current_sectio is not fitted')
            return
        """
        self.widget.tableWidget_PkParams.clearContents()
        n_columns = 8
        n_rows = self.model.current_section.get_number_of_peaks_in_queue()
        self.widget.tableWidget_PkParams.setColumnCount(n_columns)
        self.widget.tableWidget_PkParams.setRowCount(n_rows)
        self.widget.tableWidget_PkParams.horizontalHeader().setVisible(True)
        self._widen_row_header(self.widget.tableWidget_PkParams)
        self.widget.tableWidget_PkParams.setHorizontalHeaderLabels(
            ['Phase', 'h', 'k', 'l', 'Area', 'Pos', 'FWHM', 'nL'])
        row = 0
        self.model.current_section.peaks_in_queue.sort(
            key=lambda p: float(p.get('center', 0.0)))
        for peak in self.model.current_section.peaks_in_queue:
            # symmetric peaks
            peak['phasename'] = normalize_peak_phase_name(peak['phasename'])
            Item = QtWidgets.QTableWidgetItem(peak['phasename'])
            self.widget.tableWidget_PkParams.setItem(row, 0, Item)
            Item = QtWidgets.QTableWidgetItem(str(int(peak['h'])))
            self.widget.tableWidget_PkParams.setItem(row, 1, Item)
            Item = QtWidgets.QTableWidgetItem(str(int(peak['k'])))
            self.widget.tableWidget_PkParams.setItem(row, 2, Item)
            Item = QtWidgets.QTableWidgetItem(str(int(peak['l'])))
            self.widget.tableWidget_PkParams.setItem(row, 3, Item)
            amp = "{:f}".format(peak['amplitude'])
            Item = QtWidgets.QTableWidgetItem(amp)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self._style_peak_parameter_item(Item, peak, 'amplitude_vary')
            self.widget.tableWidget_PkParams.setItem(row, 4, Item)
            center = "{:.5e}".format(peak['center'])
            Item = QtWidgets.QTableWidgetItem(center)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self._style_peak_parameter_item(Item, peak, 'center_vary')
            self.widget.tableWidget_PkParams.setItem(row, 5, Item)
            sigma = "{:.5e}".format(peak['sigma'])
            Item = QtWidgets.QTableWidgetItem(sigma)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self._style_peak_parameter_item(Item, peak, 'sigma_vary')
            self.widget.tableWidget_PkParams.setItem(row, 6, Item)
            fraction = "{:.5e}".format(peak['fraction'])
            Item = QtWidgets.QTableWidgetItem(fraction)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self._style_peak_parameter_item(Item, peak, 'fraction_vary')
            self.widget.tableWidget_PkParams.setItem(row, 7, Item)
            row += 1
        self.widget.tableWidget_PkParams.cellChanged.connect(
            self._get_cellvalue)
        self.widget.tableWidget_PkParams.resizeColumnsToContents()
        self.widget.tableWidget_PkParams.resizeRowsToContents()

    def _get_cellvalue(self):
        col = self.widget.tableWidget_PkParams.currentColumn()
        row = self.widget.tableWidget_PkParams.currentRow()
        """ Not sure why we need this.  This causes loss of fit_result
        if (col == 0) or (col == 1) or (col == 2) or (col == 3):
            pass
        else:
            self.model.current_section.invalidate_fit_result()
        """
        if col == 0:
            self.model.current_section.peaks_in_queue[row]['phasename'] =\
                normalize_peak_phase_name(
                    self.widget.tableWidget_PkParams.currentItem().text())
        if col == 1:
            self.model.current_section.peaks_in_queue[row]['h'] =\
                int(self.widget.tableWidget_PkParams.currentItem().text())
        if col == 2:
            self.model.current_section.peaks_in_queue[row]['k'] =\
                int(self.widget.tableWidget_PkParams.currentItem().text())
        if col == 3:
            self.model.current_section.peaks_in_queue[row]['l'] =\
                int(self.widget.tableWidget_PkParams.currentItem().text())

    def update_sections(self):
        '''show a list of sections'''
        valid_sections = []
        for section in self.model.section_lst:
            x = getattr(section, "x", None)
            if (x is None) or (len(x) == 0):
                continue
            valid_sections.append(section)
        if len(valid_sections) != len(self.model.section_lst):
            self.model.section_lst = valid_sections
        n_columns = 5
        n_rows = len(valid_sections)  # count for number of sections
        if n_rows == 0:
            self.widget.tableWidget_PkFtSections.clearContents()
            self.widget.tableWidget_PkFtSections.setRowCount(0)
            self.widget.tableWidget_PkFtSections.setColumnCount(0)
            return
        self.widget.tableWidget_PkFtSections.setColumnCount(n_columns)
        self.widget.tableWidget_PkFtSections.setRowCount(n_rows)
        self.widget.tableWidget_PkFtSections.horizontalHeader().setVisible(
            True)
        self._widen_row_header(self.widget.tableWidget_PkFtSections)
        self.widget.tableWidget_PkFtSections.setHorizontalHeaderLabels(
            ['Time', 'xmin', 'xmax', 'Source', 'Azimuth'])
        i = 0
        for section in valid_sections:
            # column 0 - time
            item1 = QtWidgets.QTableWidgetItem(section.get_timestamp())
            item1.setFlags(QtCore.Qt.ItemIsEnabled |
                           QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 0, item1)
            # column 1 - Xmin
            item2 = QtWidgets.QTableWidgetItem("{:.2f}".format(section.x[0]))
            item2.setFlags(QtCore.Qt.ItemIsEnabled |
                           QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 1, item2)
            # column 2 - Xmax
            item3 = QtWidgets.QTableWidgetItem("{:.2f}".format(section.x[-1]))
            item3.setFlags(QtCore.Qt.ItemIsEnabled |
                           QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 2, item3)
            provenance = getattr(section, "source_provenance", {}) or {}
            item4 = QtWidgets.QTableWidgetItem(source_label(provenance))
            item4.setFlags(QtCore.Qt.ItemIsEnabled |
                           QtCore.Qt.ItemIsSelectable)
            item4.setToolTip(str(provenance.get("source_chi", "")))
            self.widget.tableWidget_PkFtSections.setItem(i, 3, item4)
            item5 = QtWidgets.QTableWidgetItem(source_ranges_label(provenance))
            item5.setFlags(QtCore.Qt.ItemIsEnabled |
                           QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 4, item5)
            i += 1
        self.widget.tableWidget_PkFtSections.resizeColumnsToContents()
        self.widget.tableWidget_PkFtSections.resizeRowsToContents()

    def update_baseline_constraints(self):
        if not self.model.current_section_exist():
            if hasattr(self.widget, "tableWidget_BGCoefficients"):
                self.widget.tableWidget_BGCoefficients.clearContents()
                self.widget.tableWidget_BGCoefficients.setRowCount(0)
                self.widget.tableWidget_BGCoefficients.setColumnCount(0)
            return
        n_columns = 2
        poly_order = self.model.current_section.\
            get_order_of_baseline_in_queue()
        if hasattr(self.widget, "spinBox_BGPolyOrder") and poly_order >= 0:
            old_state = self.widget.spinBox_BGPolyOrder.blockSignals(True)
            self.widget.spinBox_BGPolyOrder.setValue(poly_order)
            self.widget.spinBox_BGPolyOrder.blockSignals(old_state)
        n_rows = poly_order + 1
        if hasattr(self.widget, "tableWidget_BGCoefficients"):
            self.widget.tableWidget_BGCoefficients.clearContents()
            self.widget.tableWidget_BGCoefficients.setColumnCount(n_columns)
            self.widget.tableWidget_BGCoefficients.setRowCount(n_rows)
            self.widget.tableWidget_BGCoefficients.horizontalHeader().setVisible(True)
            self.widget.tableWidget_BGCoefficients.setHorizontalHeaderLabels(['Factor', 'Vary'])
            for row in range(n_rows):
                # column 0 - factor
                self.Background_doubleSpinBox = QtWidgets.QDoubleSpinBox()
                self.Background_doubleSpinBox.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                    QtCore.Qt.AlignVCenter)
                self.Background_doubleSpinBox.setMaximum(100000.)
                self.Background_doubleSpinBox.setMinimum(-100000.)
                self.Background_doubleSpinBox.setSingleStep(0.001)
                self.Background_doubleSpinBox.setDecimals(3)
                self.Background_doubleSpinBox.setValue(
                    self.model.current_section.baseline_in_queue[row]['value'])
                self.Background_doubleSpinBox.setKeyboardTracking(False)
                self.Background_doubleSpinBox.valueChanged.connect(
                    self._bglist_handle_doubleSpinBoxChanged)
                self.widget.tableWidget_BGCoefficients.setCellWidget(
                    row, 0, self.Background_doubleSpinBox)
                # column 1 - fix checkbox
                item = QtWidgets.QTableWidgetItem()
                item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                              QtCore.Qt.ItemIsEnabled)
                if self.model.current_section.baseline_in_queue[row]['vary']:
                    item.setCheckState(QtCore.Qt.Checked)
                else:
                    item.setCheckState(QtCore.Qt.Unchecked)
                self.widget.tableWidget_BGCoefficients.setItem(row, 1, item)
                self.widget.tableWidget_BGCoefficients.itemClicked.connect(
                    self._bglist_handle_ItemClicked)
            self.widget.tableWidget_BGCoefficients.resizeColumnsToContents()
            self.widget.tableWidget_BGCoefficients.resizeRowsToContents()

    def _bglist_handle_ItemClicked(self, item):
        if (item.column() != 1):
            return
        row = item.row()
        col = item.column()
        self.model.current_section.invalidate_fit_result()
        value = (item.checkState() == QtCore.Qt.Checked)
        self.model.current_section.baseline_in_queue[row]['vary'] = value

    def _bglist_handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        if not hasattr(self.widget, "tableWidget_BGCoefficients"):
            return
        index = self.widget.tableWidget_BGCoefficients.indexAt(box.pos())
        if not index.isValid():
            return
        self.model.current_section.invalidate_fit_result()
        row = index.row()
        col = index.column()
        if col == 0:
            self.model.current_section.baseline_in_queue[row]['value'] = \
                value

    def update_peak_constraints(self):
        if not self.model.current_section_exist():
            if hasattr(self.widget, "tableWidget_PeakConstraints"):
                self.widget.tableWidget_PeakConstraints.clearContents()
                self.widget.tableWidget_PeakConstraints.setRowCount(0)
                self.widget.tableWidget_PeakConstraints.setColumnCount(0)
            return
        if not hasattr(self.widget, "tableWidget_PeakConstraints"):
            return
        self.widget.tableWidget_PeakConstraints.clearContents()
        self._apply_peak_constraints_selection_behavior()
        n_columns = 8
        n_rows = self.model.current_section.get_number_of_peaks_in_queue()
        self.widget.tableWidget_PeakConstraints.setColumnCount(n_columns)
        self.widget.tableWidget_PeakConstraints.setRowCount(n_rows)
        self.widget.tableWidget_PeakConstraints.horizontalHeader().setVisible(
            True)
        self._widen_row_header(self.widget.tableWidget_PeakConstraints)
        self.widget.tableWidget_PeakConstraints.setHorizontalHeaderLabels(
            ['Ampl', 'Vary', 'Center', 'Vary', 'FWHM', 'Vary', 'n_L', 'Vary'])
        for row in range(n_rows):
            # column 0 - height
            self.PkConst_doubleSpinBox_height = QtWidgets.QDoubleSpinBox()
            self.PkConst_doubleSpinBox_height.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.PkConst_doubleSpinBox_height.setMaximum(100000.)
            self.PkConst_doubleSpinBox_height.setSingleStep(10.)
            self.PkConst_doubleSpinBox_height.setDecimals(3)
            self.PkConst_doubleSpinBox_height.setValue(
                self.model.current_section.peaks_in_queue[row]['amplitude'])
            self.PkConst_doubleSpinBox_height.valueChanged.connect(
                self._peaklist_handle_doubleSpinBoxChanged)
            self.PkConst_doubleSpinBox_height.setKeyboardTracking(False)
            self.widget.tableWidget_PeakConstraints.setCellWidget(
                row, 0, self.PkConst_doubleSpinBox_height)
            # column 1 - fix checkbox
            item_h = QtWidgets.QTableWidgetItem()
            item_h.setFlags(QtCore.Qt.ItemIsSelectable |
                            QtCore.Qt.ItemIsUserCheckable |
                            QtCore.Qt.ItemIsEnabled)
            if self.model.current_section.\
                    peaks_in_queue[row]['amplitude_vary'] == False:
                item_h.setCheckState(QtCore.Qt.Unchecked)
            else:
                item_h.setCheckState(QtCore.Qt.Checked)
            self.widget.tableWidget_PeakConstraints.setItem(row, 1, item_h)
            # column 2 - pos
            self.PkConst_doubleSpinBox_pos = QtWidgets.QDoubleSpinBox()
            self.PkConst_doubleSpinBox_pos.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.PkConst_doubleSpinBox_pos.setMaximum(10000.)
            self.PkConst_doubleSpinBox_pos.setSingleStep(0.001)
            self.PkConst_doubleSpinBox_pos.setDecimals(3)
            self.PkConst_doubleSpinBox_pos.setValue(
                self.model.current_section.peaks_in_queue[row]['center'])
            self.PkConst_doubleSpinBox_pos.valueChanged.connect(
                self._peaklist_handle_doubleSpinBoxChanged)
            self.PkConst_doubleSpinBox_pos.setKeyboardTracking(False)
            self.widget.tableWidget_PeakConstraints.setCellWidget(
                row, 2, self.PkConst_doubleSpinBox_pos)
            # column 3 - fix checkbox
            item_p = QtWidgets.QTableWidgetItem()
            item_p.setFlags(QtCore.Qt.ItemIsSelectable |
                            QtCore.Qt.ItemIsUserCheckable |
                            QtCore.Qt.ItemIsEnabled)
            if self.model.current_section.peaks_in_queue[row][
                    'center_vary'] == False:
                item_p.setCheckState(QtCore.Qt.Unchecked)
            else:
                item_p.setCheckState(QtCore.Qt.Checked)
            self.widget.tableWidget_PeakConstraints.setItem(row, 3, item_p)
            # column 4 - width
            self.PkConst_doubleSpinBox_width = QtWidgets.QDoubleSpinBox()
            self.PkConst_doubleSpinBox_width.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.PkConst_doubleSpinBox_width.setMaximum(10000.)
            self.PkConst_doubleSpinBox_width.setSingleStep(0.00001)
            self.PkConst_doubleSpinBox_width.setDecimals(5)
            self.PkConst_doubleSpinBox_width.setValue(
                self.model.current_section.peaks_in_queue[row]['sigma'])
            self.PkConst_doubleSpinBox_width.valueChanged.connect(
                self._peaklist_handle_doubleSpinBoxChanged)
            self.PkConst_doubleSpinBox_width.setKeyboardTracking(False)
            self.widget.tableWidget_PeakConstraints.setCellWidget(
                row, 4, self.PkConst_doubleSpinBox_width)
            # column 5 - fix checkbox
            item_w = QtWidgets.QTableWidgetItem()
            item_w.setFlags(QtCore.Qt.ItemIsSelectable |
                            QtCore.Qt.ItemIsUserCheckable |
                            QtCore.Qt.ItemIsEnabled)
            if self.model.current_section.peaks_in_queue[row]['sigma_vary'] \
                    == False:
                item_w.setCheckState(QtCore.Qt.Unchecked)
            else:
                item_w.setCheckState(QtCore.Qt.Checked)
            self.widget.tableWidget_PeakConstraints.setItem(row, 5, item_w)
            # column 6 - nL
            self.PkConst_doubleSpinBox_nL = QtWidgets.QDoubleSpinBox()
            self.PkConst_doubleSpinBox_nL.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.PkConst_doubleSpinBox_nL.setMaximum(1.)
            self.PkConst_doubleSpinBox_nL.setSingleStep(0.01)
            self.PkConst_doubleSpinBox_nL.setDecimals(2)
            self.PkConst_doubleSpinBox_nL.setValue(
                self.model.current_section.peaks_in_queue[row]['fraction'])
            self.PkConst_doubleSpinBox_nL.valueChanged.connect(
                self._peaklist_handle_doubleSpinBoxChanged)
            self.PkConst_doubleSpinBox_nL.setKeyboardTracking(False)
            self.widget.tableWidget_PeakConstraints.setCellWidget(
                row, 6, self.PkConst_doubleSpinBox_nL)
            # column 7 - fix checkbox
            item_nL = QtWidgets.QTableWidgetItem()
            item_nL.setFlags(QtCore.Qt.ItemIsSelectable |
                             QtCore.Qt.ItemIsUserCheckable |
                             QtCore.Qt.ItemIsEnabled)
            if self.model.current_section.\
                    peaks_in_queue[row]['fraction_vary'] == False:
                item_nL.setCheckState(QtCore.Qt.Unchecked)
            else:
                item_nL.setCheckState(QtCore.Qt.Checked)
            self.widget.tableWidget_PeakConstraints.setItem(row, 7, item_nL)
        self.widget.tableWidget_PeakConstraints.itemClicked.connect(
            self._peaklist_handle_ItemClicked)
        self.widget.tableWidget_PeakConstraints.resizeColumnsToContents()
        self.widget.tableWidget_PeakConstraints.resizeRowsToContents()
        self._sync_peak_constraints_selection_style()

    def _apply_peak_constraints_selection_behavior(self):
        if not hasattr(self.widget, "tableWidget_PeakConstraints"):
            return
        table = self.widget.tableWidget_PeakConstraints
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setStyleSheet(
            "QTableWidget#tableWidget_PeakConstraints::item:selected {"
            "background-color: #1565c0;"
            "color: #ffffff;"
            "}"
            "QTableWidget#tableWidget_PeakConstraints::item:selected:!active {"
            "background-color: #1565c0;"
            "color: #ffffff;"
            "}")
        try:
            table.itemSelectionChanged.disconnect(
                self._sync_peak_constraints_selection_style)
        except Exception:
            pass
        table.itemSelectionChanged.connect(
            self._sync_peak_constraints_selection_style)

    def _sync_peak_constraints_selection_style(self):
        if not hasattr(self.widget, "tableWidget_PeakConstraints"):
            return
        table = self.widget.tableWidget_PeakConstraints
        selected_rows = set()
        selection_model = table.selectionModel()
        if selection_model is not None:
            selected_rows = {index.row()
                             for index in selection_model.selectedRows()}
            if not selected_rows:
                selected_rows = {index.row()
                                 for index in selection_model.selectedIndexes()}
        selected_style = (
            "QDoubleSpinBox {"
            "background-color: #1565c0;"
            "color: #ffffff;"
            "selection-background-color: #0d47a1;"
            "}")
        for row in range(table.rowCount()):
            style = selected_style if row in selected_rows else ""
            for col in (0, 2, 4, 6):
                widget = table.cellWidget(row, col)
                if widget is not None:
                    widget.setStyleSheet(style)

    def _peaklist_handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        if not hasattr(self.widget, "tableWidget_PeakConstraints"):
            return
        index = self.widget.tableWidget_PeakConstraints.indexAt(box.pos())
        if not index.isValid():
            return
        self.model.current_section.invalidate_fit_result()
        row = index.row()
        col = index.column()
        if col == 0:
            self.model.current_section.peaks_in_queue[row]['amplitude'] = \
                value
        elif col == 2:
            self.model.current_section.peaks_in_queue[row]['center'] = \
                value
        elif col == 4:
            self.model.current_section.peaks_in_queue[row]['sigma'] = \
                value
        elif col == 6:
            self.model.current_section.peaks_in_queue[row]['fraction'] = \
                value
        # self.update_graph()

    def _peaklist_handle_ItemClicked(self, item):
        if (item.column() != 1) and (item.column() != 3) and \
                (item.column() != 5) and (item.column() != 7):
            return
        self.model.current_section.invalidate_fit_result()
        row = item.row()
        col = item.column()
        value = (item.checkState() == QtCore.Qt.Checked)
        if col == 1:
            self.model.current_section.peaks_in_queue[row]['amplitude_vary'] \
                = value
        elif col == 3:
            self.model.current_section.peaks_in_queue[row]['center_vary'] \
                = value
        elif col == 5:
            self.model.current_section.peaks_in_queue[row]['sigma_vary'] \
                = value
        elif col == 7:
            self.model.current_section.peaks_in_queue[row]['fraction_vary'] \
                = value
