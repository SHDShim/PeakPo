from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import QtGui
from .mplcontroller import MplController
from ..utils import SpinBoxFixStyle
from ..utils import xls_ucfitlist, dialog_savefile


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

    def _included_duplicate_rows(self):
        if self.phase is None or self.phase not in self.ucfit_model:
            return set()
        counts = {}
        for peak in self.ucfit_model[self.phase]:
            if not bool(peak.get('display', True)):
                continue
            hkl = self._hkl_key(peak)
            counts[hkl] = counts.get(hkl, 0) + 1
        duplicate_rows = set()
        for row, peak in enumerate(self.ucfit_model[self.phase]):
            if not bool(peak.get('display', True)):
                continue
            if counts.get(self._hkl_key(peak), 0) > 1:
                duplicate_rows.add(row)
        return duplicate_rows

    def _hkl_key(self, peak):
        return (
            int(round(float(peak['h']))),
            int(round(float(peak['k']))),
            int(round(float(peak['l']))),
        )

    def _style_unit_cell_row_item(self, item, duplicate=False):
        if duplicate:
            item.setBackground(QtGui.QBrush(QtGui.QColor("#5c2d2d")))
            item.setForeground(QtGui.QBrush(QtGui.QColor("#ffd6d6")))
            item.setToolTip(
                "Included data point has the same Miller index as another included row.")
        return item

    def update(self, phase):
        """
        Show ucfit in the QTableWidget
        data4ucfit should be a list and individual elements should be dictionary
        {'h';'k';'l';'twoth';'display'}
        """
        self.phase = phase
        if self.phase == None:
            return
        n_columns = 7
        n_rows = len(self.ucfit_model[self.phase])  # count for number of jcpds
        self.widget.tableWidget_UnitCell.setColumnCount(n_columns)
        self.widget.tableWidget_UnitCell.setRowCount(n_rows)
        self.widget.tableWidget_UnitCell.horizontalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.verticalHeader().setVisible(True)
        self.widget.tableWidget_UnitCell.setHorizontalHeaderLabels(
            ['Include', 'h', 'k', 'l', 'Two Theta', 'Source', 'Azimuth'])
        self.widget.tableWidget_UnitCell.setVerticalHeaderLabels(
            [str(i) for i in range(n_rows)])
        duplicate_rows = self._included_duplicate_rows()
        for row in range(n_rows):
            duplicate = row in duplicate_rows
            # column 0 - checkbox
            item0 = QtWidgets.QTableWidgetItem()
            item0.setFlags(
                QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            if self.ucfit_model[self.phase][row]['display']:
                item0.setCheckState(QtCore.Qt.Checked)
            else:
                item0.setCheckState(QtCore.Qt.Unchecked)
            self._style_unit_cell_row_item(item0, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 0, item0)
            # column 1 - h
            Item1 = QtWidgets.QTableWidgetItem(
                "{:.0f}".format(float(self.ucfit_model[self.phase][row]['h'])))
            Item1.setFlags(QtCore.Qt.ItemIsEnabled)
            self._style_unit_cell_row_item(Item1, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 1, Item1)
            # column 2 - k
            Item2 = QtWidgets.QTableWidgetItem(
                "{:.0f}".format(float(self.ucfit_model[self.phase][row]['k'])))
            Item2.setFlags(QtCore.Qt.ItemIsEnabled)
            self._style_unit_cell_row_item(Item2, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 2, Item2)
            # column 3 - l
            Item3 = QtWidgets.QTableWidgetItem(
                "{:.0f}".format(float(self.ucfit_model[self.phase][row]['l'])))
            Item3.setFlags(QtCore.Qt.ItemIsEnabled)
            self._style_unit_cell_row_item(Item3, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 3, Item3)
            # column 4 - twoth
            Item4 = QtWidgets.QTableWidgetItem(
                "{:.3f}".format(
                    float(self.ucfit_model[self.phase][row]['twoth'])))
            Item4.setFlags(QtCore.Qt.ItemIsEnabled)
            self._style_unit_cell_row_item(Item4, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 4, Item4)
            Item5 = QtWidgets.QTableWidgetItem(
                str(self.ucfit_model[self.phase][row].get('source', 'Full CHI')))
            Item5.setFlags(QtCore.Qt.ItemIsEnabled)
            self._style_unit_cell_row_item(Item5, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 5, Item5)
            Item6 = QtWidgets.QTableWidgetItem(
                str(self.ucfit_model[self.phase][row].get('azimuth', '')))
            Item6.setFlags(QtCore.Qt.ItemIsEnabled)
            self._style_unit_cell_row_item(Item6, duplicate)
            self.widget.tableWidget_UnitCell.setItem(row, 6, Item6)
        self.widget.tableWidget_UnitCell.resizeColumnsToContents()
#        self.widget.tableWidget_UnitCell.resizeRowsToContents()
        try:
            self.widget.tableWidget_UnitCell.itemClicked.disconnect(
                self._handle_ItemClicked)
        except Exception:
            pass
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
            self.update(self.phase)
            self._apply_changes_to_graph()

    """
    def update_steps_only(self, step):
        self.widget.tableWidget_UnitCell.clear()
        self.update(step=step)
    """
