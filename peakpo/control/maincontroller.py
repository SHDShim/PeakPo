import os
import glob
import numpy as np
#from matplotlib.backend_bases import key_press_handler
from qtpy import QtWidgets
from qtpy import QtCore
import gc
import datetime
from ..view import MainWindow
from ..model import PeakPoModel, PeakPoModel8
from .basepatterncontroller import BasePatternController
from .mplcontroller import MplController
# cake controller is called in BasePatternController already.
# from .cakecontroller import CakeController
from .waterfallcontroller import WaterfallController
from .jcpdscontroller import JcpdsController
from .ucfitcontroller import UcfitController
from .waterfalltablecontroller import WaterfallTableController
from .jcpdstablecontroller import JcpdsTableController
#from .ucfittablecontroller import UcfitTableController
from .sessioncontroller import SessionController
from .peakfitcontroller import PeakFitController
from .peakfittablecontroller import PeakfitTableController
from .cakeazicontroller import CakeAziController
from ..utils import dialog_savefile, writechi, extract_extension, \
    convert_wl_to_energy, get_sorted_filelist, find_from_filelist, \
    make_filename, get_directory, get_temp_dir
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ..ds_jcpds import UnitCell
from ..ds_powdiff import get_DataSection
#from utils import readchi, make_filename, writechi


