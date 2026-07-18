import os
import shutil
import glob
from qtpy import QtWidgets
import numpy as np
from ..utils import dialog_savefile, writechi, get_directory, make_filename, \
    get_temp_dir, extract_filename, extract_extension, InformationBox, \
        make_poni2_from_poni21, samefilename, \
        read_any_poni_file, dialog_openfile_hide_param_dirs
from .mplcontroller import MplController
from .cakemakecontroller import CakemakeController
from ..model.azimuthal_integration import provenance_for_chi
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
        self.refresh_config_metadata_panel()

    def connect_channel(self):
        self.widget.pushButton_Info.clicked.connect(self.show_tif_header)
        self.widget.checkBox_ShowCake.clicked.connect(
            self.addremove_cake)
        self.widget.pushButton_GetPONI.clicked.connect(self.get_poni)
        if hasattr(self.widget, "pushButton_GetH5"):
            self.widget.pushButton_GetH5.clicked.connect(self.get_h5)
        self.widget.pushButton_ApplyCakeView.clicked.connect(self.update_cake)
        self.widget.lineEdit_PONI.editingFinished.connect(
            self.load_new_poni_from_name)
        if hasattr(self.widget, "lineEdit_H5"):
            self.widget.lineEdit_H5.editingFinished.connect(
                self.load_new_h5_from_name)
        self.widget.pushButton_ResetCakeScale.clicked.connect(
            self.reset_max_cake_scale)
        if hasattr(self.widget, "comboBox_CakeColormap"):
            self.widget.comboBox_CakeColormap.currentIndexChanged.connect(
                self._apply_changes_to_graph)
        if hasattr(self.widget, "cake_hist_widget"):
            self.widget.cake_hist_widget.boundChanged.connect(
                self._set_cake_bound_from_hist)
            self.widget.cake_hist_widget.rangeChanged.connect(
                self._set_cake_range_from_hist)
        """
        self.widget.pushButton_Load_CakeFormatFile.clicked.connect(
            self.load_cake_format_file)
        self.widget.pushButton_Save_CakeFormatFile.clicked.connect(
            self.save_cake_format_file)
        """

    def update_cake(self):
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose CHI file first.')
            return
        if not self._sync_poni_from_line_edit(warn_if_missing=True):
            return
        if not self.model.poni_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Choose PONI file first.')
            return
        if not self.model.associated_image_exists():
            self._set_image_file_box_missing()
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',
                'Raw XRD image file does not exist in the CHI folder.\n'
                'Move the raw image file (e.g., h5, mar3450, tif, tiff, cbf) '
                'into the same folder as the CHI file first.')
            return
        image_file = self._associated_image_file()
        if not self._confirm_non_h5_reprocess(image_file):
            return

        success = self.produce_cake()
        if not success:
            return
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)
        self._set_image_file_box()
        # The cake data itself changed, so this requires a full axes rebuild.
        self.plot_ctrl.update()

    def _associated_image_file(self):
        if not hasattr(self.model, "get_associated_image_candidates"):
            return None
        for filename in self.model.get_associated_image_candidates():
            if os.path.exists(filename):
                return filename
        return None

    def _confirm_non_h5_reprocess(self, image_file):
        if image_file is None:
            return True
        if extract_extension(image_file).lower() in ("h5", "nxs"):
            return True

        msg = QtWidgets.QMessageBox(self.widget)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Reprocess cake?")
        msg.setText(
            "This raw image is not an H5/NXS file. Reprocessing will overwrite "
            "the existing cake files for this pattern.")
        msg.setInformativeText(
            "Older cake files may already be correct. If the existing cake image "
            "looks fine, cancel and keep the current files.")
        reprocess_button = msg.addButton(
            "Reprocess", QtWidgets.QMessageBox.AcceptRole)
        msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
        msg.setDefaultButton(reprocess_button)
        msg.exec()
        return msg.clickedButton() == reprocess_button

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
        self._set_cake_scale_bar_value(temp_values[4])
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
                  self._get_cake_scale_bar_value()]

        with open(filen, "w") as f:
            for n, v in zip(names, values):
                f.write(n + ' : ' + str(v) + '\n')
    """

    def reset_max_cake_scale(self):
        if hasattr(self.widget, "checkBox_Diff") and self.widget.checkBox_Diff.isChecked():
            return
        intensity_cake, _, _ = self.model.diff_img.get_cake()
        self.widget.spinBox_MaxCakeScale.setValue(int(intensity_cake.max()))
        self._apply_changes_to_graph()

    def _apply_changes_to_graph(self):
        self.plot_ctrl.refresh_cake_style()

    def _get_cake_scale_bar_value(self):
        return 0

    def _set_cake_scale_bar_value(self, value):
        del value
        self.widget.horizontalSlider_MaxScaleBars.setValue(0)
        if hasattr(self.widget, "cake_hist_widget"):
            combo = self.widget.cake_hist_widget.combo_scale_mode
            idx = combo.findData(0)
            if idx >= 0 and combo.currentIndex() != idx:
                combo.setCurrentIndex(idx)

    def _set_cake_bound_from_hist(self, bound_type, intensity_value):
        prefactor = self.widget.spinBox_MaxCakeScale.value() / \
            (10. ** self._get_cake_scale_bar_value())
        if prefactor <= 0:
            return
        current_min = self.widget.horizontalSlider_VMin.value()
        current_max = self.widget.horizontalSlider_VMax.value()
        slider_value = self._cake_slider_value_from_intensity(intensity_value, prefactor)
        if bound_type == "min":
            if slider_value == current_min:
                current_min_intensity = current_min / 100.0 * prefactor
                if intensity_value < current_min_intensity:
                    slider_value = max(0, current_min - 1)
                elif intensity_value > current_min_intensity:
                    slider_value = min(999, current_min + 1)
            if slider_value >= current_max:
                slider_value = max(0, current_max - 1)
            self.widget.horizontalSlider_VMin.setValue(slider_value)
        elif bound_type == "max":
            if slider_value == current_max:
                current_max_intensity = current_max / 100.0 * prefactor
                if intensity_value < current_max_intensity:
                    slider_value = max(1, current_max - 1)
                elif intensity_value > current_max_intensity:
                    slider_value = min(1000, current_max + 1)
            if slider_value <= current_min:
                slider_value = min(1000, current_min + 1)
            self.widget.horizontalSlider_VMax.setValue(slider_value)

    def _cake_slider_value_from_intensity(self, intensity_value, prefactor):
        return int(np.clip(round(float(intensity_value) / prefactor * 100.0), 0, 1000))

    def _set_cake_range_from_hist(self, vmin, vmax):
        prefactor = self.widget.spinBox_MaxCakeScale.value() / \
            (10. ** self._get_cake_scale_bar_value())
        if prefactor <= 0:
            return
        min_value = self._cake_slider_value_from_intensity(vmin, prefactor)
        max_value = self._cake_slider_value_from_intensity(vmax, prefactor)
        if max_value <= min_value:
            max_value = min(1000, min_value + 1)
            if max_value <= min_value:
                min_value = max(0, max_value - 1)

        old_min_blocked = self.widget.horizontalSlider_VMin.blockSignals(True)
        old_max_blocked = self.widget.horizontalSlider_VMax.blockSignals(True)
        try:
            self.widget.horizontalSlider_VMin.setValue(min_value)
            self.widget.horizontalSlider_VMax.setValue(max_value)
        finally:
            self.widget.horizontalSlider_VMin.blockSignals(old_min_blocked)
            self.widget.horizontalSlider_VMax.blockSignals(old_max_blocked)
        self._apply_changes_to_graph()

    def _ignore_raw_data_missing(self):
        return self.widget.checkBox_IgnoreRawDataExistence.isChecked()

    def _default_raw_image_path(self):
        getter = getattr(self.model, "get_default_raw_image_path", None)
        if callable(getter):
            return getter()
        return None

    def _set_raw_image_line_edit_text(self, image_path, mark_missing=False):
        if not hasattr(self.widget, "lineEdit_H5"):
            return
        line_edit = self.widget.lineEdit_H5
        old_state = line_edit.blockSignals(True)
        try:
            if mark_missing:
                line_edit.setText(
                    "Image file does not exist in the same folder as CHI.")
                line_edit.setStyleSheet(
                    "QLineEdit { background-color: #8b1e1e; color: white; }")
            else:
                line_edit.setText("" if image_path is None else str(image_path))
                line_edit.setStyleSheet("")
            line_edit.setModified(False)
        finally:
            line_edit.blockSignals(old_state)

    def _is_valid_raw_image_for_current_chi(self, image_path):
        checker = getattr(self.model, "image_matches_base_pattern", None)
        if callable(checker):
            return checker(image_path)
        if (not image_path) or (not self.model.base_ptn_exist()):
            return False
        return samefilename(self.model.get_base_ptn_filename(), image_path)

    def _adopt_default_or_selected_raw_image(self):
        if not self.model.base_ptn_exist():
            if hasattr(self.model, "raw_image_path"):
                self.model.raw_image_path = None
                self.model.h5_path = None
            self._set_raw_image_line_edit_text(None)
            return
        if not hasattr(self.model, "raw_image_path"):
            return
        current_image = getattr(
            self.model, "raw_image_path", getattr(self.model, "h5_path", None))
        if current_image and self._is_valid_raw_image_for_current_chi(current_image) and \
                os.path.exists(current_image):
            self.model.raw_image_path = current_image
            self.model.h5_path = current_image
            self._set_raw_image_line_edit_text(current_image)
            return
        default_image = self._default_raw_image_path()
        if default_image and os.path.exists(default_image):
            self.model.raw_image_path = default_image
            self.model.h5_path = default_image
            self._set_raw_image_line_edit_text(default_image)
            return
        self.model.raw_image_path = None
        self.model.h5_path = None
        self._set_raw_image_line_edit_text(None, mark_missing=True)

    def _sync_raw_image_from_line_edit(self, warn_if_invalid=False):
        if not hasattr(self.widget, "lineEdit_H5"):
            return True
        image_path = self.widget.lineEdit_H5.text().strip()
        if image_path == "" or image_path == "Image file does not exist in the same folder as CHI.":
            self.model.raw_image_path = None
            self.model.h5_path = None
            self._adopt_default_or_selected_raw_image()
            return True
        if not os.path.exists(image_path):
            if warn_if_invalid:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "The image file does not exist.")
            self._adopt_default_or_selected_raw_image()
            return False
        if not self._is_valid_raw_image_for_current_chi(image_path):
            if warn_if_invalid:
                allowed = ", ".join(
                    "*." + ext for ext in getattr(
                        self.model, "get_allowed_image_extensions", lambda: ())())
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Image file must have the same base name as the CHI file "
                    "and use a supported image extension.\n\n"
                    "Supported types:\n" + allowed)
            self._adopt_default_or_selected_raw_image()
            return False
        self.model.raw_image_path = image_path
        self.model.h5_path = image_path
        self._set_raw_image_line_edit_text(image_path)
        return True

    def _set_image_file_box_missing(self):
        self.widget.textEdit_DiffractionImageFilename.setText(
            'Image file is missing. Move the raw image file into the same folder as CHI.')
        self.refresh_config_metadata_panel()

    def _set_image_file_box(self):
        if self.model.diff_img_exist() and (self.model.diff_img.img_filename is not None):
            self.widget.textEdit_DiffractionImageFilename.setText(
                self.model.diff_img.img_filename)
        else:
            self._set_image_file_box_missing()
            return
        self.refresh_config_metadata_panel()

    def _warn_cannot_process_cake(self):
        QtWidgets.QMessageBox.warning(
            self.widget, 'Warning',
            'PeakPo cannot process Cake: no raw image or cached Cake files '
            'were found for this CHI or its full-azimuth source.')

    def _current_azimuth_source_chi(self):
        if not self.model.base_ptn_exist():
            return None
        provenance = provenance_for_chi(self.model.get_base_ptn_filename())
        if provenance.get("source_kind") != "azimuthal_integration":
            return None
        source_chi = provenance.get("source_chi", "")
        if not source_chi:
            return None
        return os.path.abspath(source_chi)

    def _valid_loaded_cake(self):
        if self.model.diff_img is None:
            return False
        intensity, tth, chi = self.model.diff_img.get_cake()
        return intensity is not None and tth is not None and chi is not None

    def _diff_img_related_to_chi(self, chi_path):
        if self.model.diff_img is None:
            return False
        img_filename = getattr(self.model.diff_img, "img_filename", None)
        if not img_filename:
            return False
        img_root = os.path.splitext(os.path.basename(img_filename))[0]
        chi_root = os.path.splitext(os.path.basename(chi_path))[0]
        return img_root == chi_root or img_root.startswith(chi_root + "__")

    def _image_candidates_for_chi(self, chi_path):
        exts = ("tif", "tiff", "mar3450", "cbf", "h5")
        candidates = []
        for ext in exts:
            for original in (True, False):
                filen = make_filename(chi_path, ext, original=original)
                if filen not in candidates:
                    candidates.append(filen)
        return candidates

    def _load_cake_from_temp_for_chi(self, chi_path):
        if self.model.diff_img is None:
            self.model.reset_diff_img()
        temp_dir = get_temp_dir(chi_path)
        for candidate in self._image_candidates_for_chi(chi_path):
            self.model.diff_img.img_filename = candidate
            if self.model.diff_img.read_cake_from_tempfile(temp_dir=temp_dir):
                self.refresh_config_metadata_panel()
                return True
        return False

    def _load_cake_from_temp_without_raw_image(self, temp_dir):
        # Temp cake files are named from the base pattern root name.
        if self.model.diff_img is None:
            self.model.reset_diff_img()
        self.model.diff_img.img_filename = self.model.make_filename(
            'tif', original=True)
        success = self.model.diff_img.read_cake_from_tempfile(temp_dir=temp_dir)
        if success:
            self.refresh_config_metadata_panel()
        return success

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
            infobox.exec()
            #self.widget.plainTextEdit_ViewJCPDS.setPlainText(textoutput)


    def addremove_cake(self):
        """
        add / remove cake to the graph
        """
        update = self._addremove_cake()
        if update:
            self.plot_ctrl.update()
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
        if self._current_azimuth_source_chi() is not None:
            if self.process_temp_cake():
                return True
            self._warn_cannot_process_cake()
            self.widget.checkBox_ShowCake.setChecked(False)
            return False
        if not self.model.associated_image_exists():
            if not self._ignore_raw_data_missing():
                self._set_image_file_box_missing()
                QtWidgets.QMessageBox.warning(
                    self.widget, 'Warning',
                    'Cannot find image file.')
                self.widget.checkBox_ShowCake.setChecked(False)
                return False
            if self.model.poni is None:
                poni_all = self.get_all_temp_poni()
                if len(poni_all) == 1:
                    self._set_current_poni(poni_all[0])
            if not self.process_temp_cake():
                self._warn_cannot_process_cake()
                self.widget.checkBox_ShowCake.setChecked(False)
                return False
            return True

        # if base pattern and image exist
        poni_all = self.get_all_temp_poni()
        if len(poni_all) == 1:
            self._set_current_poni(poni_all[0])
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
        if not self.process_temp_cake():
            self._warn_cannot_process_cake()
            self.widget.checkBox_ShowCake.setChecked(False)
            return False
        return True

    def _load_new_image(self):
        """
        Load new image for cake view.  Cake should be the same as base pattern.
        no signal to update_graph
        """
        self.model.reset_diff_img()
        if not self.model.associated_image_exists():
            self._set_image_file_box_missing()
            return False
        self.model.load_associated_img()
        self._set_image_file_box()
        return True

    def produce_cake(self):
        """
        Reprocess to get cake.  Slower re - processing
        does not signal to update_graph
        """
        success = self._load_new_image()
        if not success:
            return False
        self.cakemake_ctrl.cook()
        self._set_image_file_box()
        self.refresh_config_metadata_panel()
        return True

    def process_temp_cake(self):
        """
        load cake through either temporary file or make a new cake
        """
        source_chi = self._current_azimuth_source_chi()
        if source_chi is not None:
            source_cake_loaded = (
                self._valid_loaded_cake() and
                self._diff_img_related_to_chi(source_chi))
            if source_cake_loaded:
                self.refresh_config_metadata_panel()
                return True
            if self._load_cake_from_temp_for_chi(source_chi):
                print(str(datetime.datetime.now())[:-7],
                    ": Load source Cake image from temporary file.")
                self.refresh_config_metadata_panel()
                return True
            return False

        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        has_raw_image = self.model.associated_image_exists()
        if not has_raw_image:
            self._set_image_file_box_missing()
            if not self._ignore_raw_data_missing():
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Image file for the base pattern does not exist.")
                return False
            return self._load_cake_from_temp_without_raw_image(temp_dir)
        #temp_dir = os.path.join(self.model.chi_path, 'temporary_pkpo')
        if self.widget.checkBox_UseTempCake.isChecked():
            #if os.path.exists(temp_dir):
            success = self._load_new_image()
            if not success:
                return False
            success = self.model.diff_img.read_cake_from_tempfile(
                temp_dir=temp_dir)
            if success:
                print(str(datetime.datetime.now())[:-7], 
                    ": Load cake image from temporary file.")
                self.refresh_config_metadata_panel()
            else:
                print(str(datetime.datetime.now())[:-7], 
                    ": Create new temporary file for cake image.")
                self._update_temp_cake_files(temp_dir)
                return True
            #else:
                #os.makedirs(temp_dir)
                #self._update_temp_cake_files(temp_dir)
            return True
        else:
            self._update_temp_cake_files(temp_dir)
            return True

    def _update_temp_cake_files(self, temp_dir):
        success = self.produce_cake()
        if not success:
            return
        self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)

    def get_all_temp_poni(self):
        """
        Check if a poni file exist in temp_dir
        returns 1 if there is one
        returns 0 if non
        returns number of poni files if multiples
        """
        if not self.model.base_ptn_exist():
            return []
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

    def _set_current_poni(self, poni_path):
        self.model.poni = poni_path
        self._set_poni_line_edit_text(self.model.poni)
        self.refresh_config_metadata_panel()

    def _set_poni_line_edit_text(self, poni_path, mark_missing=False):
        line_edit = self.widget.lineEdit_PONI
        old_state = line_edit.blockSignals(True)
        try:
            if mark_missing:
                line_edit.setText("No PONI file is assigned or found.")
                line_edit.setStyleSheet(
                    "QLineEdit { background-color: #8b1e1e; color: white; }")
            else:
                line_edit.setText("" if poni_path is None else str(poni_path))
                line_edit.setStyleSheet("")
            line_edit.setModified(False)
        finally:
            line_edit.blockSignals(old_state)

    def _adopt_current_or_found_poni(self):
        if not self.model.base_ptn_exist():
            self._set_poni_line_edit_text(None)
            return
        current_poni = getattr(self.model, "poni", None)
        if current_poni and os.path.exists(current_poni):
            self._set_poni_line_edit_text(current_poni)
            return
        poni_all = self.get_all_temp_poni()
        if len(poni_all) == 1 and os.path.exists(poni_all[0]):
            self.model.poni = poni_all[0]
            self._set_poni_line_edit_text(poni_all[0])
            return
        self.model.poni = None
        self._set_poni_line_edit_text(None, mark_missing=True)

    def _sync_poni_from_line_edit(self, warn_if_missing=False):
        """
        Keep the model calibration path synchronized with the visible PONI field.

        Button clicks may be handled before the edited line edit has committed its
        value through editingFinished.  The cake regeneration path must therefore
        read the visible field directly before loading the calibration.
        """
        poni_path = self.widget.lineEdit_PONI.text().strip()
        if poni_path in ("", "No PONI file is assigned or found."):
            self._adopt_current_or_found_poni()
            return self.model.poni_exist()
        if not os.path.exists(poni_path):
            if warn_if_missing:
                QtWidgets.QMessageBox.warning(
                    self.widget, 'Warning', 'The PONI file does not exist.')
            self._adopt_current_or_found_poni()
            return False
        if poni_path != self.model.poni:
            self.model.poni = poni_path
            self._set_poni_line_edit_text(self.model.poni)
        return True

    def _apply_poni_change(self, poni_path):
        self._set_current_poni(poni_path)
        if self.model.diff_img_exist():
            self.produce_cake()
        self._apply_changes_to_graph()

    def _is_same_poni_file(self, file_a, file_b):
        if (not file_a) or (not file_b):
            return False
        if (not os.path.exists(file_a)) or (not os.path.exists(file_b)):
            return False
        try:
            return os.path.samefile(file_a, file_b)
        except OSError:
            return False

    def _remove_temp_poni_files(self, keep=None):
        keep_paths = set()
        if keep:
            keep_paths.add(os.path.abspath(keep))
        for existing_poni in self.get_all_temp_poni():
            try:
                if os.path.abspath(existing_poni) in keep_paths:
                    continue
            except OSError:
                pass
            try:
                os.remove(existing_poni)
            except OSError:
                pass

    def _store_selected_poni(self, filename, temp_dir, current_poni=None):
        if not os.path.exists(filename):
            return False
        if self._is_same_poni_file(filename, current_poni):
            self._set_current_poni(current_poni)
            return False

        stored_filename = extract_filename(filename) + '.' + \
            extract_extension(filename)
        stored_path = os.path.join(temp_dir, stored_filename)
        if os.path.abspath(filename) != os.path.abspath(stored_path):
            staging_path = stored_path + '.incoming'
            try:
                if os.path.exists(staging_path):
                    os.remove(staging_path)
            except OSError:
                pass
            shutil.copy2(filename, staging_path)
            os.replace(staging_path, stored_path)

        # PeakPo still expects a v2 PONI. Convert only the param-folder copy.
        poni_content = read_any_poni_file(stored_path)
        if 'poni_version' in poni_content:
            try:
                poni_version = float(poni_content['poni_version'])
            except (TypeError, ValueError):
                poni_version = None
            if poni_version != 2.0:
                converted_path = stored_path + '.converted'
                make_poni2_from_poni21(stored_path, converted_path)
                os.replace(converted_path, stored_path)
        self._remove_temp_poni_files(keep=stored_path)
        self._apply_poni_change(stored_path)
        return True

    def _choose_and_store_poni(self, temp_dir, current_poni=None):
        filen = dialog_openfile_hide_param_dirs(
            self.widget, "Open a PONI File",
            self.model.chi_path, "PONI files (*.poni)")[0]
        filename = str(filen)
        return self._store_selected_poni(
            filename, temp_dir, current_poni=current_poni)

    def get_poni(self):
        """
        Opens a pyFAI calibration file
        signal to update_graph
        """
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Open a CHI or base pattern first before choosing a PONI file.")
            return
        poni_all = self.get_all_temp_poni()
        num_poni = len(poni_all)
        temp_dir = get_temp_dir(
            self.model.get_base_ptn_filename())
        if num_poni == 1:
            existing_poni = poni_all[0]
            self._set_current_poni(existing_poni)
            reply = QtWidgets.QMessageBox.question(
                self.widget, 'Question',
                'A PONI file already exists in the folder.\n\n' +
                existing_poni + '\n\n' +
                'Do you want to choose a different PONI file?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                self._choose_and_store_poni(
                    temp_dir, current_poni=existing_poni)
        elif num_poni == 0:
            self._choose_and_store_poni(temp_dir)
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning',  
                    'More than 2 PONI files exist in TEMP folder. ' + \
                    'Delete except for a correct one.')

    def get_h5(self):
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Open a CHI or base pattern first before choosing an image file.")
            return
        allowed_exts = getattr(
            self.model, "get_allowed_image_extensions", lambda: ())()
        filter_text = "Supported image files (*)"
        filen = dialog_openfile_hide_param_dirs(
            self.widget, "Open an image file",
            self.model.chi_path, filter_text,
            allowed_file_extensions=allowed_exts)[0]
        filename = str(filen)
        if filename == "":
            return
        if not self._is_valid_raw_image_for_current_chi(filename):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Image file must have the same base name as the CHI file.")
            self._adopt_default_or_selected_raw_image()
            return
        self.model.raw_image_path = filename
        self.model.h5_path = filename
        self._set_raw_image_line_edit_text(filename)
        self.refresh_config_metadata_panel()

    def load_new_poni_from_name(self):
        if self.widget.lineEdit_PONI.isModified():
            if not self._sync_poni_from_line_edit(warn_if_missing=True):
                return
            if not self.model.base_ptn_exist():
                return
            temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
            self._store_selected_poni(self.model.poni, temp_dir)

    def load_new_h5_from_name(self):
        if hasattr(self.widget, "lineEdit_H5") and self.widget.lineEdit_H5.isModified():
            self._sync_raw_image_from_line_edit(warn_if_invalid=True)

    def _format_metadata_label(self, key):
        key = str(key or "").strip().replace("_", " ")
        lowered = key.lower()
        if lowered == "poni version":
            return "PONI version"
        if lowered == "detector config":
            return "Detector config"
        if lowered == "wavelength":
            return "Wavelength"
        return key[:1].upper() + key[1:]

    def _format_float(self, value, precision=6):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return str(value)
        if not np.isfinite(value):
            return str(value)
        return f"{value:.{precision}g}"

    def _build_poni_table_entries(self):
        poni_path = getattr(self.model, "poni", None)
        if not poni_path:
            return [("Status", "No PONI file selected.")]
        if not os.path.exists(poni_path):
            return [
                ("Status", "Selected PONI file is missing."),
            ]

        entries = []
        try:
            poni_content = read_any_poni_file(poni_path)
        except OSError:
            return entries + [("Status", "Could not read PONI file.")]
        for key, value in poni_content.items():
            entries.append((self._format_metadata_label(key), value))
        return entries

    def _build_cake_summary_entries(self):
        diff_img = getattr(self.model, "diff_img", None)
        if diff_img is None:
            return [("Status", "Cake not loaded.")]

        entries = []
        img = getattr(diff_img, "img", None)
        if img is not None:
            try:
                img_arr = np.asarray(img)
                img_y, img_x = img_arr.shape[:2]
                entries.append(("Image pixels X", str(int(img_x))))
                entries.append(("Image pixels Y", str(int(img_y))))
                z_range = diff_img.get_img_zrange()
                if z_range is not None:
                    entries.append((
                        "Image z range",
                        f"{self._format_float(z_range[0])} to "
                        f"{self._format_float(z_range[1])}",
                    ))
            except Exception:
                pass

        intensity_cake, tth_cake, chi_cake = diff_img.get_cake()
        if intensity_cake is None or tth_cake is None or chi_cake is None:
            if entries == []:
                return [("Status", "Cake not loaded.")]
            entries.append(("Cake status", "Cake not loaded."))
            return entries

        cake_arr = np.asarray(intensity_cake)
        if cake_arr.ndim >= 2:
            entries.append(("Cake pixels X", str(int(cake_arr.shape[1]))))
            entries.append(("Cake pixels Y", str(int(cake_arr.shape[0]))))
        else:
            entries.append(("Cake pixels", str(int(cake_arr.size))))
        try:
            entries.append((
                "2theta range",
                f"{self._format_float(np.nanmin(tth_cake))} to "
                f"{self._format_float(np.nanmax(tth_cake))} deg",
            ))
            entries.append((
                "Azimuth range",
                f"{self._format_float(np.nanmin(chi_cake))} to "
                f"{self._format_float(np.nanmax(chi_cake))} deg",
            ))
        except Exception:
            pass

        finite_vals = cake_arr[np.isfinite(cake_arr)]
        if finite_vals.size > 0:
            entries.append((
                "Cake z range",
                f"{self._format_float(np.nanmin(finite_vals))} to "
                f"{self._format_float(np.nanmax(finite_vals))}",
            ))
        return entries or [("Status", "Cake not loaded.")]

    def refresh_config_metadata_panel(self):
        self._adopt_current_or_found_poni()
        self._adopt_default_or_selected_raw_image()
        if not hasattr(self.widget, "set_key_value_table_rows"):
            return
        if hasattr(self.widget, "tableWidget_CakePoniInfo"):
            self.widget.set_key_value_table_rows(
                self.widget.tableWidget_CakePoniInfo,
                self._build_poni_table_entries())
        if hasattr(self.widget, "tableWidget_CakeSummary"):
            self.widget.set_key_value_table_rows(
                self.widget.tableWidget_CakeSummary,
                self._build_cake_summary_entries())
