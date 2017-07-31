import os
from PyQt5 import QtWidgets
from utils import undo_button_press, dialog_savefile, writechi
from .mplcontroller import MplController


class CakeController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.checkBox_ShowCake.clicked.connect(
            self.addremove_cake)
        self.widget.pushButton_GetPONI.clicked.connect(self.get_poni)
        self.widget.pushButton_ApplyCakeView.clicked.connect(
            self._apply_changes_to_graph)
        self.widget.pushButton_ApplyMask.clicked.connect(self.apply_mask)
        self.widget.pushButton_IntegrateCake.clicked.connect(
            self.integrate_to_1d)

    def integrate_to_1d(self):
        tth_range, azi_range = self.plot_ctrl.get_cake_range()
        if tth_range is None:
            return
        # self.produce_cake()
        self.model.diff_img.set_calibration(self.model.poni)
        self.model.diff_img.set_mask((self.widget.spinBox_MaskMin.value(),
                                      self.widget.spinBox_MaskMax.value()))
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

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def addremove_cake(self):
        """
        add/remove cake to the graph
        """
        update = self._addremove_cake()
        if update:
            self._apply_changes_to_graph()

    def _addremove_cake(self):
        """
        add/remove cake
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
        if not os.path.exists(filen_tif):
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find %s.' % filen_tif)
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
            '2D Image: ' + self.model.diff_img.img_filename)

    def apply_mask(self):
        self.produce_cake()
        self._apply_changes_to_graph()

    def produce_cake(self):
        """
        Reprocess to get cake.  Slower re-processing
        does not signal to update_graph
        """
        self._load_new_image()
        self.model.diff_img.set_calibration(self.model.poni)
        self.model.diff_img.set_mask((self.widget.spinBox_MaskMin.value(),
                                      self.widget.spinBox_MaskMax.value()))
        self.model.diff_img.integrate_to_cake()

    def process_temp_cake(self):
        """
        load cake through either temporary file or make a new cake
        """
        if not self.model.associated_image_exists():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Image file for the base pattern does not exist.")
            return
        temp_dir = os.path.join(self.model.chi_path, 'temporary_pkpo')
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
            self.widget.textEdit_PONI.setText('PONI: ' + self.model.poni)
            if self.model.diff_img_exist():
                self.produce_cake()
            self._apply_changes_to_graph()
