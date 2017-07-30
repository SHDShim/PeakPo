from PyQt5 import QtCore
from PyQt5 import QtWidgets
# from .mplcontroller import MplController


class PeakfitTableController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget

    def update_peak_parameters(self):
        '''
        show a list of peaks in the list window of tab 2
        '''
        if not self.model.current_section_exist():
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
        self.widget.tableWidget_PkParams.setHorizontalHeaderLabels(
            ['Phase', 'h', 'k', 'l', 'Area', 'Pos', 'FWHM', 'nL'])
        row = 0
        for peak in self.model.current_section.peaks_in_queue:
            # symmetric peaks
            Item = QtWidgets.QTableWidgetItem(peak['phasename'])
            self.widget.tableWidget_PkParams.setItem(row, 0, Item)
            Item = QtWidgets.QTableWidgetItem(str(int(peak['h'])))
            self.widget.tableWidget_PkParams.setItem(row, 1, Item)
            Item = QtWidgets.QTableWidgetItem(str(int(peak['k'])))
            self.widget.tableWidget_PkParams.setItem(row, 2, Item)
            Item = QtWidgets.QTableWidgetItem(str(int(peak['l'])))
            self.widget.tableWidget_PkParams.setItem(row, 3, Item)
            amp = "{:.5e}".format(peak['amplitude'])
            Item = QtWidgets.QTableWidgetItem(amp)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 4, Item)
            center = "{:.5e}".format(peak['center'])
            Item = QtWidgets.QTableWidgetItem(center)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 5, Item)
            sigma = "{:.5e}".format(peak['sigma'])
            Item = QtWidgets.QTableWidgetItem(sigma)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 6, Item)
            fraction = "{:.5e}".format(peak['fraction'])
            Item = QtWidgets.QTableWidgetItem(fraction)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
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
                self.widget.tableWidget_PkParams.currentItem().text()
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
        n_columns = 3
        n_rows = self.model.get_number_of_section()  # count for number of jcpds
        if n_rows == 0:
            return
        self.widget.tableWidget_PkFtSections.setColumnCount(n_columns)
        self.widget.tableWidget_PkFtSections.setRowCount(n_rows)
        self.widget.tableWidget_PkFtSections.horizontalHeader().setVisible(
            True)
        self.widget.tableWidget_PkFtSections.setHorizontalHeaderLabels(
            ['Time', 'xmin', 'xmax'])
        i = 0
        for section in self.model.section_lst:
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
            i += 1
        self.widget.tableWidget_PkFtSections.resizeColumnsToContents()
        self.widget.tableWidget_PkFtSections.resizeRowsToContents()

    def update_baseline_constraints(self):
        '''show a list of local bg in a tab'''
        if not self.model.current_section_exist():
            return
        self.widget.tableWidget_BackgroundConstraints.clearContents()
        n_columns = 2
        poly_order = self.model.current_section.\
            get_order_of_baseline_in_queue()
        n_rows = poly_order + 1
        self.widget.tableWidget_BackgroundConstraints.setColumnCount(n_columns)
        self.widget.tableWidget_BackgroundConstraints.setRowCount(n_rows)
        self.widget.tableWidget_BackgroundConstraints.horizontalHeader().\
            setVisible(True)
        self.widget.tableWidget_BackgroundConstraints.\
            setHorizontalHeaderLabels(['Factor', 'Vary'])
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
            self.widget.tableWidget_BackgroundConstraints.setCellWidget(
                row, 0, self.Background_doubleSpinBox)
            # column 1 - fix checkbox
            item = QtWidgets.QTableWidgetItem()
            item.setFlags(QtCore.Qt.ItemIsUserCheckable |
                          QtCore.Qt.ItemIsEnabled)
            if self.model.current_section.baseline_in_queue[row]['vary']:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            self.widget.tableWidget_BackgroundConstraints.setItem(row, 1, item)
            self.widget.tableWidget_BackgroundConstraints.itemClicked.connect(
                self._bglist_handle_ItemClicked)
        self.widget.tableWidget_BackgroundConstraints.resizeColumnsToContents()
        self.widget.tableWidget_BackgroundConstraints.resizeRowsToContents()

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
        index = self.widget.tableWidget_BackgroundConstraints.\
            indexAt(box.pos())
        if not index.isValid():
            return
        self.model.current_section.invalidate_fit_result()
        row = index.row()
        col = index.column()
        if col == 0:
            self.model.current_section.baseline_in_queue[row]['value'] = \
                value

    def update_peak_constraints(self):
        '''show a list of peaks in the list window of tab 3 for config'''
        if not self.model.current_section_exist():
            return
        self.widget.tableWidget_PeakConstraints.clearContents()
        n_columns = 8
        n_rows = self.model.current_section.get_number_of_peaks_in_queue()
        self.widget.tableWidget_PeakConstraints.setColumnCount(n_columns)
        self.widget.tableWidget_PeakConstraints.setRowCount(n_rows)
        self.widget.tableWidget_PeakConstraints.horizontalHeader().setVisible(
            True)
        self.widget.tableWidget_PeakConstraints.setHorizontalHeaderLabels(
            ['Ampl', 'Vary', 'Center', 'Vary', 'FHWM', 'Vary', 'n_L', 'Vary'])
        for row in range(n_rows):
            # column 0 - height
            self.PkConst_doubleSpinBox_height = QtWidgets.QDoubleSpinBox()
            self.PkConst_doubleSpinBox_height.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.PkConst_doubleSpinBox_height.setMaximum(100000.)
            self.PkConst_doubleSpinBox_height.setSingleStep(10.)
            self.PkConst_doubleSpinBox_height.setDecimals(0)
            self.PkConst_doubleSpinBox_height.setValue(
                self.model.current_section.peaks_in_queue[row]['amplitude'])
            self.PkConst_doubleSpinBox_height.valueChanged.connect(
                self._peaklist_handle_doubleSpinBoxChanged)
            self.PkConst_doubleSpinBox_height.setKeyboardTracking(False)
            self.widget.tableWidget_PeakConstraints.setCellWidget(
                row, 0, self.PkConst_doubleSpinBox_height)
            # column 1 - fix checkbox
            item_h = QtWidgets.QTableWidgetItem()
            item_h.setFlags(QtCore.Qt.ItemIsUserCheckable |
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
            item_p.setFlags(QtCore.Qt.ItemIsUserCheckable |
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
            item_w.setFlags(QtCore.Qt.ItemIsUserCheckable |
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
            item_nL.setFlags(QtCore.Qt.ItemIsUserCheckable |
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

    def _peaklist_handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
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
