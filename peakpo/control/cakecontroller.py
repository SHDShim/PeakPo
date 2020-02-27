import os
from PyQt5 import QtWidgets
import numpy as np
from utils import dialog_savefile, writechi, get_directory, make_filename
from .mplcontroller import MplController
from .cakemakecontroller import CakemakeController


class CakeController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.cakemake_ctrl = CakemakeController(self.model, self.widget)
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.checkBox_ShowCake.clicked.connect(
            self.addremove_cake)
        self.widget.pushButton_GetPONI.clicked.connect(self.get_poni)
        self.widget.pushButton_ApplyCakeView.clicked.connect(self.update_cake)
        self.widget.pushButton_ApplyMask.clicked.connect(self.apply_mask)
        self.widget.lineEdit_PONI.editingFinished.connect(
            self.load_new_poni_from_name)
        self.widget.pushButton_ResetCakeScale.clicked.connect(
            self.reset_max_cake_scale)
        self.widget.checkBox_WhiteForPeak.clicked.connect(
            self._apply_changes_to_graph)
        self.widget.pushButton_Load_CakeFormatFile.clicked.connect(
            self.load_cake_format_file)
        self.widget.pushButton_Save_CakeFormatFile.clicked.connect(
            self.save_cake_format_file)

    def update_cake(self):
        if self.model.poni_exist():
            self.produce_cake()
            temp_dir = get_directory(self.model.get_base_ptn_filename(), '-param')
            self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)
            self._apply_changes_to_graph()

    def load_cake_format_file(self):
        # get filename
        temp_dir = get_directory(self.model.get_base_ptn_filename(), '-param')
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a cake format File", temp_dir,  # self.model.chi_path,
            "Data files (*.cakeformat)")[0]
        if filen == '':
            return
        temp_values = []
        with open(filen, "r") as f:
            for line in f:
                temp_values.append(float(line.split(':')[1]))
        self.widget.spinBox_AziShift.setValue(temp_values[0])
        self.widget.spinBox_MaxCakeScale.setValue(temp_values[1])
        self.widget.horizontalSlider_VMin.setValue(temp_values[2])
        self.widget.horizontalSlider_VMax.setValue(temp_values[3])
        self.widget.horizontalSlider_MaxScaleBars.setValue(temp_values[4])
        self._apply_changes_to_graph()

    def save_cake_format_file(self):
        # make filename
        temp_dir = get_directory(self.model.get_base_ptn_filename(), '-param')
        ext = "cakeformat"
        #filen_t = self.model.make_filename(ext)
        filen_t = make_filename(self.model.base_ptn.fname, ext,
                                temp_dir=temp_dir)
        filen = dialog_savefile(self.widget, filen_t)
        if str(filen) == '':
            return
        # save cake related Values
        names = ['azi_shift', 'int_max', 'min_bar', 'max_bar', 'scale_bar']
        values = [self.widget.spinBox_AziShift.value(),
                  self.widget.spinBox_MaxCakeScale.value(),
                  self.widget.horizontalSlider_VMin.value(),
                  self.widget.horizontalSlider_VMax.value(),
                  self.widget.horizontalSlider_MaxScaleBars.value()]

        with open(filen, "w") as f:
            for n, v in zip(names, values):
                f.write(n + ' : ' + str(v) + '\n')

    def reset_max_cake_scale(self):
        intensity_cake, _, _ = self.model.diff_img.get_cake()
        self.widget.spinBox_MaxCakeScale.setValue(intensity_cake.max())
        self._apply_changes_to_graph()

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def addremove_cake(self):
        """
        add / remove cake to the graph
        """
        update = self._addremove_cake()
        if update:
            self._apply_changes_to_graph()

    def _addremove_cake(self):
        """
        add / remove cake
        no signal to update_graph
        """
        if not self.widget.checkBox_ShowCake.isChecked():
            return True
        if not self.model.poni_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose PONI file first.')
            self.widget.checkBox_ShowCake.setChecked(False),
            return False
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose CHI file first.')
            self.widget.checkBox_ShowCake.setChecked(False)
            return False
        filen_tif = self.model.make_filename('tif', original=True)
        filen_mar3450 = self.model.make_filename('mar3450', original=True)
        filen_cbf = self.model.make_filename('cbf', original=True)
        if not ((os.path.exists(filen_tif) or
                 os.path.exists(filen_mar3450)) or
                os.path.exists(filen_cbf)):
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'Cannot find image file: %s or %s or %s or %s.' %
                (filen_tif, filen_tif, filen_mar3450, filen_cbf))
            self.widget.checkBox_ShowCake.setChecked(False)
            return False
        if self.model.diff_img_exist() and \
                self.model.same_filename_as_base_ptn(
                self.model.diff_img.img_filename):
            return True
        self.process_temp_cake()
        return True

    def _load_new_image(self):
        """
        Load new image for cake view.  Cake should be the same as base pattern.
        no signal to update_graph
        """
        self.model.reset_diff_img()
        self.model.load_associated_img()
        self.widget.textEdit_DiffractionImageFilename.setText(
            self.model.diff_img.img_filename)

    def apply_mask(self):
        self.produce_cake()
        self._apply_changes_to_graph()

    def produce_cake(self):
        """
        Reprocess to get cake.  Slower re - processing
        does not signal to update_graph
        """
        self._load_new_image()
        self.cakemake_ctrl.cook()

    def process_temp_cake(self):
        """
        load cake through either temporary file or make a new cake
        """
        if not self.model.associated_image_exists():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Image file for the base pattern does not exist.")
            return
        temp_dir = get_directory(self.model.get_base_ptn_filename(), '-param')
        #temp_dir = os.path.join(self.model.chi_path, 'temporary_pkpo')
        if self.widget.checkBox_UseTempCake.isChecked():
            if os.path.exists(temp_dir):
                self._load_new_image()
                success = self.model.diff_img.read_cake_from_tempfile(
                    temp_dir=temp_dir)
                if success:
                    pass
                else:
                    self._update_temp_cake_files(temp_dir)
            else:
                os.makedirs(temp_dir)
                self._update_temp_cake_files(temp_dir)
        else:
            self._update_temp_cake_files(temp_dir)

    def _update_temp_cake_files(self, temp_dir):
        self.produce_cake()
        self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)

    def get_poni(self):
        """
        Opens a pyFAI calibration file
        signal to update_graph
        """
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a PONI File",
            self.model.chi_path, "PONI files (*.poni)")[0]
        filename = str(filen)
        if os.path.exists(filename):
            self.model.poni = filename
            self.widget.lineEdit_PONI.setText(self.model.poni)
            if self.model.diff_img_exist():
                self.produce_cake()
            self._apply_changes_to_graph()

    def load_new_poni_from_name(self):
        if self.widget.lineEdit_PONI.isModified():
            filen = self.widget.lineEdit_PONI.text()
            if os.path.exists(filen):
                self.model.poni = filen
                self.widget.lineEdit_PONI.setText(self.model.poni)
                if self.model.diff_img_exist():
                    self.produce_cake()
                self._apply_changes_to_graph()
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, 'Warning', 'The PONI file does not exist.')
