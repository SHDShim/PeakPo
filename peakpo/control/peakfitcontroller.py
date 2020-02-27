import os
import dill
from PyQt5 import QtWidgets
from .mplcontroller import MplController
from .peakfittablecontroller import PeakfitTableController


class PeakFitController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.peakfit_table_ctrl = PeakfitTableController(
            self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_SetFitSection.clicked.connect(
            self.set_fit_section)
        self.widget.pushButton_ConductFitting.clicked.connect(
            self.conduct_fitting)
        self.widget.pushButton_PkSave.clicked.connect(
            self.save_to_section)
        self.widget.pushButton_ClearSection.clicked.connect(
            self.clear_this_section)
        self.widget.pushButton_PkFtSectionRemove.clicked.connect(
            self.remove_section)
        self.widget.pushButton_PkFtSectionSetToCurrent.clicked.\
            connect(self.set_section_to_current)
        self.widget.pushButton_AddRemoveFromJlist.clicked.connect(
            self.get_peaks_from_jcpds)
        self.widget.pushButton_ZoomToSection.clicked.connect(
            self.zoom_to_section)
        self.widget.pushButton_PkFtSectionSavetoXLS.clicked.\
            connect(self.save_to_xls)
        self.widget.pushButton_PkFtSectionImport.clicked.connect(
            self.import_section_from_dpp)
        self.widget.pushButton_PlotSelectedPkFtResults.clicked.connect(
            self._plot_selected_fitting)
        # The line below exist in session_ctrl
        # self.widget.pushButton_PkFtSectionSavetoDPP.clicked.coonect

    def _plot_selected_fitting(self):
        self.plot_ctrl.update_to_gsas_style()

    def import_section_from_dpp(self):
        fn = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.model.chi_path, "(*.dpp)")[0]
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        success = self._load_from_dpp(fn)
        if success:
            self.peakfit_table_ctrl.update_sections()

    def _load_from_dpp(self, filen_dpp):
        '''
        internal method for reading dilled dpp file
        '''
        try:
            with open(filen_dpp, 'rb') as f:
                model_dpp = dill.load(f)
        except Exception as inst:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", str(inst))
            return False
        self.model.import_section_list(model_dpp)
        return True

    def zoom_to_section(self):
        if not self.model.current_section_exist():
            return
        x_range = self.model.current_section.get_xrange()
        y_range = self.model.current_section.get_yrange(
            bgsub=self.widget.checkBox_BgSub.isChecked())
        margin = 0.1 * (y_range[1] - y_range[0])
        self.plot_ctrl.update(
            limits=(x_range[0], x_range[1],
                    y_range[0] - margin, y_range[1] + margin))

    def get_peaks_from_jcpds(self):
        if not self.model.jcpds_exist():
            return
        i = 0
        for j in self.model.jcpds_lst:
            if j.display:
                i += 1
        if i == 0:
            return
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Set a section first.")
            return
        else:
            if self.model.current_section.fitted():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, "Question",
                    "Are you OK with clearing any unsaved results?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.No:
                    return
                else:
                    self.clear_this_section()
            else:
                pass
        x_range = self.model.current_section.get_xrange()
        peaks = []
        int_threshold = float(
            self.widget.spinBox_PeaksFromJlistIntensity.value())
        for j in self.model.jcpds_lst:
            if j.display:
                tths, intensities = j.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                for ii in range(tths.__len__()):
                    tth = float(tths[ii])
                    if (tth >= x_range[0]) and (tth <= x_range[1]) and \
                            (intensities[ii] >= int_threshold):
                        """
                        height = \
                            self.model.current_section.get_nearest_intensity(tth)
                        """
                        width = self.widget.doubleSpinBox_InitialFWHM.value()
                        hkl = [j.DiffLines[ii].h, j.DiffLines[ii].k,
                               j.DiffLines[ii].l]
                        phasename = j.name
                        self.model.current_section.set_single_peak(
                            tth, width, hkl=hkl, phase_name=phasename)
                    else:
                        pass
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        self.plot_ctrl.update()

    def get_style_for_unsaved(self):
        return "Background-color:rgb(255,204,255);color:rgb(0,0,0);"

    def get_style_for_saved(self):
        return "Background-color:None;color:rgb(0,0,0);"

    def set_tableWidget_PkParams_saved(self):
        self.widget.tableWidget_PkParams.setStyleSheet(
            self.get_style_for_saved())

    def set_tableWidget_PkParams_unsaved(self):
        self.widget.tableWidget_PkParams.setStyleSheet(
            self.get_style_for_unsaved())

    def set_tableWidget_PkFtSections_saved(self):
        self.widget.tableWidget_PkFtSections.setStyleSheet(
            self.get_style_for_saved())

    def set_tableWidget_PkFtSections_unsaved(self):
        self.widget.tableWidget_PkFtSections.setStyleSheet(
            self.get_style_for_unsaved())

    def set_section_to_current(self):
        if self.widget.tableWidget_PkFtSections.selectionModel().\
                selectedRows().__len__() != 1:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'Select a row to make current.')
            return
        if self.model.current_section_exist():
            if not self.model.current_section_saved():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Message',
                    'Are you OK to loose current section information?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.No:
                    return
                else:
                    pass
            else:
                pass
        else:
            pass
        idx = self.widget.tableWidget_PkFtSections.selectionModel().\
            selectedRows()[0].row()
        self.model.set_this_section_current(idx)
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_sections()
        self.peakfit_table_ctrl.update_baseline_constraints()
        self.peakfit_table_ctrl.update_peak_constraints()
        """
        self._list_peaks()
        self._list_localbg()
        self._update_config
        """
        self.zoom_to_section()

    def clear_section_list(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Any unsaved sections will be erased. Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        self._clear_all_sections()

    def _clear_all_sections(self):
        '''clean both sections and currentSection'''
        self.model.clear_section_list()
        self.widget.tableWidget_PkFtSections.clearContents()
        self._clear_current_section()

    def remove_section(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Are you sure you want to delete the selected sections?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        idx_checked = []
        for item in \
                self.widget.tableWidget_PkFtSections.selectionModel().\
                selectedRows():
            idx_checked.append(item.row())
        # remove checked ones
        if idx_checked != []:
            idx_checked.reverse()
            for idx in idx_checked:
                self.model.section_lst.pop(idx)
                self.widget.tableWidget_PkFtSections.removeRow(idx)

    def clear_this_section(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'Any unsaved fitting result will be discarded.  Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        limits = self.widget.mpl.canvas.ax_pattern.axis()
        if reply == QtWidgets.QMessageBox.No:
            return
        else:
            self._clear_current_section()
            # self.plot_ctrl.update(limits, False)
            self.plot_ctrl.update()

    def _clear_current_section(self):
        '''erase only current section'''
        self.widget.tableWidget_BackgroundConstraints.clearContents()
        self.widget.tableWidget_PeakConstraints.clearContents()
        self.widget.tableWidget_PkParams.clearContents()
        self.model.initialize_current_section()

    def save_to_section(self):
        if not self.model.current_section_exist():
            return
        self.model.save_current_section()
        self.set_tableWidget_PkParams_saved()
        self.set_tableWidget_PkFtSections_unsaved()
        # self._list_sections()
        self.model.initialize_current_section()
        self.widget.tableWidget_PkParams.clearContents()
        self.widget.tableWidget_PeakConstraints.clearContents()
        self.widget.tableWidget_BackgroundConstraints.clearContents()
        self.peakfit_table_ctrl.update_sections()
        self.plot_ctrl.update()

    def set_fit_section(self):
        # if there is unsaved section, ask if it needs to be saved,
        # this can be checked by looking at timestamp
        if self.model.current_section_exist():
            if not self.model.current_section_saved():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Message',
                    'Do you want to save the unsaved section?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.Yes:
                    self.model.save_current_section()
        self.model.initialize_current_section()
        # Warn the users about what is going to happen
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'I will set current plot range as current section. OK?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        # get X range from the current view
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        self.model.set_current_section([axisrange[0], axisrange[1]])
        # This button itself should activate the mouse for peak picking model
        self.widget.pushButton_AddRemoveFromMouse.setChecked(True)
        self.set_tableWidget_PkParams_unsaved()

    def set_mouse_for_peak_input(self):
        if self.widget.pushButton_AddRemoveFromMouse.isChecked():
            self.release_mouse_from_peak_input()
        else:
            self.widget.pushButton_AddRemoveFromMouse.setChecked(True)

    def release_mouse_from_peak_input(self):
        if self.widget.mpl.ntb._active == 'PAN':
            self.widget.mpl.ntb.pan()
        if self.widget.mpl.ntb._active == 'ZOOM':
            self.widget.mpl.ntb.zoom()
        self.widget.pushButton_AddRemoveFromMouse.setChecked(False)
        return
    '''
    def pick_peak(self, mouse_button, xdata, ydata):
        """
        """
        if mouse_button == 'left':  # left click
            success = self.model.current_section.set_single_peak(
                float(xdata),
                self.widget.doubleSpinBox_InitialFWHM.value())
            if not success:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You picked outside of the current section.")
                return
        elif mouse_button == 'right':  # right button for removal
            if not self.model.current_section.peaks_exist():
                return
            self.model.current_section.remove_single_peak_nearby(xdata)
        else:
            return
        self.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        self.plot_ctrl.update()
    '''

    def conduct_fitting(self):
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No section is defined")
            return
        if self.model.current_section.get_number_of_peaks_in_queue() == 0:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No pick exists in the section.")
            return
        width = self.widget.doubleSpinBox_InitialFWHM.value()
        order = self.widget.spinBox_BGPolyOrder.value()
        maxwidth = self.widget.doubleSpinBox_MaxFWHM.value()
        centerrange = self.widget.doubleSpinBox_PeakCenterRange.value()
        self.model.current_section.prepare_for_fitting(order,
                                                       maxwidth, centerrange)
        success = self.model.current_section.conduct_fitting()
        if success:
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          'Fitting finished.')
            self.plot_ctrl.update()
            self.peakfit_table_ctrl.update_peak_parameters()
            self.peakfit_table_ctrl.update_baseline_constraints()
            self.peakfit_table_ctrl.update_peak_constraints()
            self.set_tableWidget_PkParams_unsaved()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          'Fitting failed.')

    def save_to_xls(self):
        filen_xls = self.model.make_filename('peakfit.xls')
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Question',
            'Do you want to save in default filename, %s ?' % filen_xls,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            filen_xls = QtWidgets.QFileDialog.getSaveFileName(
                self.widget, "Save an Excel File", filen_xls, "(*.xls)")
        else:
            if os.path.exists(filen_xls):
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Question',
                    'The file already exist.  Overwrite?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.No:
                    return
        self.model.save_peak_fit_results_to_xls(filen_xls)
