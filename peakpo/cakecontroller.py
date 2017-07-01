from PyQt5 import QtWidgets
import os
from utils import undo_button_press

from mplcontroller import MplController


class CakeController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        # Tab: Cake
        self.widget.pushButton_AddRemoveCake.clicked.connect(
            self.addremove_cake)
        self.widget.pushButton_GetPONI.clicked.connect(self._get_poni)
        self.widget.pushButton_ApplyCakeView.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.pushButton_ApplyMask.clicked.connect(self._apply_mask)

    def apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def addremove_cake(self, update_plot=True):
        """
        add/remove cake to the graph
        """
        self._addremove_cake()
        if update_plot:
            self.apply_changes_to_graph()

    def _addremove_cake(self):
        """
        add/remove cake
        no signal to update_graph
        """
        if not self.widget.pushButton_AddRemoveCake.isChecked():
            self.widget.pushButton_AddRemoveCake.setText('Add Cake')
            return
        else:
            self.widget.pushButton_AddRemoveCake.setText('Remove Cake')
        if not self.model.poni_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose PONI file first.')
            undo_button_press(
                self.widget.pushButton_AddRemoveCake,
                released_text='Add Cake', pressed_text='Remove Cake')
            return
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose CHI file first.')
            undo_button_press(
                self.widget.pushButton_AddRemoveCake,
                released_text='Add Cake', pressed_text='Remove Cake')
            return
        filen_tif = self.model.make_filename('tif')
        if not os.path.exists(filen_tif):
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find %s.' % filen_tif)
            undo_button_press(
                self.widget.pushButton_AddRemoveCake,
                released_text='Add Cake', pressed_text='Remove Cake')
            return
        if self.model.diff_img_exist() and \
                self.model.same_filename_as_base_ptn(
                self.model.diff_img.img_filename):
            return
        self._load_new_image(filen_tif)
        self._produce_cake()

    def _load_new_image(self, filen_tif):
        """
        Load new image for cake view.  Cake should be the same as base pattern.
        no signal to update_graph
        """
        self.model.reset_diff_img()
        self.model.diff_img.load(filen_tif)
        self.widget.textEdit_DiffractionImageFilename.setText(
            '2D Image: ' + filen_tif)

    def _apply_mask(self):
        self._produce_cake()
        self.apply_changes_to_graph()

    def _produce_cake(self):
        """
        Reprocess to get cake.  Slower re-processing
        does not signal to update_graph
        """
        self.model.diff_img.set_calibration(self.model.poni)
        self.model.diff_img.set_mask((self.widget.spinBox_MaskMin.value(),
                                      self.widget.spinBox_MaskMax.value()))
        self.model.diff_img.integrate_to_cake()

    def _get_poni(self):
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
                self._produce_cake()
            self.apply_changes_to_graph()
