import os
from PyQt5 import QtWidgets
from PyQt5 import QtGui
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
        self.widget.pushButton_PkSave.clicked.connect(self.save_to_section)
        self.widget.pushButton_ClearSection.clicked.connect(
            self.clear_this_section)
        self.widget.pushButton_PkFtSectionRemove.clicked.connect(
            self.remove_section)
        self.widget.pushButton_PkFtSectionClear.clicked.connect(
            self.clear_section_list)
        # self.widget.pushButton_AddRemoveFromMouse.clicked.connect(
        #    self.set_mouse_for_pick_input)
        # self.widget.mpl.canvas.mpl_connect(
        #    'button_press_event', self.pick_peak)

    def clear_section_list(self):
        reply = QtGui.QMessageBox.question(
            self.widget, 'Message', 'Unsaved sections will be erased. Proceed?',
            QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
            QtGui.QMessageBox.Yes)
        if reply == QtGui.QMessageBox.No:
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
            'Unsaved fitting result will be discarded.  Proceed?',
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
        self.widget.tableWidget_PkParams.setStyleSheet(
            "Background-color:None;")
        # udpate the section table.
        self.widget.tableWidget_PkFtSections.setStyleSheet(
            "Background-color:rgb(255,104,255);")
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

    def pick_peak(self, event):
        """
        if self.widget.mpl.ntb._active is not None:
            self.release_mouse_from_peak_input()
            return
        if (event.xdata is None) or (event.ydata is None):
            return
        """
        if not self.model.current_section_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Set section first.")
            return
        if not self.widget.pushButton_AddRemoveFromMouse.isChecked():
            return
        if self.model.current_section.fitted():
            reply = QtWidgets.QMessageBox.question(
                self.widget, 'Message',
                'Do you want to add to the last fitting result without save?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes)
            if reply == QtWidgets.QMessageBox.No:
                return
            """
            else:
                self.model.current_section.copy_fit_result_to_queue()
                self.model.current_section.invalidate_fit_result()
            """
        if event.button == 1:  # left click
            success = self.model.current_section.set_single_peak(
                float(event.xdata))
            if not success:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You picked outside of the current section.")
                return
        else:  # right button for removal
            if not self.model.current_section.peaks_exist():
                return
            self.model.current_section.remove_single_peak_nearby(event.xdata)
        self.widget.tableWidget_PkParams.setStyleSheet(
            "Background-color:rgb(255,104,255);")
        # self._list_peaks()
        # self._list_pkparams()
        self.plot_ctrl.update()

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
        self.model.current_section.prepare_for_fitting(width, order)
        success = self.model.current_section.conduct_fitting()
        if success:
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          'Fitting finished.')
            self.plot_ctrl.update()
            self.peakfit_table_ctrl.update_pkparams()
            # self.model.current_section.clear_picks()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          'Fitting failed.')
    # -------------------------------------------

    # This should add the section in the tableWidget_PkFtSections
