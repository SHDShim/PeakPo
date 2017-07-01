from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from mplcontroller import MplController
from utils import extract_filename
from utils import SpinBoxFixStyle


class WaterfallController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        # Tab: waterfall
        self.widget.pushButton_AddPatterns.clicked.connect(self.add_patterns)
        self.widget.doubleSpinBox_WaterfallGaps.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.pushButton_CleanPatterns.clicked.connect(
            self.erase_waterfall)
        self.widget.pushButton_RemovePatterns.clicked.connect(
            self.remove_waterfall)
        self.widget.pushButton_UpPattern.clicked.connect(
            self.move_up_waterfall)
        self.widget.pushButton_DownPattern.clicked.connect(
            self.move_down_waterfall)
        self.widget.pushButton_ApplyWaterfallChange.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_IntNorm.clicked.connect(
            self.apply_changes_to_graph)

    def apply_changes_to_graph(self, reinforced=False):
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

    def _find_a_waterfall_ptn(self):
        idx_checked = [
            s.row() for s in
            self.widget.tableWidget_wfPatterns.selectionModel().selectedRows()]
        if idx_checked == []:
            return None
        else:
            return idx_checked[0]

    def add_patterns(self):
        """
        get files for waterfall plot
        """
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Pick a base pattern first.")
            return
        files = QtWidgets.QFileDialog.getOpenFileNames(
            self.widget, "Choose additional data files", self.model.chi_path,
            "Data files (*.chi)")[0]
        if files is None:
            return
        for f in files:
            filename = str(f)
            wavelength = self.widget.doubleSpinBox_SetWavelength.value()
            bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                      self.widget.doubleSpinBox_Background_ROI_max.value()]
            bg_params = [self.widget.spinBox_BGParam0.value(),
                         self.widget.spinBox_BGParam1.value(),
                         self.widget.spinBox_BGParam2.value()]
            self.model.append_a_waterfall_ptn(
                filename, wavelength, bg_roi, bg_params)
        self.update_table()
        self.apply_changes_to_graph()

    def update_table(self):
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
        # self.apply_changes_to_graph(reinforced=True)

    def _handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_wfPatterns.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            self.model.waterfall_ptn[idx].wavelength = value
            self.apply_changes_to_graph()

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
                    self.apply_changes_to_graph()

    def _handle_ItemClicked(self, item):
        if item.column() != 0:
            return
        idx = item.row()
        box_checked = (item.checkState() == QtCore.Qt.Checked)
        if box_checked == self.model.waterfall_ptn[idx].display:
            return
        else:
            self.model.waterfall_ptn[idx].display = box_checked
        self.apply_changes_to_graph(reinforced=True)

    def move_up_waterfall(self):
        # get selected cell number
        idx_selected = self._find_a_waterfall_ptn()
        if idx_selected is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Highlight the item to move first.")
            return
        i = idx_selected
        self.model.waterfall_ptn[i - 1], self.model.waterfall_ptn[i] = \
            self.model.waterfall_ptn[i], self.model.waterfall_ptn[i - 1]
        self.widget.tableWidget_wfPatterns.selectRow(i - 1)
        self.update_table()
        self.apply_changes_to_graph()

    def move_down_waterfall(self):
        idx_selected = self._find_a_waterfall_ptn()
        if idx_selected is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Highlight the item to move first.")
            return
        i = idx_selected
        self.model.waterfall_ptn[i + 1], self.model.waterfall_ptn[i] = \
            self.model.waterfall_ptn[i], self.model.waterfall_ptn[i + 1]
        self.widget.tableWidget_wfPatterns.selectRow(i + 1)
        self.update_table()
        self.apply_changes_to_graph()

    def erase_waterfall(self):
        self.model.reset_waterfall_ptn()
        self.widget.tableWidget_wfPatterns.clearContents()
        self.apply_changes_to_graph()

    def remove_waterfall(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Are you sure you want to remove the highlighted pattern?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        # print self.widget.tableWidget_JCPDS.selectedIndexes().__len__()
        idx_checked = [
            s.row() for s in
            self.widget.tableWidget_wfPatterns.selectionModel().selectedRows()]
        if idx_checked == []:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')
            return
        else:
            idx_checked.reverse()
            for idx in idx_checked:
                self.model.waterfall_ptn.remove(self.model.waterfall_ptn[idx])
                self.widget.tableWidget_wfPatterns.removeRow(idx)
#        self._list_jcpds()
            self.apply_changes_to_graph()
