import os
import sys
import dill
from importlib.metadata import entry_points
#from pkg_resources import add_activation_listener
import datetime
import pyFAI
import zipfile
import copy
from PyQt5 import QtWidgets
from .mplcontroller import MplController
from .waterfalltablecontroller import WaterfallTableController
from .jcpdstablecontroller import JcpdsTableController
from .peakfittablecontroller import PeakfitTableController
from .cakemakecontroller import CakemakeController
from utils import dialog_savefile, convert_wl_to_energy, get_temp_dir, \
    make_filename, extract_filename, get_unique_filename, backup_copy

class SessionController(object):

    def __init__(self, model, widget):
        self.model = model
        self.widget = widget
        self.plot_ctrl = MplController(self.model, self.widget)
        self.waterfalltable_ctrl = \
            WaterfallTableController(self.model, self.widget)
        self.jcpdstable_ctrl = JcpdsTableController(self.model, self.widget)
        self.peakfit_table_ctrl = PeakfitTableController(
            self.model, self.widget)
        self.cakemake_ctrl = CakemakeController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_SaveDPP.clicked.connect(self.save_dpp)
        self.widget.pushButton_SavePPSS.clicked.connect(self.save_ppss)
        self.widget.pushButton_LoadPPSS.clicked.connect(self.load_ppss)
        self.widget.pushButton_LoadDPP.clicked.connect(self.load_dpp)
        self.widget.pushButton_ZipSession.clicked.connect(self.zip_ppss)
        self.widget.pushButton_SaveJlist.clicked.connect(self.save_dpp)
        self.widget.pushButton_SaveDPPandPPSS.clicked.connect(
            self.save_dpp_ppss)
        self.widget.pushButton_S_SaveSession.clicked.connect(self.save_dpp_ppss)

    def load_ppss(self):
        """
        get existing jlist file from data folder
        """
        fn = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.model.chi_path, "(*.ppss)")[0]
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        self._load_ppss(fn, jlistonly=False)
        self.plot_ctrl.zoom_out_graph()
        self.update_inputs()

    def load_dpp(self):
        """
        get existing jlist file from data folder
        """
        fn = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.model.chi_path, "(*.dpp)")[0]
        # options=QtWidgets.QFileDialog.DontUseNativeDialog
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        success = self._load_dpp(fn, jlistonly=False)
        if success:
            if self.model.exist_in_waterfall(self.model.base_ptn.fname):
                self.widget.pushButton_AddBasePtn.setChecked(True)
            else:
                self.widget.pushButton_AddBasePtn.setChecked(False)
            if self.widget.checkBox_ShowCake.isChecked():
                self._load_cake_format_file()
            self.plot_ctrl.zoom_out_graph()
            self.update_inputs()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "DPP loading was not successful.")

    def _update_ppss(self):
        if not self.model.base_ptn_exist():
            return
        fn = self.model.make_filename('ppss')
        if not os.path.exists(fn):
            return
        self._load_ppss(fn, jlistonly=False)
        self.update_inputs()

    def _load_ppss(self, fsession, jlistonly=False):
        '''
        internal method for reading pickled ppss file
        '''
        self.model.read_ppss(fsession)
        success = self._load_jcpds_from_ppss()
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The JCPDS in the PPSS cannot be found.")
        else:
            self.widget.textEdit_Jlist.setText(str(fsession))
        if jlistonly:
            return
        success = self._load_base_ptn_from_ppss(fsession)
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The base pattern file in the PPSS cannot be found.")
        else:
            # self.widget.textEdit_DiffractionPatternFileName.setText(
            #    '1D pattern: ' + str(self.model.base_ptn.fname))
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            # ppss should not do this.
            #self.widget.textEdit_SessionFileName.setText(str(fsession))
        success = self._load_waterfall_ptn_from_ppss()
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The waterfall pattern files in the PPSS cannot be found.")

    def _load_dpp(self, filen_dpp, jlistonly=False):
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
        # inspect the paths of baseptn and update all file paths
        if (model_dpp.chi_path != os.path.dirname(filen_dpp)):
            if os.path.exists(model_dpp.chi_path):
                if self.widget.checkBox_IgnoreDirChange.isChecked():
                    return self._set_from_dpp(filen_dpp, model_dpp,
                                              jlistonly=jlistonly)
                else:
                    reply = QtWidgets.QMessageBox.question(
                        self.widget, "Question",
                        "DPP seems to be moved from the original folder. \
                        However, you seem to have files in the original folder.\
                        OK to proceed?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes)
                    if reply == QtWidgets.QMessageBox.Yes:
                        return self._set_from_dpp(filen_dpp, model_dpp,
                                                  jlistonly=jlistonly)
                    else:
                        return False
            else:  # file no longer exist in the original location
                if self.widget.checkBox_IgnoreDirChange.isChecked():
                    return self._set_from_dpp(
                        filen_dpp, model_dpp,
                        new_folder=os.path.dirname(filen_dpp),
                        jlistonly=jlistonly)
                else:
                    reply = QtWidgets.QMessageBox.question(
                        self.widget, "Question",
                        "DPP seems to be moved from the original folder. " +
                        "Move related files to this DPP folder " +
                        " if they are not in the new folder." +
                        "If files have been moved, click Yes.",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes)
                    if reply == QtWidgets.QMessageBox.Yes:
                        return self._set_from_dpp(
                            filen_dpp, model_dpp,
                            new_folder=os.path.dirname(filen_dpp),
                            jlistonly=jlistonly)
                    else:
                        return False
        else:
            return self._set_from_dpp(filen_dpp, model_dpp,
                                      jlistonly=jlistonly)
        #

    def _load_cake_format_file(self):
        # get filename
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        """
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a cake format File", temp_dir,
            # self.model.chi_path,
            "Data files (*.cakeformat)")[0]
        """
        ext = "cakeformat"
        #filen_t = self.model.make_filename(ext)
        filen = make_filename(self.model.base_ptn.fname, ext,
                              temp_dir=temp_dir)
        if os.path.exists(filen):
            temp_values = []
            with open(filen, "r") as f:
                for line in f:
                    temp_values.append(float(line.split(':')[1]))
            self.widget.spinBox_AziShift.setValue(temp_values[0])
            self.widget.spinBox_MaxCakeScale.setValue(temp_values[1])
            self.widget.horizontalSlider_VMin.setValue(temp_values[2])
            self.widget.horizontalSlider_VMax.setValue(temp_values[3])
            self.widget.horizontalSlider_MaxScaleBars.setValue(temp_values[4])

    def _save_cake_format_file(self):
        # make filename
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        ext = "cakeformat"
        #filen_t = self.model.make_filename(ext)
        filen = make_filename(self.model.base_ptn.fname, ext,
                              temp_dir=temp_dir)
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

    def _set_from_dpp(self, filen_dpp, model_dpp, new_folder=None,
                      jlistonly=False):
        if new_folder is None:
            self.model.set_from(model_dpp, jlistonly=jlistonly)
        else:
            self.model.set_from(model_dpp, new_chi_path=new_folder,
                                jlistonly=jlistonly)
        if self.model.poni_exist() and (not self.model.diff_img_exist()):
            self.model.load_associated_img()
            self.cakemake_ctrl.cook()
        self.widget.textEdit_Jlist.setText(str(filen_dpp))
        # self.widget.textEdit_DiffractionPatternFileName.setText(
        #    '1D pattern: ' + str(self.model.base_ptn.fname))
        self.widget.lineEdit_DiffractionPatternFileName.setText(
            str(self.model.base_ptn.fname))
        self.widget.textEdit_SessionFileName.setText(str(filen_dpp))
        if self.model.poni_exist():
            self.widget.lineEdit_PONI.setText(self.model.poni)
        else:
            self.widget.lineEdit_PONI.setText('')
        if self.model.diff_img_exist():
            self.widget.textEdit_DiffractionImageFilename.setText(
                self.model.diff_img.img_filename)
        else:
            self.widget.textEdit_DiffractionImageFilename.setText(
                'Image file must have the same name ' +
                'as base ptn in the same folder.')
        self.widget.doubleSpinBox_Pressure.setValue(
            self.model.get_saved_pressure())
        self.widget.doubleSpinBox_Temperature.setValue(
            self.model.get_saved_temperature())
        self.widget.doubleSpinBox_SetWavelength.setValue(
            self.model.get_base_ptn_wavelength())
        xray_energy = convert_wl_to_energy(self.model.get_base_ptn_wavelength())
        self.widget.label_XRayEnergy.setText("({:.3f} keV)".format(xray_energy))
        return True

        """
        success = self._load_jcpds_from_session()
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The JCPDS in the PPSS cannot be found.")
        else:
            self.widget.textEdit_Jlist.setText('Jlist: ' + str(fsession))
        if jlistonly:
            return
        success = self._load_base_ptn_from_session(fsession)
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The base pattern file in the PPSS cannot be found.")
        else:
            self.widget.textEdit_DiffractionPatternFileName.setText(
                '1D pattern: ' + str(self.model.base_ptn.fname))
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            self.widget.textEdit_SessionFileName.setText(
                'Session: ' + str(fsession))
        success = self._load_waterfall_ptn_from_session()
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "The waterfall pattern files in the PPSS cannot be found.")
        """

    def _load_base_ptn_from_ppss(self, fsession):
        if self.model.session.chi_path == '':
            return False
        if not os.path.exists(self.model.session.chi_path):
            chi_path_from_fsession = os.path.dirname(str(fsession))
            chi_basefilen = os.path.basename(self.model.session.pattern.fname)
            chi_filen_at_fsession_dir = os.path.join(
                chi_path_from_fsession, chi_basefilen)
            if os.path.exists(chi_filen_at_fsession_dir):
                new_chi_filen = chi_filen_at_fsession_dir
                new_chi_path = chi_path_from_fsession
            else:
                return False
        else:
            new_chi_filen = self.model.session.pattern.fname
        self.model.set_base_ptn(new_chi_filen, self.model.session.wavelength)
        self.model.base_ptn.get_chbg(self.model.session.bg_roi,
                                     self.model.session.bg_params, yshift=0)
        self.widget.doubleSpinBox_SetWavelength.setValue(
            self.model.session.wavelength)
        xray_energy = convert_wl_to_energy(self.model.session.wavelength)
        self.widget.label_XRayEnergy.setText(
            "({:.3f} keV)".format(xray_energy))
        self.widget.doubleSpinBox_Pressure.setValue(
            self.model.session.pressure)
        self.widget.doubleSpinBox_Temperature.setValue(
            self.model.session.temperature)
        self.widget.doubleSpinBox_Background_ROI_min.setValue(
            self.model.session.bg_roi[0])
        self.widget.doubleSpinBox_Background_ROI_max.setValue(
            self.model.session.bg_roi[1])
        self.widget.spinBox_BGParam0.setValue(
            self.model.session.bg_params[0])
        self.widget.spinBox_BGParam1.setValue(
            self.model.session.bg_params[1])
        self.widget.spinBox_BGParam2.setValue(
            self.model.session.bg_params[2])
        return True

    def _load_waterfall_ptn_from_ppss(self):
        if self.model.session.chi_path == '':
            return False
        if self.model.session.waterfallpatterns == []:
            return True
        else:
            new_wf_ptn_names = []
            new_wf_wavelength = []
            new_wf_display = []
            for ptn in self.model.session.waterfallpatterns:
                if os.path.exists(ptn.fname):
                    new_wf_ptn_names.append(ptn.fname)
                elif os.path.exists(os.path.join(
                        self.model.chi_path, os.path.basename(ptn.fname))):
                    new_wf_ptn_names.append(
                        os.path.join(
                            self.model.chi_path, os.path.basename(ptn.fname)))
                    new_wf_wavelength.append(ptn.wavelength)
                    new_wf_display.append(ptn.display)
                else:
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        "Some waterfall paterns in PPSS do not exist.")
            if new_wf_ptn_names == []:
                return False
            else:
                self.model.set_waterfall_ptn(
                    new_wf_ptn_names, new_wf_wavelength, new_wf_display,
                    self.model.session.bg_roi, self.model.session.bg_params)
                return True

    def _load_jcpds_from_ppss(self):
        if (self.model.session.jcpds_path == ''):
            return False
        if os.path.exists(self.model.session.jcpds_path):
            self.model.set_jcpds_path(self.model.session.jcpds_path)
            self.model.set_jcpds_from_ppss()
            return True
        else:
            reply = QtWidgets.QMessageBox.question(
                self.widget, "Question",
                "The JCPDS path in the PPSS does not exist.  \
                Do you want to update the JCPDS path?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes)
            if reply == QtWidgets.QMessageBox.Yes:
                jcpds_path = \
                    QtWidgets.QFileDialog.getExistingDirectory(
                        self.widget, "Open Directory", self.model.jcpds_path,
                        QtWidgets.QFileDialog.ShowDirsOnly)
                self.model.set_jcpds_path(jcpds_path)
                self.model.set_jcpds_from_ppss()
                return True
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "JCPDS path does not match.")
                return False

    def _dump_dpp(self, filen_dpp):
        with open(filen_dpp, 'wb') as f:
            # cake cannot be dilled, so I remove it before dill
            model_dill = copy.deepcopy(self.model.to_model7())
            try:
                dill.dump(model_dill, f)
                self.model.save_to_txtdata(get_temp_dir(self.model.get_base_ptn_filename()))
            except:
                model_dill.diff_img = None
                dill.dump(model_dill, f)
                self.model.save_to_txtdata(get_temp_dir(self.model.get_base_ptn_filename()))

    def _dump_ppss(self, fsession):
        """
        session = *.ppss
        """
        self.model.write_as_ppss(
            fsession, self.widget.doubleSpinBox_Pressure.value(),
            self.widget.doubleSpinBox_Temperature.value())

    def update_inputs(self):
        self.reset_bgsub()
        self.waterfalltable_ctrl.update()
        self.jcpdstable_ctrl.update()
        self.peakfit_table_ctrl.update_sections()
        self.peakfit_table_ctrl.update_peak_parameters()

    def zip_ppss(self):
        """
        session = *.ppss
        """
        if not self.model.base_ptn_exist():
            fzip = os.path.join(self.model.chi_path, 'default.zip')
        else:
            fzip = self.model.make_filename('zip')
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Question',
            'Do you want to save in default filename, %s ?' % fzip,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            fzip = QtWidgets.QFileDialog.getSaveFileName(
                self.widget, "Save A Zip File",
                fzip, "(*.zip)", None)[0]
        else:
            if os.path.exists(fzip):
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Question',
                    'The file already exist.  Do you want to overwrite?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.No:
                    return
        if str(fzip) != '':
            path, filen = os.path.split(str(fzip))
            fsession_name = '%s.forzip.dpp' % filen
            fsession = os.path.join(path, fsession_name)
            self._dump_dpp(str(fsession))
            self.widget.textEdit_Jlist.setText('Jlist : ' + str(fsession))
            zf = zipfile.ZipFile(str(fzip), 'w', zipfile.ZIP_DEFLATED)
            zf.write(fsession, arcname=fsession_name)
            if self.model.base_ptn_exist():
                dum, filen = os.path.split(self.model.base_ptn.fname)
                zf.write(self.model.base_ptn.fname, arcname=filen)
            if self.model.diff_img is not None:
                dum, filen = os.path.split(self.model.diff_img.img_filename)
                zf.write(self.model.diff_img.img_filename, arcname=filen)
            path, filen = os.path.split(str(fzip))
            folder_name = extract_filename(fzip) + '-param'
            folder_path = os.path.join(path, folder_name)
            for file in os.listdir(folder_path):
                full_path = os.path.join(folder_path, file)
                if os.path.isfile(full_path):
                    zf.write(full_path, arcname=os.path.join(folder_name, file))
            """
            if self.model.waterfall_exist():
                for wf in self.model.waterfall_ptn:
                    dum, filen = os.path.split(wf.fname)
                    zf.write(wf.fname, arcname=filen)
            """
            zf.close()
            QtWidgets.QMessageBox.warning(
                self.widget, "Information",
                "A Zip file was saved for sharing in " + fzip)

            print(str(datetime.datetime.now())[:-7], 
                    ": Save ", fzip)
            print("            Because waterfall paths can be complicated, chi and tif files listed in waterfall are not included.")

    def save_dpp_ppss(self):
        # save temp files
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        if (self.model.associated_image_exists() and 
            (self.model.diff_img != None) ):
            self.model.diff_img.write_temp_cakefiles(temp_dir=temp_dir)
        self.model.base_ptn.write_temporary_bgfiles(temp_dir)
        self.save_dpp()
        self.save_ppss()

    def save_dpp(self, quiet=False):
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.model.chi_path, 'default.dpp')
        else:
            fsession = self.model.make_filename('dpp')
        if self.widget.checkBox_ForceOverwite.isChecked():
            new_filename = fsession
            if os.path.exists(fsession) and (not quiet):
                msg_box = QtWidgets.QMessageBox(self.widget)
                msg_box.setWindowTitle("Question")
                msg_box.setText("DPP with default name already exist. Overwrite?\n\n" + \
                    "For Backup, a copy of the existing DPP will be made\n" + \
                    "and then the default named DPP will be created."    )
                overwrite_button = msg_box.addButton("Overwrite", 
                                                     QtWidgets.QMessageBox.YesRole)
                backup_button = msg_box.addButton("Backup", 
                                                  QtWidgets.QMessageBox.NoRole)
                cancel_button = msg_box.addButton("Cancel", 
                                                  QtWidgets.QMessageBox.RejectRole)

                msg_box.setDefaultButton(overwrite_button)
                msg_box.exec_()
                reply = msg_box.clickedButton()
                if reply == backup_button:
                    backup_file_name = backup_copy(new_filename)
                    if backup_file_name == None:
                        QtWidgets.QMessageBox.warning(
                            self.widget, "Warning",
                            "More than 99 backup files were found.\n" +
                            "Delete some unused backup files and try again.")
                    else:
                        print(str(datetime.datetime.now())[:-7],
                            ": Existing DPP file copied to: " + 
                            backup_file_name)
                elif reply == cancel_button:
                    return 
        else:
            new_filename = dialog_savefile(self.widget, fsession)
        if new_filename != '':
            self.model.save_pressure(
                self.widget.doubleSpinBox_Pressure.value())
            self.model.save_temperature(
                self.widget.doubleSpinBox_Temperature.value())
            self._dump_dpp(new_filename)
            print(str(datetime.datetime.now())[:-7], 
                    ": Save ", new_filename)
            if self.widget.checkBox_ShowCake.isChecked():
                self._save_cake_format_file()
                print(str(datetime.datetime.now())[:-7], 
                    ": Update temporary cake image file.")
            # save version information for key modules
            try:
                env = os.environ['CONDA_DEFAULT_ENV']
            except:
                env = 'unknown'            
            temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
            ext = "sysinfo.txt"
            #filen_t = self.model.make_filename(ext)
            filen = make_filename(self.model.base_ptn.fname, ext,
                                  temp_dir=temp_dir)
            with open(filen, "w") as f:
                f.write('OS: ' + os.name + '\n')
                f.write('Python ver.: ' + sys.version + '\n')
                f.write("Environment: " + env + '\n')
                f.write("dill ver.: " + dill.__version__ + '\n')
                f.write("pyFAI ver.: " + pyFAI.version + '\n')
            print(str(datetime.datetime.now())[:-7], 
                    ": Save ", filen)
            self.widget.textEdit_SessionFileName.setText(str(new_filename))
            self.widget.tableWidget_PkFtSections.setStyleSheet(
                "Background-color:None;color:rgb(0,0,0);")

    def save_ppss(self, quiet=False):
        """
        session = *.ppss
        """
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.model.chi_path, 'dum.ppss')
        else:
            fsession = self.model.make_filename('ppss')
        if self.widget.checkBox_ForceOverwite.isChecked():
            new_filename = fsession
            """
            if not quiet:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Force overwrite is On, so existing ppss with default name" +
                    " will be overwritten.")
            """
        else:
            new_filename = dialog_savefile(self.widget, fsession)
        if new_filename != '':
            self._dump_ppss(new_filename)
            print(str(datetime.datetime.now())[:-7], 
                ": Save ", new_filename)
            # ppss should not do this.
            #self.widget.textEdit_SessionFileName.setText(str(new_filename))

    def save_ppss_with_default_name(self):
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.model.chi_path, 'dum.ppss')
        else:
            fsession = self.model.make_filename('ppss')
        if os.path.exists(fsession):
            reply = QtWidgets.QMessageBox.question(
                self.widget, 'Question',
                'The file already exist.  Do you want to overwrite?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes)
            if reply == QtWidgets.QMessageBox.No:
                return
        if str(fsession) != '':
            self._dump_ppss(str(fsession))
            # ppss should not do this.
            #self.widget.textEdit_SessionFileName.setText(str(fsession))

    def reset_bgsub(self):
        '''
        this is to read from session file and put to the table
        '''
        self.widget.spinBox_BGParam0.setValue(
            self.model.base_ptn.params_chbg[0])
        self.widget.spinBox_BGParam1.setValue(
            self.model.base_ptn.params_chbg[1])
        self.widget.spinBox_BGParam2.setValue(
            self.model.base_ptn.params_chbg[2])
        self.widget.doubleSpinBox_Background_ROI_min.setValue(
            self.model.base_ptn.x_bg[0])
        self.widget.doubleSpinBox_Background_ROI_max.setValue(
            self.model.base_ptn.x_bg[-1])
        # the line below seems to be unnecessary, as there should be bgsub
        # self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        # if self.model.waterfall_exist():
        #    for pattern in self.model.waterfall_ptn:
        #        pattern.get_chbg(bg_roi, bg_params, yshift=0)