class MainController(object):

    def __init__(self):

        print("MainController.__init__ - START")
        self.widget = MainWindow()
        print("  ✓ MainWindow created")

        self.model = PeakPoModel8()
        print("  ✓ PeakPoModel8 created")
        
        self.base_ptn_ctrl = BasePatternController(self.model, self.widget)
        print("  ✓ BasePatternController created")
        
        self.plot_ctrl = MplController(self.model, self.widget)
        print("  ✓ MplController created")
        
        self.cakeazi_ctrl = CakeAziController(self.model, self.widget)
        print("  ✓ CakeAziController created")
        
        self.waterfall_ctrl = WaterfallController(self.model, self.widget)
        print("  ✓ WaterfallController created")
        
        self.ucfit_ctrl = UcfitController(self.model, self.widget)
        print("  ✓ UcfitController created")
        
        self.jcpds_ctrl = JcpdsController(self.model, self.widget)
        print("  ✓ JcpdsController created")
        
        self.waterfalltable_ctrl = WaterfallTableController(self.model, self.widget)
        print("  ✓ WaterfallTableController created")
        
        self.jcpdstable_ctrl = JcpdsTableController(self.model, self.widget)
        print("  ✓ JcpdsTableController created")
        
        self.session_ctrl = SessionController(self.model, self.widget)
        print("  ✓ SessionController created")
        
        self.peakfit_ctrl = PeakFitController(self.model, self.widget)
        print("  ✓ PeakFitController created")
        
        self.peakfit_table_ctrl = PeakfitTableController(self.model, self.widget)
        print("  ✓ PeakfitTableController created")
        
        self.read_setting()
        print("  ✓ read_setting() done")
        
        self.connect_channel()
        print("  ✓ connect_channel() done")
        
        self.clip = QtWidgets.QApplication.clipboard()
        print("  ✓ clipboard set")
        self._shutdown_done = False
        
        print("MainController.__init__ - DONE\n")

    def show_window(self):
        """Show the main window and ensure it renders"""
        # Show and let Qt/Matplotlib render in normal event flow.
        self.widget.show()
        
        # Bring to front (important on macOS)
        self.widget.raise_()
        self.widget.activateWindow()

    def shutdown(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True
        try:
            self.write_setting()
        except Exception:
            pass
        try:
            if hasattr(self.widget, 'mpl') and hasattr(self.widget.mpl, 'shutdown'):
                self.widget.mpl.shutdown()
        except Exception:
            pass
        try:
            if self.widget is not None:
                self.widget.close()
        except Exception:
            pass
        
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
        self.widget.pushButton_S_PIncrease.clicked.connect(
            lambda: self.quick_p_change(1))
        self.widget.pushButton_S_PDecrease.clicked.connect(
            lambda: self.quick_p_change(-1))
        self.widget.pushButton_S_TIncrease.clicked.connect(
            lambda: self.quick_temp_change(1))
        self.widget.pushButton_S_TDecrease.clicked.connect(
            lambda: self.quick_temp_change(-1))
        self.widget.doubleSpinBox_Temperature.valueChanged.connect(
            self.apply_pt_to_graph)
        self.widget.doubleSpinBox_SetWavelength.valueChanged.connect(
            self.apply_wavelength)
        self.widget.pushButton_SaveBgSubCHI.clicked.connect(self.save_bgsubchi)
        self.widget.pushButton_SetXEat30.clicked.connect(
            lambda: self.setXEat(0.4133))
        self.widget.pushButton_SetXEat37.clicked.connect(
            lambda: self.setXEat(0.3344))
        self.widget.pushButton_SetXEat42.clicked.connect(
            lambda: self.setXEat(0.2952))
        """
        self.widget.pushButton_ExportToUCFit.clicked.connect(
            self.export_to_ucfit)
        """
        self.widget.pushButton_ImportJlist.clicked.connect(
            self.load_jlist_from_session)
        self.widget.pushButton_UpdateBackground.clicked.connect(
            self.update_bgsub)
        self.widget.checkBox_LongCursor.stateChanged.connect(
            self._handle_cursor_toggle)  # Changed from clicked to stateChanged
        # ✅ ADD: Connect checkbox to deactivate toolbar
        self.widget.checkBox_LongCursor.stateChanged.connect(
            self._on_long_cursor_changed)
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
        self.widget.comboBox_PnTFontSize.currentIndexChanged.connect(
            self.apply_changes_to_graph)
        if hasattr(self.widget, "comboBox_LegendFontSize"):
            self.widget.comboBox_LegendFontSize.currentIndexChanged.connect(
                self.apply_changes_to_graph)
        if hasattr(self.widget, "comboBox_WaterfallFontSize"):
            self.widget.comboBox_WaterfallFontSize.currentIndexChanged.connect(
                self.apply_changes_to_graph)
        self.widget.checkBox_ShortPlotTitle.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShowCakeLabels.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShowLargePnT.clicked.connect(
            self.apply_changes_to_graph)
        # navigation toolbar modification.  Do not move the followings to
        # other controller files.
        #self.widget.pushButton_toPkFt.clicked.connect(self.to_PkFt)
        #self.widget.pushButton_fromPkFt.clicked.connect(self.from_PkFt)
        self.widget.checkBox_NightView.clicked.connect(self.set_nightday_view)
        self.widget.pushButton_S_Zoom.clicked.connect(self.plot_new_graph)
        self.widget.checkBox_AutoY.clicked.connect(self.apply_changes_to_graph)
        self.widget.checkBox_BgSub.clicked.connect(self.apply_changes_to_graph)
        self.widget.checkBox_ShowWaterfallLabels.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShowMillerIndices_Cake.clicked.connect(
            self.apply_changes_to_graph)
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
        self.widget.doubleSpinBox_JCPDS_cake_Alpha.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.doubleSpinBox_JCPDS_ptn_Alpha.valueChanged.connect(
            self.apply_changes_to_graph)
        self.widget.pushButton_UpdateJCPDSSteps.clicked.connect(
            self.update_jcpds_table)
        """
        self.widget.pushButton_UpdateUCFitSteps.clicked.connect(
            self.update_ucfit_table)
        """
        self.widget.pushButton_IntegrateCake.clicked.connect(
            self.integrate_to_1d)
        self.widget.pushButton_PrevBasePtn.clicked.connect(
            lambda: self.goto_next_file('previous'))
        self.widget.pushButton_NextBasePtn.clicked.connect(
            lambda: self.goto_next_file('next'))
        self.widget.pushButton_S_PrevBasePtn.clicked.connect(
            lambda: self.goto_next_file('previous'))
        self.widget.pushButton_S_NextBasePtn.clicked.connect(
            lambda: self.goto_next_file('next'))
        self.widget.pushButton_LastBasePtn.clicked.connect(
            lambda: self.goto_next_file('last'))
        self.widget.pushButton_FirstBasePtn.clicked.connect(
            lambda: self.goto_next_file('first'))

    def _on_long_cursor_changed(self, state):
        """Deactivate pan/zoom when vertical cursor is enabled"""
        if state == QtCore.Qt.Checked:
            # Deactivate any active toolbar mode
            toolbar = self.widget.mpl.canvas.toolbar
            if toolbar and toolbar.mode:
                # Click the active button again to deactivate it
                if toolbar.mode == 'zoom rect':
                    toolbar.zoom()  # Toggle off
                elif toolbar.mode == 'pan/zoom':
                    toolbar.pan()   # Toggle off
            
            # Update the plot to show cursor
            self.plot_ctrl.update()
        else:
            # Update the plot to remove cursor
            self.plot_ctrl.update()

    def _handle_cursor_toggle(self, state):
        """Handle vertical cursor checkbox - implement mutual exclusivity with toolbar"""
        if state == QtCore.Qt.Checked:
            # Cursor was just checked - deactivate toolbar pan/zoom
            toolbar = self.widget.mpl.canvas.toolbar
            if toolbar:
                # Check which mode is active
                current_mode = ''
                if hasattr(toolbar, 'mode'):
                    # New matplotlib API (3.3+)
                    current_mode = toolbar.mode
                elif hasattr(toolbar, '_active'):
                    # Old matplotlib API
                    current_mode = toolbar._active or ''
                
                # Deactivate zoom or pan if active
                if current_mode == 'zoom rect' or current_mode == 'ZOOM':
                    toolbar.zoom()  # Toggle zoom off
                    print("  ✓ Zoom deactivated (cursor enabled)")
                elif current_mode == 'pan/zoom' or current_mode == 'PAN':
                    toolbar.pan()   # Toggle pan off
                    print("  ✓ Pan deactivated (cursor enabled)")
                
                # Ensure toolbar state is cleared
                if hasattr(toolbar, 'mode'):
                    toolbar.mode = ''
                if hasattr(self.plot_ctrl, '_toolbar_active'):
                    self.plot_ctrl._toolbar_active = False
        
        # Update plot to show/hide cursor
        self.apply_changes_to_graph()

    def integrate_to_1d(self):
        # cakeazi_ctrl is pointing CakeAziController 
        # which is in cakeazicontroller.py
        filen = self.cakeazi_ctrl.integrate_to_1d()

        if filen is None:
            return
        else:
            reply = QtWidgets.QMessageBox.question(
                self.widget, 'Message',
                'Do you want to add this file ({:s}) to the waterfall list?'.
                format(filen),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes)
            if reply == QtWidgets.QMessageBox.No:
                return
            else:
                # add to waterfall
                self.waterfall_ctrl._add_patterns([filen])

    def quick_p_change(self, direction):
        step = self.widget.doubleSpinBox_PStep.value()
        p_value = self.widget.doubleSpinBox_Pressure.value()
        self.widget.doubleSpinBox_Pressure.setValue(p_value + step * direction)

    def quick_temp_change(self, direction):
        step = self.widget.spinBox_TStep.value()
        temp_value = self.widget.doubleSpinBox_Temperature.value()
        self.widget.doubleSpinBox_Temperature.setValue(
            temp_value + step * direction)

    def update_jcpds_table(self):
        step = float(self.widget.doubleSpinBox_JCPDSStep.value())
        self.jcpdstable_ctrl.update_steps_only(step)

    """
    def update_ucfit_table(self):
        step = self.widget.doubleSpinBox_UCFitStep.value()
        self.ucfittable_ctrl.update_steps_only(step)
    """

    def del_temp_chi(self):
        reply = QtWidgets.QMessageBox.question(
            self.widget, 'Message',
            'This can slow down PeakPo, but update the background. Proceed?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes)
        if reply == QtWidgets.QMessageBox.No:
            return
        if self._temporary_pkpo_exists():
            temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
            temp_chi = os.path.join(temp_dir, '*.chi')
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
            temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
            temp_cake = os.path.join(temp_dir, '*.npy')
            for f in glob.glob(temp_cake):
                os.remove(f)

    def _temporary_pkpo_exists(self):
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
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

    """
    def export_to_ucfit(self):
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
            if self.model.jcpds_lst[idx_checked[j]].symmetry != 'nosymmetry':
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
        # self.ucfittable_ctrl.update()
        self.jcpdstable_ctrl.update()
        self.plot_ctrl.update()
        return
    """

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
        self.settings.setValue(
            'fontsize_pt_label', self.widget.comboBox_PnTFontSize.currentText())
        self.settings.setValue(
            'fontsize_miller', self.widget.comboBox_HKLFontSize.currentText())
        if hasattr(self.widget, "comboBox_LegendFontSize"):
            self.settings.setValue(
                'fontsize_legend',
                self.widget.comboBox_LegendFontSize.currentText())
        if hasattr(self.widget, "comboBox_WaterfallFontSize"):
            self.settings.setValue(
                'fontsize_waterfall_label',
                self.widget.comboBox_WaterfallFontSize.currentText())
        

    def read_setting(self):
        """
        Read default setting
        """
        self.settings = QtCore.QSettings('DS', 'PeakPo')
        # self.settings.setFallbacksEnabled(False)
        self.model.set_chi_path(self.settings.value('chi_path'))
        self.model.set_jcpds_path(self.settings.value('jcpds_path'))
        pnt_fs = str(self.settings.value(
            'fontsize_pt_label', self.widget.comboBox_PnTFontSize.currentText()))
        hkl_fs = str(self.settings.value(
            'fontsize_miller', self.widget.comboBox_HKLFontSize.currentText()))
        if self.widget.comboBox_PnTFontSize.findText(pnt_fs) >= 0:
            self.widget.comboBox_PnTFontSize.setCurrentText(pnt_fs)
        if self.widget.comboBox_HKLFontSize.findText(hkl_fs) >= 0:
            self.widget.comboBox_HKLFontSize.setCurrentText(hkl_fs)
        if hasattr(self.widget, "comboBox_LegendFontSize"):
            leg_fs = str(self.settings.value(
                'fontsize_legend',
                self.widget.comboBox_LegendFontSize.currentText()))
            if self.widget.comboBox_LegendFontSize.findText(leg_fs) >= 0:
                self.widget.comboBox_LegendFontSize.setCurrentText(leg_fs)
        if hasattr(self.widget, "comboBox_WaterfallFontSize"):
            wf_fs = str(self.settings.value(
                'fontsize_waterfall_label',
                self.widget.comboBox_WaterfallFontSize.currentText()))
            if self.widget.comboBox_WaterfallFontSize.findText(wf_fs) >= 0:
                self.widget.comboBox_WaterfallFontSize.setCurrentText(wf_fs)

    """
    def closeEvent(self, event):
        self.write_setting()
        self.widget.deleteLater()
        gc.collect()
        self.deleteLater()
        event.accept()
    """

    def on_key_press(self, event):
        from matplotlib.backend_bases import key_press_handler
        
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
    """
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
    """

    def set_nightday_view(self):
        self.plot_ctrl._set_nightday_view()
        self.waterfalltable_ctrl.update()
        self.plot_ctrl.update()

    def deliver_mouse_signal(self, event):
        # ✅ Compatible with matplotlib 3.3+
        if hasattr(self.widget.mpl.ntb, 'mode'):
            # New matplotlib API
            if self.widget.mpl.ntb.mode != '':
                return
        elif hasattr(self.widget.mpl.ntb, '_active'):
            # Old matplotlib API
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
        if (self.widget.tabWidget.currentIndex() == 4) and \
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
            "Clicked position: {0:.4f}, {1:.1f}, \n d-sp = {2:.4f} \u212B".\
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

    def setXEat(self, wavelength):
        self.widget.doubleSpinBox_SetWavelength.setValue(wavelength)
        self.apply_wavelength()

    def apply_wavelength(self):
        # self.wavelength = value
        self.model.base_ptn.wavelength = \
            self.widget.doubleSpinBox_SetWavelength.value()
        xray_energy = convert_wl_to_energy(self.model.base_ptn.wavelength)
        self.widget.label_XRayEnergy.setText(
            "({:.3f} keV)".format(xray_energy))
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
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        self.model.base_ptn.write_temporary_bgfiles(temp_dir=temp_dir)
        if self.model.waterfall_exist():
            print(str(datetime.datetime.now())[:-7], 
                ": BGfit and BGsub for waterfall patterns even if they are displayed.\n",
                "Yes this is a bit of waste.  Future fix needed.")
            for pattern in self.model.waterfall_ptn:
                pattern.subtract_bg(bg_roi, bg_params, yshift=0)
        self.plot_new_graph()

    def apply_pt_to_graph(self):
        """
        if self.model.jcpds_exist():
            self.plot_ctrl.update_jcpds_only()
        else:
        """
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
        line1 = '2\u03B8 = {0:.4f} \u00B0, d-sp = {1:.4f} \u212B'.format(
            float(tth_min), float(dsp_min))
        line2 = 'intensity = {0: .0f}, hkl = {1: .0f} {2: .0f} {3: .0f}'.\
            format(int(int_min), int(h_min), int(k_min), int(l_min))
        textoutput = name_min + '\n' + line1 + '\n' + line2
        return textoutput

    def goto_next_file(self, move):
        """
        quick move to the next base pattern file
        """
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Choose a base pattern first.")
            return
        if self.widget.checkBox_NavDPP.isChecked():
            self._goto_dpp_next_file(move)
        else:
            self._goto_chi_next_file(move)
        return

    def _goto_chi_next_file(self, move):
        filelist_chi = get_sorted_filelist(
            self.model.chi_path,
            sorted_by_name=self.widget.radioButton_SortbyNme.isChecked(),
            search_ext='*.chi')

        idx_chi = find_from_filelist(filelist_chi,
                                     os.path.split(
                                         self.model.base_ptn.fname)[1])

        if idx_chi == -1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Cannot find current file")
            return  # added newly

        step = self.widget.spinBox_FileStep.value()
        if move == 'next':
            idx_chi_new = idx_chi + step
        elif move == 'previous':
            idx_chi_new = idx_chi - step
        elif move == 'last':
            idx_chi_new = filelist_chi.__len__() - 1
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        elif move == 'first':
            idx_chi_new = 0
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return

        if idx_chi_new > filelist_chi.__len__() - 1:
            idx_chi_new = filelist_chi.__len__() - 1
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        if idx_chi_new < 0:
            idx_chi_new = 0
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return
        new_filename_chi = filelist_chi[idx_chi_new]
        if os.path.exists(new_filename_chi):
            self.base_ptn_ctrl._load_a_new_pattern(new_filename_chi)
            # self.model.set_base_ptn_color(self.obj_color)
            self.plot_ctrl.update()
        else:
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          new_filename_chi +
                                          " does not exist.")

    def _goto_dpp_next_file(self, move):

        filelist_chi = get_sorted_filelist(
            self.model.chi_path,
            sorted_by_name=self.widget.radioButton_SortbyNme.isChecked(),
            search_ext='*.chi')
        filelist_dpp = get_sorted_filelist(
            self.model.chi_path,
            sorted_by_name=self.widget.radioButton_SortbyNme.isChecked(),
            search_ext='*.dpp')

        idx_chi = find_from_filelist(filelist_chi,
                                     os.path.split(
                                         self.model.base_ptn.fname)[1])
        dpp_filen = make_filename(self.model.base_ptn.fname, 'dpp')
        idx_dpp = find_from_filelist(filelist_dpp,
                                     dpp_filen)

        if idx_chi == -1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Cannot find current chi file")
            return  # added newly

        # for radioButton_NavDPP
        if idx_dpp == -1:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Cannot find current dpp file.\n" +
                "Manually save one for current chi file first.")
            return  # added newly

        step = self.widget.spinBox_FileStep.value()
        if move == 'next':
            idx_chi_new = idx_chi + step
        elif move == 'previous':
            idx_chi_new = idx_chi - step
        elif move == 'last':
            idx_chi_new = filelist_chi.__len__() - 1
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        elif move == 'first':
            idx_chi_new = 0
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return
        if idx_chi_new > filelist_chi.__len__() - 1:
            idx_chi_new = filelist_chi.__len__() - 1
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the last file.")
                return
        if idx_chi_new < 0:
            idx_chi_new = 0
            if idx_chi == idx_chi_new:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "It is already the first file.")
                return

        if self.widget.checkBox_SaveDPPMove.isChecked():
            self.session_ctrl.save_dpp(quiet=True)
        else:
            reply = QtWidgets.QMessageBox.question(
                self.widget, 'Message',
                'Do you want to save this to dpp before you move to the next?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes)
            if reply == QtWidgets.QMessageBox.Yes:
                self.session_ctrl.save_dpp()

        new_filename_chi = filelist_chi[idx_chi_new]
        new_filename_dpp = make_filename(new_filename_chi, 'dpp')
        idx = find_from_filelist(filelist_dpp,
                                 new_filename_dpp)

        if idx == -1:
            # no pre-existing dpp
            # check the checkbox for autogenerate
            if self.widget.checkBox_AutoGenDPP.isChecked():
                self.base_ptn_ctrl._load_a_new_pattern(new_filename_chi)
                self.session_ctrl.save_dpp(quiet=True)
                self.model.clear_section_list()
                self.plot_ctrl.update()
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "Cannot find pre-existing dpp.\n" +
                    "Consider Create with Move function.")
                return
            # call autogenerate subroutine
            # self._load_a_new_pattern(new_filename_chi)
            # self.model.set_base_ptn_color(self.obj_color)
            # self.plot_ctrl.update()
        else:
            # pre-existing dpp
            # question if overwrite or not
            if self.widget.checkBox_AutoGenDPP.isChecked() and \
                (not self.widget.checkBox_AutogenMissing.isChecked()):
                reply = QtWidgets.QMessageBox.question(
                    self.widget, 'Message',
                    "The next pattern already has a dpp.\n" +
                    "If you want to overwrite the existing one based" +
                    " on the dpp of the last pattern, choose YES.\n" +
                    "If you want to keep and open the existing dpp, choose NO.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.Yes:
                    self.base_ptn_ctrl._load_a_new_pattern(new_filename_chi)
                    self.session_ctrl.save_dpp(quiet=True)
                    self.model.clear_section_list()
                    self.plot_ctrl.update()
                else:
                    # load the existing dpp
                    # QtWidgets.QMessageBox.warning(
                    #    self.widget, "Warning", "The existing dpp will be open.")
                    success = self.session_ctrl._load_dpp(new_filename_dpp)
                    if success:
                        if self.model.exist_in_waterfall(
                            self.model.base_ptn.fname):
                            self.widget.pushButton_AddBasePtn.setChecked(True)
                        else:
                            self.widget.pushButton_AddBasePtn.setChecked(False)
                        if self.widget.checkBox_ShowCake.isChecked():
                            self.session_ctrl._load_cake_format_file()
                        self.plot_ctrl.update()
                    else:
                        QtWidgets.QMessageBox.warning(
                            self.widget, "Warning",
                            "DPP loading was not successful.")
                        return
            else:
                # simply open the next existing one
                success = self.session_ctrl._load_dpp(new_filename_dpp)
                if success:
                    if self.model.exist_in_waterfall(
                        self.model.base_ptn.fname):
                        self.widget.pushButton_AddBasePtn.setChecked(True)
                    else:
                        self.widget.pushButton_AddBasePtn.setChecked(False)
                    if self.widget.checkBox_ShowCake.isChecked():
                        self.session_ctrl._load_cake_format_file()
                    self.plot_ctrl.update()
                else:
                    QtWidgets.QMessageBox.warning(
                        self.widget, "Warning",
                        "DPP loading was not successful.")
                    return
        self.jcpdstable_ctrl.update()
        self.peakfit_table_ctrl.update_sections()
        self.peakfit_table_ctrl.update_peak_parameters()
        self.peakfit_table_ctrl.update_baseline_constraints()
        self.peakfit_table_ctrl.update_peak_constraints()
        return

        # QtWidgets.QMessageBox.warning(self.widget, "Warning",
        #                              new_filename_chi + " does not exist.")
