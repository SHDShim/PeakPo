from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
# from collections import OrderedDict
import os
import numpy as np
from matplotlib.backend_bases import key_press_handler
import pickle
import zipfile
from mainwidget import MainWindow
from model import PeakPoModel
from mplcontroller import MplController
from cakecontroller import CakeController
from waterfallcontroller import WaterfallController
from jcpdscontroller import JcpdsController
from ucfitcontroller import UcfitController
# from model import PeakPoModel
from utils import get_sorted_filelist, find_from_filelist, dialog_savefile, \
    xls_ucfitlist, xls_jlist, writechi, extract_filename
from utils import SpinBoxFixStyle
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ds_jcpds import Session, UnitCell
from ds_powdiff import get_DataSection


class MainController(object):

    def __init__(self):

        self.widget = MainWindow()
        self.model = PeakPoModel()
        self.obj_color = 'white'
        self.read_setting()
        self.connect_channel()
        self.plot_ctrl = MplController(self.model, self.widget)
        self.waterfall_ctrl = WaterfallController(
            self.model, self.widget, self.chi_path)
        self.cake_ctrl = CakeController(self.model, self.widget, self.chi_path)
        self.ucfit_ctrl = UcfitController(self.model, self.widget)
        self.jcpds_ctrl = JcpdsController(self.model, self.widget,
                                          self.jcpds_path)
        #
        self.clip = QtWidgets.QApplication.clipboard()
        # no more stuff can be added below

    def show_window(self):
        self.widget.show()

    def connect_channel(self):
        # connecting events
        self.widget.mpl.canvas.mpl_connect(
            'button_press_event', self.read_plot)
        self.widget.mpl.canvas.mpl_connect(
            'key_press_event', self.on_key_press)
        # Tab: Main
        self.widget.pushButton_NewBasePtn.clicked.connect(
            self.select_base_ptn)
        self.widget.pushButton_PrevBasePtn.clicked.connect(
            lambda: self.goto_next_file('previous'))
        self.widget.pushButton_NextBasePtn.clicked.connect(
            lambda: self.goto_next_file('next'))
        self.widget.pushButton_LastBasePtn.clicked.connect(
            lambda: self.goto_next_file('last'))
        self.widget.pushButton_FirstBasePtn.clicked.connect(
            lambda: self.goto_next_file('first'))
        self.widget.doubleSpinBox_Pressure.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.doubleSpinBox_Temperature.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.pushButton_SaveSession.clicked.connect(self.save_session)
        self.widget.pushButton_LoadSession.clicked.connect(self.load_session)
        self.widget.pushButton_ZipSession.clicked.connect(self.zip_session)
        self.widget.lineEdit_DiffractionPatternFileName.editingFinished.\
            connect(self.load_new_base_pattern_from_name)
        self.widget.pushButton_SaveJlist.clicked.connect(self.save_session)
        self.widget.doubleSpinBox_SetWavelength.valueChanged.connect(
            self.apply_wavelength)
        self.widget.pushButton_ExportXLS.clicked.connect(self.save_xls)
        self.widget.pushButton_SaveCHI.clicked.connect(self.save_bgsubchi)
        # while the button is located in JCPDS tab, this one connect different
        # tabs, so stays in main controller
        self.widget.pushButton_ExportToUCFit.clicked.connect(
            self.export_to_ucfit)
        # save Jlist is linked to save_session in the main controller
        self.widget.pushButton_LoadJlist.clicked.connect(self.load_jlist)
        self.widget.pushButton_ViewJCPDS.clicked.connect(self.view_jcpds)
        # Tab: process
        self.widget.pushButton_UpdatePlots_tab2.clicked.connect(
            self.update_bgsub)
        # file menu items
        self.widget.actionClose.triggered.connect(self.closeEvent)
        # navigation toolbar modification
        self.widget.ntb_WholePtn.clicked.connect(self.zoom_out_graph)
        self.widget.ntb_toPkFt.clicked.connect(self.to_PkFt)
        self.widget.ntb_fromPkFt.clicked.connect(self.from_PkFt)
        self.widget.ntb_ResetY.clicked.connect(self.apply_changes_to_graph)
        self.widget.ntb_Bgsub.clicked.connect(self.apply_changes_to_graph)
        self.widget.ntb_NightView.clicked.connect(self.set_nightday_view)

    def apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def view_jcpds(self):
        if not self.model.jcpds_exist():
            return
        idx_checked = [
            s.row() for s in
            self.widget.tableWidget_JCPDS.selectionModel().selectedRows()]

        if idx_checked == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Highlight the name of JCPDS to view")
            return
        if idx_checked.__len__() != 1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Only one JCPDS card can be shown at a time.")
        else:
            textoutput = self.model.jcpds_lst[idx_checked[0]].make_TextOutput(
                self.widget.doubleSpinBox_Pressure.value(),
                self.widget.doubleSpinBox_Temperature.value())
            self.widget.plainTextEdit_ViewJCPDS.setPlainText(textoutput)

    def load_jlist(self):
        """get existing jlist file from data folder"""
        fn_jlist = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.chi_path, "(*.ppss)")[0]
        if fn_jlist == '':
            return
        self._load_session(fn_jlist, True)
        self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn_jlist))
        self.jcpds_ctrl.update_table()
        self.plot_ctrl.update()

    def export_to_ucfit(self):
        """
        UCFit function
        Export an item from jlist to ucfitlist
        """
        if not self.model.jcpds_exist():
            return
        idx_checked = [
            s.row() for s in self.widget.tableWidget_JCPDS.selectionModel().
            selectedRows()]

        if idx_checked == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Highlight the name of JCPDS to export")
            return
        i = 0
        for j in range(idx_checked.__len__()):
            if self.model.jcpds_lst[idx_checked[j]].symmetry != 'manual':
                phase = UnitCell()
                phase.name = self.model.jcpds_lst[idx_checked[j]].name
                phase.color = self.model.jcpds_lst[idx_checked[j]].color
                phase.symmetry = self.model.jcpds_lst[idx_checked[j]].symmetry
                phase.a = self.model.jcpds_lst[idx_checked[j]].a
                phase.b = self.model.jcpds_lst[idx_checked[j]].b
                phase.c = self.model.jcpds_lst[idx_checked[j]].c
                phase.alpha = self.model.jcpds_lst[idx_checked[j]].alpha
                phase.beta = self.model.jcpds_lst[idx_checked[j]].beta
                phase.gamma = self.model.jcpds_lst[idx_checked[j]].gamma
                phase.v = self.model.jcpds_lst[idx_checked[j]].v
                phase.DiffLines = \
                    self.model.jcpds_lst[idx_checked[j]].DiffLines
                self.model.ucfit_lst.append(phase)
                i += 1
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You cannot send a jcpds without symmetry.")
        self.ucfit_ctrl.update_table()
        self.jcpds_ctrl.update_table()
        self.plot_ctrl.update()
        return

    def save_bgsubchi(self):
        """
        Output function
        Save bg subtractd pattern to a chi file
        """
        if not self.model.base_ptn_exist():
            return
        filen_chi_t = self.model.make_filename('bgsub.chi')
        filen_chi = dialog_savefile(self.widget, filen_chi_t)
        if str(filen_chi) == '':
            return
        x, y = self.model.base_ptn.get_bgsub()
        writechi(filen_chi, x, y)

    def write_setting(self):
        """
        Write default setting
        """
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        self.settings.setValue('chi_path', self.chi_path)
        self.settings.setValue('jcpds_path', self.jcpds_path)

    def read_setting(self):
        """
        Read default setting
        """
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        self.chi_path = str(self.settings.value('chi_path'))
        self.jcpds_path = str(self.settings.value('jcpds_path'))

    def closeEvent(self, event):
        """
        Close event function
        """
        self.write_setting()
        self.deleteLater()

    def on_key_press(self, event):
        if event.key == 'i':
            if self.widget.mpl.ntb._active == 'PAN':
                self.widget.mpl.ntb.pan()
            if self.widget.mpl.ntb._active == 'ZOOM':
                self.widget.mpl.ntb.zoom()
        elif event.key == 's':
            self.save_session_with_default_name()
        elif event.key == 'w':
            self.zoom_out_graph()
        elif event.key == 'v':
            lims = self.widget.mpl.canvas.ax_pattern.axis()
            if self.widget.ntb_Bgsub.isChecked():
                x, y = self.model.base_ptn.get_bgsub()
            else:
                x, y = self.model.base_ptn.get_raw()
            xroi, yroi = get_DataSection(x, y, [lims[0], lims[1]])
            self.plot_ctrl.update([lims[0], lims[1], yroi.min(), yroi.max()])
        else:
            key_press_handler(event, self.widget.mpl.canvas,
                              self.widget.mpl.ntb)

    def to_PkFt(self):
        # listen
        if not self.model.base_ptn_exist():
            return
        lims = self.widget.mpl.canvas.ax_pattern.axis()
        talk = "PeakPo,{0},{1: .2f},{2: .2f},{3: .2f},{4: .2f}".format(
            self.model.base_ptn.fname, lims[0], lims[1], lims[2], lims[3])
        self.clip.setText(talk)

    def from_PkFt(self):
        l = self.clip.text()
        listen = str(l)
        if listen.find("PeakFt") == -1:
            return
        a = listen.split(',')
        new_filen = a[1]
        new_lims = [float(i) for i in a[2:6]]
        self._load_a_new_pattern(new_filen)
        self.plot_ctrl.update(new_lims)

    def save_xls(self):
        """
        JCPDS function
        Export jlist to an excel file
        """
        if not self.model.jcpds_exist():
            return
        filen_xls_t = self.model.make_filename('pkpo.xls')
        filen_xls = dialog_savefile(self.widget, filen_xls_t)
        if str(filen_xls) == '':
            return
        xls_jlist(filen_xls, self.model.jcpds_lst,
                  self.widget.doubleSpinBox_Pressure.value(),
                  self.widget.doubleSpinBox_Temperature.value())

    def load_session(self):
        """
        get existing jlist file from data folder
        """
        fn = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File", self.chi_path, "(*.ppss)")[0]
