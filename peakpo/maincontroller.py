from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
# from collections import OrderedDict
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cmx
from matplotlib import colors
from matplotlib.backend_bases import key_press_handler
import pickle
import time
import datetime
import zipfile
from mainwidget import MainWindow
from model import PeakPoModel
# from model import PeakPoModel
from utils import undo_button_press
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
        self.widget.pushButton_NewBasePtn.clicked.connect(self.select_base_ptn)
        self.widget.pushButton_PrevBasePtn.clicked.connect(
            lambda: self.goto_next_file('previous'))
        self.widget.pushButton_NextBasePtn.clicked.connect(
            lambda: self.goto_next_file('next'))
        self.widget.pushButton_LastBasePtn.clicked.connect(
            lambda: self.goto_next_file('last'))
        self.widget.pushButton_FirstBasePtn.clicked.connect(
            lambda: self.goto_next_file('first'))
        self.widget.radioButton_P01.clicked.connect(self.set_pstep)
        self.widget.radioButton_P1.clicked.connect(self.set_pstep)
        self.widget.radioButton_P10.clicked.connect(self.set_pstep)
        self.widget.radioButton_P100.clicked.connect(self.set_pstep)
        self.widget.radioButton_T1.clicked.connect(self.set_tstep)
        self.widget.radioButton_T10.clicked.connect(self.set_tstep)
        self.widget.radioButton_T100.clicked.connect(self.set_tstep)
        self.widget.radioButton_T1000.clicked.connect(self.set_tstep)
        self.widget.pushButton_RoomT.clicked.connect(
            lambda: self.set_temperature(300))
        self.widget.pushButton_1000K.clicked.connect(
            lambda: self.set_temperature(1000))
        self.widget.pushButton_1500K.clicked.connect(
            lambda: self.set_temperature(1500))
        self.widget.pushButton_2000K.clicked.connect(
            lambda: self.set_temperature(2000))
        self.widget.pushButton_2500K.clicked.connect(
            lambda: self.set_temperature(2500))
        self.widget.pushButton_3000K.clicked.connect(
            lambda: self.set_temperature(3000))
        self.widget.pushButton_3500K.clicked.connect(
            lambda: self.set_temperature(3500))
        self.widget.pushButton_4000K.clicked.connect(
            lambda: self.set_temperature(4000))
        self.widget.pushButton_4500K.clicked.connect(
            lambda: self.set_temperature(4500))
        self.widget.pushButton_5000K.clicked.connect(
            lambda: self.set_temperature(5000))
        self.widget.doubleSpinBox_Pressure.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.doubleSpinBox_Temperature.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.pushButton_SaveSession.clicked.connect(self.save_session)
        self.widget.pushButton_LoadSession.clicked.connect(self.load_session)
        self.widget.pushButton_ZipSession.clicked.connect(self.zip_session)
        self.widget.checkBox_IntNorm.clicked.connect(
            self.normalize_waterfall_intensity)
        self.widget.lineEdit_DiffractionPatternFileName.editingFinished.\
            connect(self.load_new_base_pattern_from_name)
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
        # Tab: process
        self.widget.pushButton_UpdatePlots_tab2.clicked.connect(
            self.update_bgsub)
        # Tab: JCPDS List
        self.widget.pushButton_NewJlist.clicked.connect(self.make_jlist)
        self.widget.pushButton_RemoveJCPDS.clicked.connect(self.remove_a_jcpds)
        self.widget.pushButton_AddToJlist.clicked.connect(
            lambda: self.make_jlist(append=True))
        self.widget.pushButton_SaveJlist.clicked.connect(self.save_session)
        self.widget.pushButton_LoadJlist.clicked.connect(self.load_jlist)
        self.widget.pushButton_ViewJCPDS.clicked.connect(self.view_jcpds)
        self.widget.checkBox_Intensity.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.doubleSpinBox_SetWavelength.valueChanged.connect(
            self.apply_wavelength)
        self.widget.pushButton_CheckAllJCPDS.clicked.connect(
            self.check_all_jcpds)
        self.widget.pushButton_UncheckAllJCPDS.clicked.connect(
            self.uncheck_all_jcpds)
        self.widget.pushButton_MoveUp.clicked.connect(self.move_up_jcpds)
        self.widget.pushButton_MoveDown.clicked.connect(self.move_down_jcpds)
        self.widget.pushButton_ExportXLS.clicked.connect(self.save_xls)
        self.widget.pushButton_SaveCHI.clicked.connect(self.save_bgsubchi)
        self.widget.pushButton_ExportToUCFit.clicked.connect(
            self.export_to_ucfit)
        # Tab: Cake
        self.widget.pushButton_AddRemoveCake.clicked.connect(
            self.addremove_cake)
        self.widget.pushButton_GetPONI.clicked.connect(self.get_poni)
        self.widget.pushButton_ApplyCakeView.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.pushButton_ApplyMask.clicked.connect(self.apply_mask)
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

    def load_new_base_pattern_from_name(self):
        if self.widget.lineEdit_DiffractionPatternFileName.isModified():
            filen = str(self.widget.lineEdit_DiffractionPatternFileName.text())
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
                    self.update_graph()
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, 'Warning', 'Cannot find ' + filen)
                return

    def addremove_cake(self):
        """
        Cake function
        Add/remove cake to the graph
        """
        self._addremove_cake()
        self.update_graph()

    def _addremove_cake(self):
        if not self.widget.pushButton_AddRemoveCake.isChecked():
            self.widget.pushButton_AddRemoveCake.setText('Add Cake')
            return
        else:
            self.widget.pushButton_AddRemoveCake.setText('Remove Cake')
        if not self.model.poni_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose PONI file first.')
            undo_button_press(
                self.widget.pushButton_AddRemoveCake,
                released_text='Add Cake', pressed_text='Remove Cake')
            return
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose CHI file first.')
            undo_button_press(
                self.widget.pushButton_AddRemoveCake,
                released_text='Add Cake', pressed_text='Remove Cake')
            return
        filen_tif = self.model.make_filename('tif')
        if not os.path.exists(filen_tif):
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find %s.' % filen_tif)
            undo_button_press(
                self.widget.pushButton_AddRemoveCake,
                released_text='Add Cake', pressed_text='Remove Cake')
            return
        if self.model.diff_img_exist() and \
                self.model.same_filename_as_base_ptn(
                self.model.diff_img.img_filename):
            return
        self._load_new_image(filen_tif)
        self._update_cake()

    def _load_new_image(self, filen_tif):
        """
        Cake function
        Load new image for cake view.  Cake should be the same as base pattern.
        """
        self.model.reset_diff_img()
        self.model.diff_img.load(filen_tif)
        self.widget.textEdit_DiffractionImageFilename.setText(
            '2D Image: ' + filen_tif)

    def apply_mask(self):
        self._update_cake()
        self.update_graph()

    def _update_cake(self):
        """
        Cake function
        Reprocess to get cake.  Slower re-processing
        """
        self.model.diff_img.set_calibration(self.model.poni)
        self.model.diff_img.set_mask((self.widget.spinBox_MaskMin.value(),
                                      self.widget.spinBox_MaskMax.value()))
        self.model.diff_img.integrate_to_cake()
        intensity_cake, tth_cake, chi_cake = self.model.diff_img.get_cake()
        self.intensity_cake = intensity_cake
        self.tth_cake = tth_cake
        self.chi_cake = chi_cake

    def get_poni(self):
        """
        Cake function
        Opens a pyFAI calibration file
        """
        file = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a PONI File",
            self.chi_path, "PONI files (*.poni)")[0]
        if os.path.exists(str(file)):
            poni_path, dum = os.path.split(str(file))
            # I am unsure poni_path would be needed to be self
            self.poni_path = poni_path
            self.model.poni = str(file)
            self.widget.textEdit_PONI.setText('PONI: ' + self.model.poni)
            if self.model.diff_img_exist():
                self._update_cake()
            self.update_graph()

    def normalize_waterfall_intensity(self):
        """
        Waterfall function
        Need documentation for its function
        """
        if not self.model.waterfall_exist():
            return
        count = 0
        for wf in self.model.waterfall_ptn:
            if wf.display:
                count += 1
        if count == 0:
            return
        # update figure
        self.update_graph()
        return

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
            self.update_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')

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
        self._list_jcpds()
        self.update_graph()
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
                self.update_graph()

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
                    self.update_graph()

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
            self.update_graph()
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
            self.update_graph([lims[0], lims[1], yroi.min(), yroi.max()])
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
        self.update_graph(new_lims)

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

    def _find_a_jcpds(self):
        idx_checked = \
            self.widget.tableWidget_JCPDS.selectionModel().selectedRows()
        if idx_checked == []:
            print('no row selected')
            return None
        else:
            return idx_checked[0].row()

    def _find_a_wf(self):
        idx_checked = [
            s.row() for s in
            self.widget.tableWidget_wfPatterns.selectionModel().selectedRows()]
        if idx_checked == []:
            return None
        else:
            return idx_checked[0]

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
        """
        self.widget.tableWidget_JCPDS.setCurrentItem(
            self.widget.tableWidget_JCPDS.item(i - 1, 1))
        """
        # self.widget.tableWidget_JCPDS.setCurrentItem(
        #    self.widget.tableWidget_JCPDS.item(i, 1), False)
        """
        self.widget.tableWidget_JCPDS.setItemSelected(
            self.widget.tableWidget_JCPDS.item(i - 1, 1), True)
        self.widget.tableWidget_JCPDS.setItemSelected(
            self.widget.tableWidget_JCPDS.item(i, 1), False)
        """
        self._list_jcpds()

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
        self._list_jcpds()

    def check_all_jcpds(self):
        if not self.model.jcpds_exist():
            return
        for j in self.model.jcpds_lst:
            j.display = True
        self._list_jcpds()
        self.update_graph()

    def uncheck_all_jcpds(self):
        if not self.model.jcpds_exist():
            return
        for j in self.model.jcpds_lst:
            j.display = False
        self._list_jcpds()
        self.update_graph()

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
        self._list_wfpatterns()
        self._list_jcpds()

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
        self._set_nightday_view()
        self._list_wfpatterns()
        self.update_graph()

    def _set_nightday_view(self):
        if not self.widget.ntb_NightView.isChecked():
            self.widget.mpl.canvas.set_toNight(False)
            # reset plot objects with white
            if self.model.base_ptn_exist():
                self.model.base_ptn.color = 'k'
            if self.model.waterfall_exist():
                for pattern in self.model.waterfall_ptn:
                    if (pattern.color == 'white') or \
                            (pattern.color == '#ffffff'):
                        pattern.color = 'k'
            self.obj_color = 'k'
        else:
            self.widget.mpl.canvas.set_toNight(True)
            if self.model.base_ptn_exist():
                self.model.base_ptn.color = 'white'
            if self.model.waterfall_exist():
                for pattern in self.model.waterfall_ptn:
                    if (pattern.color == 'k') or (pattern.color == '#000000'):
                        pattern.color = 'white'
            self.obj_color = 'white'

    def add_patterns(self):
        """ get files for waterfall plot """
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Pick a base pattern first.")
            return
        files = QtWidgets.QFileDialog.getOpenFileNames(
            self.widget,
            "Choose additional data files", self.chi_path,
            "Data files (*.chi)")[0]
        if files is None:
            return
        new_patterns = []
        for f in files:
            filename = str(f)
            pattern = PatternPeakPo()
            pattern.read_file(filename)
            pattern.wavelength = \
                self.widget.doubleSpinBox_SetWavelength.value()
            pattern.display = False
            bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                      self.widget.doubleSpinBox_Background_ROI_max.value()]
            bg_params = [self.widget.spinBox_BGParam0.value(),
                         self.widget.spinBox_BGParam1.value(),
                         self.widget.spinBox_BGParam2.value()]
            pattern.get_chbg(bg_roi, bg_params, yshift=0)
            new_patterns.append(pattern)
        self.model.waterfall_ptn += new_patterns
        self._list_wfpatterns()
        i = 0
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                i += 1
        if i != 0:
            self.update_graph()

    def _list_wfpatterns(self):
        """show a list of jcpds in the list window of tab 3"""
        n_columns = 4
        n_rows = self.model.waterfall_ptn.__len__()  # count for number of jcpds
        self.widget.tableWidget_wfPatterns.setColumnCount(n_columns)
        self.widget.tableWidget_wfPatterns.setRowCount(n_rows)
        self.widget.tableWidget_wfPatterns.horizontalHeader().setVisible(True)
        self.widget.tableWidget_wfPatterns.setHorizontalHeaderLabels(
            ['', 'Color', 'Color change', 'Wavelength'])
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
                QtWidgets.QPushButton('change')
            self.widget.tableWidget_wfPatterns.item(row, 1).setBackground(
                QtGui.QColor(self.model.waterfall_ptn[row].color))
            self.widget.tableWidget_wfPatterns_pushButton_color.clicked.\
                connect(self._wfPatterns_handle_ColorButtonClicked)
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
                    self._wfPatterns_handle_doubleSpinBoxChanged)
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
            self._wfPatterns_handle_ItemClicked)
        i = 0
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                i += 1
        if i != 0:
            self.update_graph()

    def _wfPatterns_handle_doubleSpinBoxChanged(self, value):
        box = self.widget.sender()
        index = self.widget.tableWidget_wfPatterns.indexAt(box.pos())
        if index.isValid():
            idx = index.row()
            self.model.waterfall_ptn[idx].wavelength = value
            i = 0
            for pattern in self.model.waterfall_ptn:
                if pattern.display:
                    i += 1

    def _wfPatterns_handle_ColorButtonClicked(self):
        button = self.widget.sender()
        index = self.widget.tableWidget_wfPatterns.indexAt(button.pos())
        if index.isValid():
            idx = index.row()
            if index.column() == 2:
                color = QtWidgets.QColorDialog.getColor()
                if color.isValid():
                    self.widget.tableWidget_wfPatterns.item(idx, 2).\
                        setBackground(color)
                    self.model.waterfall_ptn[idx].color = str(color.name())
                    i = 0
                    for pattern in self.model.waterfall_ptn:
                        if pattern.display:
                            i += 1
                    if i != 0:
                        self.update_graph()

    def _wfPatterns_handle_ItemClicked(self, item):
        if item.column() == 0:
            idx = item.row()
            if item.checkState() == QtCore.Qt.Checked:
                self.model.waterfall_ptn[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.waterfall_ptn[idx].display = False
            self.update_graph()
        else:
            return

    def load_jlist(self):
        """get existing jlist file from data folder"""
        fn_jlist = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.chi_path, "(*.ppss)")[0]
        if fn_jlist == '':
            return
        self._load_session(fn_jlist, True)
        self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn_jlist))
        self._list_jcpds()
        self.update_graph()

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
#        self._list_jcpds()
            self.update_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')

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

    def _list_jcpds(self):
        """show jcpds cards in the QTableWidget"""
        n_columns = 10
        n_rows = self.model.jcpds_lst.__len__()  # count for number of jcpds
        self.widget.tableWidget_JCPDS.setColumnCount(n_columns)
        self.widget.tableWidget_JCPDS.setRowCount(n_rows)
        self.widget.tableWidget_JCPDS.horizontalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.verticalHeader().setVisible(True)
        self.widget.tableWidget_JCPDS.setHorizontalHeaderLabels(
            ['', 'Color', 'Color Change', 'V0 Tweak', 'K0 Tweak', 'K0p Tweak',
             'alpha0 Tweak', 'b/a Tweak', 'c/a Tweak', 'Int Tweak'])
        self.widget.tableWidget_JCPDS.setVerticalHeaderLabels(
            [j.name for j in self.model.jcpds_lst])
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
                QtWidgets.QPushButton('change')
            self.widget.tableWidget_JCPDS.item(row, 1).setBackground(
                QtGui.QColor(self.model.jcpds_lst[row].color))
            self.widget.tableWidget_JCPDS_pushButton_color.clicked.connect(
                self._jcpds_handle_ColorButtonClicked)
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
                connect(self._jcpds_handle_doubleSpinBoxChanged)
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
                connect(self._jcpds_handle_doubleSpinBoxChanged)
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
                connect(self._jcpds_handle_doubleSpinBoxChanged)
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
                valueChanged.connect(self._jcpds_handle_doubleSpinBoxChanged)
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
                        self._jcpds_handle_doubleSpinBoxChanged)
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
                        self._jcpds_handle_doubleSpinBoxChanged)
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
                connect(self._jcpds_handle_doubleSpinBoxChanged)
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
            self._jcpds_handle_ItemClicked)

    def _jcpds_handle_doubleSpinBoxChanged(self, value):
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
                self.update_graph()

    def _jcpds_handle_ColorButtonClicked(self):
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
                    self.update_graph()

    def _jcpds_handle_ItemClicked(self, item):
        if item.column() == 0:
            idx = item.row()
            if (item.checkState() == QtCore.Qt.Checked) ==\
                    self.model.jcpds_lst[idx].display:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.model.jcpds_lst[idx].display = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.model.jcpds_lst[idx].display = False
            self.update_graph()
        else:
            return

    def make_jlist(self, append=False):
        """collect files for jlist"""
        files = QtWidgets.QFileDialog.getOpenFileNames(
            self.widget, "Choose JPCDS Files", self.jcpds_path, "(*.jcpds)")[0]
        if files == []:
            return
        # reset jcpds_path
        self.jcpds_path, dum = os.path.split(str(files[0]))
        # construct jlist and assign default values
        jlist = []
