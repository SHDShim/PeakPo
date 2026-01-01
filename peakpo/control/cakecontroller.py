import os
import shutil
import glob
from PyQt5 import QtWidgets
import numpy as np
from utils import dialog_savefile, writechi, get_directory, make_filename, \
    get_temp_dir, extract_filename, extract_extension, InformationBox, \
        make_converted_poni2_filename, make_poni2_from_poni21, read_any_poni_file
from .mplcontroller import MplController
from .cakemakecontroller import CakemakeController
from PIL import Image
import json
import datetime

class CakeController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.cakemake_ctrl = CakemakeController(self.model, self.widget)
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_Info.clicked.connect(self.show_tif_header)
        self.widget.checkBox_ShowCake.clicked.connect(
            self.addremove_cake)
        self.widget.pushButton_GetPONI.clicked.connect(self.get_poni)
        self.widget.pushButton_ApplyCakeView.clicked.connect(self.update_cake)
        self.widget.pushButton_ApplyMask.clicked.connect(self.apply_mask)
        self.widget.pushButton_MaskReset.clicked.connect(self.reset_maskrange)
        self.widget.lineEdit_PONI.editingFinished.connect(
            self.load_new_poni_from_name)
        self.widget.pushButton_ResetCakeScale.clicked.connect(
            self.reset_max_cake_scale)
        self.widget.checkBox_WhiteForPeak.clicked.connect(
            self._apply_changes_to_graph)
        """
        self.widget.pushButton_Load_CakeFormatFile.clicked.connect(
            self.load_cake_format_file)
        self.widget.pushButton_Save_CakeFormatFile.clicked.connect(
            self.save_cake_format_file)
        """

    def update_cake(self):
        if self.model.poni_exist():
            self.produce_cake()
            temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
            self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)
            self._apply_changes_to_graph()

    """
    def load_cake_format_file(self):
        # get filename
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
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
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
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
    """

    def reset_max_cake_scale(self):
        intensity_cake, _, _ = self.model.diff_img.get_cake()
        self.widget.spinBox_MaxCakeScale.setValue(int(intensity_cake.max()))
        self._apply_changes_to_graph()

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def show_tif_header(self):
        if not self.model.base_ptn_exist():
            return
        filen_tif = self.model.make_filename('tif', original=True)
        filen_tiff = self.model.make_filename('tiff', original=True)
        if not (os.path.exists(filen_tif) or
                os.path.exists(filen_tiff)):
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'Cannot find image file: %s or %s in the chi folder.' %
                (filen_tif, filen_tiff))
        else:
            textoutput = ''
            if os.path.exists(filen_tif):
                f = filen_tif
            else:
                f = filen_tiff
            metadata = {}
            with Image.open(f) as img:
                for key in img.tag:
                    metadata[key] = img.tag[key]
            infobox = InformationBox()
            infobox.setText(json.dumps(metadata, indent=4))
            print(str(datetime.datetime.now())[:-7], ': TIF metadata\n', 
                json.dumps(metadata, indent=4))
            infobox.exec_()
            #self.widget.plainTextEdit_ViewJCPDS.setPlainText(textoutput)


    def addremove_cake(self):
        """
        add / remove cake to the graph
        """
        update = self._addremove_cake()
        if update:
            self._apply_changes_to_graph()
    """
    def image_file_exists(self):
        # if no image file, no cake
        filen_tif = self.model.make_filename('tif', original=True)
        filen_tiff = self.model.make_filename('tiff', original=True)
        filen_mar3450 = self.model.make_filename('mar3450',
            original=True)
        filen_cbf = self.model.make_filename('cbf', original=True)
        filen_h5 = self.model.make_filename('h5', original=True)
        if not (os.path.exists(filen_tif) or
                os.path.exists(filen_tiff) or
                os.path.exists(filen_mar3450) or
                os.path.exists(filen_h5) or
                os.path.exists(filen_cbf)):
            return False
        else:
            return True
    """

    def _addremove_cake(self):
        """
        add / remove cake
        no signal to update_graph
        """
        if not self.widget.checkBox_ShowCake.isChecked():
            return True
        # if no base ptn, no cake
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose CHI file first.')
            self.widget.checkBox_ShowCake.setChecked(False)
            return False
        if not self.model.associated_image_exists():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'Cannot find image file.')
            self.widget.checkBox_ShowCake.setChecked(False)
            return False

        # if base pattern and image exist
        poni_all = self.get_all_temp_poni()
        if len(poni_all) == 1:
            self.model.poni = poni_all[0]
            self.widget.lineEdit_PONI.setText(self.model.poni)
            if self.model.diff_img_exist():
                #self.produce_cake()
                self.process_temp_cake()
            #self._apply_changes_to_graph()
            #return True
        else:
            if not self.model.poni_exist():
                if len(poni_all) == 0:
                        QtWidgets.QMessageBox.warning(
                            self.widget, 'Warning', 'Choose PONI file first.')
                        self.widget.checkBox_ShowCake.setChecked(False),
                        return False
                else:
                    QtWidgets.QMessageBox.warning(
                        self.widget, 'Warning', 
                        'More than 2 PONI files were found in TEMP folder. Delete all but one.')
                    self.widget.checkBox_ShowCake.setChecked(False),
                    return False
            else:
                # check if model.poni exist
                if not os.path.exists(self.model.poni):
                    QtWidgets.QMessageBox.warning(
                        self.widget, 'Warning', 'The poni does not exist in the path.')
                    self.widget.checkBox_ShowCake.setChecked(False),
                    return False
            """ unsure why the code below is needed.
            # check if model.poni is in temp_dir
            temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
            poni_filen = extract_filename(self.model.poni) + '.' + \
                        extract_extension(self.model.poni)
            # if model.poni and temp poni do not match, model.poni will be copied to TEMP folder
            if self.model.poni != os.path.join(temp_dir, poni_filen):
                shutil.copy(self.model.poni, os.path.join(temp_dir, poni_filen))
                self.model.poni = os.path.join(temp_dir, poni_filen)
                self.widget.lineEdit_PONI.setText(self.model.poni)
            """
        """ Not sure why we need this.
        if self.model.diff_img_exist() and \
                self.model.same_filename_as_base_ptn(
                self.model.diff_img.img_filename):
            return True
        """
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
        # self.produce_cake()
        min_mask = float(self.widget.spinBox_MaskMin.value())
        max_mask = float(self.widget.spinBox_MaskMax.value())
        zrange = self.model.diff_img.get_img_zrange()
        print('img z range', zrange)
        print('mask range', min_mask, max_mask)
        if (zrange[0] < min_mask) or (zrange[1] > max_mask):
            # case for meaningful mask
            if self.widget.pushButton_ApplyMask.isChecked():
                self.cakemake_ctrl.cook()
        else:
            self.model.diff_img.set_mask(None)
        self._apply_changes_to_graph()

    def reset_maskrange(self):
        # get min and max of the cake image
        #intensity_cake, _, _ = self.model.diff_img.get_cake()
        zrange = self.model.diff_img.get_img_zrange()
        if zrange != None:
            # push those values to spinboxes
            self.widget.spinBox_MaskMin.setValue(int(zrange[0]))
            self.widget.spinBox_MaskMax.setValue(int(zrange[1]))
            self.model.diff_img.set_mask(None)
            self._apply_changes_to_graph()
        # reprocess the image
        # self.apply_mask()

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
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        #temp_dir = os.path.join(self.model.chi_path, 'temporary_pkpo')
        if self.widget.checkBox_UseTempCake.isChecked():
            #if os.path.exists(temp_dir):
            self._load_new_image()
            success = self.model.diff_img.read_cake_from_tempfile(
                temp_dir=temp_dir)
            if success:
                print(str(datetime.datetime.now())[:-7], 
                    ": Load cake image from temporary file.")
                pass
            else:
                print(str(datetime.datetime.now())[:-7], 
                    ": Create new temporary file for cake image.")
                self._update_temp_cake_files(temp_dir)
            #else:
                #os.makedirs(temp_dir)
                #self._update_temp_cake_files(temp_dir)
        else:
            self._update_temp_cake_files(temp_dir)

    def _update_temp_cake_files(self, temp_dir):
        self.produce_cake()
        self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)

    def get_all_temp_poni(self):
        """
        Check if a poni file exist in temp_dir
        returns 1 if there is one
        returns 0 if non
        returns number of poni files if multiples
        """
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        search_pattern = os.path.join(temp_dir, "*.poni")
        poni_all = glob.glob(search_pattern)
        return poni_all
    
    def temp_cake_exists(self):
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        search_pattern = os.path.join(temp_dir, "*.cake.npy")
        cake_all = glob.glob(search_pattern)
        print(len(cake_all))
        if len(cake_all) < 3:
            return False
        else:
            return True

    def get_poni(self):
        """
        Opens a pyFAI calibration file
        signal to update_graph
        """
        poni_all = self.get_all_temp_poni()
        num_poni = len(poni_all)
        temp_dir = get_temp_dir(
            self.model.get_base_ptn_filename())
        if num_poni == 1:
            # single poni file in temp folder
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', self.model.poni + \
                    ' already exists in TEMP folder.' + \
                    ' If the file is not correct, delete it in TEMP folder.')
            self.model.poni = poni_all[0]
            self.widget.lineEdit_PONI.setText(self.model.poni)
            if self.model.diff_img_exist():
                self.produce_cake()
            self._apply_changes_to_graph()
        elif num_poni == 0:
            # no poni file in temp folder
            filen = QtWidgets.QFileDialog.getOpenFileName(
                self.widget, "Open a PONI File",
                self.model.chi_path, "PONI files (*.poni)")[0]
            filename = str(filen)
            if os.path.exists(filename):
                # Check if the chosen poni file is version 2.1
                poni_content = read_any_poni_file(filename)
                if 'poni_version' in poni_content:
                    if poni_content['poni_version'] != 2:
                        # Call the function to modify the file
                        output_file = make_converted_poni2_filename(filename)
                        make_poni2_from_poni21(filename, output_file)
                        # copy the chose file to temp_dir
                        shutil.move(output_file, temp_dir)
                        filen = extract_filename(output_file) + '.' + \
                                extract_extension(output_file)
                    else:
                        shutil.copy(filename, temp_dir)
                        filen = extract_filename(filename) + '.' + \
                                extract_extension(filename)
                else:
                    # copy the chose file to temp_dir
                    shutil.copy(filename, temp_dir)
                    filen = extract_filename(filename) + '.' + \
                            extract_extension(filename)
                # set filename to that exists in temp_dir
                self.model.poni = os.path.join(temp_dir, filen)
                self.widget.lineEdit_PONI.setText(self.model.poni)
                if self.model.diff_img_exist():
                    self.produce_cake()
                self._apply_changes_to_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',  
                    'More than 2 PONI files exist in TEMP folder. ' + \
                    'Delete except for a correct one.')

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

