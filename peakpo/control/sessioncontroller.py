import os
import sys
import dill
import traceback
import tempfile
from importlib.metadata import entry_points
#from pkg_resources import add_activation_listener
import datetime
import pyFAI
import zipfile
import copy
import shutil
import dill._dill as _dill_impl
from qtpy import QtWidgets
from .mplcontroller import MplController
from .waterfalltablecontroller import WaterfallTableController
from .jcpdstablecontroller import JcpdsTableController
from .peakfittablecontroller import PeakfitTableController
from .cakemakecontroller import CakemakeController
from ..utils import dialog_savefile, convert_wl_to_energy, get_temp_dir, \
    make_filename, extract_filename
from ..compat_pickle import PeakPoCompatDillUnpickler
from ..model.param_session_io import (
    save_model_to_param,
    load_model_from_param,
    list_backup_events,
    is_new_param_folder,
)

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
        self.widget.pushButton_LoadDPP.clicked.connect(self.save_dpp)
        if hasattr(self.widget, "pushButton_OpenBackupInfo"):
            self.widget.pushButton_OpenBackupInfo.clicked.connect(
                self.open_backup_info)
        self.widget.pushButton_ZipSession.clicked.connect(self.zip_ppss)
        self.widget.pushButton_SaveJlist.clicked.connect(self.save_dpp)
        self.widget.pushButton_SaveDPPandPPSS.clicked.connect(
            self.save_dpp_ppss)
        self.widget.pushButton_S_SaveSession.clicked.connect(self.save_dpp)

    def _archive_legacy_dpp(self, filen_dpp, base_chi_file):
        """
        Move migrated legacy DPP into PARAM archive folder.
        """
        if not os.path.exists(filen_dpp):
            return None
        param_dir = get_temp_dir(base_chi_file)
        archive_dir = os.path.join(param_dir, "archive-dpp")
        os.makedirs(archive_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.basename(filen_dpp)
        archived = os.path.join(archive_dir, f"{base}.{timestamp}.dpp")
        shutil.move(filen_dpp, archived)
        return archived

    def migrate_dpp_for_chi_if_exists(self, chi_file):
        """
        For CHI-first workflow:
        - if matching legacy DPP exists, open it
        - convert to PARAM session
        - archive original DPP
        Returns True when migration path was used successfully.
        """
        filen_dpp = os.path.splitext(chi_file)[0] + ".dpp"
        if not os.path.exists(filen_dpp):
            return False
        QtWidgets.QMessageBox.information(
            self.widget,
            "Legacy DPP Detected",
            "A legacy DPP session file was detected and will be used to "
            "populate PeakPo information for this CHI.\n\n"
            f"DPP: {filen_dpp}\n\n"
            "After conversion, this DPP will be moved into the PARAM archive."
        )
        success = self._load_dpp(filen_dpp, jlistonly=False)
        if not success:
            return False
        result = save_model_to_param(
            self.model,
            ui_state=self._collect_ui_state(),
            reason="auto-convert-from-dpp",
        )
        archived = self._archive_legacy_dpp(filen_dpp, chi_file)
        if archived is not None:
            print(str(datetime.datetime.now())[:-7],
                  ": Archived migrated DPP:", archived)
            QtWidgets.QMessageBox.information(
                self.widget,
                "DPP Archived",
                "Legacy DPP conversion completed.\n\n"
                "The original DPP has been moved to archive:\n"
                f"{archived}"
            )
        self._sync_ui_from_model(
            manifest_path=str(result.manifest_path),
            ui_state=self._collect_ui_state(),
        )
        return True

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
            self.model.chi_path,
            "Session files (*.dpp *.chi *peakpo_manifest.json)")[0]
        # options=QtWidgets.QFileDialog.DontUseNativeDialog
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        ext = os.path.splitext(fn)[1].lower()
        if ext == ".dpp":
            success = self._load_dpp(fn, jlistonly=False)
            if success:
                try:
                    result = save_model_to_param(
                        self.model,
                        ui_state=self._collect_ui_state(),
                        reason="auto-convert-from-dpp",
                    )
                    print(str(datetime.datetime.now())[:-7],
                          ": Converted DPP to PARAM session:", result.manifest_path)
                except Exception as inst:
                    print(str(datetime.datetime.now())[:-7],
                          ": Warning: DPP opened but PARAM auto-conversion failed.")
                    print("            ", str(inst))
        else:
            success = self._load_new_param_session(fn)
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
                self.widget, "Warning", "Session loading was not successful.")

    def _collect_ui_state(self):
        return {
            "pt_controls": {
                "p_step": self.widget.doubleSpinBox_PStep.value(),
                "t_step": self.widget.spinBox_TStep.value(),
                "jcpds_step": self.widget.doubleSpinBox_JCPDSStep.value(),
            },
            "cake": {
                "azi_shift": self.widget.spinBox_AziShift.value(),
                "int_max": self.widget.spinBox_MaxCakeScale.value(),
                "min_bar": self.widget.horizontalSlider_VMin.value(),
                "max_bar": self.widget.horizontalSlider_VMax.value(),
                "scale_bar": self.widget.horizontalSlider_MaxScaleBars.value(),
            }
        }

    def _apply_ui_state(self, ui_state):
        pt = (ui_state or {}).get("pt_controls", {})
        if pt != {}:
            if "p_step" in pt:
                self.widget.doubleSpinBox_PStep.setValue(float(pt["p_step"]))
            if "t_step" in pt:
                self.widget.spinBox_TStep.setValue(int(pt["t_step"]))
            if "jcpds_step" in pt:
                self.widget.doubleSpinBox_JCPDSStep.setValue(float(pt["jcpds_step"]))
        cake = (ui_state or {}).get("cake", {})
        if cake == {}:
            return
        if "azi_shift" in cake:
            self.widget.spinBox_AziShift.setValue(int(cake["azi_shift"]))
        if "int_max" in cake:
            self.widget.spinBox_MaxCakeScale.setValue(int(cake["int_max"]))
        if "min_bar" in cake:
            self.widget.horizontalSlider_VMin.setValue(int(cake["min_bar"]))
        if "max_bar" in cake:
            self.widget.horizontalSlider_VMax.setValue(int(cake["max_bar"]))
        if "scale_bar" in cake:
            self.widget.horizontalSlider_MaxScaleBars.setValue(int(cake["scale_bar"]))

    def _sync_ui_from_model(self, manifest_path="", ui_state=None):
        """
        Repopulate GUI state from current model after session load/restore.
        """
        if self.model.base_ptn_exist():
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            self.widget.doubleSpinBox_SetWavelength.setValue(
                self.model.get_base_ptn_wavelength())
            xray_energy = convert_wl_to_energy(self.model.get_base_ptn_wavelength())
            self.widget.label_XRayEnergy.setText("({:.3f} keV)".format(xray_energy))
            if self.model.exist_in_waterfall(self.model.base_ptn.fname):
                self.widget.pushButton_AddBasePtn.setChecked(True)
            else:
                self.widget.pushButton_AddBasePtn.setChecked(False)
        self.widget.textEdit_Jlist.setText(str(manifest_path))
        self.widget.textEdit_SessionFileName.setText(str(manifest_path))
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
        self.widget.doubleSpinBox_Pressure.setValue(self.model.get_saved_pressure())
        self.widget.doubleSpinBox_Temperature.setValue(self.model.get_saved_temperature())
        self._apply_ui_state(ui_state or {})
        self.update_inputs()
        self._sync_peakfit_selection_to_current_section()
        self.plot_ctrl.zoom_out_graph()

    def _sync_peakfit_selection_to_current_section(self):
        if not self.model.current_section_exist():
            self.widget.tableWidget_PkFtSections.clearSelection()
            return
        current_ts = self.model.current_section.get_timestamp()
        if current_ts is None:
            self.widget.tableWidget_PkFtSections.clearSelection()
            return
        for i, sec in enumerate(self.model.section_lst):
            if sec.get_timestamp() == current_ts:
                self.widget.tableWidget_PkFtSections.selectRow(i)
                return

    def _infer_base_chi_from_manifest(self, manifest_file):
        param_dir = os.path.dirname(manifest_file)
        basename = os.path.basename(param_dir)
        if not basename.endswith("-param"):
            return None
        base_no_ext = basename[:-6]
        candidate = os.path.join(os.path.dirname(param_dir), base_no_ext + ".chi")
        if os.path.exists(candidate):
            return candidate
        return None

    def _load_new_param_session(self, selected_file):
        ext = os.path.splitext(selected_file)[1].lower()
        if ext == ".chi":
            base_chi = selected_file
            param_dir = os.path.join(
                os.path.dirname(base_chi),
                os.path.splitext(os.path.basename(base_chi))[0] + "-param",
            )
        else:
            base_chi = self._infer_base_chi_from_manifest(selected_file)
            param_dir = os.path.dirname(selected_file)
            if base_chi is None:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Cannot infer base .chi file from selected manifest.")
                return False
        if not is_new_param_folder(param_dir):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "No valid new-format session manifest found in PARAM folder.")
            return False

        backup_events = list_backup_events(param_dir)
        backup_idx = None
        if backup_events:
            items = ["Current (latest)"]
            labels_to_idx = {}
            for idx, event in reversed(list(enumerate(backup_events))):
                highlights = ", ".join(event.get("highlights", []))
                if highlights == "":
                    highlights = "none"
                label = (
                    f"{event.get('id')} | "
                    f"{event.get('timestamp', '')} | "
                    f"{event.get('reason', 'save')} | "
                    f"{highlights}"
                )
                items.append(label)
                labels_to_idx[label] = idx
            selected, ok = QtWidgets.QInputDialog.getItem(
                self.widget,
                "Load Session Version",
                "Choose setup timestamp:",
                items, 0, False)
            if not ok:
                return False
            if selected != "Current (latest)":
                backup_idx = labels_to_idx.get(selected)

        success, meta = load_model_from_param(
            self.model,
            base_chi,
            backup_event_index=backup_idx,
        )
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Failed to load PARAM session: " + str(meta.get("reason")))
            return False

        self._sync_ui_from_model(
            manifest_path=str(meta.get("manifest", "")),
            ui_state=meta.get("ui_state", {}),
        )
        return True

    def autoload_param_for_chi(self, base_chi_file):
        """
        Automatically load PARAM session data for an opened CHI file, if found.
        Returns True when PARAM session is loaded, False otherwise.
        """
        param_dir = os.path.join(
            os.path.dirname(base_chi_file),
            os.path.splitext(os.path.basename(base_chi_file))[0] + "-param",
        )
        if not is_new_param_folder(param_dir):
            return False
        success, meta = load_model_from_param(self.model, base_chi_file)
        if not success:
            print(str(datetime.datetime.now())[:-7],
                  ": PARAM autoload failed:", str(meta.get("reason")))
            return False
        self._sync_ui_from_model(
            manifest_path=str(meta.get("manifest", "")),
            ui_state=meta.get("ui_state", {}),
        )
        return True

    def open_backup_info(self):
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Open a CHI file first.")
            return
        param_dir = get_temp_dir(self.model.get_base_ptn_filename())
        if not is_new_param_folder(param_dir):
            QtWidgets.QMessageBox.information(
                self.widget, "Backup Info",
                "No new-format PARAM session was found for this CHI.")
            return
        events = list_backup_events(param_dir)
        if not events:
            QtWidgets.QMessageBox.information(
                self.widget, "Backup Info",
                "No backup snapshots were recorded yet.")
            return
        items = []
        labels_to_idx = {}
        for idx, ev in reversed(list(enumerate(events))):
            highlights = ", ".join(ev.get("highlights", []))
            if highlights == "":
                highlights = "none"
            label = (
                f"{ev.get('id')} | {ev.get('reason', 'save')} | "
                f"{ev.get('timestamp', '')} | "
                f"{len(ev.get('changed_files', []))} files | "
                f"{highlights}"
            )
            items.append(label)
            labels_to_idx[label] = idx
        selected, ok = QtWidgets.QInputDialog.getItem(
            self.widget,
            "Restore Backup Snapshot",
            "Select a backup to restore:",
            items, 0, False)
        if not ok:
            return
        backup_idx = labels_to_idx.get(selected)
        if backup_idx is None:
            return
        backup_id = events[backup_idx].get("id")
        # Ensure in-progress spinbox text is committed before pre-restore save.
        self.jcpdstable_ctrl.sync_model_from_table()
        self.widget.doubleSpinBox_Pressure.interpretText()
        self.widget.doubleSpinBox_Temperature.interpretText()
        # Sync model scalar state from GUI before creating pre-restore backup.
        self.model.save_pressure(self.widget.doubleSpinBox_Pressure.value())
        self.model.save_temperature(self.widget.doubleSpinBox_Temperature.value())
        # Before restore, backup current setup.
        pre = save_model_to_param(
            self.model,
            ui_state=self._collect_ui_state(),
            reason=f"pre-restore-{backup_id}",
            force_backup=True,
        )
        base_chi = self.model.get_base_ptn_filename()
        success, meta = load_model_from_param(
            self.model, base_chi, backup_event_index=backup_idx)
        if not success:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Backup restore failed: " + str(meta.get("reason")))
            return
        self._sync_ui_from_model(
            manifest_path=str(meta.get("manifest", "")),
            ui_state=meta.get("ui_state", {}),
        )
        if pre.backup_id is None:
            pre_text = "No pre-restore backup was created (no file changes)."
        else:
            pre_text = f"Current setup was backed up first as: {pre.backup_id}"
        msg = (
            f"Restored backup: {backup_id}\n\n{pre_text}"
        )
        QtWidgets.QMessageBox.information(
            self.widget, "Backup Restored", msg)

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
        debug_compat = os.environ.get("PEAKPO_DEBUG_COMPAT_PICKLE", "").strip() == "1"
        if (not os.path.exists(filen_dpp)) or (os.path.getsize(filen_dpp) == 0):
            QtWidgets.QMessageBox.warning(
                self.widget,
                "Warning",
                "DPP file is empty or missing.\n\n"
                f"File: {filen_dpp}\n"
                f"Size: {os.path.getsize(filen_dpp) if os.path.exists(filen_dpp) else 0} bytes",
            )
            return False
        try:
            from .. import compat_pickle as _compat_pickle_module
            debug_info = (
                f"compat_pickle: {_compat_pickle_module.__file__}\n"
                f"dill._create_code: {_dill_impl._create_code} "
                f"[{getattr(_dill_impl._create_code, '__module__', '?')}]\n"
                f"dill.CodeType: {_dill_impl.CodeType} "
                f"[{getattr(_dill_impl.CodeType, '__module__', '?')}]\n"
                f"types.CodeType: {__import__('types').CodeType} "
                f"[{getattr(__import__('types').CodeType, '__module__', '?')}]\n"
                f"builtins.code: {getattr(__import__('builtins'), 'code', None)}\n"
                f"compat_code_ctor_calls(before): "
                f"{getattr(_compat_pickle_module, '_compat_code_ctor_calls', 'n/a')}"
            )
            if debug_compat:
                print(debug_info)
            with open(filen_dpp, 'rb') as f:
                model_dpp = PeakPoCompatDillUnpickler(f).load()
        except EOFError:
            QtWidgets.QMessageBox.warning(
                self.widget,
                "Warning",
                "DPP file appears truncated or corrupted (unexpected end of file).\n\n"
                f"File: {filen_dpp}\n"
                f"Size: {os.path.getsize(filen_dpp)} bytes\n\n"
                "Try loading a backup copy (*.bak*), or re-save this session from the source data."
            )
            return False
        except Exception as inst:
            from .. import compat_pickle as _compat_pickle_module
            err = traceback.format_exc()
            if debug_compat:
                print(err)
            debug_info = debug_info + "\n" + (
                "compat_code_ctor_calls(after): "
                f"{getattr(_compat_pickle_module, '_compat_code_ctor_calls', 'n/a')}"
            )
            message = str(inst)
            if debug_compat:
                message += "\n\n" + debug_info + "\n\n" + err
            QtWidgets.QMessageBox.warning(self.widget, "Warning", message)
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
                    temp_values.append(int(line.split(':')[1]))
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
        if self.model.poni_exist() and (not self.model.diff_img_exist()) and \
                self.model.associated_image_exists():
            success_img = self.model.load_associated_img()
            if success_img:
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
        # Write atomically to avoid creating partial/empty .dpp on failures.
        model_dill = copy.deepcopy(self.model.to_model7())
        # Keep DPP lean: do not embed raw/cake image data in session files.
        model_dill.diff_img = None
        try:
            payload = dill.dumps(model_dill)
        except Exception:
            # Fallback: strip transient lmfit runtime objects.
            self._strip_runtime_fit_objects(model_dill)
            payload = dill.dumps(model_dill)

        target_dir = os.path.dirname(os.path.abspath(filen_dpp)) or "."
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=target_dir) as tmpf:
                tmp_path = tmpf.name
                tmpf.write(payload)
                tmpf.flush()
                os.fsync(tmpf.fileno())
            os.replace(tmp_path, filen_dpp)
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.remove(tmp_path)

        try:
            self.model.save_to_txtdata(get_temp_dir(self.model.get_base_ptn_filename()))
        except Exception as inst:
            # Text export is auxiliary; do not fail DPP save when this fails.
            print(str(datetime.datetime.now())[:-7],
                  ": Warning: save_to_txtdata failed, DPP is still saved.")
            print("            ", str(inst))

    def _strip_runtime_fit_objects(self, model_dill):
        def _clean_section(section):
            if section is None:
                return
            if hasattr(section, 'fit_result'):
                section.fit_result = None
            if hasattr(section, 'fit_model'):
                section.fit_model = None
            if hasattr(section, 'parameters'):
                section.parameters = None

        if hasattr(model_dill, 'section_lst') and (model_dill.section_lst is not None):
            for section in model_dill.section_lst:
                _clean_section(section)
        if hasattr(model_dill, 'current_section'):
            _clean_section(model_dill.current_section)

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
        step = float(self.widget.doubleSpinBox_JCPDSStep.value())
        self.jcpdstable_ctrl.update(step=step)
        self.peakfit_table_ctrl.update_sections()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_baseline_constraints()
        self.peakfit_table_ctrl.update_peak_constraints()

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
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Open a base chi file before saving a session.")
            return
        # Ensure in-progress table/field edits are committed before save.
        self.jcpdstable_ctrl.sync_model_from_table()
        self.widget.doubleSpinBox_Pressure.interpretText()
        self.widget.doubleSpinBox_Temperature.interpretText()
        self.model.save_pressure(
            self.widget.doubleSpinBox_Pressure.value())
        self.model.save_temperature(
            self.widget.doubleSpinBox_Temperature.value())
        try:
            result = save_model_to_param(
                self.model,
                ui_state=self._collect_ui_state(),
                reason="manual-save",
            )
        except Exception as inst:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Saving PARAM session failed:\n" + str(inst))
            return
        print(str(datetime.datetime.now())[:-7],
              ": Save PARAM session:", result.manifest_path)
        if result.backup_id is not None:
            events = list_backup_events(result.param_dir)
            highlights = []
            if events:
                highlights = events[-1].get("highlights", [])
            highlights_text = ", ".join(highlights) if highlights else "none"
            print(str(datetime.datetime.now())[:-7],
                  f": Backup snapshot created: {result.backup_id} "
                  f"({len(result.changed_files)} changed files; "
                  f"highlights: {highlights_text})")
        else:
            print(str(datetime.datetime.now())[:-7],
                  ": No backup snapshot created (no file changes detected).")
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
        self.widget.textEdit_SessionFileName.setText(str(result.manifest_path))
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
