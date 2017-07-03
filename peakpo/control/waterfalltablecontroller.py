import os
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from utils import SpinBoxFixStyle
from .mplcontroller import MplController


class WaterfallTableController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)

    def _apply_changes_to_graph(self, reinforced=False):
        """
        this does not do actual nomalization but the processing.
        actual normalization takes place in plotting.
        """
        if reinforced:
            pass
        else:
            if not self.model.waterfall_exist():
                return
            count = 0
            for ptn in self.model.waterfall_ptn:
                if ptn.display:
                    count += 1
            if count == 0:
                return
        self.plot_ctrl.update()

    def update(self):
        """
        show a list of jcpds in the list window of tab 3
        called from maincontroller
        """
        n_columns = 4
        n_rows = self.model.waterfall_ptn.__len__()  # count for number of jcpds
        self.widget.tableWidget_wfPatterns.setColumnCount(n_columns)
        self.widget.tableWidget_wfPatterns.setRowCount(n_rows)
        self.widget.tableWidget_wfPatterns.horizontalHeader().setVisible(True)
        self.widget.tableWidget_wfPatterns.setHorizontalHeaderLabels(
            ['', 'Color', ' ', 'Wavelength'])
        self.widget.tableWidget_wfPatterns.setVerticalHeaderLabels(
            [extract_filename(wfp.fname) for wfp in self.model.waterfall_ptn])
        for row in range(n_rows):
            # column 0 - checkbox
            item0 = QtWidgets.QTableWidgetItem()
            item0.setFlags(QtCore.Qt.ItemIsUserCheckable |
                           QtCore.Qt.ItemIsEnabled)
            if self.model.waterfall_ptn[row].display:
                item0.setCheckState(QtCore.Qt.Checked)
            else:
                item0.setCheckState(QtCore.Qt.Unchecked)
            self.widget.tableWidget_wfPatterns.setItem(row, 0, item0)
            # column 1 - color
            item2 = QtWidgets.QTableWidgetItem('    ')
            self.widget.tableWidget_wfPatterns.setItem(row, 1, item2)
            # column 3 - color setup
            self.widget.tableWidget_wfPatterns_pushButton_color = \
                QtWidgets.QPushButton('...')
            self.widget.tableWidget_wfPatterns.item(row, 1).setBackground(
                QtGui.QColor(self.model.waterfall_ptn[row].color))
            self.widget.tableWidget_wfPatterns_pushButton_color.clicked.\
                connect(self._handle_ColorButtonClicked)
            self.widget.tableWidget_wfPatterns.setCellWidget(
                row, 2,
                self.widget.tableWidget_wfPatterns_pushButton_color)
            # column 3 - wavelength
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                    QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setMaximum(2.0)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setSingleStep(0.0001)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setDecimals(4)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setProperty("value", self.model.waterfall_ptn[row].wavelength)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                valueChanged.connect(
                    self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setStyle(SpinBoxFixStyle())
            self.widget.tableWidget_wfPatterns.setCellWidget(
                row, 3,
                self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setKeyboardTracking(False)
            self.widget.tableWidget_wfPatterns_doubleSpinBox_wavelength.\
                setFocusPolicy(QtCore.Qt.StrongFocus)
        self.widget.tableWidget_wfPatterns.resizeColumnsToContents()
#        self.widget.tableWidget_wfPatterns.resizeRowsToContents()
        self.widget.tableWidget_wfPatterns.itemClicked.connect(
            self._handle_ItemClicked)
        # self._apply_changes_to_graph(reinforced=True)

    def _handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_wfPatterns.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            self.model.waterfall_ptn[idx].wavelength = value
            self._apply_changes_to_graph()

    def _handle_ColorButtonClicked(self):
        button = self.widget.sender()
        index = self.widget.tableWidget_wfPatterns.indexAt(button.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 2:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    self.widget.tableWidget_wfPatterns.item(idx, 1).\
                        setBackground(color)
                    self.model.waterfall_ptn[idx].color = str(color.name())
                    self._apply_changes_to_graph()

    def _handle_ItemClicked(self, item):
        if item.column() != 0:
            return
        idx = item.row()
        box_checked = (item.checkState() == QtCore.Qt.Checked)
        if box_checked == self.model.waterfall_ptn[idx].display:
            return
        else:
            self.model.waterfall_ptn[idx].display = box_checked
        self._apply_changes_to_graph(reinforced=True)
