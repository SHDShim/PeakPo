import os
import copy
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
# import matplotlib.pyplot as plt
from matplotlib import colors
import matplotlib.cm as cmx
from .mplcontroller import MplController
from .jcpdstablecontroller import JcpdsTableController
from utils import xls_jlist, dialog_savefile, make_filename, get_temp_dir, \
    InformationBox, extract_filename, extract_extension
from ds_jcpds import JCPDS
import pymatgen as mg
import datetime

class JcpdsController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.jcpdstable_ctrl = JcpdsTableController(self.model, self.widget)
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_NewJlist.clicked.connect(self.make_jlist)
        self.widget.pushButton_RemoveJCPDS.clicked.connect(self.remove_a_jcpds)
        self.widget.pushButton_AddToJlist.clicked.connect(
            lambda: self.make_jlist(append=True))
        self.widget.checkBox_Intensity.clicked.connect(
            lambda: self._apply_changes_to_graph(limits=None))
        """
        self.widget.pushButton_CheckAllJCPDS.clicked.connect(
            self.check_all_jcpds)
        self.widget.pushButton_UncheckAllJCPDS.clicked.connect(
            self.uncheck_all_jcpds)
        """
        self.widget.pushButton_MoveUp.clicked.connect(self.move_up_jcpds)
        self.widget.pushButton_MoveDown.clicked.connect(self.move_down_jcpds)
        self.widget.pushButton_ExportXLS.clicked.connect(self.save_xls)
        self.widget.pushButton_ViewJCPDS.clicked.connect(self.view_jcpds)
        self.widget.checkBox_JCPDSinPattern.clicked.connect(
            lambda: self._apply_changes_to_graph(limits=None))
        self.widget.checkBox_JCPDSinCake.clicked.connect(
            lambda: self._apply_changes_to_graph(limits=None))
        self.widget.pushButton_ForceUpdatePlot.clicked.connect(
            lambda: self._apply_changes_to_graph(limits=None))
        self.widget.pushButton_SaveTwkJCPDS.clicked.connect(
            self.write_twk_jcpds)

    def _apply_changes_to_graph(self, limits=None):
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
            self.widget, "Choose JPCDS Files", self.model.jcpds_path,
            "(*.jcpds)")[0]
        if files == []:
            return
        self.model.set_jcpds_path(os.path.split(str(files[0]))[0])
        self._make_jlist(files, append=append)

    def _make_jlist(self, files, append=False):
        n_color = 20
        # jet = plt.get_cmap('gist_rainbow')
        jet = cmx.get_cmap('gist_rainbow')
        cNorm = colors.Normalize(vmin=0, vmax=n_color)
        c_index = range(n_color)
        scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=jet)
        c_value = [value for value in c_index]
        """
                   [c_index[0], c_index[3], c_index[6], c_index[1], c_index[4],
                   c_index[7], c_index[2], c_index[5], c_index[8]]
        """
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
            if self.model.append_a_jcpds(str(f), color):
                i += 1
                if i >= n_color - 1:
                    i = 0
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    f+" seems to have errors in format.")
        # display on the QTableWidget
        self.jcpdstable_ctrl.update()
        if self.model.base_ptn_exist():
            self._apply_changes_to_graph()
        else:
            self._apply_changes_to_graph(limits=(0., 25., 0., 100.))

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
        former_below = copy.copy(self.model.jcpds_lst[i])
        former_above = copy.copy(self.model.jcpds_lst[i-1])
        self.model.jcpds_lst[i - 1], self.model.jcpds_lst[i] = \
            former_below, former_above
        # self.model.jcpds_lst[i - 1], self.model.jcpds_lst[i] = \
        #    self.model.jcpds_lst[i], self.model.jcpds_lst[i - 1]
        self.widget.tableWidget_JCPDS.clearContents()
        self.jcpdstable_ctrl.update()
        self.widget.tableWidget_JCPDS.selectRow(i - 1)

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
        former_below = copy.copy(self.model.jcpds_lst[i+1])
        former_above = copy.copy(self.model.jcpds_lst[i])
        self.model.jcpds_lst[i + 1], self.model.jcpds_lst[i] = \
            former_above, former_below
        # self.model.jcpds_lst[i + 1], self.model.jcpds_lst[i] = \
        #    self.model.jcpds_lst[i], self.model.jcpds_lst[i + 1]
        self.widget.tableWidget_JCPDS.clearContents()
        self.jcpdstable_ctrl.update()
        self.widget.tableWidget_JCPDS.selectRow(i + 1)
        """
        self.widget.tableWidget_JCPDS.setCurrentItem(
            self.widget.tableWidget_JCPDS.item(i + 1, 1))
        self.widget.tableWidget_JCPDS.setItemSelected(
            self.widget.tableWidget_JCPDS.item(i + 1, 1), True)
        self.widget.tableWidget_JCPDS.setItemSelected(
            self.widget.tableWidget_JCPDS.item(i, 1), False)
        """
    """
    def check_all_jcpds(self):
        if not self.model.jcpds_exist():
            return
        for phase in self.model.jcpds_lst:
            phase.display = True
        self.jcpdstable_ctrl.update()
        self._apply_changes_to_graph()

    def uncheck_all_jcpds(self):
        if not self.model.jcpds_exist():
            return
        for phase in self.model.jcpds_lst:
            phase.display = False
        self.jcpdstable_ctrl.update()
        self._apply_changes_to_graph()
    """

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
            self._apply_changes_to_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')

    def save_xls(self):
        """
        Export jlist to an excel file
        """
        if not self.model.jcpds_exist():
            return
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        filen_xls_t = make_filename(self.model.get_base_ptn_filename(),
                      'jlist.xls', temp_dir=temp_dir)
        filen_xls = dialog_savefile(self.widget, filen_xls_t)
        if str(filen_xls) == '':
            return
        xls_jlist(filen_xls, self.model.jcpds_lst,
                  self.widget.doubleSpinBox_Pressure.value(),
                  self.widget.doubleSpinBox_Temperature.value())

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
            infobox = InformationBox()
            infobox.setText(textoutput)
            infobox.exec_()
            #self.widget.plainTextEdit_ViewJCPDS.setPlainText(textoutput)

    def write_twk_jcpds(self):
        if not self.model.jcpds_exist():
            return
        idx_checked = [
            s.row() for s in
            self.widget.tableWidget_JCPDS.selectionModel().selectedRows()]

        if idx_checked == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Highlight the name of JCPDS to write twk jcpds.")
            return
        if idx_checked.__len__() != 1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Only one JCPDS card can be written at a time.")
            return
        # get filename to write
        path, __ = os.path.split(self.model.get_base_ptn_filename())
        suggested_filen = os.path.join(
            path,
            self.model.jcpds_lst[idx_checked[0]].name + '-twk.jcpds')
        filen_twk_jcpds = dialog_savefile(self.widget, suggested_filen)
        if filen_twk_jcpds == '':
            return
        # make comments
        comments = "modified from " + \
            self.model.jcpds_lst[idx_checked[0]].file + \
            ", twk for " + \
            self.model.base_ptn.fname
        self.model.jcpds_lst[idx_checked[0]].write_to_twk_jcpds(
            filen_twk_jcpds, comments=comments)
