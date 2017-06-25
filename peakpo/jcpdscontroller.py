from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
import matplotlib.pyplot as plt
from matplotlib import colors
import matplotlib.cm as cmx
from mplcontroller import MplController
from utils import extract_filename
from utils import SpinBoxFixStyle


class JcpdsController(object):

    def __init__(self, model, widget, jcpds_path):
        self.model = model
        self.widget = widget
        self.jcpds_path = jcpds_path
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_NewJlist.clicked.connect(self.make_jlist)
        self.widget.pushButton_RemoveJCPDS.clicked.connect(self.remove_a_jcpds)
        self.widget.pushButton_AddToJlist.clicked.connect(
            lambda: self.make_jlist(append=True))
        self.widget.checkBox_Intensity.clicked.connect(
            lambda: self.apply_changes_to_graph(limits=None))
        self.widget.pushButton_CheckAllJCPDS.clicked.connect(
            self.check_all_jcpds)
        self.widget.pushButton_UncheckAllJCPDS.clicked.connect(
            self.uncheck_all_jcpds)
        self.widget.pushButton_MoveUp.clicked.connect(self.move_up_jcpds)
        self.widget.pushButton_MoveDown.clicked.connect(self.move_down_jcpds)

    def apply_changes_to_graph(self, limits=None):
        self.plot_ctrl.update(limits=limits)

    def _find_a_jcpds(self):
        idx_checked = \
            self.widget.tableWidget_JCPDS.selectionModel().selectedRows()
        if idx_checked == []:
            return None
        else:
            return idx_checked[0].row()

    def make_jlist(self, append=False):
        """
        collect files for jlist
        """
        files = QtWidgets.QFileDialog.getOpenFileNames(
            self.widget, "Choose JPCDS Files", self.jcpds_path, "(*.jcpds)")[0]
        if files == []:
            return
        self.jcpds_path = os.path.split(str(files[0]))[0]
        n_color = 9
        jet = plt.get_cmap('gist_rainbow')
        cNorm = colors.Normalize(vmin=0, vmax=n_color)
        c_index = range(n_color)
        scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=jet)
        c_value = [c_index[0], c_index[3], c_index[6], c_index[1], c_index[4],
                   c_index[7], c_index[2], c_index[5], c_index[8]]
        if append:
            n_existingjcpds = self.model.jcpds_lst.__len__()
            n_addedjcpds = files.__len__()
            if ((n_existingjcpds + n_addedjcpds) > n_color):
                i = 0
            else:
                i = n_existingjcpds
        else:
            self.model.reset_jcpds_lst()
            i = 0
        for f in files:
            color = colors.rgb2hex(scalarMap.to_rgba(c_value[i]))
            self.model.append_a_jcpds(str(f), color)
            i += 1
            if i >= n_color - 1:
                i = 0
        # display on the QTableWidget
        self.update_table()
        if self.model.base_ptn_exist():
            self.apply_changes_to_graph()
        else:
            self.apply_changes_to_graph(limits=(0., 25., 0., 100.))

    def move_up_jcpds(self):
        # get selected cell number
        idx_selected = self._find_a_jcpds()
        if idx_selected is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Highlight the item to move first.")
            return
        i = idx_selected
        if i == 0:
            return
        self.model.jcpds_lst[i - 1], self.model.jcpds_lst[i] = \
            self.model.jcpds_lst[i], self.model.jcpds_lst[i - 1]
        self.widget.tableWidget_JCPDS.selectRow(i - 1)
        self.update_table()

    def move_down_jcpds(self):
        # get selected cell number
        idx_selected = self._find_a_jcpds()
        if idx_selected is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Highlight the item to move first.")
            return
        i = idx_selected
        if i >= self.model.jcpds_lst.__len__() - 1:
            return
        self.model.jcpds_lst[i + 1], self.model.jcpds_lst[i] = \
            self.model.jcpds_lst[i], self.model.jcpds_lst[i + 1]
        self.widget.tableWidget_JCPDS.selectRow(i + 1)
        """
        self.widget.tableWidget_JCPDS.setCurrentItem(
            self.widget.tableWidget_JCPDS.item(i + 1, 1))
        self.widget.tableWidget_JCPDS.setItemSelected(
            self.widget.tableWidget_JCPDS.item(i + 1, 1), True)
        self.widget.tableWidget_JCPDS.setItemSelected(
            self.widget.tableWidget_JCPDS.item(i, 1), False)
        """
        self.update_table()

    def check_all_jcpds(self):
        if not self.model.jcpds_exist():
            return
        for phase in self.model.jcpds_lst:
            phase.display = True
        self.update_table()
        self.apply_changes_to_graph()

    def uncheck_all_jcpds(self):
        if not self.model.jcpds_exist():
            return
        for phase in self.model.jcpds_lst:
            phase.display = False
        self.update_table()
        self.apply_changes_to_graph()

    def remove_a_jcpds(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Are you sure you want to remove the highlighted JPCDSs?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        # print self.widget.tableWidget_JCPDS.selectedIndexes().__len__()
        idx_checked = [s.row() for s in
                       self.widget.tableWidget_JCPDS.selectionModel().
                       selectedRows()]
        # remove checked ones
        if idx_checked != []:
            idx_checked.reverse()
            for idx in idx_checked:
                self.model.jcpds_lst.remove(self.model.jcpds_lst[idx])
                self.widget.tableWidget_JCPDS.removeRow(idx)
#        self.update_table()
            self.apply_changes_to_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')

    def update_table(self):
        """
        show jcpds cards in the QTableWidget
        """
        n_columns = 10
        n_rows = self.model.jcpds_lst.__len__()  # count for number of jcpds
        self.widget.tableWidget_JCPDS.setColumnCount(n_columns)
        self.widget.tableWidget_JCPDS.setRowCount(n_rows)
        self.widget.tableWidget_JCPDS.horizontalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.verticalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.setHorizontalHeaderLabels(
            ['', 'Color', ' ', 'V0 Tweak', 'K0 Tweak', 'K0p Tweak',
             'alpha0 Tweak', 'b/a Tweak', 'c/a Tweak', 'Int Tweak'])
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
            item2 = QtWidgets.QTableWidgetItem('    ')
            self.widget.tableWidget_JCPDS.setItem(row, 1, item2)
            # column 2 - color setup
            self.widget.tableWidget_JCPDS_pushButton_color = \
                QtWidgets.QPushButton('...')
            self.widget.tableWidget_JCPDS.item(row, 1).setBackground(
                QtGui.QColor(self.model.jcpds_lst[row].color))
            self.widget.tableWidget_JCPDS_pushButton_color.clicked.connect(
                self._handle_ColorButtonClicked)
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 2, self.widget.tableWidget_JCPDS_pushButton_color)
            # column 3 - V0 tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setMaximum(2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_V0twk.setSingleStep(
                0.001)
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
            # column 4 - K0 tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setMaximum(2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setSingleStep(
                0.01)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setDecimals(2)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setProperty(
                "value", self.model.jcpds_lst[row].twk_k0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 4, self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0twk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            # column 5 - K0p tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setMaximum(2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setSingleStep(
                0.01)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setDecimals(2)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setProperty(
                "value", self.model.jcpds_lst[row].twk_k0p)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.valueChanged.\
                connect(self._handle_doubleSpinBoxChanged)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setStyle(
                SpinBoxFixStyle())
            self.widget.tableWidget_JCPDS.setCellWidget(
                row, 5, self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk)
            self.widget.tableWidget_JCPDS_doubleSpinBox_K0ptwk.setFocusPolicy(
                QtCore.Qt.StrongFocus)
            # column 6 - alpha0 tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.setMaximum(
                2.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk.\
                setSingleStep(0.01)
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
                row, 6, self.widget.tableWidget_JCPDS_doubleSpinBox_alpha0twk)
            # column 7 - b/a tweak
            if (self.model.jcpds_lst[row].symmetry == 'cubic') or \
                    (self.model.jcpds_lst[row].symmetry == 'tetragonal') or \
                    (self.model.jcpds_lst[row].symmetry == 'hexagonal'):
                item8 = QtWidgets.QTableWidgetItem('')
                item8.setFlags(QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_JCPDS.setItem(row, 8, item8)
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
                    setSingleStep(0.001)
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
                    row, 7, self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_b_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 8 - c/a tweak
            if (self.model.jcpds_lst[row].symmetry == 'cubic'):
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
                    setSingleStep(0.001)
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
                    row, 8, self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setKeyboardTracking(False)
                self.widget.tableWidget_JCPDS_doubleSpinBox_c_atwk.\
                    setFocusPolicy(QtCore.Qt.StrongFocus)
            # column 9 - int tweak
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk = \
                QtWidgets.QDoubleSpinBox()
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing |
                QtCore.Qt.AlignVCenter)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setMaximum(1.0)
            self.widget.tableWidget_JCPDS_doubleSpinBox_inttwk.setSingleStep(
                0.05)
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
            elif index.column() == 4:
                self.model.jcpds_lst[idx].twk_k0 = value
            elif index.column() == 5:
                self.model.jcpds_lst[idx].twk_k0p = value
            elif index.column() == 6:
                self.model.jcpds_lst[idx].twk_thermal_expansion = value
            elif index.column() == 7:
                self.model.jcpds_lst[idx].twk_b_a = value
            elif index.column() == 8:
                self.model.jcpds_lst[idx].twk_c_a = value
            elif index.column() == 9:
                self.model.jcpds_lst[idx].twk_int = value
            if self.model.jcpds_lst[idx].display:
                self.apply_changes_to_graph()

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
                    self.apply_changes_to_graph()

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
            self.apply_changes_to_graph()
        else:
            return

    def _find_closestjcpds(self, x):
        jcount = 0
        for j in self.model.jcpds_lst:
            if j.display:
                jcount += 1
        ucount = 0
        for u in self.model.ucfit_lst:
            if u.display:
                ucount += 1
        if (jcount + ucount) == 0:
            return ''
        if jcount != 0:
            idx_j = []
            diff_j = []
            tth_j = []
            h_j = []
            k_j = []
            l_j = []
            names_j = []
            dsp_j = []
            int_j = []
            for j in self.model.jcpds_lst:
                if j.display:
                    i, d, t = j.find_DiffLine(
                        x, self.widget.doubleSpinBox_SetWavelength.value())
                    idx_j.append(i)
                    diff_j.append(d)
                    tth_j.append(t)
                    h_j.append(j.DiffLines[i].h)
                    k_j.append(j.DiffLines[i].k)
                    l_j.append(j.DiffLines[i].l)
                    dsp_j.append(j.DiffLines[i].dsp)
                    int_j.append(j.DiffLines[i].intensity)
                    names_j.append(j.name)
        if ucount != 0:
            idx_u = []
            diff_u = []
            tth_u = []
            h_u = []
            k_u = []
            l_u = []
            names_u = []
            dsp_u = []
            int_u = []
            for u in self.model.ucfit_lst:
                if u.display:
                    i, d, t = u.find_DiffLine(
                        x, self.widget.doubleSpinBox_SetWavelength.value())
                    idx_u.append(i)
                    diff_u.append(d)
                    tth_u.append(t)
                    h_u.append(u.DiffLines[i].h)
                    k_u.append(u.DiffLines[i].k)
                    l_u.append(u.DiffLines[i].l)
                    dsp_u.append(u.DiffLines[i].dsp)
                    int_u.append(u.DiffLines[i].intensity)
                    names_u.append(u.name)
        if (jcount != 0) and (ucount == 0):
            idx_min = diff_j.index(min(diff_j))
            tth_min = tth_j[idx_min]
            dsp_min = dsp_j[idx_min]
            int_min = int_j[idx_min]
            h_min = h_j[idx_min]
            k_min = k_j[idx_min]
            l_min = l_j[idx_min]
            name_min = names_j[idx_min]
        elif (jcount == 0) and (ucount != 0):
            idx_min = diff_u.index(min(diff_u))
            tth_min = tth_u[idx_min]
            dsp_min = dsp_u[idx_min]
            int_min = int_u[idx_min]
            h_min = h_u[idx_min]
            k_min = k_u[idx_min]
            l_min = l_u[idx_min]
            name_min = names_u[idx_min]
        else:
            if min(diff_j) <= min(diff_u):
                idx_min = diff_j.index(min(diff_j))
                tth_min = tth_j[idx_min]
                dsp_min = dsp_j[idx_min]
                int_min = int_j[idx_min]
                h_min = h_j[idx_min]
                k_min = k_j[idx_min]
                l_min = l_j[idx_min]
                name_min = names_j[idx_min]
            else:
                idx_min = diff_u.index(min(diff_u))
                tth_min = tth_u[idx_min]
                dsp_min = dsp_u[idx_min]
                int_min = int_u[idx_min]
                h_min = h_u[idx_min]
                k_min = k_u[idx_min]
                l_min = l_u[idx_min]
                name_min = names_u[idx_min]
        line1 = 'Two theta = {0: 10.4f}, d-spacing = {1: 10.4f} A'.format(
            float(tth_min), float(dsp_min))
        line2 = 'intensity = {0: 5.0f}, hkl = {1: 3.0f} {2: 3.0f} {3: 3.0f}'.\
            format(int(int_min), int(h_min), int(k_min), int(l_min))
        textoutput = name_min + '\n' + line1 + '\n' + line2
        return textoutput
