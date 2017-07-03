from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from .mplcontroller import MplController
from utils import SpinBoxFixStyle
from utils import xls_ucfitlist, dialog_savefile


class UcfitTableController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def update(self):
        """
        Show ucfit in the QTableWidget
        """
        n_columns = 10
        n_rows = self.model.ucfit_lst.__len__()  # count for number of jcpds
        self.widget.tableWidget_UnitCell.setColumnCount(n_columns)
        self.widget.tableWidget_UnitCell.setRowCount(n_rows)
        self.widget.tableWidget_UnitCell.horizontalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.verticalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.setHorizontalHeaderLabels(
            ['', 'Color', '  ', 'Volume', 'a', 'b', 'c',
             'alpha', 'beta', 'gamma'])
        self.widget.tableWidget_UnitCell.setVerticalHeaderLabels(
            [s.name for s in self.model.ucfit_lst])
        for row in range(n_rows):
            # column 0 - checkbox
            item0 = QtWidgets.QTableWidgetItem()
            item0.setFlags(
                QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            if self.model.ucfit_lst[row].display:
                item0.setCheckState(QtCore.Qt.Checked)
            else:
                item0.setCheckState(QtCore.Qt.Unchecked)
            self.widget.tableWidget_UnitCell.setItem(row, 0, item0)
            # column 1 - color
            item2 = QtWidgets.QTableWidgetItem('    ')
            self.widget.tableWidget_UnitCell.setItem(row, 1, item2)
            # column 2 - color setup
            self.widget.tableWidget_UnitCell_pushButton_color = \
                QtWidgets.QPushButton('...')
            self.widget.tableWidget_UnitCell.item(row, 1).setBackground(
                QtGui.QColor(self.model.ucfit_lst[row].color))
            self.widget.tableWidget_UnitCell_pushButton_color.clicked.connect(
                self._handle_ColorButtonClicked)
            self.widget.tableWidget_UnitCell.setCellWidget(
                row, 2, self.widget.tableWidget_UnitCell_pushButton_color)
            # column 3 - V output
            self.model.ucfit_lst[row].cal_dsp()
            Item4 = QtWidgets.QTableWidgetItem(
                "{:.3f}".format(float(self.model.ucfit_lst[row].v)))
            Item4.setFlags(QtCore.Qt.ItemIsSelectable |
                           QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_UnitCell.setItem(row, 3, Item4)
            # column 4 - a
            self.widget.tableWidget_UnitCell_doubleSpinBox_a = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setMaximum(50.0)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setSingleStep(
                0.001)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setDecimals(4)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setProperty(
                "value", float(self.model.ucfit_lst[row].a))
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_UnitCell.setCellWidget(
                row, 4, self.widget.tableWidget_UnitCell_doubleSpinBox_a)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.\
                setKeyboardTracking(False)
            self.widget.tableWidget_UnitCell_doubleSpinBox_a.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            # column 5 - b output
            if (self.model.ucfit_lst[row].symmetry == 'cubic') or\
                    (self.model.ucfit_lst[row].symmetry == 'tetragonal') or\
                    (self.model.ucfit_lst[row].symmetry == 'hexagonal'):
                item6 = QtWidgets.QTableWidgetItem('')
                item6.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(row, 5, item6)
            else:
                self.widget.tableWidget_UnitCell_doubleSpinBox_b = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                    QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.setMaximum(
                    50.0)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.setSingleStep(
                    0.001)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.setDecimals(4)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.setProperty(
                    "value", float(self.model.ucfit_lst[row].b))
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.valueChanged.\
                    connect(
                        self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_UnitCell.setCellWidget(
                    row, 5, self.widget.tableWidget_UnitCell_doubleSpinBox_b)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_UnitCell_doubleSpinBox_b.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 6 - c output
            if (self.model.ucfit_lst[row].symmetry == 'cubic'):
                item7 = QtWidgets.QTableWidgetItem('')
                item7.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(row, 6, item7)
            else:
                self.widget.tableWidget_UnitCell_doubleSpinBox_c = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                    QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.setMaximum(
                    50.0)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.setSingleStep(
                    0.001)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.setDecimals(4)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.setProperty(
                    "value", float(self.model.ucfit_lst[row].c))
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.valueChanged.\
                    connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_UnitCell.setCellWidget(
                    row, 6, self.widget.tableWidget_UnitCell_doubleSpinBox_c)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_UnitCell_doubleSpinBox_c.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 7 - alpha output
            if not (self.model.ucfit_lst[row].symmetry == 'triclinic'):
                item8 = QtWidgets.QTableWidgetItem('90.')
                item8.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(row, 7, item8)
            else:
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                        QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setMaximum(179.0)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setSingleStep(0.1)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setDecimals(1)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setProperty("value",
                                float(self.model.ucfit_lst[row].alpha))
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    valueChanged.\
                    connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_UnitCell.setCellWidget(
                    row, 7,
                    self.widget.tableWidget_UnitCell_doubleSpinBox_alpha)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_UnitCell_doubleSpinBox_alpha.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 8 - beta output
            if (self.model.ucfit_lst[row].symmetry == 'cubic') or \
                    (self.model.ucfit_lst[row].symmetry == 'tetragonal') or\
                    (self.model.ucfit_lst[row].symmetry == 'hexagonal') or\
                    (self.model.ucfit_lst[row].symmetry == 'orthorhombic'):
                item9 = QtWidgets.QTableWidgetItem('90.')
                item9.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(row, 8, item9)
            else:
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    setAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                        QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.setMaximum(
                    179.0)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    setSingleStep(0.1)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    setDecimals(1)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    setProperty("value", float(self.model.ucfit_lst[row].beta))
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    valueChanged.\
                    connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_UnitCell.setCellWidget(
                    row, 8,
                    self.widget.tableWidget_UnitCell_doubleSpinBox_beta)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_UnitCell_doubleSpinBox_beta.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 9 - gamma output
            if not (self.model.ucfit_lst[row].symmetry == 'triclinic'):
                if self.model.ucfit_lst[row].symmetry == 'hexagonal':
                    item10 = QtWidgets.QTableWidgetItem('120.')
                else:
                    item10 = QtWidgets.QTableWidgetItem('90.')
                item10.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(row, 9, item10)
            else:
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                        QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setMaximum(179.0)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setSingleStep(0.1)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setDecimals(1)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setProperty("value",
                                float(self.model.ucfit_lst[row].gamma))
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    valueChanged.connect(
                        self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_UnitCell.setCellWidget(
                    row, 9,
                    self.widget.tableWidget_UnitCell_doubleSpinBox_gamma)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_UnitCell_doubleSpinBox_gamma.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
        self.widget.tableWidget_UnitCell.resizeColumnsToContents()
#        self.widget.tableWidget_UnitCell.resizeRowsToContents()
        self.widget.tableWidget_UnitCell.itemClicked.connect(
            self._handle_ItemClicked)

    def _handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_UnitCell.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 4:
                self.model.ucfit_lst[idx].a = value
                if self.model.ucfit_lst[idx].symmetry == 'cubic':
                    self.model.ucfit_lst[idx].b = value
                    self.model.ucfit_lst[idx].c = value
                elif (self.model.ucfit_lst[idx].symmetry == 'tetragonal') or \
                        (self.model.ucfit_lst[idx].symmetry == 'hexagonal'):
                    self.model.ucfit_lst[idx].b = value
                else:
                    pass
            elif index.column() == 5:
                self.model.ucfit_lst[idx].b = value
            elif index.column() == 6:
                self.model.ucfit_lst[idx].c = value
            elif index.column() == 7:
                self.model.ucfit_lst[idx].alpha = value
            elif index.column() == 8:
                self.model.ucfit_lst[idx].beta = value
            elif index.column() == 9:
                self.model.ucfit_lst[idx].gamma = value
            if self.model.ucfit_lst[idx].display:
                self._apply_changes_to_graph()

    def _handle_ColorButtonClicked(self):
        button = self.widget.sender()
        index = self.widget.tableWidget_UnitCell.indexAt(button.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 2:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    self.widget.tableWidget_UnitCell.item(idx, 1).\
                        setBackground(color)
                    self.model.ucfit_lst[idx].color = str(color.name())
                    self._apply_changes_to_graph()

    def _handle_ItemClicked(self, item):
        if item.column() == 0:
            idx = item.row()
            if (item.checkState() == QtCore.Qt.Checked) == \
                    self.model.ucfit_lst[idx].display:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.model.ucfit_lst[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.ucfit_lst[idx].display = False
            self._apply_changes_to_graph()
