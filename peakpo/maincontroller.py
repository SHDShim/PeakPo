from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
# from collections import OrderedDict
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backend_bases import key_press_handler
import pickle
import zipfile
from mainwidget import MainWindow
from model import PeakPoModel
from mplcontroller import MplController
from cakecontroller import CakeController
from waterfallcontroller import WaterfallController
from jcpdscontroller import JcpdsController
# from model import PeakPoModel
from utils import get_sorted_filelist, find_from_filelist, dialog_savefile, \
    xls_ucfitlist, xls_jlist, writechi, extract_filename
from utils import SpinBoxFixStyle
# ultimately the lines below should be moved to model
from ds_cake import DiffImg
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ds_jcpds import JCPDSplt, Session, UnitCell, convert_tth
from ds_powdiff import PatternPeakPo, get_DataSection


class MainController(object):

    def __init__(self):

        self.widget = MainWindow()
        self.model = PeakPoModel()
        self.obj_color = 'white'
        self.read_setting()
        self.connect_channel()
        self.plot_ctrl = MplController(self.model, self.widget)
        self.waterfall_ctrl = WaterfallController(
            self.model, self.widget, self.chi_path)
        self.jcpds_ctrl = JcpdsController(self.model, self.widget,
                                          self.jcpds_path)
        self.cake_ctrl = CakeController(self.model, self.widget, self.chi_path)
        #
        self.clip = QtWidgets.QApplication.clipboard()
        # no more stuff can be added below

    def show_window(self):
        self.widget.show()

    def connect_channel(self):
        # connecting events
        self.widget.mpl.canvas.mpl_connect(
            'button_press_event', self.read_plot)
        self.widget.mpl.canvas.mpl_connect(
            'key_press_event', self.on_key_press)
        # Tab: Main
        self.widget.pushButton_NewBasePtn.clicked.connect(
            self.select_base_ptn)
        self.widget.pushButton_PrevBasePtn.clicked.connect(
            lambda: self.goto_next_file('previous'))
        self.widget.pushButton_NextBasePtn.clicked.connect(
            lambda: self.goto_next_file('next'))
        self.widget.pushButton_LastBasePtn.clicked.connect(
            lambda: self.goto_next_file('last'))
        self.widget.pushButton_FirstBasePtn.clicked.connect(
            lambda: self.goto_next_file('first'))
        self.widget.doubleSpinBox_Pressure.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.doubleSpinBox_Temperature.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.pushButton_SaveSession.clicked.connect(self.save_session)
        self.widget.pushButton_LoadSession.clicked.connect(self.load_session)
        self.widget.pushButton_ZipSession.clicked.connect(self.zip_session)
        self.widget.lineEdit_DiffractionPatternFileName.editingFinished.\
            connect(self.load_new_base_pattern_from_name)
        self.widget.pushButton_SaveJlist.clicked.connect(self.save_session)
        self.widget.doubleSpinBox_SetWavelength.valueChanged.connect(
            self.apply_wavelength)
        self.widget.pushButton_ExportXLS.clicked.connect(self.save_xls)
        self.widget.pushButton_SaveCHI.clicked.connect(self.save_bgsubchi)
        # while the button is located in JCPDS tab, this one connect different
        # tabs, so stays in main controller
        self.widget.pushButton_ExportToUCFit.clicked.connect(
            self.export_to_ucfit)
        # save Jlist is linked to save_session in the main controller
        self.widget.pushButton_LoadJlist.clicked.connect(self.load_jlist)
        self.widget.pushButton_ViewJCPDS.clicked.connect(self.view_jcpds)
        # Tab: process
        self.widget.pushButton_UpdatePlots_tab2.clicked.connect(
            self.update_bgsub)
        # Tab: UCFit List
        self.widget.pushButton_RemoveUClist.clicked.connect(self.remove_ucfit)
        self.widget.pushButton_ExportXLS_2.clicked.connect(self.export_to_xls)
        # file menu items
        self.widget.actionClose.triggered.connect(self.closeEvent)
        # navigation toolbar modification
        self.widget.ntb_WholePtn.clicked.connect(self.zoom_out_graph)
        self.widget.ntb_toPkFt.clicked.connect(self.to_PkFt)
        self.widget.ntb_fromPkFt.clicked.connect(self.from_PkFt)
        self.widget.ntb_ResetY.clicked.connect(self.apply_changes_to_graph)
        self.widget.ntb_Bgsub.clicked.connect(self.apply_changes_to_graph)
        self.widget.ntb_NightView.clicked.connect(self.set_nightday_view)

    def apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def export_to_xls(self):
        """
        UCFit function
        Export ucfitlist to an excel file
        """
        if not self.model.ucfit_exist():
            return
        new_filen_xls = self.model.make_filename('peakpo.ucfit.xls')
        filen_xls = dialog_savefile(self.widget, new_filen_xls)
        if str(filen_xls) == '':
            return
        xls_ucfitlist(filen_xls, self.model.ucfit_lst)

    def view_jcpds(self):
        if not self.model.jcpds_exist():
            return
        idx_checked = [
            s.row() for s in
            self.widget.tableWidget_JCPDS.selectionModel().selectedRows()]

        if idx_checked == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Highlight the name of JCPDS to view")
            return
        if idx_checked.__len__() != 1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Only one JCPDS card can be shown at a time.")
        else:
            textoutput = self.model.jcpds_lst[idx_checked[0]].make_TextOutput(
                self.widget.doubleSpinBox_Pressure.value(),
                self.widget.doubleSpinBox_Temperature.value())
            self.widget.plainTextEdit_ViewJCPDS.setPlainText(textoutput)

    def remove_ucfit(self):
        """
        UCFit function
        Remove items from the ucfitlist
        """
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Are you sure you want to remove the highlighted phases?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        idx_checked = [
            s.row() for s in self.widget.tableWidget_UnitCell.selectionModel().
            selectedRows()]
        if idx_checked != []:
            idx_checked.reverse()
            for idx in idx_checked:
                self.model.ucfit_lst.remove(self.model.ucfit_lst[idx])
                self.widget.tableWidget_UnitCell.removeRow(idx)
            self.plot_ctrl.update()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')

    def load_jlist(self):
        """get existing jlist file from data folder"""
        fn_jlist = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.chi_path, "(*.ppss)")[0]
        if fn_jlist == '':
            return
        self._load_session(fn_jlist, True)
        self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn_jlist))
        self.jcpds_ctrl.update_table()
        self.plot_ctrl.update()

    def export_to_ucfit(self):
        """
        UCFit function
        Export an item from jlist to ucfitlist
        """
        if not self.model.jcpds_exist():
            return
        idx_checked = [
            s.row() for s in self.widget.tableWidget_JCPDS.selectionModel().
            selectedRows()]

        if idx_checked == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Highlight the name of JCPDS to export")
            return
        i = 0
        for j in range(idx_checked.__len__()):
            if self.model.jcpds_lst[idx_checked[j]].symmetry != 'manual':
                phase = UnitCell()
                phase.name = self.model.jcpds_lst[idx_checked[j]].name
                phase.color = self.model.jcpds_lst[idx_checked[j]].color
                phase.symmetry = self.model.jcpds_lst[idx_checked[j]].symmetry
                phase.a = self.model.jcpds_lst[idx_checked[j]].a
                phase.b = self.model.jcpds_lst[idx_checked[j]].b
                phase.c = self.model.jcpds_lst[idx_checked[j]].c
                phase.alpha = self.model.jcpds_lst[idx_checked[j]].alpha
                phase.beta = self.model.jcpds_lst[idx_checked[j]].beta
                phase.gamma = self.model.jcpds_lst[idx_checked[j]].gamma
                phase.v = self.model.jcpds_lst[idx_checked[j]].v
                phase.DiffLines = \
                    self.model.jcpds_lst[idx_checked[j]].DiffLines
                self.model.ucfit_lst.append(phase)
                i += 1
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You cannot send a jcpds without symmetry.")
        self._list_ucfit()
        self.jcpds_ctrl.update_table()
        self.plot_ctrl.update()
        return

    def _list_ucfit(self):
        """
        UCFit function
        Show ucfit in the QTableWidget
        """
        n_columns = 10
        n_rows = self.model.ucfit_lst.__len__()  # count for number of jcpds
        self.widget.tableWidget_UnitCell.setColumnCount(n_columns)
        self.widget.tableWidget_UnitCell.setRowCount(n_rows)
        self.widget.tableWidget_UnitCell.horizontalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.verticalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.setHorizontalHeaderLabels(
            ['', 'Color', 'Color Change', 'Volume', 'a', 'b', 'c',
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
                QtWidgets.QPushButton('change')
            self.widget.tableWidget_UnitCell.item(row, 1).setBackground(
                QtGui.QColor(self.model.ucfit_lst[row].color))
            self.widget.tableWidget_UnitCell_pushButton_color.clicked.connect(
                self._ucfitlist_handle_ColorButtonClicked)
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
                connect(self._ucfitlist_handle_doubleSpinBoxChanged)
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
                        self._ucfitlist_handle_doubleSpinBoxChanged)
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
                    connect(self._ucfitlist_handle_doubleSpinBoxChanged)
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
                    connect(self._ucfitlist_handle_doubleSpinBoxChanged)
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
                    connect(self._ucfitlist_handle_doubleSpinBoxChanged)
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
                        self._ucfitlist_handle_doubleSpinBoxChanged)
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
            self._ucfitlist_handle_ItemClicked)

    def _ucfitlist_handle_doubleSpinBoxChanged(self, value):
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
                self.plot_ctrl.update()

    def _ucfitlist_handle_ColorButtonClicked(self):
        button = self.widget.sender()
        index = self.widget.tableWidget_UnitCell.indexAt(button.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 2:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    self.widget.tableWidget_UnitCell.item(idx, 2).\
                        setBackground(color)
                    self.model.ucfit_lst[idx].color = str(color.name())
                    self.plot_ctrl.update()

    def _ucfitlist_handle_ItemClicked(self, item):
        if item.column() == 0:
            idx = item.row()
            if (item.checkState() == QtCore.Qt.Checked) == \
                    self.model.ucfit_lst[idx].display:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.model.ucfit_lst[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.ucfit_lst[idx].display = False
            self.plot_ctrl.update()
        else:
            return

    def save_bgsubchi(self):
        """
        Output function
        Save bg subtractd pattern to a chi file
        """
        if not self.model.base_ptn_exist():
            return
        filen_chi_t = self.model.make_filename('bgsub.chi')
        filen_chi = dialog_savefile(self.widget, filen_chi_t)
        if str(filen_chi) == '':
            return
        x, y = self.model.base_ptn.get_bgsub()
        writechi(filen_chi, x, y)

    def write_setting(self):
        """
        Write default setting
        """
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        self.settings.setValue('chi_path', self.chi_path)
        self.settings.setValue('jcpds_path', self.jcpds_path)

    def read_setting(self):
        """
        Read default setting
        """
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        self.chi_path = str(self.settings.value('chi_path'))
        self.jcpds_path = str(self.settings.value('jcpds_path'))

    def closeEvent(self, event):
        """
        Close event function
        """
        self.write_setting()
        self.deleteLater()

    def on_key_press(self, event):
        if event.key == 'i':
            if self.widget.mpl.ntb._active == 'PAN':
                self.widget.mpl.ntb.pan()
            if self.widget.mpl.ntb._active == 'ZOOM':
                self.widget.mpl.ntb.zoom()
        elif event.key == 's':
            self.save_session_with_default_name()
        elif event.key == 'w':
            self.zoom_out_graph()
        elif event.key == 'v':
            lims = self.widget.mpl.canvas.ax_pattern.axis()
            if self.widget.ntb_Bgsub.isChecked():
                x, y = self.model.base_ptn.get_bgsub()
            else:
                x, y = self.model.base_ptn.get_raw()
            xroi, yroi = get_DataSection(x, y, [lims[0], lims[1]])
            self.plot_ctrl.update([lims[0], lims[1], yroi.min(), yroi.max()])
        else:
            key_press_handler(event, self.widget.mpl.canvas,
                              self.widget.mpl.ntb)

    def to_PkFt(self):
        # listen
        if not self.model.base_ptn_exist():
            return
        lims = self.widget.mpl.canvas.ax_pattern.axis()
        talk = "PeakPo,{0},{1: .2f},{2: .2f},{3: .2f},{4: .2f}".format(
            self.model.base_ptn.fname, lims[0], lims[1], lims[2], lims[3])
        self.clip.setText(talk)

    def from_PkFt(self):
        l = self.clip.text()
        listen = str(l)
        if listen.find("PeakFt") == -1:
            return
        a = listen.split(',')
        new_filen = a[1]
        new_lims = [float(i) for i in a[2:6]]
        self._load_a_new_pattern(new_filen)
        self.plot_ctrl.update(new_lims)

    def save_xls(self):
        """
        JCPDS function
        Export jlist to an excel file
        """
        if not self.model.jcpds_exist():
            return
        filen_xls_t = self.model.make_filename('pkpo.xls')
        filen_xls = dialog_savefile(self.widget, filen_xls_t)
        if str(filen_xls) == '':
            return
        xls_jlist(filen_xls, self.model.jcpds_lst,
                  self.widget.doubleSpinBox_Pressure.value(),
                  self.widget.doubleSpinBox_Temperature.value())

    def load_session(self):
        """
        get existing jlist file from data folder
        """
        fn = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File", self.chi_path, "(*.ppss)")[0]
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        success = self._load_session(fn, False)
        if success:
            self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn))
            self.widget.textEdit_SessionFileName.setText('Session: ' + str(fn))
            self.widget.textEdit_DiffractionPatternFileName.setText(
                '1D pattern: ' + str(self.model.base_ptn.fname))
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            self.zoom_out_graph()
            self.update_inputs()

    def _update_session(self):
        if not self.model.base_ptn_exist():
            return
        fn = self.model.make_filename('ppss')
        if not os.path.exists(fn):
            return
        success = self._load_session(fn, False)
        if success:
            self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn))
            self.widget.textEdit_DiffractionPatternFileName.setText(
                '1D pattern: ' + str(self.model.base_ptn.fname))
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            self.widget.textEdit_SessionFileName.setText('Session: ' + str(fn))
            self.update_inputs()

    def _load_session(self, fsession, jlistonly=False):
        '''
        internal method for reading pickled ppss file
        '''