#       replaceing chi_path with '' does not work
        if fn == '':
            return
        success = self._load_session(fn, False)
        if success:
            self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn))
            self.widget.textEdit_SessionFileName.setText('Session: ' + str(fn))
            self.widget.textEdit_DiffractionPatternFileName.setText(
                '1D pattern: ' + str(self.model.base_ptn.fname))
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            self.zoom_out_graph()
            self.update_inputs()

    def _update_session(self):
        if not self.model.base_ptn_exist():
            return
        fn = self.model.make_filename('ppss')
        if not os.path.exists(fn):
            return
        success = self._load_session(fn, False)
        if success:
            self.widget.textEdit_Jlist.setText('Jlist: ' + str(fn))
            self.widget.textEdit_DiffractionPatternFileName.setText(
                '1D pattern: ' + str(self.model.base_ptn.fname))
            self.widget.lineEdit_DiffractionPatternFileName.setText(
                str(self.model.base_ptn.fname))
            self.widget.textEdit_SessionFileName.setText('Session: ' + str(fn))
            self.update_inputs()

    def _load_session(self, fsession, jlistonly=False):
        '''
        internal method for reading pickled ppss file
        '''
#        session = Session()
#        try:
        f = open(fsession, 'rb')
        session = pickle.load(f, encoding='latin1')