#        for f, c in zip(files, colors.cnames):
#        n_files = files.__len__()
        n_color = 9
        jet = plt.get_cmap('gist_rainbow')
        cNorm = colors.Normalize(vmin=0, vmax=n_color)
        val = range(n_color)
        scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=jet)
        values = [val[0], val[3], val[6], val[1], val[4], val[7], val[2],
                  val[5], val[8]]
        if append:
            n_existingjcpds = self.model.jcpds_lst.__len__()
            n_addedjcpds = files.__len__()
            if ((n_existingjcpds + n_addedjcpds) > n_color):
                i = 0
            else:
                i = n_existingjcpds
        else:
            i = 0
        for f in files:
            phase = JCPDSplt()
            phase.read_file(str(f))  # phase.file = f
            phase.color = colors.rgb2hex(scalarMap.to_rgba(values[i]))
            jlist.append(phase)
            i += 1
        if append:
            self.model.jcpds_lst += jlist
        else:  # initiate self.model.jcpds_lst
            self.model.reset_jcpds_lst()
            self.model.jcpds_lst = jlist
        # display on the QTableWidget
        self._list_jcpds()
        if not self.model.base_ptn_exist():
            self.update_graph(limits=[0., 25., 0., 100.])
        else:
            self.update_graph()

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

    def erase_waterfall(self):
        self.model.reset_waterfall_ptn()
        self.widget.tableWidget_wfPatterns.clearContents()
        self.update_graph()

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
            self.update_graph()

    def move_up_waterfall(self):
        # get selected cell number
        idx_selected = self._find_a_wf()
        if idx_selected is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Highlight the item to move first.")
            return
        i = idx_selected
        self.model.waterfall_ptn[i - 1], self.model.waterfall_ptn[i] = \
            self.model.waterfall_ptn[i], self.model.waterfall_ptn[i - 1]
        self.widget.tableWidget_wfPatterns.selectRow(i - 1)
        self._list_wfpatterns()

    def move_down_waterfall(self):
        idx_selected = self._find_a_wf()
        if idx_selected is None:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Highlight the item to move first.")
            return
        i = idx_selected
        self.model.waterfall_ptn[i + 1], self.model.waterfall_ptn[i] = \
            self.model.waterfall_ptn[i], self.model.waterfall_ptn[i + 1]
        self.widget.tableWidget_wfPatterns.selectRow(i + 1)
        self._list_wfpatterns()

    def apply_changes_to_graph(self, value):
        self.update_graph()

    def apply_wavelength(self):
        # self.wavelength = value
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        self.update_graph()

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
        self.update_graph(limits=[x.min(), x.max(), y.min(), y.max()])

    def apply_pt_to_graph(self):
        if self.model.jcpds_exist():
            self.update_graph()

    def set_temperature(self, temperature=None):
        self.widget.doubleSpinBox_Temperature.setValue(temperature)
