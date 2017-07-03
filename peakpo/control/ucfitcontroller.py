from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from .mplcontroller import MplController
from .ucfittablecontroller import UcfitTableController
from utils import SpinBoxFixStyle
from utils import xls_ucfitlist, dialog_savefile


class UcfitController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_RemoveUClist.clicked.connect(self.remove_ucfit)
        self.widget.pushButton_ExportXLS_2.clicked.connect(self.export_to_xls)

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

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
            self._apply_changes_to_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'In order to remove, highlight the names.')

    def export_to_xls(self):
        """
        Export ucfitlist to an excel file
        """
        if not self.model.ucfit_exist():
            return
        new_filen_xls = self.model.make_filename('peakpo.ucfit.xls')
        filen_xls = dialog_savefile(self.widget, new_filen_xls)
        if str(filen_xls) == '':
            return
        xls_ucfitlist(filen_xls, self.model.ucfit_lst)
