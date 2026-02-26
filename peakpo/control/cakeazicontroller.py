import os
from qtpy import QtWidgets
import numpy as np
from ..utils import dialog_savefile, writechi
from .mplcontroller import MplController
from .cakemakecontroller import CakemakeController

class CakeAziController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.cakemake_ctrl = CakemakeController(self.model, self.widget)
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        """
        Integrate handling exists in maincontroller.py
        """
        # self.widget.pushButton_IntegrateCake.clicked.connect(self.integrate_to_1d)
        self.widget.pushButton_AddAzi.clicked.connect(
            self._add_azi_to_list)
        self.widget.pushButton_RemoveAzi.clicked.connect(
            self._remove_azi_from_list)
        self.widget.pushButton_ClearAziList.clicked.connect(
            self._clear_azilist)
        self.widget.pushButton_InvertCakeBoxes.clicked.connect(
            self._invert_cake_selections)
        self.widget.pushButton_SaveCakeMarkerFile.clicked.connect(
            self._save_cake_marker_file)
        self.widget.pushButton_LoadCakeMarkerFile.clicked.connect(
            self._load_cake_marker_file)
        self.widget.pushButton_HighlightSelectedMarker.clicked.connect(
            self._apply_changes_to_graph)

    def _save_cake_marker_file(self):
        azi_list = self._read_azilist()
        if azi_list is None:
            return
        ext = "cake.marker"
        filen_t = self.model.make_filename(ext)
        filen = dialog_savefile(self.widget, filen_t)
        if str(filen) == '':
            return
        with open(filen, "w") as f:
            for s in azi_list:
                f.write(s[0] + ',' + str(s[1]) + ',' +
                        str(s[2]) + ',' + str(s[3]) + ',' +
                        str(s[4]) + '\n')

    def _load_cake_marker_file(self):
        # get filename
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a marker File", self.model.chi_path,
            "Data files (*.marker)")[0]
        if filen == '':
            return
        temp_markers = []
        with open(filen, "r") as f:
            for line in f:
                temp_markers.append([x.strip() for x in line.split(',')])
        new_markers = []
        for line in temp_markers:
            new_markers.append([line[0], float(line[1]), float(line[2]),
                                float(line[3]), float(line[4])])
        self._clear_azilist()
        self._post_to_table(new_markers)
        self._apply_changes_to_graph()

    def _invert_cake_selections(self):
        # azi_list is read from the table
        azi_list = self._read_azilist()
        # each component of azi_list has [comment, tth_min, azi_min, tth_max, azi_max]
        if azi_list is None:
            return
        # azi_whole is a numpy array with azimuthal angles where 1D pattern exists
        __, __, azi_whole = self.model.diff_img.get_cake() 
        new_azi_list = []
        # epsilon is threshold for the azimuthal angle differences.
        epsilon = 0.01
        # inversion of 1 range does not have a problem.
        if azi_list.__len__() == 1:
            azi = azi_list[0]
            if (np.abs(azi[2] - azi_whole.min()) < epsilon) and \
                    (np.abs(azi[4] - azi_whole.max()) < epsilon):
                self._clear_azilist()
            elif np.abs(azi[2] - azi_whole.min()) < epsilon:
                new_azi_list.append([azi[0], azi[1], azi[4], azi[3],
                                     azi_whole.max()])
            elif np.abs(azi[4] - azi_whole.max()) < epsilon:
                new_azi_list.append([azi[0], azi[1], azi_whole.min(),
                                     azi[3], azi[2]])
            else:
                new_azi_list.append([azi[0], azi[1], azi_whole.min(),
                                     azi[3], azi[2]])
                new_azi_list.append([azi[0], azi[1], azi[4], azi[3],
                                     azi_whole.max()])
        else:
            sorted_azi_list = sorted(azi_list,
                                     key=lambda azi_list: azi_list[2])
            print('sorted', sorted_azi_list)
            lower_azi = azi_whole.min()
            for azi in sorted_azi_list:
                if np.abs(lower_azi - azi[2]) > epsilon:
                    new_azi_list.append([azi[0], azi[1], lower_azi,
                                         azi[3], azi[2]])
                else:
                    pass
                lower_azi = azi[4]
            last_azi = sorted_azi_list[-1]
            if np.abs(last_azi[4] - azi_whole.max()) > epsilon:
                new_azi_list.append(
                    [azi[0], azi[1], last_azi[4], azi[3], azi_whole.max()])
        if new_azi_list != []:
            self._clear_azilist()
            self._post_to_table(new_azi_list)
            self._apply_changes_to_graph()

    def _post_to_table(self, azi_list):
        i = 0
        for azi in azi_list:
            self.widget.tableWidget_DiffImgAzi.insertRow(i)
            for j in (1, 2, 3, 4):
                self.widget.tableWidget_DiffImgAzi.setItem(
                    i, j, QtWidgets.QTableWidgetItem("{:.3f}".format(azi[j])))
            self.widget.tableWidget_DiffImgAzi.setItem(
                i, 0, QtWidgets.QTableWidgetItem(azi[0]))

    def _add_azi_to_list(self):
        # read azimuth_range
        tth_range, azi_range = self._read_azi_from_plot()
        if azi_range is None:
            return
        rowPosition = self.widget.tableWidget_DiffImgAzi.rowCount()
        self.widget.tableWidget_DiffImgAzi.insertRow(rowPosition)
        self.widget.tableWidget_DiffImgAzi.setItem(
            rowPosition, 1, QtWidgets.QTableWidgetItem(
                "{:.3f}".format(tth_range[0])))
        self.widget.tableWidget_DiffImgAzi.setItem(
            rowPosition, 3, QtWidgets.QTableWidgetItem(
                "{:.3f}".format(tth_range[1])))
        self.widget.tableWidget_DiffImgAzi.setItem(
            rowPosition, 2, QtWidgets.QTableWidgetItem(
                "{:.3f}".format(azi_range[0])))
        self.widget.tableWidget_DiffImgAzi.setItem(
            rowPosition, 4, QtWidgets.QTableWidgetItem(
                "{:.3f}".format(azi_range[1])))
        self.widget.tableWidget_DiffImgAzi.setItem(
            rowPosition, 0, QtWidgets.QTableWidgetItem(
                " "))
        # self._apply_changes_to_graph()
        self._zoom_out_graph()

    def _remove_azi_from_list(self):
        # get higtlighted row, if not return
        rows = self.widget.tableWidget_DiffImgAzi.selectionModel().\
            selectedRows()
        if rows == []:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Highlight the row to remove first.')
            return
        # update plot to highligh the selected row
        self._apply_changes_to_graph()
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'The red highlighted area will be removed from the list, OK?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        # remove the row
        for r in rows:
            self.widget.tableWidget_DiffImgAzi.removeRow(r.row())
        self._apply_changes_to_graph()

    def _read_azilist(self):
        n_row = self.widget.tableWidget_DiffImgAzi.rowCount()
        if n_row == 0:
            return None
        azi_list = []
        for i in range(n_row):
            tth_min = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 1).text())
            azi_min = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 2).text())
            tth_max = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 3).text())
            azi_max = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 4).text())
            comment = self.widget.tableWidget_DiffImgAzi.item(i, 0).text()
            azi_list.append([comment, tth_min, azi_min, tth_max, azi_max])
        return azi_list

    def _clear_azilist(self):
        self.widget.tableWidget_DiffImgAzi.setRowCount(0)
        self._apply_changes_to_graph()

    def _read_azi_from_plot(self):
        tth_range, azi_range = self.plot_ctrl.get_cake_range()
        if tth_range is None:
            return None, None
        else:
            return tth_range, azi_range

    def integrate_to_1d(self):

        # get azimuthal angle list from UI
        azi_list = self._read_azilist()
        if azi_list is None:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'No azimuthal ranges in the queue.')
            return None
        # self.produce_cake()
        self.cakemake_ctrl.read_settings()
        tth = []
        intensity = []
        mid_angle = self.widget.spinBox_AziShift.value()

        # azi_conv = converted azimuthal angle for mid_angle shift.
        # azi_real = azimuthal angle in original img data.
        for azi_i in azi_list:
            azi_conv = []
            if mid_angle <= 180:
                azi_conv.append(azi_i[2] - mid_angle)
                azi_conv.append(azi_i[4] - mid_angle)
            else:
                azi_conv.append(azi_i[2] + 360 - mid_angle)
                azi_conv.append(azi_i[4] + 360 - mid_angle)
            azi_real = []
            for azi_conv_i in azi_conv:
                if azi_conv_i < -180:
                    azi_real.append(360 + azi_conv_i)
                elif azi_conv_i > 180:
                    azi_real.append(azi_conv_i - 360)
                else:
                    azi_real.append(azi_conv_i)
            tth_i, intensity_i = self.model.diff_img.integrate_to_1d(
                azimuth_range=(azi_real[0], azi_real[1]))
            tth.append(tth_i)
            intensity.append(intensity_i)
        intensity_merged = np.zeros_like(intensity[0])
        # adding 1D intensities of different azi sections on top of each other
        for tth_i, intensity_i in zip(tth, intensity):
            if not np.array_equal(tth_i, tth[0]):
                QtWidgets.QMessageBox.warning(
                    self.widget, 'Warning',
                    'Error occured while preparing for azimuthal ' + \
                    'integration. No output.')
                return None
            intensity_merged += intensity_i
        n_azi = azi_list.__len__()
        first_azi = azi_list[0]
        intensity_output = intensity_merged
        ext = "{0:d}_{1:d}_{2:d}.chi".format(
            n_azi, int(first_azi[2]), int(first_azi[4]))
        filen_chi_t = self.model.make_filename(ext)
        filen_chi = dialog_savefile(self.widget, filen_chi_t)
        if str(filen_chi) == '':
            return None
        azi_text = '# azi. angles: '
        for azi_i in azi_list:
            azi_text += "({0:.5e}, {1:.5e})".format(azi_i[2], azi_i[4])
        preheader_line0 = azi_text + ' \n'
        preheader_line1 = '2-theta\n'
        preheader_line2 = '\n'
        writechi(filen_chi, tth[0], intensity_output,
                 preheader=preheader_line0 + preheader_line1 +
                 preheader_line2)
        self._save_cake_marker_file()
        return filen_chi
    """
    def integrate_to_1d(self):
        azi_range = self._read_azi_from_plot()
        if azi_range is None:
            return
        # self.produce_cake()
        self.cakemake_ctrl.read_settings()
        tth, intensity = self.model.diff_img.integrate_to_1d(
            azimuth_range=azi_range)
        ext = "{0:d}to{1:d}.chi".format(int(azi_range[0]), int(azi_range[1]))
        filen_chi_t = self.model.make_filename(ext)
        filen_chi = dialog_savefile(self.widget, filen_chi_t)
        if str(filen_chi) == '':
            return
        preheader_line0 = \
            '# azimutal angle: {0: .5e}, {1: .5e} \n'.format(
                azi_range[0], azi_range[1])
        preheader_line1 = '\n'
        preheader_line2 = '\n'
        writechi(filen_chi, tth, intensity, preheader=preheader_line0 +
                 preheader_line1 + preheader_line2)
    """

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def _zoom_out_graph(self):
        self.plot_ctrl.zoom_out_graph()
