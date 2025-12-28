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
        # ✅ UPDATED: Reduced from 10 to 9 columns (merged color columns)
        n_columns = 9
        n_rows = self.model.jcpds_lst.__len__()
        self.widget.tableWidget_JCPDS.setColumnCount(n_columns)
        self.widget.tableWidget_JCPDS.setRowCount(n_rows)
        self.widget.tableWidget_JCPDS.horizontalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.verticalHeader().setVisible(True)
        # ✅ UPDATED: Removed one color column
        self.widget.tableWidget_JCPDS.setHorizontalHeaderLabels(
            ['',  # 0 - checkbox
             '',  # 1 - color (merged, clickable)
             'V0 twk',  # 2
             'b/a twk',  # 3
             'c/a twk',  # 4
             'Int twk',  # 5
             'K0 twk',  # 6
             'K0p twk',  # 7
             'alpha0 twk'])  # 8
        self.widget.tableWidget_JCPDS.setVerticalHeaderLabels(
            [phase.name for phase in self.model.jcpds_lst])
        
        # ✅ Set narrow width for color column
        self.widget.tableWidget_JCPDS.setColumnWidth(0, 30)  # Checkbox
        self.widget.tableWidget_JCPDS.setColumnWidth(1, 35)  # Color (narrow!)
        
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
            
            # ✅ column 1 - color (merged: shows color AND is clickable)
            item_color = QtWidgets.QTableWidgetItem('')
            item_color.setBackground(QtGui.QColor(self.model.jcpds_lst[row].color))
            # Make it selectable so clicks are detected
            item_color.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_JCPDS.setItem(row, 1, item_color)
            
            # column 2 - V0 tweak
            if (self.model.jcpds_lst[row].symmetry == 'nosymmetry'):
                item_v0 = QtWidgets.QTableWidgetItem(' ')
                item_v0.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 2, item_v0)
            else:
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk = \
                    QtWidgets.QDoubleSpinBox()
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
                    row, 2, self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setFocusPolicy(
                    QtCore.Qt.StrongFocus)
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.\
                    setKeyboardTracking(False)
            
            # column 3 - b/a tweak
            if (self.model.jcpds_lst[row].symmetry == 'cubic') or \
                    (self.model.jcpds_lst[row].symmetry == 'tetragonal') or \
                    (self.model.jcpds_lst[row].symmetry == 'hexagonal') or \
                    (self.model.jcpds_lst[row].symmetry == 'nosymmetry'):
                item_b_a = QtWidgets.QTableWidgetItem(' ')
                item_b_a.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 3, item_b_a)
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
                    row, 3, self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            
            # column 4 - c/a tweak
            if (self.model.jcpds_lst[row].symmetry == 'cubic') or \
                    (self.model.jcpds_lst[row].symmetry == 'nosymmetry'):
                item_c_a = QtWidgets.QTableWidgetItem(' ')
                item_c_a.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 4, item_c_a)
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
                    row, 4, self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            
            # column 5 - Int tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setMaximum(1.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setSingleStep(
                step)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setDecimals(3)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setProperty(
                "value", self.model.jcpds_lst[row].twk_int)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 5, self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.\
                setKeyboardTracking(False)
            
            # column 6 - K0 tweak
            if (self.model.jcpds_lst[row].symmetry == 'nosymmetry'):
                item_k0 = QtWidgets.QTableWidgetItem(' ')
                item_k0.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 6, item_k0)
            else:
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                    QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setMaximum(
                    2.0)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setSingleStep(
                    step)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setDecimals(3)
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
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.\
                    setKeyboardTracking(False)
            
            # column 7 - K0p tweak
            if (self.model.jcpds_lst[row].symmetry == 'nosymmetry'):
                item_k0p = QtWidgets.QTableWidgetItem(' ')
                item_k0p.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 7, item_k0p)
            else:
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk = \
                    QtWidgets.QDoubleSpinBox()
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                    QtCore.Qt.AlignVCenter)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setMaximum(2.0)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setSingleStep(
                    step)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setDecimals(3)
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
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.\
                    setKeyboardTracking(False)
            
            # column 8 - alpha0 tweak
            if (self.model.jcpds_lst[row].symmetry == 'nosymmetry'):
                item_alpha0 = QtWidgets.QTableWidgetItem(' ')
                item_alpha0.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 8, item_alpha0)
            else:
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
                    3)
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
                self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                    setKeyboardTracking(False)
        
        self.widget.tableWidget_JCPDS.resizeColumnsToContents()
        self.widget.tableWidget_JCPDS.itemClicked.connect(
            self._handle_ItemClicked)

    def _handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_JCPDS.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            # ✅ UPDATED: All column indices shifted by -1
            if index.column() == 2:  # V0 twk (was 3)
                self.model.jcpds_lst[idx].twk_v0 = value
            elif index.column() == 3:  # b/a twk (was 4)
                self.model.jcpds_lst[idx].twk_b_a = value
            elif index.column() == 4:  # c/a twk (was 5)
                self.model.jcpds_lst[idx].twk_c_a = value
            elif index.column() == 5:  # Int twk (was 6)
                self.model.jcpds_lst[idx].twk_int = value
            elif index.column() == 6:  # K0 twk (was 7)
                self.model.jcpds_lst[idx].twk_k0 = value
            elif index.column() == 7:  # K0p twk (was 8)
                self.model.jcpds_lst[idx].twk_k0p = value
            elif index.column() == 8:  # alpha0 twk (was 9)
                self.model.jcpds_lst[idx].twk_thermal_expansion = value
            
            if self.model.jcpds_lst[idx].display:
                self._apply_changes_to_graph()

    def _handle_ItemClicked(self, item):
        idx = item.row()
        
        # ✅ Handle checkbox clicks (column 0)
        if item.column() == 0:
            if (item.checkState() == QtCore.Qt.Checked) ==\
                    self.model.jcpds_lst[idx].display:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.model.jcpds_lst[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.jcpds_lst[idx].display = False
            self._apply_changes_to_graph()
        
        # ✅ NEW: Handle color clicks (column 1)
        elif item.column() == 1:
            color = QtWidgets.QColorDialog.getColor(
                QtGui.QColor(self.model.jcpds_lst[idx].color))
            if color.isValid():
                item.setBackground(color)
                self.model.jcpds_lst[idx].color = str(color.name())
                self._apply_changes_to_graph()

    def update_steps_only(self, step):
        """
        show jcpds cards in the QTableWidget
        """
        self.widget.tableWidget_JCPDS.clear()
        self.update(step=step)