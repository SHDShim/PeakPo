from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
from .mplcontroller import MplController
from utils import SpinBoxFixStyle
from utils import xls_ucfitlist, dialog_savefile


class UcfitTableController(object):

    def __init__(self, model, ucfit_model, phase, widget):
        self.model = model
        self.ucfit_model = ucfit_model
        self.phase = phase
        self.widget = widget
        # the new ucfit will update after conducting the fit
        # update the JCPDS list and check the box and then update the plot
        self.plot_ctrl = MplController(self.model, self.widget)

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def update(self, phase):
        """
        Show ucfit in the QTableWidget
        data4ucfit should be a list and individual elements should be dictionary
        {'h';'k';'l';'twoth';'display'}
        """
        self.phase = phase
        if self.phase == None:
            return
        n_columns = 5
        n_rows = len(self.ucfit_model[self.phase])  # count for number of jcpds
        self.widget.tableWidget_UnitCell.setColumnCount(n_columns)
        self.widget.tableWidget_UnitCell.setRowCount(n_rows)
        self.widget.tableWidget_UnitCell.horizontalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.verticalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.setHorizontalHeaderLabels(
            ['Include', 'h', 'k', 'l', 'Two Theta'])
        self.widget.tableWidget_UnitCell.setVerticalHeaderLabels(
            [str(i) for i in range(n_rows)])
        for row in range(n_rows):
            # column 0 - checkbox
            item0 = QtWidgets.QTableWidgetItem()
            item0.setFlags(
                QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            if self.ucfit_model[self.phase][row]['display']:
                item0.setCheckState(QtCore.Qt.Checked)
            else:
                item0.setCheckState(QtCore.Qt.Unchecked)
            self.widget.tableWidget_UnitCell.setItem(row, 0, item0)
            # column 1 - h
            Item1 = QtWidgets.QTableWidgetItem(
                "{:.0f}".format(float(self.ucfit_model[self.phase][row]['h'])))
            Item1.setFlags(QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_UnitCell.setItem(row, 1, Item1)
            # column 2 - k
            Item2 = QtWidgets.QTableWidgetItem(
                "{:.0f}".format(float(self.ucfit_model[self.phase][row]['k'])))
            Item2.setFlags(QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_UnitCell.setItem(row, 2, Item2)
            # column 3 - l
            Item3 = QtWidgets.QTableWidgetItem(
                "{:.0f}".format(float(self.ucfit_model[self.phase][row]['l'])))
            Item3.setFlags(QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_UnitCell.setItem(row, 3, Item3)
            # column 4 - twoth
            Item4 = QtWidgets.QTableWidgetItem(
                "{:.3f}".format(
                    float(self.ucfit_model[self.phase][row]['twoth'])))
            Item4.setFlags(QtCore.Qt.ItemIsEnabled)
            self.widget.tableWidget_UnitCell.setItem(row, 4, Item4)
        self.widget.tableWidget_UnitCell.resizeColumnsToContents()
#        self.widget.tableWidget_UnitCell.resizeRowsToContents()
        self.widget.tableWidget_UnitCell.itemClicked.connect(
            self._handle_ItemClicked)

    def _handle_ItemClicked(self, item):
        if item.column() == 0:
            idx = item.row()
            if (item.checkState() == QtCore.Qt.Checked) == \
                    self.ucfit_model[self.phase][idx]['display']:
                return
            if item.checkState() == QtCore.Qt.Checked:
                self.ucfit_model[self.phase][idx]['display'] = True
            elif item.checkState() == QtCore.Qt.Unchecked:
                self.ucfit_model[self.phase][idx]['display'] = False
            self._apply_changes_to_graph()

    """
    def update_steps_only(self, step):
        self.widget.tableWidget_UnitCell.clear()
        self.update(step=step)
    """
