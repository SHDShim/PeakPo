from PyQt5 import QtCore
from PyQt5 import QtWidgets
# from .mplcontroller import MplController


class PeakfitTableController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget

    def update_pkparams(self):
        '''
        show a list of peaks in the list window of tab 2
        '''
        if not self.model.current_section_exist():
            return
        if not self.model.current_section.fitted():
            return
        self.widget.tableWidget_PkParams.clearContents()
        n_columns = 8
        n_rows = self.model.current_section.get_number_of_peaks_in_queue()
        self.widget.tableWidget_PkParams.setColumnCount(n_columns)
        self.widget.tableWidget_PkParams.setRowCount(n_rows)
        self.widget.tableWidget_PkParams.horizontalHeader().setVisible(True)
        self.widget.tableWidget_PkParams.setHorizontalHeaderLabels(
            ['Phase', 'h', 'k', 'l', 'Area', 'Pos', 'FWHM', 'nL'])
        params = self.model.current_section.get_fit_result()
        peakinfo = self.model.current_section.peakinfo
        for row in range(n_rows):
            prefix = "p{0:d}_".format(row)
            # symmetric peaks
            Item = QtWidgets.QTableWidgetItem(peakinfo[prefix + 'phasename'])
            self.widget.tableWidget_PkParams.setItem(row, 0, Item)
            Item = QtWidgets.QTableWidgetItem(peakinfo[prefix + 'h'])
            self.widget.tableWidget_PkParams.setItem(row, 1, Item)
            Item = QtWidgets.QTableWidgetItem(peakinfo[prefix + 'k'])
            self.widget.tableWidget_PkParams.setItem(row, 2, Item)
            Item = QtWidgets.QTableWidgetItem(peakinfo[prefix + 'l'])
            self.widget.tableWidget_PkParams.setItem(row, 3, Item)
            amp = "{:.5e}".format(params[prefix + 'amplitude'].value)
            Item = QtWidgets.QTableWidgetItem(amp)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 4, Item)
            center = "{:.5e}".format(params[prefix + 'center'].value)
            Item = QtWidgets.QTableWidgetItem(center)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 5, Item)
            sigma = "{:.5e}".format(params[prefix + 'sigma'].value)
            Item = QtWidgets.QTableWidgetItem(sigma)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 6, Item)
            fraction = "{:.5e}".format(params[prefix + 'fraction'].value)
            Item = QtWidgets.QTableWidgetItem(fraction)
            Item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_PkParams.setItem(row, 7, Item)
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
        prefix = "p{0:d}_".format(row)
        if col == 0:
            self.model.current_section.peakinfo[prefix + 'phasename'] =\
                self.widget.tableWidget_PkParams.currentItem().text()
        if col == 1:
            self.model.current_section.peakinfo[prefix + 'h'] =\
                int(self.widget.tableWidget_PkParams.currentItem().text())
        if col == 2:
            self.model.current_section.peakinfo[prefix + 'k'] =\
                int(self.widget.tableWidget_PkParams.currentItem().text())
        if col == 3:
            self.model.current_section.peakinfo[prefix + 'l'] =\
                int(self.widget.tableWidget_PkParams.currentItem().text())

    def update_sections(self):
        '''show a list of sections'''
        n_columns = 3
        n_rows = self.model.get_number_of_section()  # count for number of jcpds
        if n_rows == 0:
            return
        self.widget.tableWidget_PkFtSections.setColumnCount(n_columns)
        self.widget.tableWidget_PkFtSections.setRowCount(n_rows)
        self.widget.tableWidget_PkFtSections.horizontalHeader().setVisible(True)
        self.widget.tableWidget_PkFtSections.setHorizontalHeaderLabels(
            ['Time', 'xmin', 'xmax'])
        i = 0
        for section in self.model.section_lst:
            '''
            # column 0 - checkbox
            item0 = QtGui.QTableWidgetItem()
            item0.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            item0.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_SectionsCurrent.setItem(row, 0, item0)
            '''
            # column 1 - time
            item1 = QtWidgets.QTableWidgetItem(section.get_timestamp())
            item1.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 0, item1)
            # column 2 - Xmin
            item2 = QtWidgets.QTableWidgetItem("{:.2f}".format(section.x[0]))
            item2.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 1, item2)
            # column 3 - Xmax
            item3 = QtWidgets.QTableWidgetItem("{:.2f}".format(section.x[-1]))
            item3.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_PkFtSections.setItem(i, 2, item3)
            i += 1
        self.widget.tableWidget_PkFtSections.resizeColumnsToContents()
        self.widget.tableWidget_PkFtSections.resizeRowsToContents()

    """
    def _peaklist_handle_ItemClicked(self, item):
        if (item.column() == 1) or (item.column() == 3) or \
            (item.column() == 5) or (item.column() == 7) or\
                (item.column() == 9) or (item.column() == 11):
            self.currentSection.fittime = ''
            row = item.row()
            col = item.column()
            if item.checkState() == QtCore.Qt.Checked:
                if (self.currentSection.fitmodel.peaks[row].coeffs.__len__() == 4):
                    if col <= 5:
                        self.currentSection.fitmodel.peaks[row].constraints[(col - 1) / 2] = 1
                    elif col == 9:
                        self.currentSection.fitmodel.peaks[row].constraints[3] = 1
                else:
                    self.currentSection.fitmodel.peaks[row].constraints[(col - 1) / 2] = 1
            elif item.checkState() == QtCore.Qt.Unchecked:
                if (self.currentSection.fitmodel.peaks[row].coeffs.__len__() == 4):
                    if col <= 5:
                        self.currentSection.fitmodel.peaks[row].constraints[(col - 1) / 2] = 0
                    elif col == 9:
                        self.currentSection.fitmodel.peaks[row].constraints[3] = 0
                else:
                    self.currentSection.fitmodel.peaks[row].constraints[(col - 1) / 2] = 0
        else:
            return
#        for i in range(self.currentSection.fitmodel.peaks.__len__()):
#            print self.currentSection.fitmodel.peaks[i].coeffs, self.currentSection.fitmodel.peaks[i].constraints

    def _peaklist_handle_doubleSpinBoxChanged(self, value):
        box = self.sender()
        index = self.tableWidget_Peaks.indexAt(box.pos())
        if index.isValid():
            self.currentSection.fittime = ''
            row = index.row()
            col = index.column()
            if (self.currentSection.fitmodel.peaks[row].coeffs.__len__() == 4):
                if col <= 4:
                    self.currentSection.fitmodel.peaks[row].coeffs[col / 2] = value
                elif col == 8:
                    self.currentSection.fitmodel.peaks[row].coeffs[3] = value
            else:
                self.currentSection.fitmodel.peaks[row].coeffs[col / 2] = value
            self.update_graph()
        else:
            return
"""