#        print type(session).__name__
#        if type(session).__name__ == 'Session':
#            QtGui.QMessageBox.warning(self.widget, 'Warning',
#                'This PPSS file has an old format.
#               Make sure you overwrite the file again after opening.')
        f.close()
        # except:
        #     QtGui.QMessageBox.warning(self.widget, "Warning", \
        #         "Session loading failed.  But no harm, just inconvenience.")
        #     return False
        # through check of the file existence
        if jlistonly:
            self.model.jcpds_lst = session.jlist
            self.jcpds_path = session.jcpds_path
        else:
            if (session.chi_path != ''):
                if not os.path.exists(session.chi_path):
                    chi_path = os.path.dirname(str(fsession))
                    chi_basefilen = os.path.basename(session.pattern.fname)
                    chi_filen = os.path.join(chi_path, chi_basefilen)
                    if os.path.exists(chi_filen):
                        session.pattern.read_file(chi_filen)
                        session.pattern.get_chbg(
                            session.bg_roi, session.bg_params, yshift=0)
                        session.chi_path = chi_path
                    else:
                        QtWidgets.QMessageBox.warning(
                            self.widget, "Warning",
                            "The base file in the PPSS cannot be found.")
                        return False
                    if session.waterfallpatterns != []:
                        for wfp in session.waterfallpatterns:
                            wfp_basefilen = os.path.basename(wfp.fname)
                            chi_filen = os.path.join(chi_path, wfp_basefilen)
                            if os.path.exists(chi_filen):
                                wfp.read_file(chi_filen)
                                wfp.get_chbg(session.bg_roi, session.bg_params,
                                             yshift=0)
                            else:
                                reply = QtWidgets.QMessageBox.question(
                                    self.widget, "Question",
                                    "The waterfall files in the PPSS cannot \
                                    be found. Do you want to ignore the water \
                                    fall?",
                                    QtWidgets.QMessageBox.Yes |
                                    QtWidgets.QMessageBox.No,
                                    QtWidgets.QMessageBox.Yes)
                                if reply == QtWidgets.QMessageBox.Yes:
                                    session.waterfallpatterns = []
                                    break
                                else:
                                    return False
            if (session.jcpds_path != ''):
                if not os.path.exists(session.jcpds_path):
                    reply = QtWidgets.QMessageBox.question(
                        self.widget, "Question",
                        "The JCPDS path in the PPSS does not exist.  \
                        Do you want to update the JCPDS path?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes)
                    if reply == QtWidgets.QMessageBox.Yes:
                        jcpds_path = \
                            QtWidgets.QFileDialog.getExistingDirectory(
                                self.widget, "Open Directory", self.jcpds_path,
                                QtWidgets.QFileDialog.ShowDirsOnly)
                        if jcpds_path != '':
                            session.jcpds_path = jcpds_path
                        else:
                            return False
                    else:
                        QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                                      "PPSS read failed.")
                        return False
            if (session.pattern is None):
                if not os.path.exists(session.jcpds_path):
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        "No base pattern exists in the previous session.")
                    return False
            self.model.set_base_ptn(session.pattern)
            self.model.waterfall_ptn = session.waterfallpatterns
            self.widget.doubleSpinBox_SetWavelength.setValue(
                session.wavelength)
            self.widget.doubleSpinBox_Pressure.setValue(session.pressure)
            self.widget.doubleSpinBox_Temperature.setValue(session.temperature)
            self.model.jcpds_lst = session.jlist
            self.widget.doubleSpinBox_Background_ROI_min.setValue(
                session.bg_roi[0])
            self.widget.doubleSpinBox_Background_ROI_max.setValue(
                session.bg_roi[1])
            self.widget.spinBox_BGParam0.setValue(session.bg_params[0])
            self.widget.spinBox_BGParam1.setValue(session.bg_params[1])
            self.widget.spinBox_BGParam2.setValue(session.bg_params[2])
            self.jcpds_path = session.jcpds_path
            self.chi_path = session.chi_path
        return True

    def _dump_session(self, fsession):
        session = Session()
        session.pattern = self.model.get_base_ptn()
        session.waterfallpatterns = self.model.waterfall_ptn
        session.wavelength = self.widget.doubleSpinBox_SetWavelength.value()
        session.pressure = self.widget.doubleSpinBox_Pressure.value()
        session.temperature = self.widget.doubleSpinBox_Temperature.value()
        session.jlist = self.model.jcpds_lst
        session.bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                          self.widget.doubleSpinBox_Background_ROI_max.value()]
        session.bg_params = [self.widget.spinBox_BGParam0.value(),
                             self.widget.spinBox_BGParam1.value(),
                             self.widget.spinBox_BGParam2.value()]
        session.jcpds_path = self.jcpds_path
        session.chi_path = self.chi_path
        f = open(fsession, 'wb')
        pickle.dump(session, f)
        f.close()

    def update_inputs(self):
        self.reset_bgsub()
        self.waterfall_ctrl.update_table()
        self.jcpds_ctrl.update_table()

    def zip_session(self):
        if not self.model.base_ptn_exist():
            fzip = os.path.join(self.chi_path, 'dum.zip')
        else:
            """
            path, filen = os.path.split(self.model.base_ptn.fname)
            new_filen = '%s.zip' % filen
            fzip = os.path.join(path, new_filen)
            """
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
            fsession_name = '%s.forzip.ppss' % filen
            fsession = os.path.join(path, fsession_name)
            self._dump_session(str(fsession))
            self.widget.textEdit_Jlist.setText('Jlist : ' + str(fsession))
            zf = zipfile.ZipFile(str(fzip), 'w', zipfile.ZIP_DEFLATED)
            zf.write(fsession, arcname=fsession_name)
            if self.model.base_ptn_exist():
                dum, filen = os.path.split(self.model.base_ptn.fname)
                zf.write(self.model.base_ptn.fname, arcname=filen)
            if self.model.waterfall_exist():
                for wf in self.model.waterfall_ptn:
                    dum, filen = os.path.split(wf.fname)
                    zf.write(wf.fname, arcname=filen)
            zf.close()

    def save_session(self):
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.chi_path, 'dum.ppss')
        else:
            fsession = self.model.make_filename('ppss')
        new_filename = dialog_savefile(self.widget, fsession)
        if new_filename != '':
            self._dump_session(new_filename)
            self.widget.textEdit_SessionFileName.setText('Session: ' +
                                                         str(new_filename))

    def save_session_with_default_name(self):
        if not self.model.base_ptn_exist():
            fsession = os.path.join(self.chi_path, 'dum.ppss')
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
            self._dump_session(str(fsession))
            self.widget.textEdit_SessionFileName.setText(
                'Session: ' + str(fsession))

    def set_nightday_view(self):
        self.plot_ctrl._set_nightday_view()
        self.waterfall_ctrl.update_table()
        self.plot_ctrl.update()

    def read_plot(self, event):
        if self.widget.mpl.ntb._active is not None:
            return
        if (event.xdata is None) or (event.ydata is None):
            return
        x_click = float(event.xdata)
        y_click = float(event.ydata)
        x_click_dsp = self.widget.doubleSpinBox_SetWavelength.value() / 2. / \
            np.sin(np.radians(x_click / 2.))
        clicked_position = \
            "Clicked position: {0: 10.4f}, {1: 7.1f}, \n dsp = {2: 10.4f} A".\
            format(x_click, y_click, x_click_dsp)
        if (not self.model.jcpds_exist()) and (not self.model.ucfit_exist()):
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          clicked_position)
        else:
            # get jcpds information
            x_find = event.xdata
            textinfo = self._find_closestjcpds(x_find)
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          clicked_position + '\n' + textinfo)

    def apply_wavelength(self):
        # self.wavelength = value
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        self.plot_ctrl.update()

    def update_bgsub(self):
        '''
        this is only to read the current inputs and replot
        '''
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Load a base pattern first.")
            return
        """receive new bg parameters and update the graph"""
        bg_params = [self.widget.spinBox_BGParam0.value(),
                     self.widget.spinBox_BGParam1.value(),
                     self.widget.spinBox_BGParam2.value()]
        bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                  self.widget.doubleSpinBox_Background_ROI_max.value()]
        self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        if self.model.waterfall_exist():
            for pattern in self.model.waterfall_ptn:
                pattern.subtract_bg(bg_roi, bg_params, yshift=0)
        self.zoom_out_graph()

    def reset_bgsub(self):
        '''
        this is to read from session file and put to the table
        '''
        bg_params = [self.widget.spinBox_BGParam0.value(),
                     self.widget.spinBox_BGParam1.value(),
                     self.widget.spinBox_BGParam2.value()]
        bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                  self.widget.doubleSpinBox_Background_ROI_max.value()]
        self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        if self.model.waterfall_exist():
            for pattern in self.model.waterfall_ptn:
                pattern.get_chbg(bg_roi, bg_params, yshift=0)

    def zoom_out_graph(self):
        if not self.model.base_ptn_exist():
            return
        if self.widget.ntb_Bgsub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
        else:
            x, y = self.model.base_ptn.get_raw()
        self.plot_ctrl.update(limits=[x.min(), x.max(), y.min(), y.max()])

    def apply_pt_to_graph(self):
        if self.model.jcpds_exist():
            self.plot_ctrl.update()

    ###########################################################################
    # base pattern control
    def _load_a_new_pattern(self, new_filename):
        """
        load and process base pattern.  does not signal to update_graph
        """
        self.model.reset_base_ptn()
        self.model.base_ptn.read_file(new_filename)
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        self.model.base_ptn.display = True
        self.widget.textEdit_DiffractionPatternFileName.setText(
            '1D Pattern: ' + self.model.base_ptn.fname)
        self.widget.lineEdit_DiffractionPatternFileName.setText(
            str(self.model.base_ptn.fname))

        x_raw, y_raw = self.model.base_ptn.get_raw()
        if (x_raw.min() >=
            self.widget.doubleSpinBox_Background_ROI_min.value()) or\
                (x_raw.max() <=
                    self.widget.doubleSpinBox_Background_ROI_min.value()):
            self.widget.doubleSpinBox_Background_ROI_min.setValue(x_raw.min())
        if (x_raw.max() <=
            self.widget.doubleSpinBox_Background_ROI_max.value()) or\
                (x_raw.min() >=
                    self.widget.doubleSpinBox_Background_ROI_max.value()):
            self.widget.doubleSpinBox_Background_ROI_max.setValue(x_raw.max())
        self.model.base_ptn.subtract_bg(
            [self.widget.doubleSpinBox_Background_ROI_min.value(),
                self.widget.doubleSpinBox_Background_ROI_max.value()],
            [self.widget.spinBox_BGParam0.value(),
                self.widget.spinBox_BGParam1.value(),
                self.widget.spinBox_BGParam2.value()], yshift=0)
        if self.widget.pushButton_AddRemoveCake.isChecked() and \
                self.model.poni is not None:
            self.cake_ctrl.addremove_cake(update_plot=False)

    def select_base_ptn(self):
        """
        opens a file select dialog
        2017/06/10 remove support for other file formats
        """
        filen = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Open a Chi File", self.chi_path,
            "Data files (*.chi)")[0]
        self._setshow_new_base_ptn(str(filen))

    def goto_next_file(self, move):
        """
        quick move to the next base pattern file
        """
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Choose a base pattern first.")
            return
        filelist = get_sorted_filelist(
            self.chi_path,
            sorted_by_name=self.widget.radioButton_SortbyNme.isChecked())
        idx = find_from_filelist(filelist,
                                 os.path.split(self.model.base_ptn.fname)[1])
        if idx == -1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Cannot find current file")
        if self.widget.radioButton_FileStep1.isChecked():
            step = 1
        else:
            step = 10
        if move == 'next':
            idx_new = idx + step
        elif move == 'previous':
            idx_new = idx - step
        elif move == 'last':
            idx_new = filelist.__len__() - 1
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        elif move == 'first':
            idx_new = 0
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return
        if idx_new > filelist.__len__() - 1:
            idx_new = filelist.__len__() - 1
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        if idx_new < 0:
            idx_new = 0
            if idx == idx_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return
        new_filename = filelist[idx_new]
        if os.path.exists(new_filename):
            self._load_a_new_pattern(new_filename)
            self.model.base_ptn.color = self.obj_color
            self.plot_ctrl.update()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          new_filename + " does not exist.")

    def load_new_base_pattern_from_name(self):
        if self.widget.lineEdit_DiffractionPatternFileName.isModified():
            filen = str(self.widget.lineEdit_DiffractionPatternFileName.text())
            self._setshow_new_base_ptn(self, filen)

    def _setshow_new_base_ptn(self, filen):
        """
        load and then send signal to update_graph
        """
        if os.path.exists(filen):
            self.chi_path = os.path.split(filen)[0]
            if self.model.base_ptn_exist():
                old_filename = self.model.base_ptn.fname
            else:
                old_filename = None
            new_filename = filen
            self._load_a_new_pattern(new_filename)
            if old_filename is None:
                self.zoom_out_graph()
            else:
                self.plot_ctrl.update()
        else:
            QtWidgets.QMessageBox.warning(
                self.widget, 'Warning', 'Cannot find ' + filen)
            return

    def _find_closestjcpds(self, x):
        jcount = 0
        for phase in self.model.jcpds_lst:
            if phase.display:
                jcount += 1
        ucount = 0
        for phase in self.model.ucfit_lst:
            if phase.display:
                ucount += 1
        if (jcount + ucount) == 0:
            return ''
        if jcount != 0:
            idx_j = []
            diff_j = []
            tth_j = []
            h_j = []
            k_j = []
            l_j = []
            names_j = []
            dsp_j = []
            int_j = []
            for j in self.model.jcpds_lst:
                if j.display:
                    i, d, t = j.find_DiffLine(
                        x, self.widget.doubleSpinBox_SetWavelength.value())
                    idx_j.append(i)
                    diff_j.append(d)
                    tth_j.append(t)
                    h_j.append(j.DiffLines[i].h)
                    k_j.append(j.DiffLines[i].k)
                    l_j.append(j.DiffLines[i].l)
                    dsp_j.append(j.DiffLines[i].dsp)
                    int_j.append(j.DiffLines[i].intensity)
                    names_j.append(j.name)
        if ucount != 0:
            idx_u = []
            diff_u = []
            tth_u = []
            h_u = []
            k_u = []
            l_u = []
            names_u = []
            dsp_u = []
            int_u = []
            for u in self.model.ucfit_lst:
                if u.display:
                    i, d, t = u.find_DiffLine(
                        x, self.widget.doubleSpinBox_SetWavelength.value())
                    idx_u.append(i)
                    diff_u.append(d)
                    tth_u.append(t)
                    h_u.append(u.DiffLines[i].h)
                    k_u.append(u.DiffLines[i].k)
                    l_u.append(u.DiffLines[i].l)
                    dsp_u.append(u.DiffLines[i].dsp)
                    int_u.append(u.DiffLines[i].intensity)
                    names_u.append(u.name)
        if (jcount != 0) and (ucount == 0):
            idx_min = diff_j.index(min(diff_j))
            tth_min = tth_j[idx_min]
            dsp_min = dsp_j[idx_min]
            int_min = int_j[idx_min]
            h_min = h_j[idx_min]
            k_min = k_j[idx_min]
            l_min = l_j[idx_min]
            name_min = names_j[idx_min]
        elif (jcount == 0) and (ucount != 0):
            idx_min = diff_u.index(min(diff_u))
            tth_min = tth_u[idx_min]
            dsp_min = dsp_u[idx_min]
            int_min = int_u[idx_min]
            h_min = h_u[idx_min]
            k_min = k_u[idx_min]
            l_min = l_u[idx_min]
            name_min = names_u[idx_min]
        else:
            if min(diff_j) <= min(diff_u):
                idx_min = diff_j.index(min(diff_j))
                tth_min = tth_j[idx_min]
                dsp_min = dsp_j[idx_min]
                int_min = int_j[idx_min]
                h_min = h_j[idx_min]
                k_min = k_j[idx_min]
                l_min = l_j[idx_min]
                name_min = names_j[idx_min]
            else:
                idx_min = diff_u.index(min(diff_u))
                tth_min = tth_u[idx_min]
                dsp_min = dsp_u[idx_min]
                int_min = int_u[idx_min]
                h_min = h_u[idx_min]
                k_min = k_u[idx_min]
                l_min = l_u[idx_min]
                name_min = names_u[idx_min]
        line1 = 'Two theta = {0: 10.4f}, d-spacing = {1: 10.4f} A'.format(
            float(tth_min), float(dsp_min))
        line2 = 'intensity = {0: 5.0f}, hkl = {1: 3.0f} {2: 3.0f} {3: 3.0f}'.\
            format(int(int_min), int(h_min), int(k_min), int(l_min))
        textoutput = name_min + '\n' + line1 + '\n' + line2
        return textoutput