#        if self.model.jcpds_lst != []:
#            self.update_graph()

    def set_pstep(self, value):
        if self.widget.radioButton_P01.isChecked():
            value = 0.1
        elif self.widget.radioButton_P10.isChecked():
            value = 10.
        elif self.widget.radioButton_P100.isChecked():
            value = 100.
        else:
            value = 1.
        self.widget.doubleSpinBox_Pressure.setSingleStep(value)

    def set_tstep(self, value):
        if self.widget.radioButton_T1.isChecked():
            value = 1.
        elif self.widget.radioButton_T10.isChecked():
            value = 10.
        elif self.widget.radioButton_T1000.isChecked():
            value = 1000.
        else:
            value = 100.
        self.widget.doubleSpinBox_Temperature.setSingleStep(value)

    ###########################################################################
    # base pattern control
    def _load_a_new_pattern(self, new_filename):
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
            self._addremove_cake()
            # self._load_new_image()
            # self._update_cake()

    def select_base_ptn(self):
        """
        opens a file select dialog

        2017/06/10 remove support for other file formats than chi
        """
        file = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a Chi File", self.chi_path,
            "Data files (*.chi)")[0]
        chi_path, dum = os.path.split(str(file))
        if os.path.exists(str(file)):
            self.chi_path = chi_path
            if self.model.base_ptn_exist():
                old_filename = self.model.base_ptn.fname
            else:
                old_filename = ''
            new_filename = str(file)
            self._load_a_new_pattern(new_filename)
            if old_filename == '':
                self.zoom_out_graph()
            else:
                self.update_graph()

    def goto_next_file(self, move):
        """quick move to the next file"""
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
            # Turn off the option below during synchrotron.  Not helping much.
            # self._update_session()
            self.update_graph()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          new_filename + " does not exist.")

    def update_graph(self, limits=None):
        """Updates the graph"""
        t_start = time.time()
        self.widget.setCursor(QtCore.Qt.WaitCursor)
        if limits is None:
            limits = self.widget.mpl.canvas.ax_pattern.axis()
        if (not self.model.base_ptn_exist()) and \
                (not self.model.jcpds_exist()):
            return
        if self.widget.pushButton_AddRemoveCake.isChecked():
            self.widget.mpl.canvas.resize_axes(
                self.widget.spinBox_CakeAxisSize.value())
            self._plot_cake()
        else:
            self.widget.mpl.canvas.resize_axes(1)
        self._set_nightday_view()
        if self.model.base_ptn_exist():
            self.widget.mpl.canvas.fig.suptitle(
                self.model.base_ptn.fname, color=self.obj_color, fontsize=16)
            self._plot_diffpattern()
            if self.model.waterfall_exist():
                self._plot_waterfallpatterns()
        if self.model.jcpds_exist():
            self._plot_jcpds()
        if self.model.ucfit_exist():
            self._plot_ucfit()
        self.widget.mpl.canvas.ax_pattern.set_xlim(limits[0], limits[1])
        if not self.widget.ntb_ResetY.isChecked():
            self.widget.mpl.canvas.ax_pattern.set_ylim(limits[2], limits[3])
        xlabel = 'Two Theta (degrees), ' + \
            "{0: 5.1f} GPa, {1: 4.0f} K, {2: 6.4f} A".\
            format(self.widget.doubleSpinBox_Pressure.value(),
                   self.widget.doubleSpinBox_Temperature.value(),
                   self.widget.doubleSpinBox_SetWavelength.value())
        self.widget.mpl.canvas.ax_pattern.set_xlabel(xlabel)
        # if I move the line below to elsewhere I cannot get ylim or axis
        # self.widget.mpl.canvas.ax_pattern.autoscale(
        # enable=False, axis=u'both', tight=True)
        """Removing the lines below for the tick reduce the plot time
        significantly.  So do not turn this on.
        x_size = limits[1] - limits[0]
        if x_size <= 50.:
            majortick_interval = 1
            minortick_interval = 0.1
        else:
            majortick_interval = 10
            minortick_interval = 1
        majorLocator = MultipleLocator(majortick_interval)
        minorLocator = MultipleLocator(minortick_interval)
        self.widget.mpl.canvas.ax_pattern.xaxis.set_major_locator(majorLocator)
        self.widget.mpl.canvas.ax_pattern.xaxis.set_minor_locator(minorLocator)
        """
        self.widget.mpl.canvas.draw()
        print("Plot takes: {0:.4f} s at".format(time.time() - t_start),
              str(datetime.datetime.now()))
        self.widget.unsetCursor()

    def _plot_ucfit(self):
        i = 0
        for j in self.model.ucfit_lst:
            if j.display:
                i += 1
        if i == 0:
            return
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        bar_scale = 1. / 100. * axisrange[3]
        i = 0
        for phase in self.model.ucfit_lst:
            if phase.display:
                phase.cal_dsp()
                tth, inten = phase.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                bar_min = np.ones(tth.shape) * axisrange[2]
                intensity = inten
                bar_min = np.ones(tth.shape) * axisrange[2]
                self.widget.tableWidget_UnitCell.removeCellWidget(i, 3)
                Item4 = QtWidgets.QTableWidgetItem(
                    "{:.3f}".format(float(phase.v)))
                Item4.setFlags(
                    QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(i, 3, Item4)
                if self.widget.checkBox_Intensity.isChecked():
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, intensity * bar_scale,
                        colors=phase.color)
                else:
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, 100. * bar_scale, colors=phase.color)
            i += 1

    def _plot_cake(self):
        climits = (self.widget.spinBox_VMin.value(),
                   self.widget.spinBox_VMax.value())
        self.widget.mpl.canvas.ax_cake.imshow(
            self.intensity_cake, origin="lower",
            extent=[self.tth_cake.min(), self.tth_cake.max(),
                    self.chi_cake.min(), self.chi_cake.max()],
            aspect="auto", cmap="gray_r", clim=climits)
        # print("Cake plot takes: %.4f second" % (time.time() - t_start))

    def _plot_jcpds(self):
        i = 0
        for phase in self.model.jcpds_lst:
            if phase.display:
                i += 1
        if i == 0:
            return
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        bar_scale = 1. / 100. * axisrange[3]
        for phase in self.model.jcpds_lst:
            if phase.display:
                phase.cal_dsp(self.widget.doubleSpinBox_Pressure.value(),
                              self.widget.doubleSpinBox_Temperature.value())
                tth, inten = phase.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                intensity = inten * phase.twk_int
                bar_min = np.ones(tth.shape) * axisrange[2]
                if self.widget.checkBox_Intensity.isChecked():
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, intensity * bar_scale,
                        colors=phase.color,
                        label=phase.name + (", %.3f A^3" % phase.v))
                else:
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, 100. * bar_scale,
                        colors=phase.color,
                        label=phase.name + (", %.3f A^3" % phase.v))
                if self.widget.pushButton_AddRemoveCake.isChecked():
                    for tth_i in tth:
                        self.widget.mpl.canvas.ax_cake.axvline(
                            x=tth_i, color=phase.color, lw=0.5)
            else:
                pass
        leg_jcpds = self.widget.mpl.canvas.ax_pattern.legend(
            loc=1, prop={'size': 10}, framealpha=0., handlelength=1)

        for line, txt in zip(leg_jcpds.get_lines(), leg_jcpds.get_texts()):
            txt.set_color(line.get_color())
        # print("JCPDS plot takes: %.4f second" % (time.time() - t_start))

    def _plot_waterfallpatterns(self):
        # t_start = time.time()
        # count how many are dispaly
        i = 0
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                i += 1
        if i == 0:
            return
        n_display = i
        j = 0  # this is needed for waterfall gaps
        # get y_max
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                j += 1
                self.widget.mpl.canvas.ax_pattern.text(
                    0.01, 0.97 - n_display * 0.05 + j * 0.05,
                    os.path.basename(pattern.fname),
                    transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                    color=pattern.color)
                if self.widget.ntb_Bgsub.isChecked():
                    ygap = self.widget.doubleSpinBox_WaterfallGaps.value() * \
                        self.model.base_ptn.y_bgsub.max() * float(j)
                    if self.widget.checkBox_BasePtnBackground.isChecked() and \
                            np.array_equal(pattern.x_raw,
                                           self.model.base_ptn.x_raw):
                        y_bgsub = pattern.y_bgsub + pattern.y_bg - \
                            self.model.base_ptn.y_bg
                    else:
                        y_bgsub = pattern.y_bgsub
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = y_bgsub / y_bgsub.max() * \
                            self.model.base_ptn.y_bgsub.max()
                    else:
                        y = y_bgsub
                    x_t = pattern.x_bgsub
                else:
                    ygap = self.widget.doubleSpinBox_WaterfallGaps.value() * \
                        self.model.base_ptn.y_raw.max() * float(j)
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = pattern.y_raw / pattern.y_raw.max() *\
                            self.model.base_ptn.y_raw.max()
                    else:
                        y = pattern.y_raw
                    x_t = pattern.x_raw
                if self.widget.checkBox_SetToBasePtnLambda.isChecked():
                    x = convert_tth(x_t, pattern.wavelength,
                                    self.model.base_ptn.wavelength)
                else:
                    x = x_t
                self.widget.mpl.canvas.ax_pattern.plot(x, y + ygap, c=pattern.color)
        self.widget.mpl.canvas.ax_pattern.text(
            0.01, 0.97 - n_display * 0.05,
            os.path.basename(self.model.base_ptn.fname),
            transform=self.widget.mpl.canvas.ax_pattern.transAxes,
            color=self.model.base_ptn.color)

    def _plot_diffpattern(self):
        if self.widget.ntb_Bgsub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
            self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=self.model.base_ptn.color)
        else:
            x, y = self.model.base_ptn.get_raw()
            self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=self.model.base_ptn.color)
            x_bg, y_bg = self.model.base_ptn.get_background()
            self.widget.mpl.canvas.ax_pattern.plot(
                x_bg, y_bg, c=self.model.base_ptn.color, lw=0.5)
