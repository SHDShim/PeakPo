import os
import json
from qtpy import QtCore, QtWidgets
from ..utils import get_sorted_filelist, find_from_filelist, readchi, \
    make_filename, writechi, get_directory, dialog_openfile_hide_param_dirs
from ..utils import undo_button_press, get_temp_dir
import datetime
from .mplcontroller import MplController
from .cakecontroller import CakeController
from .xrdiohelpers import DioptasMetadataCollection
from ..model.azimuthal_integration import provenance_for_chi


class BasePatternController(object):

    def __init__(self, model, widget, session_ctrl=None):
        self.model = model
        self.widget = widget
        self.session_ctrl = session_ctrl
        self.pattern_loaded_callback = None
        self.plot_ctrl = MplController(self.model, self.widget)
        self.cake_ctrl = CakeController(self.model, self.widget)
        self.connect_channel()

    def set_pattern_loaded_callback(self, callback):
        self.pattern_loaded_callback = callback

    def _notify_pattern_loaded(self, filename):
        if callable(self.pattern_loaded_callback):
            self.pattern_loaded_callback(filename)

    def connect_channel(self):
        self.widget.pushButton_NewBasePtn.clicked.connect(
            self.select_base_ptn)
        self.widget.lineEdit_DiffractionPatternFileName.editingFinished.\
            connect(self.load_new_base_pattern_from_name)

    def select_base_ptn(self):
        """
        opens a file select dialog
        """
        filen, _ = dialog_openfile_hide_param_dirs(
            self.widget, "Open a Chi File", self.model.chi_path,
            "Data files (*.chi)", default_hide_param_dirs=True)
        if not filen:
            return
        self._setshow_new_base_ptn(str(filen))

    def load_new_base_pattern_from_name(self):
        if self.widget.lineEdit_DiffractionPatternFileName.isModified():
            filen = self.widget.lineEdit_DiffractionPatternFileName.text()
            self._setshow_new_base_ptn(filen)

    def _same_path(self, path_a, path_b):
        if not path_a or not path_b:
            return False
        return os.path.normcase(os.path.abspath(path_a)) == \
            os.path.normcase(os.path.abspath(path_b))

    def _is_derived_provenance(self, provenance):
        return (
            isinstance(provenance, dict) and
            provenance.get("source_kind") == "azimuthal_integration" and
            bool(provenance.get("source_chi"))
        )

    def _setshow_new_base_ptn(self, filen, display_derived=False):
        """
        load and then send signal to update_graph
        """
        if os.path.exists(filen):
            provenance = provenance_for_chi(filen)
            migration_target = filen
            if self._is_derived_provenance(provenance):
                source_chi = provenance.get("source_chi")
                if source_chi and os.path.exists(source_chi):
                    migration_target = source_chi
            self.model.set_chi_path(os.path.split(migration_target)[0])
            if self.session_ctrl is not None:
                migrated = self.session_ctrl.migrate_dpp_for_chi_if_exists(
                    migration_target)
                if migrated:
                    print(str(datetime.datetime.now())[:-7],
                          ': Loaded legacy DPP, converted to PARAM, and archived DPP.')
                    return
            if self.model.base_ptn_exist():
                old_filename = self.model.get_base_ptn_filename()
            else:
                old_filename = None
            new_filename = filen
            self._load_a_new_pattern(
                new_filename, display_derived=display_derived)
            if old_filename is None:
                self.plot_new_graph()
            else:
                self.apply_changes_to_graph()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find ' + filen)
            # self.widget.lineEdit_DiffractionPatternFileName.setText(
            #    self.model.get_base_ptn_filename())

    def _load_a_new_pattern(self, new_filename, display_derived=False):
        """
        load and process base pattern.  does not signal to update_graph
        """
        provenance = provenance_for_chi(new_filename)
        if self._is_derived_provenance(provenance):
            source_chi = provenance.get("source_chi")
            if display_derived:
                self._load_derived_display_pattern(new_filename, provenance)
                return
            if source_chi and os.path.exists(source_chi):
                new_filename = source_chi
                provenance = provenance_for_chi(new_filename)
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "This azimuth-derived CHI does not have an available "
                    "full-azimuth source CHI:\n" + str(source_chi))
                return

        if self.model.base_ptn_exist() and \
                self._same_path(self.model.get_base_ptn_filename(), new_filename):
            if getattr(self.model, "display_ptn_exist", lambda: False)():
                self.model.clear_display_ptn()
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.get_base_ptn_filename()))
            self._update_metadata_tab_for_chi(new_filename)
            self._notify_pattern_loaded(new_filename)
            if self.session_ctrl is not None:
                self.session_ctrl.refresh_backup_table()
            return

        if self.session_ctrl is not None:
            # Reset carry-over provenance for generic/manual loads.
            self.session_ctrl.set_carryover_source_chi(None)
        if hasattr(self.widget, "set_nav_carry_status"):
            self.widget.set_nav_carry_status("")
        self.model.set_chi_path(os.path.split(new_filename)[0])
        self.model.set_base_ptn(
            new_filename, self.widget.doubleSpinBox_SetWavelength.value())
        self.model.set_base_pattern_provenance(provenance)
        self._clear_peakfit_for_new_pattern()
        # self.widget.textEdit_DiffractionPatternFileName.setText(
        #    '1D Pattern: ' + self.model.get_base_ptn_filename())
        self.widget.lineEdit_DiffractionPatternFileName.setText(
            str(self.model.get_base_ptn_filename()))
        self._update_metadata_tab_for_chi(new_filename)
        self._notify_pattern_loaded(new_filename)
        # Prefer loading full PARAM session state when available for this CHI.
        if self.session_ctrl is not None:
            loaded_param = self.session_ctrl.autoload_param_for_chi(new_filename)
            if loaded_param:
                # Ensure File > Data backup table reflects the newly loaded CHI
                # immediately, without requiring tab changes.
                self.session_ctrl.refresh_backup_table()
                print(str(datetime.datetime.now())[:-7],
                    ': Loaded PARAM session for this CHI.')
                return
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
                        ': No temp background-subtracted CHI found. Force new bgsub fit.')
            else:
                os.makedirs(temp_dir)
                self._update_bgsub_from_current_values()
                print(str(datetime.datetime.now())[:-7], 
                    ': No temp background-subtracted CHI found. Force new bgsub fit.')
        else:
            self._update_bgsub_from_current_values()
            print(str(datetime.datetime.now())[:-7], 
                ': Temp chi ignored. Force new bgsub fit.')
        is_azimuthal_chi = (
            provenance.get("source_kind") == "azimuthal_integration" and
            bool(provenance.get("source_chi")))
        if (not self.model.associated_image_exists()) and \
                (not self.widget.checkBox_IgnoreRawDataExistence.isChecked()) and \
                (not is_azimuthal_chi):
            self.widget.checkBox_ShowCake.setChecked(False)
            return
        # self._update_bg_params_in_widget()

        poni_all = self.cake_ctrl.get_all_temp_poni()
        if len(poni_all) == 1:
            self.model.poni = poni_all[0]
            self.widget.lineEdit_PONI.setText(self.model.poni)

        if self.widget.checkBox_ShowCake.isChecked() and \
                ((self.model.poni is not None) or
                 self.widget.checkBox_IgnoreRawDataExistence.isChecked() or
                 is_azimuthal_chi):
            success = self.cake_ctrl.process_temp_cake()
            if (not success) and \
                    ((self.widget.checkBox_IgnoreRawDataExistence.isChecked() and
                      (not self.model.associated_image_exists())) or
                     is_azimuthal_chi):
                QtWidgets.QMessageBox.warning(
                    self.widget, 'Warning',
                    'PeakPo cannot process Cake: no raw image or cached Cake files '
                    'were found for this CHI or its full-azimuth source.')
                self.widget.checkBox_ShowCake.setChecked(False)
        # Keep backup table in File > Data synchronized right after CHI load.
        if self.session_ctrl is not None:
            self.session_ctrl.refresh_backup_table()

    def _load_derived_display_pattern(self, derived_filename, provenance):
        source_chi = provenance.get("source_chi")
        if not source_chi or not os.path.exists(source_chi):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Cannot display this azimuth-derived CHI because the "
                "full-azimuth source CHI is missing:\n" + str(source_chi))
            return

        source_loaded = self.model.base_ptn_exist() and \
            self._same_path(self.model.get_base_ptn_filename(), source_chi)
        if not source_loaded:
            self._load_a_new_pattern(source_chi, display_derived=False)
            if not self.model.base_ptn_exist() or \
                    not self._same_path(
                        self.model.get_base_ptn_filename(), source_chi):
                return
        else:
            if self.session_ctrl is not None:
                self.session_ctrl.set_carryover_source_chi(None)
            if hasattr(self.widget, "set_nav_carry_status"):
                self.widget.set_nav_carry_status("")

        self.model.set_display_ptn(
            derived_filename,
            self.widget.doubleSpinBox_SetWavelength.value(),
            provenance=provenance)
        self._update_display_bgsub_from_current_values()
        self.widget.lineEdit_DiffractionPatternFileName.setText(
            str(self.model.get_base_ptn_filename()))
        self._update_metadata_tab_for_chi(source_chi)
        self._notify_pattern_loaded(derived_filename)
        if self.session_ctrl is not None:
            self.session_ctrl.refresh_backup_table()

    def _update_display_bgsub_from_current_values(self):
        if not getattr(self.model, "display_ptn_exist", lambda: False)():
            return
        pattern = self.model.get_display_ptn()
        if pattern is None:
            return
        x_raw, y_raw = pattern.get_raw()
        if x_raw is None or y_raw is None or len(x_raw) == 0:
            return
        roi_min = self.widget.doubleSpinBox_Background_ROI_min.value()
        roi_max = self.widget.doubleSpinBox_Background_ROI_max.value()
        roi_min = max(float(x_raw.min()), float(roi_min))
        roi_max = min(float(x_raw.max()), float(roi_max))
        if roi_max <= roi_min:
            roi_min = float(x_raw.min())
            roi_max = float(x_raw.max())
        pattern.subtract_bg(
            [roi_min, roi_max],
            [self.widget.spinBox_BGParam0.value(),
             self.widget.spinBox_BGParam1.value(),
             self.widget.spinBox_BGParam2.value()],
            yshift=0)

    def _clear_peakfit_for_new_pattern(self):
        self.model.current_section = None
        self.model.section_lst = []
        for table_name in (
                "tableWidget_PkFtSections",
                "tableWidget_PkParams",
                "tableWidget_BackgroundConstraints",
                "tableWidget_PeakConstraints"):
            table = getattr(self.widget, table_name, None)
            if table is None:
                continue
            table.clearContents()
            table.setRowCount(0)
            table.setColumnCount(0)
        for setter_name in (
                "set_tableWidget_PkParams_saved",
                "set_tableWidget_PkFtSections_saved"):
            setter = getattr(self.widget, setter_name, None)
            if callable(setter):
                setter()

    def _metadata_tab_widgets(self):
        path_widget = getattr(self.widget, "lineEdit_MetadataJsonPath", None)
        text_widget = getattr(self.widget, "plainTextEdit_MetadataJson", None)
        table_widget = getattr(self.widget, "tableWidget_MetadataStructured", None)
        return path_widget, text_widget, table_widget

    def _clear_metadata_tab(self):
        path_widget, text_widget, table_widget = self._metadata_tab_widgets()
        if path_widget is not None:
            path_widget.setText("")
        if text_widget is not None:
            text_widget.setPlainText("")
        if table_widget is not None:
            table_widget.setRowCount(0)
        if hasattr(self.widget, "lineEdit_MetadataSearch"):
            self.widget.lineEdit_MetadataSearch.setText("")
        if hasattr(self.widget, "label_MetadataSearchStatus"):
            self.widget.label_MetadataSearchStatus.setText("")

    def _update_metadata_tab_for_chi(self, chi_path):
        path_widget, text_widget, table_widget = self._metadata_tab_widgets()
        if path_widget is None or text_widget is None:
            return
        self._clear_metadata_tab()

        param_dir = get_temp_dir(chi_path)
        collection = DioptasMetadataCollection.from_param_dir(param_dir)
        if not collection.exports:
            return

        paths = []
        sections = []
        for export in collection.exports:
            path = str(getattr(export, "path", "") or "")
            if not path:
                continue
            paths.append(path)
            sections.append(
                f"# {path}\n" +
                json.dumps(
                    getattr(export, "payload", None),
                    indent=2,
                    sort_keys=True,
                    allow_nan=True,
                )
            )
        if not sections:
            return

        if len(paths) == 1:
            path_widget.setText(paths[0])
        else:
            path_widget.setText(f"{len(paths)} metadata JSON files")
        text_widget.setPlainText("\n\n".join(sections))
        if table_widget is not None:
            export = collection.exports[0]
            frame_index = export.frame_index_for_file(chi_path)
            self._populate_metadata_table(table_widget, export, frame_index)

    def _metadata_value_text(self, value):
        if value is None:
            return ""
        try:
            fval = float(value)
            if fval != fval:
                return ""
            return f"{fval:.6g}"
        except Exception:
            return str(value)

    def _metadata_add_group_row(self, table_widget, label):
        row = table_widget.rowCount()
        table_widget.insertRow(row)
        item = QtWidgets.QTableWidgetItem(str(label))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        table_widget.setItem(row, 0, item)
        table_widget.setSpan(row, 0, 1, table_widget.columnCount())

    def _metadata_add_value_row(self, table_widget, row_data):
        value = row_data.get("value", None)
        if value is None:
            return
        row = table_widget.rowCount()
        table_widget.insertRow(row)
        cells = [
            row_data.get("parameter", ""),
            self._metadata_value_text(value),
            row_data.get("unit", ""),
            row_data.get("source", ""),
        ]
        for col, text in enumerate(cells):
            item = QtWidgets.QTableWidgetItem(str(text))
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            table_widget.setItem(row, col, item)

    def _populate_metadata_table(self, table_widget, export, frame_index=None):
        table_widget.setRowCount(0)
        groups = [
            ("Temperature", export.get_temperature(frame_index=frame_index)),
            ("Burst Temperature", export.get_burst_temperature(frame_index=frame_index)),
            ("Laser", export.get_laser(frame_index=frame_index)),
            ("Position", export.get_position(frame_index=frame_index)),
            ("Acquisition", export.get_acquisition(frame_index=frame_index)),
            ("Membrane Pressure", export.get_pressure(frame_index=frame_index)),
            ("Beam", export.get_beam(frame_index=frame_index)),
        ]
        for group_name, rows in groups:
            visible_rows = [row for row in rows if row.get("value", None) is not None]
            if not visible_rows:
                continue
            self._metadata_add_group_row(table_widget, group_name)
            for row_data in visible_rows:
                self._metadata_add_value_row(table_widget, row_data)
        table_widget.resizeColumnsToContents()
        table_widget.horizontalHeader().setStretchLastSection(True)

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
