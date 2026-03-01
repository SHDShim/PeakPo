from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from ..utils import SpinBoxFixStyle
from .mplcontroller import MplController


class JcpdsTableController(object):
    COL_SHOW = 0
    COL_LOCK = 1
    COL_COLOR = 2
    COL_V0 = 3
    COL_BA = 4
    COL_CA = 5
    COL_INT = 6
    COL_K0 = 7
    COL_K0P = 8
    COL_ALPHA = 9

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)

    def _apply_changes_to_graph(self, limits=None):
        self.plot_ctrl.update(limits=limits)

    def sync_model_from_table(self):
        """
        Commit any in-progress table spinbox edits to model values before save.
        """
        table = self.widget.tableWidget_JCPDS
        n_rows = min(table.rowCount(), len(self.model.jcpds_lst))
        for row in range(n_rows):
            phase = self.model.jcpds_lst[row]
            item0 = table.item(row, self.COL_SHOW)
            if item0 is not None:
                phase.display = (item0.checkState() == QtCore.Qt.Checked)
            item1 = table.item(row, self.COL_LOCK)
            if item1 is not None:
                phase._pkpo_locked = (item1.checkState() == QtCore.Qt.Checked)

            def _commit_spin(col, attr):
                box = table.cellWidget(row, col)
                if box is None:
                    return
                try:
                    box.interpretText()
                except Exception:
                    pass
                setattr(phase, attr, float(box.value()))

            _commit_spin(self.COL_V0, "twk_v0")
            _commit_spin(self.COL_BA, "twk_b_a")
            _commit_spin(self.COL_CA, "twk_c_a")
            _commit_spin(self.COL_INT, "twk_int")
            _commit_spin(self.COL_K0, "twk_k0")
            _commit_spin(self.COL_K0P, "twk_k0p")
            _commit_spin(self.COL_ALPHA, "twk_thermal_expansion")

    def update(self, step=0.001):
        """
        show jcpds cards in the QTableWidget
        """
        n_columns = self.COL_ALPHA + 1
        n_rows = self.model.jcpds_lst.__len__()
        self.widget.tableWidget_JCPDS.setColumnCount(n_columns)
        self.widget.tableWidget_JCPDS.setRowCount(n_rows)
        self.widget.tableWidget_JCPDS.horizontalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.verticalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.setHorizontalHeaderLabels(
            ['👁',      # 0 - show checkbox
             '🔒',      # 1 - lock checkbox
             '',        # 2 - color (clickable if unlocked)
             'V0 twk',  # 3
             'b/a twk',  # 4
             'c/a twk',  # 5
             'Int twk',  # 6
             'K0 twk',  # 7
             'K0p twk',  # 8
             'alpha0 twk'])  # 9
        self.widget.tableWidget_JCPDS.setVerticalHeaderLabels(
            [phase.name for phase in self.model.jcpds_lst])
        
        self.widget.tableWidget_JCPDS.setColumnWidth(self.COL_SHOW, 30)
        self.widget.tableWidget_JCPDS.setColumnWidth(self.COL_LOCK, 45)
        self.widget.tableWidget_JCPDS.setColumnWidth(self.COL_COLOR, 35)
        
        for row in range(n_rows):
            phase = self.model.jcpds_lst[row]
            row_locked = bool(getattr(phase, "_pkpo_locked", False))

            # column 0 - show checkbox
            item0 = QtWidgets.QTableWidgetItem()
            item0.setFlags(QtCore.Qt.ItemIsUserCheckable |
                           QtCore.Qt.ItemIsEnabled)
            if phase.display:
                item0.setCheckState(QtCore.Qt.Checked)
            else:
                item0.setCheckState(QtCore.Qt.Unchecked)
            self.widget.tableWidget_JCPDS.setItem(row, self.COL_SHOW, item0)

            # column 1 - lock checkbox
            item_lock = QtWidgets.QTableWidgetItem()
            item_lock.setFlags(QtCore.Qt.ItemIsUserCheckable |
                               QtCore.Qt.ItemIsEnabled)
            item_lock.setCheckState(
                QtCore.Qt.Checked if row_locked else QtCore.Qt.Unchecked)
            self.widget.tableWidget_JCPDS.setItem(row, self.COL_LOCK, item_lock)
            
            # column 2 - color (clickable only when unlocked)
            item_color = QtWidgets.QTableWidgetItem('')
            item_color.setBackground(QtGui.QColor(phase.color))
            item_color.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.widget.tableWidget_JCPDS.setItem(row, self.COL_COLOR, item_color)
            
            # column 3 - V0 tweak
            if (phase.symmetry == 'nosymmetry'):
                item_v0 = QtWidgets.QTableWidgetItem(' ')
                item_v0.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, self.COL_V0, item_v0)
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
                    "value", phase.twk_v0)
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.valueChanged.\
                    connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, self.COL_V0, self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setFocusPolicy(
                    QtCore.Qt.StrongFocus)
                self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.\
                    setKeyboardTracking(False)
            
            # column 4 - b/a tweak
            if (phase.symmetry == 'cubic') or \
                    (phase.symmetry == 'tetragonal') or \
                    (phase.symmetry == 'hexagonal') or \
                    (phase.symmetry == 'nosymmetry'):
                item_b_a = QtWidgets.QTableWidgetItem(' ')
                item_b_a.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, self.COL_BA, item_b_a)
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
                    "value", phase.twk_b_a)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    valueChanged.connect(
                        self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, self.COL_BA, self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            
            # column 5 - c/a tweak
            if (phase.symmetry == 'cubic') or \
                    (phase.symmetry == 'nosymmetry'):
                item_c_a = QtWidgets.QTableWidgetItem(' ')
                item_c_a.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, self.COL_CA, item_c_a)
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
                    "value", phase.twk_c_a)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    valueChanged.connect(
                        self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, self.COL_CA, self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            
            # column 6 - Int tweak
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
                "value", phase.twk_int)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, self.COL_INT, self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.\
                setKeyboardTracking(False)
            
            # column 7 - K0 tweak
            if (phase.symmetry == 'nosymmetry'):
                item_k0 = QtWidgets.QTableWidgetItem(' ')
                item_k0.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, self.COL_K0, item_k0)
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
                    "value", phase.twk_k0)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.valueChanged.\
                    connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, self.COL_K0, self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setFocusPolicy(
                    QtCore.Qt.StrongFocus)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.\
                    setKeyboardTracking(False)
            
            # column 8 - K0p tweak
            if (phase.symmetry == 'nosymmetry'):
                item_k0p = QtWidgets.QTableWidgetItem(' ')
                item_k0p.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, self.COL_K0P, item_k0p)
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
                    "value", phase.twk_k0p)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.valueChanged.\
                    connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, self.COL_K0P, self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setFocusPolicy(
                    QtCore.Qt.StrongFocus)
                self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.\
                    setKeyboardTracking(False)
            
            # column 9 - alpha0 tweak
            if (phase.symmetry == 'nosymmetry'):
                item_alpha0 = QtWidgets.QTableWidgetItem(' ')
                item_alpha0.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, self.COL_ALPHA, item_alpha0)
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
                    "value", phase.twk_thermal_expansion)
                self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                    valueChanged.connect(self._handle_doubleSpinBoxChanged)
                self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setStyle(
                    SpinBoxFixStyle())
                self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
                self.widget.tableWidget_JCPDS.setCellWidget(
                    row, self.COL_ALPHA, self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                    setKeyboardTracking(False)
            self._set_row_locked_state(row, row_locked)
        
        self.widget.tableWidget_JCPDS.resizeColumnsToContents()
        # Disconnect all previous connections to avoid multiple dialogs
        try:
            self.widget.tableWidget_JCPDS.itemClicked.disconnect()
        except:
            pass  # No connections exist yet
        self.widget.tableWidget_JCPDS.itemClicked.connect(
            self._handle_ItemClicked)

    def _handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_JCPDS.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == self.COL_V0:
                self.model.jcpds_lst[idx].twk_v0 = value
            elif index.column() == self.COL_BA:
                self.model.jcpds_lst[idx].twk_b_a = value
            elif index.column() == self.COL_CA:
                self.model.jcpds_lst[idx].twk_c_a = value
            elif index.column() == self.COL_INT:
                self.model.jcpds_lst[idx].twk_int = value
            elif index.column() == self.COL_K0:
                self.model.jcpds_lst[idx].twk_k0 = value
            elif index.column() == self.COL_K0P:
                self.model.jcpds_lst[idx].twk_k0p = value
            elif index.column() == self.COL_ALPHA:
                self.model.jcpds_lst[idx].twk_thermal_expansion = value
            
            if self.model.jcpds_lst[idx].display:
                self._apply_changes_to_graph()

    def _handle_ItemClicked(self, item):
        idx = item.row()
        
        # Handle show checkbox clicks (column 0)
        if item.column() == self.COL_SHOW:
            if (item.checkState() == QtCore.Qt.Checked) ==\
                    self.model.jcpds_lst[idx].display:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.model.jcpds_lst[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.jcpds_lst[idx].display = False
            self._apply_changes_to_graph()
        elif item.column() == self.COL_LOCK:
            is_locked = (item.checkState() == QtCore.Qt.Checked)
            self.model.jcpds_lst[idx]._pkpo_locked = bool(is_locked)
            self._set_row_locked_state(idx, is_locked)
        
        # Handle color clicks
        elif item.column() == self.COL_COLOR:
            if bool(getattr(self.model.jcpds_lst[idx], "_pkpo_locked", False)):
                return
            color = QtWidgets.QColorDialog.getColor(
                QtGui.QColor(self.model.jcpds_lst[idx].color))
            if color.isValid():
                item.setBackground(color)
                self.model.jcpds_lst[idx].color = str(color.name())
                self._apply_changes_to_graph()

    def _set_row_locked_state(self, row, locked):
        table = self.widget.tableWidget_JCPDS
        color_item = table.item(row, self.COL_COLOR)
        if color_item is not None:
            if locked:
                color_item.setFlags(QtCore.Qt.NoItemFlags)
            else:
                color_item.setFlags(QtCore.Qt.ItemIsEnabled |
                                    QtCore.Qt.ItemIsSelectable)
        for col in range(self.COL_V0, self.COL_ALPHA + 1):
            box = table.cellWidget(row, col)
            if box is not None:
                box.setEnabled(not locked)
            item = table.item(row, col)
            if item is not None:
                if locked:
                    item.setFlags(QtCore.Qt.NoItemFlags)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled)

    def update_steps_only(self, step):
        """
        show jcpds cards in the QTableWidget
        """
        self.widget.tableWidget_JCPDS.clear()
        self.update(step=step)
