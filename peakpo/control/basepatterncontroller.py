import os
from PyQt5 import QtWidgets
from ..utils import get_sorted_filelist, find_from_filelist, readchi, \
    make_filename, writechi, get_directory
from ..utils import undo_button_press, get_temp_dir
import datetime
from .mplcontroller import MplController
from .cakecontroller import CakeController


class BasePatternController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.cake_ctrl = CakeController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_NewBasePtn.clicked.connect(
            self.select_base_ptn)
        self.widget.lineEdit_DiffractionPatternFileName.editingFinished.\
            connect(self.load_new_base_pattern_from_name)

    def select_base_ptn(self):
        """
        opens a file select dialog
        """
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a Chi File", self.model.chi_path,
            "Data files (*.chi)")[0]
        self._setshow_new_base_ptn(str(filen))

    def load_new_base_pattern_from_name(self):
        if self.widget.lineEdit_DiffractionPatternFileName.isModified():
            filen = self.widget.lineEdit_DiffractionPatternFileName.text()
            self._setshow_new_base_ptn(filen)

    def _setshow_new_base_ptn(self, filen):
        """
        load and then send signal to update_graph
        """
        if os.path.exists(filen):
            self.model.set_chi_path(os.path.split(filen)[0])
            if self.model.base_ptn_exist():
                old_filename = self.model.get_base_ptn_filename()
            else:
                old_filename = None
            new_filename = filen
            self._load_a_new_pattern(new_filename)
            if old_filename is None:
                self.plot_new_graph()
            else:
                self.apply_changes_to_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find ' + filen)
            # self.widget.lineEdit_DiffractionPatternFileName.setText(
            #    self.model.get_base_ptn_filename())

    def _load_a_new_pattern(self, new_filename):
        """
        load and process base pattern.  does not signal to update_graph
        """
        self.model.set_base_ptn(
            new_filename, self.widget.doubleSpinBox_SetWavelength.value())
        # self.widget.textEdit_DiffractionPatternFileName.setText(
        #    '1D Pattern: ' + self.model.get_base_ptn_filename())
        self.widget.lineEdit_DiffractionPatternFileName.setText(
            str(self.model.get_base_ptn_filename()))
        print(str(datetime.datetime.now())[:-7], 
                ": Receive request to open ", 
                str(self.model.get_base_ptn_filename()))
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        if self.widget.checkBox_UseTempBGSub.isChecked():
            if os.path.exists(temp_dir):
                success = self.model.base_ptn.read_bg_from_tempfile(
                    temp_dir=temp_dir)
                if success:
                    self._update_bg_params_in_widget()
                    print(str(datetime.datetime.now())[:-7], 
                        ': Read temp chi successfully.')
                else:
                    self._update_bgsub_from_current_values()
                    print(str(datetime.datetime.now())[:-7], 
                        ': No temp chi file found. Force new bgsub fit.')
            else:
                os.makedirs(temp_dir)
                self._update_bgsub_from_current_values()
                print(str(datetime.datetime.now())[:-7], 
                    ': No temp chi file found. Force new bgsub fit.')
        else:
            self._update_bgsub_from_current_values()
            print(str(datetime.datetime.now())[:-7], 
                ': Temp chi ignored. Force new bgsub fit.')
        if not self.model.associated_image_exists():
            self.widget.checkBox_ShowCake.setChecked(False)
            return
        # self._update_bg_params_in_widget()

        poni_all = self.cake_ctrl.get_all_temp_poni()
        if len(poni_all) == 1:
            self.model.poni = poni_all[0]
            self.widget.lineEdit_PONI.setText(self.model.poni)

        if self.widget.checkBox_ShowCake.isChecked() and \
                (self.model.poni is not None):
            self.cake_ctrl.process_temp_cake()
            # not sure this is correct.
            # self.cake_ctrl.addremove_cake(update_plot=False)

    def _update_bg_params_in_widget(self):
        self.widget.spinBox_BGParam0.setValue(
            self.model.base_ptn.params_chbg[0])
        self.widget.spinBox_BGParam1.setValue(
            self.model.base_ptn.params_chbg[1])
        self.widget.spinBox_BGParam2.setValue(
            self.model.base_ptn.params_chbg[2])
        self.widget.doubleSpinBox_Background_ROI_min.setValue(
            self.model.base_ptn.roi[0])
        self.widget.doubleSpinBox_Background_ROI_max.setValue(
            self.model.base_ptn.roi[1])

    def _update_bgsub_from_current_values(self):
        x_raw, y_raw = self.model.base_ptn.get_raw()
        if (x_raw.min() >= self.widget.doubleSpinBox_Background_ROI_min.value()) or \
                (x_raw.max() <= self.widget.doubleSpinBox_Background_ROI_min.value()):
            self.widget.doubleSpinBox_Background_ROI_min.setValue(x_raw.min())
        if (x_raw.max() <= self.widget.doubleSpinBox_Background_ROI_max.value()) or \
                (x_raw.min() >= self.widget.doubleSpinBox_Background_ROI_max.value()):
            self.widget.doubleSpinBox_Background_ROI_max.setValue(x_raw.max())
        self.model.base_ptn.subtract_bg(
            [self.widget.doubleSpinBox_Background_ROI_min.value(),
                self.widget.doubleSpinBox_Background_ROI_max.value()],
            [self.widget.spinBox_BGParam0.value(),
                self.widget.spinBox_BGParam1.value(),
                self.widget.spinBox_BGParam2.value()], yshift=0)
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        self.model.base_ptn.write_temporary_bgfiles(temp_dir)

    def apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def plot_new_graph(self):
        self.plot_ctrl.zoom_out_graph()