#        session = Session()
#        try:
        f = open(fsession, 'rb')
        session = pickle.load(f, encoding='latin1')
#        print type(session).__name__
#        if type(session).__name__ == 'Session':
#            QtGui.QMessageBox.warning(self.widget, 'Warning',
#                'This PPSS file has an old format.
#               Make sure you overwrite the file again after opening.')
        f.close()
        # except:
        #     QtGui.QMessageBox.warning(self.widget, "Warning", \
        #         "Session loading failed.  But no harm, just inconvenience.")
        #     return False
        # through check of the file existence
        if jlistonly:
            self.model.jcpds_lst = session.jlist
            self.jcpds_path = session.jcpds_path
        else:
            if (session.chi_path != ''):
                if not os.path.exists(session.chi_path):
                    chi_path = os.path.dirname(str(fsession))
                    chi_basefilen = os.path.basename(session.pattern.fname)
                    chi_filen = os.path.join(chi_path, chi_basefilen)
                    if os.path.exists(chi_filen):
                        session.pattern.read_file(chi_filen)
                        session.pattern.get_chbg(
                            session.bg_roi, session.bg_params, yshift=0)
                        session.chi_path = chi_path
                    else:
                        QtWidgets.QMessageBox.warning(
                            self.widget, "Warning",
                            "The base file in the PPSS cannot be found.")
                        return False
                    if session.waterfallpatterns != []:
                        for wfp in session.waterfallpatterns:
                            wfp_basefilen = os.path.basename(wfp.fname)
                            chi_filen = os.path.join(chi_path, wfp_basefilen)
                            if os.path.exists(chi_filen):
                                wfp.read_file(chi_filen)
                                wfp.get_chbg(session.bg_roi, session.bg_params,
                                             yshift=0)
                            else:
                                reply = QtWidgets.QMessageBox.question(
                                    self.widget, "Question",
                                    "The waterfall files in the PPSS cannot \
                                    be found. Do you want to ignore the water \
                                    fall?",
                                    QtWidgets.QMessageBox.Yes |
                                    QtWidgets.QMessageBox.No,
                                    QtWidgets.QMessageBox.Yes)
                                if reply == QtWidgets.QMessageBox.Yes:
                                    session.waterfallpatterns = []
                                    break
                                else:
                                    return False
            if (session.jcpds_path != ''):
                if not os.path.exists(session.jcpds_path):
                    reply = QtWidgets.QMessageBox.question(
                        self.widget, "Question",
                        "The JCPDS path in the PPSS does not exist.  \
                        Do you want to update the JCPDS path?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes)
                    if reply == QtWidgets.QMessageBox.Yes:
                        jcpds_path = \
                            QtWidgets.QFileDialog.getExistingDirectory(
                                self.widget, "Open Directory", self.jcpds_path,
                                QtWidgets.QFileDialog.ShowDirsOnly)
                        if jcpds_path != '':
                            session.jcpds_path = jcpds_path
                        else:
                            return False
                    else:
                        QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                                      "PPSS read failed.")
                        return False
            if (session.pattern is None):
                if not os.path.exists(session.jcpds_path):
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        "No base pattern exists in the previous session.")
                    return False
            self.model.set_base_ptn(session.pattern)
            self.model.waterfall_ptn = session.waterfallpatterns
            self.widget.doubleSpinBox_SetWavelength.setValue(
                session.wavelength)
            self.widget.doubleSpinBox_Pressure.setValue(session.pressure)
            self.widget.doubleSpinBox_Temperature.setValue(session.temperature)
            self.model.jcpds_lst = session.jlist
            self.widget.doubleSpinBox_Background_ROI_min.setValue(
                session.bg_roi[0])
            self.widget.doubleSpinBox_Background_ROI_max.setValue(
                session.bg_roi[1])
            self.widget.spinBox_BGParam0.setValue(session.bg_params[0])
            self.widget.spinBox_BGParam1.setValue(session.bg_params[1])
            self.widget.spinBox_BGParam2.setValue(session.bg_params[2])
            self.jcpds_path = session.jcpds_path
            self.chi_path = session.chi_path
        return True

    def _dump_session(self, fsession):
        session = Session()
        session.pattern = self.model.get_base_ptn()
        session.waterfallpatterns = self.model.waterfall_ptn
        session.wavelength = self.widget.doubleSpinBox_SetWavelength.value()
        session.pressure = self.widget.doubleSpinBox_Pressure.value()
        session.temperature = self.widget.doubleSpinBox_Temperature.value()
        session.jlist = self.model.jcpds_lst
        session.bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                          self.widget.doubleSpinBox_Background_ROI_max.value()]
        session.bg_params = [self.widget.spinBox_BGParam0.value(),
                             self.widget.spinBox_BGParam1.value(),
                             self.widget.spinBox_BGParam2.value()]
        session.jcpds_path = self.jcpds_path
        session.chi_path = self.chi_path
        f = open(fsession, 'wb')
        pickle.dump(session, f)
        f.close()

    def update_inputs(self):
        self.reset_bgsub()
        self.waterfall_ctrl.update_table()
        self.jcpds_ctrl.update_table()

    def zip_session(self):
        if not self.model.base_ptn_exist():
            fzip = os.path.join(self.chi_path, 'dum.zip')
        else:
            """
            path, filen = os.path.split(self.model.base_ptn.fname)
            new_filen = '%s.zip' % filen
            fzip = os.path.join(path, new_filen)
            """
            fzip = self.model.make_filename('zip')
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Question',
            'Do you want to save in default filename, %s ?' % fzip,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            fzip = QtWidgets.QFileDialog.getSaveFileName(
                self.widget, "Save A Zip File",
                fzip, "(*.zip)", None)[0]
        else:
            if os.path.exists(fzip):
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Question',
                    'The file already exist.  Do you want to overwrite?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.No:
                    return
        if str(fzip) != '':
            path, filen = os.path.split(str(fzip))
            fsession_name = '%s.forzip.ppss' % filen
            fsession = os.path.join(path, fsession_name)
            self._dump_session(str(fsession))
            self.widget.textEdit_Jlist.setText('Jlist : ' + str(fsession))
            zf = zipfile.ZipFile(str(fzip), 'w', zipfile.ZIP_DEFLATED)
            zf.write(fsession, arcname=fsession_name)
            if self.model.base_ptn_exist():
                dum, filen = os.path.split(self.model.base_ptn.fname)
                zf.write(self.model.base_ptn.fname, arcname=filen)
            if self.model.waterfall_exist():
                for wf in self.model.waterfall_ptn:
                    dum, filen = os.path.split(wf.fname)
                    zf.write(wf.fname, arcname=filen)
            zf.close()

    def save_session(self):
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.chi_path, 'dum.ppss')
        else:
            fsession = self.model.make_filename('ppss')
        new_filename = dialog_savefile(self.widget, fsession)
        if new_filename != '':
            self._dump_session(new_filename)
            self.widget.textEdit_SessionFileName.setText('Session: ' +
                                                         str(new_filename))

    def save_session_with_default_name(self):
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.chi_path, 'dum.ppss')
        else:
            fsession = self.model.make_filename('ppss')
        if os.path.exists(fsession):
            reply = QtWidgets.QMessageBox.question(
                self.widget, 'Question',
                'The file already exist.  Do you want to overwrite?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes)
            if reply == QtWidgets.QMessageBox.No:
                return
        if str(fsession) != '':
            self._dump_session(str(fsession))
            self.widget.textEdit_SessionFileName.setText(
                'Session: ' + str(fsession))

    def set_nightday_view(self):
        self.plot_ctrl._set_nightday_view()
        self.waterfall_ctrl.update_table()
        self.plot_ctrl.update()

    def read_plot(self, event):
        if self.widget.mpl.ntb._active is not None:
            return
        if (event.xdata is None) or (event.ydata is None):
            return
        x_click = float(event.xdata)
        y_click = float(event.ydata)
        x_click_dsp = self.widget.doubleSpinBox_SetWavelength.value() / 2. / \
            np.sin(np.radians(x_click / 2.))
        clicked_position = \
            "Clicked position: {0: 10.4f}, {1: 7.1f}, \n dsp = {2: 10.4f} A".\
            format(x_click, y_click, x_click_dsp)
        if (not self.model.jcpds_exist()) and (not self.model.ucfit_exist()):
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          clicked_position)
        else:
            # get jcpds information
            x_find = event.xdata
            textinfo = self._find_closestjcpds(x_find)
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          clicked_position + '\n' + textinfo)

    def apply_wavelength(self):
        # self.wavelength = value
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        self.plot_ctrl.update()

    def update_bgsub(self):
        '''
        this is only to read the current inputs and replot
        '''
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Load a base pattern first.")
            return
        """receive new bg parameters and update the graph"""
        bg_params = [self.widget.spinBox_BGParam0.value(),
                     self.widget.spinBox_BGParam1.value(),
                     self.widget.spinBox_BGParam2.value()]
        bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                  self.widget.doubleSpinBox_Background_ROI_max.value()]
        self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        if self.model.waterfall_exist():
            for pattern in self.model.waterfall_ptn:
                pattern.subtract_bg(bg_roi, bg_params, yshift=0)
        self.zoom_out_graph()

    def reset_bgsub(self):
        '''
        this is to read from session file and put to the table
        '''
        bg_params = [self.widget.spinBox_BGParam0.value(),
                     self.widget.spinBox_BGParam1.value(),
                     self.widget.spinBox_BGParam2.value()]
        bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                  self.widget.doubleSpinBox_Background_ROI_max.value()]
        self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        if self.model.waterfall_exist():
            for pattern in self.model.waterfall_ptn:
                pattern.get_chbg(bg_roi, bg_params, yshift=0)

    def zoom_out_graph(self):
        if not self.model.base_ptn_exist():
            return
        if self.widget.ntb_Bgsub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
        else:
            x, y = self.model.base_ptn.get_raw()
        self.plot_ctrl.update(limits=[x.min(), x.max(), y.min(), y.max()])

    def apply_pt_to_graph(self):
        if self.model.jcpds_exist():
            self.plot_ctrl.update()

    ###########################################################################
    # base pattern control
    def _load_a_new_pattern(self, new_filename):
        """
        load and process base pattern.  does not signal to update_graph
        """
        self.model.reset_base_ptn()
        self.model.base_ptn.read_file(new_filename)
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        self.model.base_ptn.display = True
        self.widget.textEdit_DiffractionPatternFileName.setText(
            '1D Pattern: ' + self.model.base_ptn.fname)
        self.widget.lineEdit_DiffractionPatternFileName.setText(
            str(self.model.base_ptn.fname))

        x_raw, y_raw = self.model.base_ptn.get_raw()
        if (x_raw.min() >=
            self.widget.doubleSpinBox_Background_ROI_min.value()) or\
                (x_raw.max() <=
                    self.widget.doubleSpinBox_Background_ROI_min.value()):
            self.widget.doubleSpinBox_Background_ROI_min.setValue(x_raw.min())
        if (x_raw.max() <=
            self.widget.doubleSpinBox_Background_ROI_max.value()) or\
                (x_raw.min() >=
                    self.widget.doubleSpinBox_Background_ROI_max.value()):
            self.widget.doubleSpinBox_Background_ROI_max.setValue(x_raw.max())
        self.model.base_ptn.subtract_bg(
            [self.widget.doubleSpinBox_Background_ROI_min.value(),
                self.widget.doubleSpinBox_Background_ROI_max.value()],
            [self.widget.spinBox_BGParam0.value(),
                self.widget.spinBox_BGParam1.value(),
                self.widget.spinBox_BGParam2.value()], yshift=0)
        if self.widget.pushButton_AddRemoveCake.isChecked() and \
                self.model.poni is not None:
            self.cake_ctrl.addremove_cake(update_plot=False)

    def select_base_ptn(self):
        """
        opens a file select dialog
        2017/06/10 remove support for other file formats
        """
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a Chi File", self.chi_path,
            "Data files (*.chi)")[0]
        self._setshow_new_base_ptn(str(filen))

    def goto_next_file(self, move):
        """
        quick move to the next base pattern file
        """
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Choose a base pattern first.")
            return
        filelist = get_sorted_filelist(
            self.chi_path,
            sorted_by_name=self.widget.radioButton_SortbyNme.isChecked())
        idx = find_from_filelist(filelist,
                                 os.path.split(self.model.base_ptn.fname)[1])
        if idx == -1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Cannot find current file")
        if self.widget.radioButton_FileStep1.isChecked():
            step = 1
        else:
            step = 10
        if move == 'next':
            idx_new = idx + step
        elif move == 'previous':
            idx_new = idx - step
        elif move == 'last':
            idx_new = filelist.__len__() - 1
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        elif move == 'first':
            idx_new = 0
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return
        if idx_new > filelist.__len__() - 1:
            idx_new = filelist.__len__() - 1
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        if idx_new < 0:
            idx_new = 0
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return
        new_filename = filelist[idx_new]
        if os.path.exists(new_filename):
            self._load_a_new_pattern(new_filename)
            self.model.base_ptn.color = self.obj_color
            self.plot_ctrl.update()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          new_filename + " does not exist.")

    def load_new_base_pattern_from_name(self):
        if self.widget.lineEdit_DiffractionPatternFileName.isModified():
            filen = str(self.widget.lineEdit_DiffractionPatternFileName.text())
            self._setshow_new_base_ptn(self, filen)

    def _setshow_new_base_ptn(self, filen):
        """
        load and then send signal to update_graph
        """
        if os.path.exists(filen):
            self.chi_path = os.path.split(filen)[0]
            if self.model.base_ptn_exist():
                old_filename = self.model.base_ptn.fname
            else:
                old_filename = None
            new_filename = filen
            self._load_a_new_pattern(new_filename)
            if old_filename is None:
                self.zoom_out_graph()
            else:
                self.plot_ctrl.update()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find ' + filen)
            return
