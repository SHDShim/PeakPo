import os
from PyQt5 import QtWidgets
from utils import undo_button_press, dialog_savefile, writechi


class CakemakeController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget

    def read_settings(self):
        self.model.diff_img.set_calibration(self.model.poni)
        mask_min = float(self.widget.spinBox_MaskMin.value())
        mask_max = float(self.widget.spinBox_MaskMax.value())
        self.model.diff_img.set_mask([mask_min, mask_max])

    def cook(self):
        self.read_settings()
        self.model.diff_img.integrate_to_cake()
