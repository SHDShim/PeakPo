import os
import glob
import numpy as np
from matplotlib.backend_bases import key_press_handler
from PyQt5 import QtWidgets
from PyQt5 import QtCore
import gc
from view import MainWindow
from model import PeakPoModel
from .basepatterncontroller import BasePatternController
from .mplcontroller import MplController
# cake controller is called in BasePatternController already.
# from .cakecontroller import CakeController
from .waterfallcontroller import WaterfallController
from .jcpdscontroller import JcpdsController
from .ucfitcontroller import UcfitController
from .waterfalltablecontroller import WaterfallTableController
from .jcpdstablecontroller import JcpdsTableController
from .ucfittablecontroller import UcfitTableController
from .sessioncontroller import SessionController
from .peakfitcontroller import PeakFitController
from .peakfittablecontroller import PeakfitTableController
from utils import dialog_savefile, writechi, extract_extension, \
    convert_wl_to_energy
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ds_jcpds import UnitCell
from ds_powdiff import get_DataSection


class MainController(object):

    def __init__(self):

        self.widget = MainWindow()
        self.model = PeakPoModel()
        # self.obj_color = 'white'
        self.base_ptn_ctrl = BasePatternController(self.model, self.widget)
        self.plot_ctrl = MplController(self.model, self.widget)
        # self.cake_ctrl = CakeController(self.model, self.widget)
        self.waterfall_ctrl = \
            WaterfallController(self.model, self.widget)
        self.ucfit_ctrl = UcfitController(self.model, self.widget)
        self.jcpds_ctrl = JcpdsController(self.model, self.widget)
        self.waterfalltable_ctrl = \
            WaterfallTableController(self.model, self.widget)
        self.ucfittable_ctrl = UcfitTableController(self.model, self.widget)
        self.jcpdstable_ctrl = JcpdsTableController(self.model, self.widget)
        self.session_ctrl = SessionController(self.model, self.widget)
        self.peakfit_ctrl = PeakFitController(self.model, self.widget)
        self.peakfit_table_ctrl = PeakfitTableController(self.model, self.widget)
        self.read_setting()
        self.connect_channel()
        #
        self.clip = QtWidgets.QApplication.clipboard()
        # no more stuff can be added below

    def show_window(self):
        self.widget.show()

    def connect_channel(self):
        # connecting events
        self.widget.mpl.canvas.mpl_connect(
            'button_press_event', self.deliver_mouse_signal)
        self.widget.mpl.canvas.mpl_connect(
            'key_press_event', self.on_key_press)
        self.widget.spinBox_AziShift.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.doubleSpinBox_Pressure.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.doubleSpinBox_Temperature.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.doubleSpinBox_SetWavelength.valueChanged.connect(
            self.apply_wavelength)
        self.widget.pushButton_SaveBgSubCHI.clicked.connect(self.save_bgsubchi)
        self.widget.pushButton_ExportToUCFit.clicked.connect(
            self.export_to_ucfit)
        self.widget.pushButton_ImportJlist.clicked.connect(
            self.load_jlist_from_session)
        self.widget.pushButton_UpdateBackground.clicked.connect(
            self.update_bgsub)
        self.widget.checkBox_LongCursor.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShowMillerIndices.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.comboBox_BasePtnLineThickness.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        self.widget.comboBox_PtnJCPDSBarThickness.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        self.widget.comboBox_CakeJCPDSBarThickness.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        self.widget.comboBox_BkgnLineThickness.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        self.widget.comboBox_WaterfallLineThickness.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        self.widget.comboBox_HKLFontSize.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShortPlotTitle.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShowCakeLabels.clicked.connect(
            self.apply_changes_to_graph)

        # navigation toolbar modification.  Do not move the followings to
        # other controller files.
        """
        self.widget.ntb_toPkFt.clicked.connect(self.to_PkFt)
        self.widget.ntb_fromPkFt.clicked.connect(self.from_PkFt)
        self.widget.ntb_NightView.clicked.connect(self.set_nightday_view)
        """
        self.widget.pushButton_toPkFt.clicked.connect(self.to_PkFt)
        self.widget.pushButton_fromPkFt.clicked.connect(self.from_PkFt)
        self.widget.checkBox_NightView.clicked.connect(self.set_nightday_view)
        self.widget.ntb_WholePtn.clicked.connect(self.plot_new_graph)
        self.widget.checkBox_AutoY.clicked.connect(self.apply_changes_to_graph)
        self.widget.checkBox_BgSub.clicked.connect(self.apply_changes_to_graph)
        # self.widget.actionClose.triggered.connect(self.closeEvent)
        self.widget.tabWidget.currentChanged.connect(self.check_for_peakfit)
        # self.widget.tabWidget.setTabEnabled(8, False)
        self.widget.pushButton_DelTempCHI.clicked.connect(self.del_temp_chi)
        self.widget.pushButton_DelTempCake.clicked.connect(self.del_temp_cake)
        # slide bars
        self.widget.horizontalSlider_VMin.setValue(0)
        self.widget.horizontalSlider_VMax.setValue(100)
        self.widget.horizontalSlider_MaxScaleBars.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.horizontalSlider_VMin.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.horizontalSlider_VMax.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.horizontalSlider_CakeAxisSize.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.horizontalSlider_JCPDSBarScale.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.horizontalSlider_JCPDSBarPosition.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.horizontalSlider_WaterfallGaps.valueChanged.connect(
            self.apply_changes_to_graph)

    def del_temp_chi(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'This can slow down PeakPo, but update the background. Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        if self._temporary_pkpo_exists():
            temp_chi = os.path.join(self.model.chi_path, 'temporary_pkpo',
                                    '*.chi')
            for f in glob.glob(temp_chi):
                os.remove(f)

    def del_temp_cake(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'This can slow down PeakPo, but update PONI. Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        if self._temporary_pkpo_exists():
            temp_cake = os.path.join(self.model.chi_path, 'temporary_pkpo',
                                     '*.npy')
            for f in glob.glob(temp_cake):
                os.remove(f)

    def _temporary_pkpo_exists(self):
        temp_dir = os.path.join(self.model.chi_path, 'temporary_pkpo')
        return os.path.exists(temp_dir)

    def check_for_peakfit(self, i):
        if i == 8:
            self.widget.checkBox_AutoY.setChecked(False)
            self.apply_changes_to_graph()

    def apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def plot_new_graph(self):
        self.plot_ctrl.zoom_out_graph()

    def load_jlist_from_session(self):
        """
        get existing jlist file from data folder
        """
        fn_jlist = QtWidgets.QFileDialog.getOpenFileName(
            self.widget, "Choose A Session File",
            self.model.chi_path, "(*.ppss *.dpp)")[0]
        if fn_jlist == '':
            return
        if extract_extension(fn_jlist) == 'ppss':
            self.session_ctrl._load_ppss(fn_jlist, jlistonly=True)
        elif extract_extension(fn_jlist) == 'dpp':
            self.session_ctrl._load_dpp(fn_jlist, jlistonly=True)
        self.widget.textEdit_Jlist.setText(str(fn_jlist))
        self.jcpdstable_ctrl.update()
        self.plot_ctrl.update()

    def export_to_ucfit(self):
        """
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
        self.ucfittable_ctrl.update()
        self.jcpdstable_ctrl.update()
        self.plot_ctrl.update()
        return

    def save_bgsubchi(self):
        """
        Save bg subtractd pattern to a chi file
        """
        if not self.model.base_ptn_exist():
            return
        filen_chi_t = self.model.make_filename('bgsub.chi')
        filen_chi = dialog_savefile(self.widget, filen_chi_t)
        if str(filen_chi) == '':
            return
        x, y = self.model.base_ptn.get_bgsub()
        preheader_line0 = \
            '2-theta # BG ROI: {0: .5e}, {1: .5e} \n'.format(
                self.widget.doubleSpinBox_Background_ROI_min.value(),
                self.widget.doubleSpinBox_Background_ROI_max.value())
        preheader_line1 = \
            '2-theta # BG Params: {0: d}, {1: d}, {2: d} \n'.format(
                self.widget.spinBox_BGParam0.value(),
                self.widget.spinBox_BGParam1.value(),
                self.widget.spinBox_BGParam2.value())
        preheader_line2 = '\n'
        writechi(filen_chi, x, y, preheader=preheader_line0 +
                 preheader_line1 + preheader_line2)

    def write_setting(self):
        """
        Write default setting
        """
        # self.settings = QtCore.QSettings('DS', 'PeakPo')
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        # print('write:' + self.model.chi_path)
        self.settings.setValue('chi_path', self.model.chi_path)
        self.settings.setValue('jcpds_path', self.model.jcpds_path)

    def read_setting(self):
        """
        Read default setting
        """
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        # self.settings.setFallbacksEnabled(False)
        self.model.set_chi_path(self.settings.value('chi_path'))
        self.model.set_jcpds_path(self.settings.value('jcpds_path'))

    """
    def closeEvent(self, event):
        self.write_setting()
        self.widget.deleteLater()
        gc.collect()
        self.deleteLater()
        event.accept()
    """

    def on_key_press(self, event):
        if event.key == 'i':
            if self.widget.mpl.ntb._active == 'PAN':
                self.widget.mpl.ntb.pan()
            if self.widget.mpl.ntb._active == 'ZOOM':
                self.widget.mpl.ntb.zoom()
        elif event.key == 's':
            self.session_ctrl.save_dpp_ppss()
        elif event.key == 'w':
            self.plot_new_graph()
        elif event.key == 'v':
            lims = self.widget.mpl.canvas.ax_pattern.axis()
            if self.widget.checkBox_BgSub.isChecked():
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
        self.base_ptn_ctrl._load_a_new_pattern(new_filen)
        self.plot_ctrl.update(new_lims)

    def set_nightday_view(self):
        self.plot_ctrl._set_nightday_view()
        self.waterfalltable_ctrl.update()
        self.plot_ctrl.update()

    def deliver_mouse_signal(self, event):
        if self.widget.mpl.ntb._active is not None:
            return
        if (event.xdata is None) or (event.ydata is None):
            return
        if (event.button != 1) and (event.button != 3):
            return
        if event.button == 1:
            mouse_button = 'left'
        elif event.button == 3:
            mouse_button = 'right'
        if (self.widget.tabWidget.currentIndex() == 8) and \
                (self.widget.pushButton_AddRemoveFromMouse.isChecked()):
            if not self.model.current_section_exist():
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "Set section first.")
                return
            """ lines below causes issues
            if self.model.current_section.fitted():
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Message',
                    'Do you want to add to the last fitting result without save?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes)
                if reply == QtWidgets.QMessageBox.No:
                    return
                else:
                    self.model.current_section.invalidate_fit_result()
            """
            if self.model.current_section.fitted():
                self.model.current_section.invalidate_fit_result()
            self.pick_peak(mouse_button, event.xdata, event.ydata)
        else:
            self.read_plot(mouse_button, event.xdata, event.ydata)

    def pick_peak(self, mouse_button, xdata, ydata):
        """
        """
        if mouse_button == 'left':  # left click
            success = self.model.current_section.set_single_peak(
                float(xdata),
                self.widget.doubleSpinBox_InitialFWHM.value())
            if not success:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You picked outside of the current section.")
                return
        elif mouse_button == 'right':  # right button for removal
            if not self.model.current_section.peaks_exist():
                return
            self.model.current_section.remove_single_peak_nearby(xdata)
        else:
            return
        self.peakfit_ctrl.set_tableWidget_PkParams_unsaved()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_peak_constraints()
        self.plot_ctrl.update()

    def read_plot(self, mouse_button, xdata, ydata):
        if mouse_button == 'right':
            return
        x_click = float(xdata)
        y_click = float(ydata)
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
            x_find = xdata
            textinfo = self._find_closestjcpds(x_find)
            QtWidgets.QMessageBox.warning(self.widget, "Information",
                                          clicked_position + '\n' + textinfo)

    def apply_wavelength(self):
        # self.wavelength = value
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        xray_energy = convert_wl_to_energy(self.model.base_ptn.wavelength)
        self.widget.label_XRayEnergy.setText("({:.3f} keV)".format(xray_energy))
        self.plot_ctrl.update()

    def update_bgsub(self):
        '''
        this is only to read the current inputs and replot
        '''
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Load a base pattern first.")
            return
        """receive new bg parameters and update the graph"""
        bg_params = [self.widget.spinBox_BGParam0.value(),
                     self.widget.spinBox_BGParam1.value(),
                     self.widget.spinBox_BGParam2.value()]
        bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                  self.widget.doubleSpinBox_Background_ROI_max.value()]
        if (bg_roi[0] <= self.model.base_ptn.x_raw.min()):
            bg_roi[0] = self.model.base_ptn.x_raw.min()
            self.widget.doubleSpinBox_Background_ROI_min.setValue(bg_roi[0])
        if (bg_roi[1] >= self.model.base_ptn.x_raw.max()):
            bg_roi[1] = self.model.base_ptn.x_raw.max()
            self.widget.doubleSpinBox_Background_ROI_max.setValue(bg_roi[1])
        self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        self.model.base_ptn.write_temporary_bgfiles()
        if self.model.waterfall_exist():
            for pattern in self.model.waterfall_ptn:
                pattern.subtract_bg(bg_roi, bg_params, yshift=0)
        self.plot_new_graph()

    def apply_pt_to_graph(self):
        if self.model.jcpds_exist():
            self.plot_ctrl.update()

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
        line1 = 'Two theta = {0: .4f}, d-spacing = {1: .4f} A'.format(
            float(tth_min), float(dsp_min))
        line2 = 'intensity = {0: .0f}, hkl = {1: .0f} {2: .0f} {3: .0f}'.\
            format(int(int_min), int(h_min), int(k_min), int(l_min))
        textoutput = name_min + '\n' + line1 + '\n' + line2
        return textoutput
