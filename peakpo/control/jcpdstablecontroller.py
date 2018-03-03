from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from utils import SpinBoxFixStyle
from .mplcontroller import MplController


class JcpdsTableController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)

    def _apply_changes_to_graph(self, limits=None):
        self.plot_ctrl.update(limits=limits)

    def update(self, step=0.001):
        """
        show jcpds cards in the QTableWidget
        """
        n_columns = 10
        n_rows = self.model.jcpds_lst.__len__()  # count for number of jcpds
        self.widget.tableWidget_JCPDS.setColumnCount(n_columns)
        self.widget.tableWidget_JCPDS.setRowCount(n_rows)
        self.widget.tableWidget_JCPDS.horizontalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.verticalHeader().setVisible(True)
        # move b/a and c/a from 7 and 8 to 4 and 5
        self.widget.tableWidget_JCPDS.setHorizontalHeaderLabels(
            ['',  # 0
             ' ',  # 1
             ' ',  # 2
             'V0 twk',  # 3
             'b/a twk',  # 4
             'c/a twk',  # 5
             'K0 twk',  # 6
             'K0p twk',  # 7
             'alpha0 twk',  # 8
             'Int twk'])  # 9
        self.widget.tableWidget_JCPDS.setVerticalHeaderLabels(
            [phase.name for phase in self.model.jcpds_lst])
        for row in range(n_rows):
            # column 0 - checkbox
            item0 = QtWidgets.QTableWidgetItem()
            item0.setFlags(QtCore.Qt.ItemIsUserCheckable |
                           QtCore.Qt.ItemIsEnabled)
            if self.model.jcpds_lst[row].display:
                item0.setCheckState(QtCore.Qt.Checked)
            else:
                item0.setCheckState(QtCore.Qt.Unchecked)
            self.widget.tableWidget_JCPDS.setItem(row, 0, item0)
            # column 1 - color
            item2 = QtWidgets.QTableWidgetItem('')
            self.widget.tableWidget_JCPDS.setItem(row, 1, item2)
            # column 2 - color setup
            self.widget.tableWidget_JCPDS_pushButton_color = \
                QtWidgets.QPushButton('.')
            self.widget.tableWidget_JCPDS.item(row, 1).setBackground(
                QtGui.QColor(self.model.jcpds_lst[row].color))
            self.widget.tableWidget_JCPDS_pushButton_color.clicked.connect(
                self._handle_ColorButtonClicked)
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 2, self.widget.tableWidget_JCPDS_pushButton_color)
            # column 3 - V0 tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk = QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setMaximum(2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setSingleStep(
                step)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setDecimals(3)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setProperty(
                "value", self.model.jcpds_lst[row].twk_v0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 3, self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            # column 4 - b/a tweak
            if (self.model.jcpds_lst[row].symmetry == 'cubic') or \
                    (self.model.jcpds_lst[row].symmetry == 'tetragonal') or \
                    (self.model.jcpds_lst[row].symmetry == 'hexagonal'):
                item_b_a = QtWidgets.QTableWidgetItem('')
                item_b_a.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 5, item_b_a)
            else:
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                        QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.setMaximum(
                    2.0)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setSingleStep(step)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.setDecimals(
                    3)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.setProperty(
                    "value", self.model.jcpds_lst[row].twk_b_a)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    valueChanged.connect(
                        self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, 4, self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 5 - c/a tweak
            if (self.model.jcpds_lst[row].symmetry == 'cubic'):
                # I do not understand why this is the case, item9 is apparently
                # intensity tweak nothing to do with symmetry.
                item9 = QtWidgets.QTableWidgetItem('')
                item9.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 9, item9)
            else:
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                        QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.setMaximum(
                    2.0)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setSingleStep(step)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.setDecimals(
                    3)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.setProperty(
                    "value", self.model.jcpds_lst[row].twk_c_a)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    valueChanged.connect(
                        self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, 5, self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 6 - K0 tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setMaximum(2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setSingleStep(
                step)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setDecimals(2)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setProperty(
                "value", self.model.jcpds_lst[row].twk_k0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 6, self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            # column 7 - K0p tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setMaximum(2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setSingleStep(
                step)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setDecimals(2)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setProperty(
                "value", self.model.jcpds_lst[row].twk_k0p)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 7, self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            # column 8 - alpha0 tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setMaximum(
                2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                setSingleStep(step)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setDecimals(
                2)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setProperty(
                "value", self.model.jcpds_lst[row].twk_thermal_expansion)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                valueChanged.connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                setFocusPolicy(QtCore.Qt.StrongFocus)
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 8, self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk)
            # column 9 - int tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setMaximum(1.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setSingleStep(
                step)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setDecimals(2)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setProperty(
                "value", self.model.jcpds_lst[row].twk_int)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 9, self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                setKeyboardTracking(False)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.\
                setKeyboardTracking(False)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.\
                setKeyboardTracking(False)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.\
                setKeyboardTracking(False)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.\
                setKeyboardTracking(False)
        self.widget.tableWidget_JCPDS.resizeColumnsToContents()
#        self.widget.tableWidget_JCPDS.resizeRowsToContents()
        self.widget.tableWidget_JCPDS.itemClicked.connect(
            self._handle_ItemClicked)

    def _handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_JCPDS.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 3:
                self.model.jcpds_lst[idx].twk_v0 = value
            elif index.column() == 6:
                self.model.jcpds_lst[idx].twk_k0 = value
            elif index.column() == 7:
                self.model.jcpds_lst[idx].twk_k0p = value
            elif index.column() == 8:
                self.model.jcpds_lst[idx].twk_thermal_expansion = value
            elif index.column() == 4:
                self.model.jcpds_lst[idx].twk_b_a = value
            elif index.column() == 5:
                self.model.jcpds_lst[idx].twk_c_a = value
            elif index.column() == 9:
                self.model.jcpds_lst[idx].twk_int = value
            if self.model.jcpds_lst[idx].display:
                self._apply_changes_to_graph()

    def _handle_ColorButtonClicked(self):
        button = self.widget.sender()
        index = self.widget.tableWidget_JCPDS.indexAt(button.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 2:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    self.widget.tableWidget_JCPDS.item(idx, 1).\
                        setBackground(color)
                    self.model.jcpds_lst[idx].color = str(color.name())
                    self._apply_changes_to_graph()

    def _handle_ItemClicked(self, item):
        if item.column() == 0:
            idx = item.row()
            if (item.checkState() == QtCore.Qt.Checked) ==\
                    self.model.jcpds_lst[idx].display:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.model.jcpds_lst[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.jcpds_lst[idx].display = False
            self._apply_changes_to_graph()
        else:
            return

    def update_steps_only(self, step):
        """
        show jcpds cards in the QTableWidget
        """
        self.widget.tableWidget_JCPDS.clear()
        self.update(step=step)
