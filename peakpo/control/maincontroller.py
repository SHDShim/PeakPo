import os
import glob
import numpy as np
import copy
#from matplotlib.backend_bases import key_press_handler
from qtpy import QtWidgets
from qtpy import QtCore
import gc
import datetime
from contextlib import contextmanager
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
from .diffcontroller import DiffController
from .peakfitcontroller import PeakFitController
from .peakfittablecontroller import PeakfitTableController
from .cakeazicontroller import CakeAziController
from .exportpythoncontroller import ExportPythonController
from .mapcontroller import MapController
from .sequencecontroller import SequenceController
from ..utils import dialog_savefile, writechi, convert_wl_to_energy, \
    get_sorted_filelist, find_from_filelist, make_filename, \
    get_directory, get_temp_dir
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
        self._mouse_mode = 'navigate'
        self._syncing_mouse_mode = False

        self.model = PeakPoModel8()
        print("  ✓ PeakPoModel8 created")

        self.session_ctrl = SessionController(self.model, self.widget)
        print("  ✓ SessionController created")

        self.base_ptn_ctrl = BasePatternController(
            self.model, self.widget, session_ctrl=self.session_ctrl)
        print("  ✓ BasePatternController created")
        
        self.plot_ctrl = MplController(self.model, self.widget)
        print("  ✓ MplController created")

        self.diff_ctrl = DiffController(self.model, self.widget, self.plot_ctrl)
        self.plot_ctrl.set_diff_controller(self.diff_ctrl)
        self._propagate_diff_controller()
        print("  ✓ DiffController created")

        self.map_ctrl = MapController(self.model, self.widget)
        self.map_ctrl.set_helpers(
            base_ptn_ctrl=self.base_ptn_ctrl,
            plot_ctrl=self.plot_ctrl,
            mouse_mode_done_cb=self._finish_temporary_mouse_mode)
        print("  ✓ MapController created")

        self.seq_ctrl = SequenceController(self.model, self.widget)
        self.seq_ctrl.set_helpers(
            base_ptn_ctrl=self.base_ptn_ctrl,
            plot_ctrl=self.plot_ctrl,
            mouse_mode_done_cb=self._finish_temporary_mouse_mode)
        print("  ✓ SequenceController created")
        
        self.cakeazi_ctrl = CakeAziController(self.model, self.widget)
        print("  ✓ CakeAziController created")
        
        self.waterfall_ctrl = WaterfallController(self.model, self.widget)
        self.waterfall_ctrl.set_navigation_helpers(
            base_ptn_ctrl=self.base_ptn_ctrl,
            capture_nav_state_cb=self._capture_nav_carry_state,
            apply_nav_state_cb=self._apply_nav_carry_state,
        )
        print("  ✓ WaterfallController created")
        
        self.ucfit_ctrl = UcfitController(self.model, self.widget)
        print("  ✓ UcfitController created")
        
        self.jcpds_ctrl = JcpdsController(self.model, self.widget)
        print("  ✓ JcpdsController created")
        
        self.waterfalltable_ctrl = WaterfallTableController(self.model, self.widget)
        print("  ✓ WaterfallTableController created")
        
        self.jcpdstable_ctrl = JcpdsTableController(self.model, self.widget)
        print("  ✓ JcpdsTableController created")
        
        self.peakfit_ctrl = PeakFitController(self.model, self.widget)
        print("  ✓ PeakFitController created")
        
        self.peakfit_table_ctrl = PeakfitTableController(self.model, self.widget)
        print("  ✓ PeakfitTableController created")

        self.export_py_ctrl = ExportPythonController(
            self.model, self.widget, plot_ctrl=self.plot_ctrl)
        print("  ✓ ExportPythonController created")
        self.map_ctrl.set_helpers(
            base_ptn_ctrl=self.base_ptn_ctrl,
            plot_ctrl=self.plot_ctrl,
            mouse_mode_done_cb=self._finish_temporary_mouse_mode,
            export_current_view_cb=self.export_py_ctrl.export_current_view)
        self.seq_ctrl.set_helpers(
            base_ptn_ctrl=self.base_ptn_ctrl,
            plot_ctrl=self.plot_ctrl,
            mouse_mode_done_cb=self._finish_temporary_mouse_mode,
            export_current_view_cb=self.export_py_ctrl.export_current_view)
        self._propagate_diff_controller()
        
        self.read_setting()
        print("  ✓ read_setting() done")
        
        self.connect_channel()
        print("  ✓ connect_channel() done")
        self._initialize_mouse_mode()
        
        self.clip = QtWidgets.QApplication.clipboard()
        print("  ✓ clipboard set")
        self._shutdown_done = False
        self._defer_plot_update_count = 0
        
        print("MainController.__init__ - DONE\n")

    def _propagate_diff_controller(self):
        # Multiple controllers keep their own MplController instances.
        # Keep Diff behavior consistent across all redraw paths.
        for ctrl_name in (
            "session_ctrl",
            "base_ptn_ctrl",
            "waterfall_ctrl",
            "ucfit_ctrl",
            "jcpds_ctrl",
            "waterfalltable_ctrl",
            "jcpdstable_ctrl",
            "peakfit_ctrl",
            "peakfit_table_ctrl",
            "cakeazi_ctrl",
        ):
            ctrl = getattr(self, ctrl_name, None)
            plot_ctrl = getattr(ctrl, "plot_ctrl", None)
            if (plot_ctrl is not None) and hasattr(plot_ctrl, "set_diff_controller"):
                plot_ctrl.set_diff_controller(self.diff_ctrl)
        # Nested cake controller under base pattern controller.
        if hasattr(self, "base_ptn_ctrl") and hasattr(self.base_ptn_ctrl, "cake_ctrl"):
            cake_plot_ctrl = getattr(self.base_ptn_ctrl.cake_ctrl, "plot_ctrl", None)
            if (cake_plot_ctrl is not None) and hasattr(cake_plot_ctrl, "set_diff_controller"):
                cake_plot_ctrl.set_diff_controller(self.diff_ctrl)

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
        self.widget.mpl.canvas.mpl_connect(
            'motion_notify_event', self._update_cursor_position_readout)
        self.widget.mpl.canvas.mpl_connect(
            'figure_leave_event', self._clear_cursor_position_readout)
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
        if hasattr(self.widget, "pushButton_ExportPythonView"):
            self.widget.pushButton_ExportPythonView.clicked.connect(
                self.export_py_ctrl.export_current_view)
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
        self.widget.pushButton_UpdateBackground.clicked.connect(
            self.update_bgsub)
        if hasattr(self.widget, "pushButton_ResetBGParams"):
            self.widget.pushButton_ResetBGParams.clicked.connect(
                self.reset_bg_params_to_default)
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
        if hasattr(self.widget, "spinBox_TitleFontSize"):
            self.widget.spinBox_TitleFontSize.valueChanged.connect(
                self.apply_changes_to_graph)
        if hasattr(self.widget, "spinBox_TitleMaxLength"):
            self.widget.spinBox_TitleMaxLength.valueChanged.connect(
                self.apply_changes_to_graph)
        if hasattr(self.widget, "checkBox_TitleTruncateMiddle"):
            self.widget.checkBox_TitleTruncateMiddle.clicked.connect(
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
        if hasattr(self.widget, "comboBox_CakeColormap"):
            self.widget.comboBox_CakeColormap.currentIndexChanged.connect(
                self.apply_changes_to_graph)
        self.widget.pushButton_S_Zoom.clicked.connect(self.plot_new_graph)
        self.widget.checkBox_AutoY.clicked.connect(self.apply_changes_to_graph)
        self.widget.checkBox_BgSub.clicked.connect(self.apply_bgsub_toggle)
        if hasattr(self.widget, "checkBox_LightBackground"):
            self.widget.checkBox_LightBackground.clicked.connect(
                self.apply_changes_to_graph)
        self.widget.checkBox_ShowWaterfallLabels.clicked.connect(
            self.apply_changes_to_graph)
        self.widget.checkBox_ShowMillerIndices_Cake.clicked.connect(
            self.apply_changes_to_graph)
        # self.widget.actionClose.triggered.connect(self.closeEvent)
        self.widget.tabWidget.currentChanged.connect(self.check_for_peakfit)
        self.widget.tabWidget.currentChanged.connect(
            self._refresh_mouse_mode_availability)
        # self.widget.tabWidget.setTabEnabled(8, False)
        self.widget.pushButton_DelTempCHI.clicked.connect(self.del_temp_chi)
        self.widget.pushButton_DelTempCake.clicked.connect(self.del_temp_cake)
        # slide bars
        self.widget.horizontalSlider_VMin.setValue(0)
        self.widget.horizontalSlider_VMax.setValue(100)
        if hasattr(self.widget, "cake_hist_widget"):
            self.widget.cake_hist_widget.combo_scale_mode.currentIndexChanged.connect(
                self._sync_cake_scale_bar_from_combo)
            self.widget.cake_hist_widget.combo_scale_mode.currentIndexChanged.connect(
                self.apply_changes_to_graph)
        self.widget.horizontalSlider_MaxScaleBars.valueChanged.connect(
            self._sync_cake_scale_combo_from_slider)
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
        if hasattr(self.widget, "buttonGroup_MouseMode"):
            self.widget.buttonGroup_MouseMode.buttonToggled.connect(
                self._on_mouse_mode_button_toggled)
        if hasattr(self.widget, "pushButton_AddRemoveFromMouse"):
            self.widget.pushButton_AddRemoveFromMouse.toggled.connect(
                self._on_peakpick_button_toggled)

    def _initialize_mouse_mode(self):
        self._refresh_mouse_mode_availability()
        self._set_mouse_mode('navigate')

    def _get_toolbar(self):
        return getattr(self.widget.mpl, "ntb", None)

    def _get_toolbar_mode(self):
        toolbar = self._get_toolbar()
        if toolbar is None:
            return ''
        if hasattr(toolbar, 'mode'):
            return toolbar.mode or ''
        if hasattr(toolbar, '_active'):
            return toolbar._active or ''
        return ''

    def _deactivate_toolbar_modes(self):
        toolbar = self._get_toolbar()
        if toolbar is None:
            return
        current_mode = self._get_toolbar_mode()
        if current_mode in ('zoom rect', 'ZOOM'):
            toolbar.zoom()
        elif current_mode in ('pan/zoom', 'PAN'):
            toolbar.pan()

    def _set_toolbar_zoom_active(self, enabled):
        toolbar = self._get_toolbar()
        if toolbar is None:
            return
        current_mode = self._get_toolbar_mode()
        if current_mode in ('pan/zoom', 'PAN'):
            toolbar.pan()
            current_mode = self._get_toolbar_mode()
        zoom_active = current_mode in ('zoom rect', 'ZOOM')
        if enabled and (not zoom_active):
            toolbar.zoom()
        elif (not enabled) and zoom_active:
            toolbar.zoom()

    def _is_map_tab_active(self):
        return hasattr(self.widget, "tab_Map") and \
            (self.widget.tabWidget.currentWidget() == self.widget.tab_Map)

    def _is_seq_tab_active(self):
        return hasattr(self.widget, "tab_Seq") and \
            (self.widget.tabWidget.currentWidget() == self.widget.tab_Seq)

    def _fits_tab_active(self):
        if hasattr(self.widget, "tab_PkFt"):
            try:
                return self.widget.tabWidget.currentWidget() == \
                    self.widget.tab_PkFt
            except Exception:
                pass
        return self.widget.tabWidget.currentIndex() in (4, 5)

    def _roi_mode_available(self):
        return self._is_map_tab_active() or self._is_seq_tab_active()

    def _set_mouse_mode_button_state(self, mode):
        button_map = {
            'navigate': getattr(self.widget, "pushButton_MouseModeZoom", None),
            'roi': getattr(self.widget, "pushButton_MouseModeROI", None),
            'peakpick': getattr(self.widget, "pushButton_MouseModePeakPick", None),
            'jcpds': getattr(self.widget, "pushButton_MouseModeJCPDS", None),
        }
        button = button_map.get(mode)
        if button is None:
            return
        self._syncing_mouse_mode = True
        button.setChecked(True)
        self._syncing_mouse_mode = False

    def _sync_peakpick_button(self, enabled):
        if not hasattr(self.widget, "pushButton_AddRemoveFromMouse"):
            return
        self._syncing_mouse_mode = True
        self.widget.pushButton_AddRemoveFromMouse.setChecked(bool(enabled))
        self._syncing_mouse_mode = False

    def _deactivate_roi_modes(self):
        if hasattr(self, "map_ctrl") and (self.map_ctrl is not None):
            self.map_ctrl.deactivate_interactions()
        if hasattr(self, "seq_ctrl") and (self.seq_ctrl is not None):
            self.seq_ctrl.deactivate_interactions()

    def _refresh_mouse_mode_availability(self, *_args):
        roi_available = self._roi_mode_available()
        peakpick_available = self._fits_tab_active()
        if hasattr(self.widget, "pushButton_MouseModeROI"):
            self.widget.pushButton_MouseModeROI.setEnabled(roi_available)
        if hasattr(self.widget, "pushButton_MouseModePeakPick"):
            self.widget.pushButton_MouseModePeakPick.setEnabled(
                peakpick_available)
        if (self._mouse_mode == 'roi') and (not roi_available):
            self._set_mouse_mode('navigate')
        if (self._mouse_mode == 'peakpick') and (not peakpick_available):
            self._set_mouse_mode('navigate')

    def _set_mouse_mode(self, mode):
        if mode == self._mouse_mode:
            if mode == 'navigate':
                self._set_toolbar_zoom_active(True)
            return
        if mode == 'roi' and (not self._roi_mode_available()):
            mode = 'navigate'
        if mode == 'peakpick' and (not self._fits_tab_active()):
            mode = 'navigate'

        self._deactivate_toolbar_modes()
        self._deactivate_roi_modes()
        self._sync_peakpick_button(False)

        if hasattr(self.widget, "checkBox_LongCursor") and \
                self.widget.checkBox_LongCursor.isChecked():
            self.widget.checkBox_LongCursor.setChecked(False)

        self._mouse_mode = mode
        self._set_mouse_mode_button_state(mode)

        if mode == 'navigate':
            self._set_toolbar_zoom_active(True)
        elif mode == 'roi':
            if self._is_map_tab_active():
                self.map_ctrl._arm_roi_selection()
            elif self._is_seq_tab_active():
                self.seq_ctrl._arm_roi_selection()
        elif mode == 'peakpick':
            self._sync_peakpick_button(True)

    def _finish_temporary_mouse_mode(self, mode):
        if mode == self._mouse_mode and mode in ('roi', 'jcpds'):
            self._set_mouse_mode('navigate')

    def _on_mouse_mode_button_toggled(self, button, checked):
        if self._syncing_mouse_mode or (not checked) or (button is None):
            return
        mode = str(button.property("mouseMode") or "navigate")
        self._set_mouse_mode(mode)

    def _on_peakpick_button_toggled(self, checked):
        if self._syncing_mouse_mode:
            return
        if checked:
            self._set_mouse_mode('peakpick')
        elif self._mouse_mode == 'peakpick':
            self._set_mouse_mode('navigate')

    def _clear_cursor_position_readout(self, _event=None):
        if hasattr(self, "plot_ctrl") and (self.plot_ctrl is not None):
            self.plot_ctrl.clear_vertical_cursor_position()
        if hasattr(self.widget, "label_CursorPosition"):
            self.widget.label_CursorPosition.setText("")

    def _update_cursor_position_readout(self, event):
        if hasattr(self, "plot_ctrl") and (self.plot_ctrl is not None):
            self.plot_ctrl.update_vertical_cursor_position(event)
        if not hasattr(self.widget, "label_CursorPosition"):
            return
        if (event is None) or (event.inaxes is None) or \
                (event.xdata is None) or (event.ydata is None):
            self._clear_cursor_position_readout()
            return
        formatter = getattr(event.inaxes, "format_coord", None)
        if callable(formatter):
            try:
                text = formatter(event.xdata, event.ydata)
            except Exception:
                text = ""
        else:
            text = ""
        text = str(text).replace("\n", " ").strip()
        self.widget.label_CursorPosition.setText(text)

    def _on_long_cursor_changed(self, state):
        """Keep vertical cursor and hidden zoom mode in sync."""
        if state == QtCore.Qt.Checked:
            self._deactivate_toolbar_modes()
            self.plot_ctrl.update()
        else:
            if self._mouse_mode == 'navigate':
                self._set_toolbar_zoom_active(True)
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
        if hasattr(self.widget, "tab_PkFt"):
            is_peakfit_tab = (self.widget.tabWidget.widget(i) == self.widget.tab_PkFt)
        else:
            is_peakfit_tab = (i == 8)
        if is_peakfit_tab:
            self.widget.checkBox_AutoY.setChecked(False)
            self.apply_changes_to_graph()

    def apply_changes_to_graph(self):
        if self._plot_update_deferred():
            return
        self.plot_ctrl.update()
        if hasattr(self, "map_ctrl") and (self.map_ctrl is not None):
            try:
                self.map_ctrl.refresh_roi_overlays()
            except Exception:
                pass
        if hasattr(self, "seq_ctrl") and (self.seq_ctrl is not None):
            try:
                self.seq_ctrl.refresh_roi_overlays()
            except Exception:
                pass

    def apply_bgsub_toggle(self):
        if self._plot_update_deferred():
            return
        if not self.model.base_ptn_exist():
            self.apply_changes_to_graph()
            return

        try:
            xlim = self.widget.mpl.canvas.ax_pattern.get_xlim()
            if self.widget.checkBox_BgSub.isChecked():
                x, y = self.model.base_ptn.get_bgsub()
            else:
                x, y = self.model.base_ptn.get_raw()
            if self.plot_ctrl.diff_ctrl is not None:
                x, y = self.plot_ctrl.diff_ctrl.get_display_pattern(x, y)

            xroi, yroi = get_DataSection(x, y, [xlim[0], xlim[1]])
            if len(yroi) == 0:
                new_limits = self.plot_ctrl._get_data_limits(y_margin=0.0)
            else:
                yroi = np.asarray(yroi, dtype=float)
                yroi = yroi[np.isfinite(yroi)]
                if yroi.size == 0:
                    new_limits = self.plot_ctrl._get_data_limits(y_margin=0.0)
                else:
                    ymin = float(np.min(yroi))
                    ymax = float(np.max(yroi))
                    if ymax <= ymin:
                        pad = max(1.0, abs(ymax) * 0.05)
                        ymin -= pad
                        ymax += pad
                    else:
                        pad = (ymax - ymin) * 0.03
                        ymin -= pad
                        ymax += pad
                    new_limits = [xlim[0], xlim[1], ymin, ymax]
            self.plot_ctrl.update(new_limits)
        except Exception:
            self.plot_ctrl.update()

        if hasattr(self, "map_ctrl") and (self.map_ctrl is not None):
            try:
                self.map_ctrl.refresh_roi_overlays()
            except Exception:
                pass
        if hasattr(self, "seq_ctrl") and (self.seq_ctrl is not None):
            try:
                self.seq_ctrl.refresh_roi_overlays()
            except Exception:
                pass

    def plot_new_graph(self):
        self.plot_ctrl.zoom_out_graph()
        if hasattr(self, "map_ctrl") and (self.map_ctrl is not None):
            try:
                self.map_ctrl.refresh_roi_overlays()
            except Exception:
                pass
        if hasattr(self, "seq_ctrl") and (self.seq_ctrl is not None):
            try:
                self.seq_ctrl.refresh_roi_overlays()
            except Exception:
                pass

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
        # Persist azimuthal shift across app restarts.
        self.settings.setValue(
            'azi_shift',
            int(self.widget.spinBox_AziShift.value()))
        # CHI navigation carry-over policy
        nav_keys = [
            ("carry_nav_jcpds", "checkBox_CarryNavJCPDS"),
            ("carry_nav_pressure", "checkBox_CarryNavPressure"),
            ("carry_nav_temperature", "checkBox_CarryNavTemperature"),
            ("carry_nav_cake_z_scale", "checkBox_CarryNavCakeZScale"),
            ("carry_nav_background", "checkBox_CarryNavBackground"),
            ("carry_nav_waterfall_list", "checkBox_CarryNavWaterfall"),
            ("carry_nav_poni", "checkBox_CarryNavPONI"),
            ("carry_nav_fits_information", "checkBox_CarryNavFits"),
        ]
        for key, attr in nav_keys:
            if hasattr(self.widget, attr):
                self.settings.setValue(key, bool(getattr(self.widget, attr).isChecked()))

        for key, attr in self._plot_config_setting_bindings():
            if hasattr(self.widget, attr):
                self._save_widget_to_settings(key, getattr(self.widget, attr))
        

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
        if hasattr(self.widget, "comboBox_CakeColormap"):
            # Always start with gray_r regardless of previous sessions/settings.
            self.widget.comboBox_CakeColormap.setCurrentText("gray_r")
        raw_azi_shift = self.settings.value(
            'azi_shift',
            int(self.widget.spinBox_AziShift.value()))
        try:
            azi_shift = int(raw_azi_shift)
        except Exception:
            azi_shift = int(self.widget.spinBox_AziShift.value())
        self.widget.spinBox_AziShift.setValue(azi_shift)
        nav_defaults = {
            "checkBox_CarryNavJCPDS": True,
            "checkBox_CarryNavPressure": True,
            "checkBox_CarryNavTemperature": True,
            "checkBox_CarryNavCakeZScale": False,
            "checkBox_CarryNavBackground": False,
            "checkBox_CarryNavWaterfall": True,
            "checkBox_CarryNavPONI": False,
            "checkBox_CarryNavFits": False,
        }
        nav_keys = {
            "checkBox_CarryNavJCPDS": "carry_nav_jcpds",
            "checkBox_CarryNavPressure": "carry_nav_pressure",
            "checkBox_CarryNavTemperature": "carry_nav_temperature",
            "checkBox_CarryNavCakeZScale": "carry_nav_cake_z_scale",
            "checkBox_CarryNavBackground": "carry_nav_background",
            "checkBox_CarryNavWaterfall": "carry_nav_waterfall_list",
            "checkBox_CarryNavPONI": "carry_nav_poni",
            "checkBox_CarryNavFits": "carry_nav_fits_information",
        }
        for attr, key in nav_keys.items():
            if hasattr(self.widget, attr):
                raw = self.settings.value(key, nav_defaults[attr])
                val = str(raw).lower() in ("1", "true", "yes") if isinstance(raw, str) else bool(raw)
                getattr(self.widget, attr).setChecked(val)

        for key, attr in self._plot_config_setting_bindings():
            if hasattr(self.widget, attr):
                self._load_widget_from_settings(
                    key, getattr(self.widget, attr))

    def _plot_config_setting_bindings(self):
        return [
            ("plot_cfg/night_view", "checkBox_NightView"),
            ("plot_cfg/night_cake", "checkBox_WhiteForPeak"),
            ("plot_cfg/show_large_pt", "checkBox_ShowLargePnT"),
            ("plot_cfg/title_filename_only", "checkBox_ShortPlotTitle"),
            ("plot_cfg/title_truncate_middle", "checkBox_TitleTruncateMiddle"),
            ("plot_cfg/title_font_size", "spinBox_TitleFontSize"),
            ("plot_cfg/title_max_length", "spinBox_TitleMaxLength"),
            ("plot_cfg/base_line_thickness", "comboBox_BasePtnLineThickness"),
            ("plot_cfg/background_line_thickness", "comboBox_BkgnLineThickness"),
            ("plot_cfg/waterfall_line_thickness", "comboBox_WaterfallLineThickness"),
            ("plot_cfg/vcursor_thickness", "comboBox_VertCursorThickness"),
            ("plot_cfg/fontsize_pt_label", "comboBox_PnTFontSize"),
            ("plot_cfg/fontsize_miller", "comboBox_HKLFontSize"),
            ("plot_cfg/fontsize_legend", "comboBox_LegendFontSize"),
            ("plot_cfg/fontsize_waterfall_label", "comboBox_WaterfallFontSize"),
            ("plot_cfg/jcpds_alpha_pattern", "doubleSpinBox_JCPDS_ptn_Alpha"),
            ("plot_cfg/jcpds_alpha_cake", "doubleSpinBox_JCPDS_cake_Alpha"),
            ("plot_cfg/jcpds_thickness_pattern", "comboBox_PtnJCPDSBarThickness"),
            ("plot_cfg/jcpds_thickness_cake", "comboBox_CakeJCPDSBarThickness"),
            ("plot_cfg/light_background", "checkBox_LightBackground"),
        ]

    def _save_widget_to_settings(self, key, widget):
        if isinstance(widget, QtWidgets.QCheckBox):
            self.settings.setValue(key, bool(widget.isChecked()))
            return
        if isinstance(widget, QtWidgets.QComboBox):
            self.settings.setValue(key, str(widget.currentText()))
            return
        if isinstance(widget, QtWidgets.QSpinBox):
            self.settings.setValue(key, int(widget.value()))
            return
        if isinstance(widget, QtWidgets.QDoubleSpinBox):
            self.settings.setValue(key, float(widget.value()))
            return

    def _load_widget_from_settings(self, key, widget):
        if isinstance(widget, QtWidgets.QCheckBox):
            raw = self.settings.value(key, widget.isChecked())
            val = str(raw).lower() in ("1", "true", "yes") if isinstance(raw, str) else bool(raw)
            widget.setChecked(val)
            return
        if isinstance(widget, QtWidgets.QComboBox):
            raw = str(self.settings.value(key, widget.currentText()))
            if widget.findText(raw) >= 0:
                widget.setCurrentText(raw)
            return
        if isinstance(widget, QtWidgets.QSpinBox):
            raw = self.settings.value(key, widget.value())
            try:
                widget.setValue(int(raw))
            except Exception:
                pass
            return
        if isinstance(widget, QtWidgets.QDoubleSpinBox):
            raw = self.settings.value(key, widget.value())
            try:
                widget.setValue(float(raw))
            except Exception:
                pass
            return

    def _capture_nav_carry_state(self):
        source_chi = None
        if self.model.base_ptn_exist():
            source_chi = os.path.basename(self.model.get_base_ptn_filename())
        cake_hist = {}
        if hasattr(self.widget, "cake_hist_widget"):
            hist = self.widget.cake_hist_widget
            cake_hist = {
                "log_y": bool(hist.check_log.isChecked()),
                "focus_range": bool(hist.check_focus.isChecked()),
                "low_pct": float(hist.spin_low_pct.value()),
                "high_pct": float(hist.spin_high_pct.value()),
            }
        return {
            "source_chi": source_chi,
            "jcpds_lst": copy.deepcopy(self.model.jcpds_lst),
            "pressure": float(self.model.get_saved_pressure()),
            "temperature": float(self.model.get_saved_temperature()),
            "cake_z_scale": {
                "int_max": int(self.widget.spinBox_MaxCakeScale.value()),
                "min_bar": int(self.widget.horizontalSlider_VMin.value()),
                "max_bar": int(self.widget.horizontalSlider_VMax.value()),
                "scale_bar": int(self._get_cake_scale_bar_value()),
                "hist": cake_hist,
            },
            "background": {
                "roi_min": float(self.widget.doubleSpinBox_Background_ROI_min.value()),
                "roi_max": float(self.widget.doubleSpinBox_Background_ROI_max.value()),
                "n_points": int(self.widget.spinBox_BGParam0.value()),
                "n_order": int(self.widget.spinBox_BGParam1.value()),
                "n_iteration": int(self.widget.spinBox_BGParam2.value()),
            },
            "waterfall_list": copy.deepcopy(self.model.waterfall_ptn),
            "poni": self.model.poni,
            "fits_information": {
                "section_lst": copy.deepcopy(self.model.section_lst),
                "current_section": copy.deepcopy(self.model.current_section),
            },
        }

    def _should_carry_nav_category(self, key, checkbox_attr):
        presence = self.session_ctrl.get_last_param_category_presence()
        if not bool(presence.get(key, False)):
            # If target CHI has no existing info, always carry from current.
            return True
        if key == "jcpds":
            # JCPDS attached to the destination CHI should take precedence over
            # carry-over. This avoids overwriting a file's own saved phase list.
            return False
        if not hasattr(self.widget, checkbox_attr):
            return True
        return bool(getattr(self.widget, checkbox_attr).isChecked())

    def _apply_nav_carry_state(self, snap):
        carried_any = False
        if self._should_carry_nav_category("jcpds", "checkBox_CarryNavJCPDS"):
            self.model.jcpds_lst = copy.deepcopy(snap["jcpds_lst"])
            self.jcpdstable_ctrl.update()
            carried_any = True

        if self._should_carry_nav_category("pressure", "checkBox_CarryNavPressure"):
            self.model.save_pressure(float(snap["pressure"]))
            self.widget.doubleSpinBox_Pressure.setValue(float(snap["pressure"]))
            carried_any = True

        if self._should_carry_nav_category("temperature", "checkBox_CarryNavTemperature"):
            self.model.save_temperature(float(snap["temperature"]))
            self.widget.doubleSpinBox_Temperature.setValue(float(snap["temperature"]))
            carried_any = True

        if self._should_carry_nav_category("cake_z_scale", "checkBox_CarryNavCakeZScale"):
            cake = snap["cake_z_scale"]
            self.widget.spinBox_MaxCakeScale.setValue(int(cake["int_max"]))
            self.widget.horizontalSlider_VMin.setValue(int(cake["min_bar"]))
            self.widget.horizontalSlider_VMax.setValue(int(cake["max_bar"]))
            self._set_cake_scale_bar_value(int(cake["scale_bar"]))
            hist = cake.get("hist", {})
            if hasattr(self.widget, "cake_hist_widget") and hist != {}:
                self.widget.cake_hist_widget.check_log.setChecked(bool(hist.get("log_y", True)))
                self.widget.cake_hist_widget.check_focus.setChecked(bool(hist.get("focus_range", True)))
                self.widget.cake_hist_widget.spin_low_pct.setValue(float(hist.get("low_pct", 40.0)))
                self.widget.cake_hist_widget.spin_high_pct.setValue(float(hist.get("high_pct", 99.95)))

        if self._should_carry_nav_category("background", "checkBox_CarryNavBackground"):
            bg = snap["background"]
            self.widget.doubleSpinBox_Background_ROI_min.setValue(float(bg["roi_min"]))
            self.widget.doubleSpinBox_Background_ROI_max.setValue(float(bg["roi_max"]))
            self.widget.spinBox_BGParam0.setValue(int(bg["n_points"]))
            self.widget.spinBox_BGParam1.setValue(int(bg["n_order"]))
            self.widget.spinBox_BGParam2.setValue(int(bg["n_iteration"]))
            if self.model.base_ptn_exist():
                self.update_bgsub()
            carried_any = True

        if self._should_carry_nav_category("waterfall_list", "checkBox_CarryNavWaterfall"):
            self.model.waterfall_ptn = copy.deepcopy(snap["waterfall_list"])
            self.waterfalltable_ctrl.update()
            carried_any = True

        if self._should_carry_nav_category("poni", "checkBox_CarryNavPONI"):
            self.model.poni = snap["poni"]
            self.widget.lineEdit_PONI.setText('' if snap["poni"] is None else str(snap["poni"]))
            carried_any = True

        if self._should_carry_nav_category("fits_information", "checkBox_CarryNavFits"):
            self.model.section_lst = copy.deepcopy(snap["fits_information"]["section_lst"])
            self.model.current_section = copy.deepcopy(snap["fits_information"]["current_section"])
            self.peakfit_table_ctrl.update_sections()
            self.peakfit_table_ctrl.update_peak_parameters()
            self.peakfit_table_ctrl.update_baseline_constraints()
            self.peakfit_table_ctrl.update_peak_constraints()
            carried_any = True

        if carried_any:
            self.session_ctrl.set_carryover_source_chi(snap.get("source_chi"))
        else:
            self.session_ctrl.set_carryover_source_chi(None)

        # Never carry over backup information across CHI navigation.
        # Always show backup info for the newly loaded file.
        self.session_ctrl.refresh_backup_table()

    def _get_cake_scale_bar_value(self):
        if hasattr(self.widget, "cake_hist_widget"):
            return int(self.widget.cake_hist_widget.combo_scale_mode.currentData())
        return int(self.widget.horizontalSlider_MaxScaleBars.value())

    def _set_cake_scale_bar_value(self, value):
        value = int(value)
        self.widget.horizontalSlider_MaxScaleBars.setValue(value)
        if hasattr(self.widget, "cake_hist_widget"):
            combo = self.widget.cake_hist_widget.combo_scale_mode
            idx = combo.findData(value)
            if idx >= 0 and combo.currentIndex() != idx:
                combo.setCurrentIndex(idx)

    def _sync_cake_scale_bar_from_combo(self):
        self.widget.horizontalSlider_MaxScaleBars.setValue(self._get_cake_scale_bar_value())

    def _sync_cake_scale_combo_from_slider(self):
        if not hasattr(self.widget, "cake_hist_widget"):
            return
        combo = self.widget.cake_hist_widget.combo_scale_mode
        value = int(self.widget.horizontalSlider_MaxScaleBars.value())
        idx = combo.findData(value)
        if idx >= 0 and combo.currentIndex() != idx:
            combo.setCurrentIndex(idx)

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
        if self._mouse_mode == 'navigate':
            if event.button == 3:
                self.plot_new_graph()
            return
        if self._mouse_mode == 'roi':
            if event.button == 3:
                if self._is_map_tab_active() and hasattr(self, "map_ctrl"):
                    self.map_ctrl._clear_roi()
                elif self._is_seq_tab_active() and hasattr(self, "seq_ctrl"):
                    self.seq_ctrl._clear_roi()
            return
        if hasattr(self, "map_ctrl") and (self.map_ctrl is not None):
            try:
                if self.map_ctrl.is_roi_selection_active():
                    return
            except Exception:
                pass
        if hasattr(self, "seq_ctrl") and (self.seq_ctrl is not None):
            try:
                if self.seq_ctrl.is_roi_selection_active():
                    return
            except Exception:
                pass
        if self._get_toolbar_mode() not in ('', None):
            return
        if (event.xdata is None) or (event.ydata is None):
            return
        # Peak add/remove must come from the main 1D pattern axes.
        if event.inaxes != self.widget.mpl.canvas.ax_pattern:
            return
        if (event.button != 1) and (event.button != 3):
            return
        if event.button == 1:
            mouse_button = 'left'
        elif event.button == 3:
            mouse_button = 'right'
        if self._mouse_mode == 'peakpick':
            if not self._fits_tab_active():
                self._set_mouse_mode('navigate')
                return
            if not self.model.current_section_exist():
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "Set section first.")
                return
            if self.model.current_section.fitted():
                self.model.current_section.invalidate_fit_result()
            self.pick_peak(mouse_button, event.xdata, event.ydata)
        elif self._mouse_mode == 'jcpds':
            self.read_plot(mouse_button, event.xdata, event.ydata)
            if mouse_button == 'left':
                self._finish_temporary_mouse_mode('jcpds')

    def pick_peak(self, mouse_button, xdata, ydata):
        """
        """
        if mouse_button == 'left':  # left click
            if (self.model.current_section is None) or \
                    (self.model.current_section.x is None) or \
                    (len(self.model.current_section.x) == 0):
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning", "Set section first.")
                return
            # Robust against tiny range mismatches: map click to nearest x
            # sample in the current section and use that as initial center.
            x_arr = np.asarray(self.model.current_section.x, dtype=float)
            idx = int(np.abs(x_arr - float(xdata)).argmin())
            x_center = float(x_arr[idx])
            success = self.model.current_section.set_single_peak(
                x_center,
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
        if self._plot_update_deferred():
            return
        self.plot_ctrl.update()

    def update_bgsub(self):
        '''
        this is only to read the current inputs and replot
        '''
        if not self.model.base_ptn_exist():
            QtWidgets.QMessageBox.warning(self.widget, "Warning",
                                          "Load a base pattern first.")
            return
        x_raw_base = getattr(self.model.base_ptn, "x_raw", None)
        y_raw_base = getattr(self.model.base_ptn, "y_raw", None)
        if (x_raw_base is None) or (y_raw_base is None) or \
                (len(x_raw_base) == 0) or (len(y_raw_base) == 0):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "Base pattern has no raw data for background fitting.")
            return
        """receive new bg parameters and update the graph"""
        bg_params = [self.widget.spinBox_BGParam0.value(),
                     self.widget.spinBox_BGParam1.value(),
                     self.widget.spinBox_BGParam2.value()]
        bg_roi = [self.widget.doubleSpinBox_Background_ROI_min.value(),
                  self.widget.doubleSpinBox_Background_ROI_max.value()]
        if (bg_roi[0] <= x_raw_base.min()):
            bg_roi[0] = x_raw_base.min()
            self.widget.doubleSpinBox_Background_ROI_min.setValue(bg_roi[0])
        if (bg_roi[1] >= x_raw_base.max()):
            bg_roi[1] = x_raw_base.max()
            self.widget.doubleSpinBox_Background_ROI_max.setValue(bg_roi[1])
        self.model.base_ptn.subtract_bg(bg_roi, bg_params, yshift=0)
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        self.model.base_ptn.write_temporary_bgfiles(temp_dir=temp_dir)
        if self.model.waterfall_exist():
            print(str(datetime.datetime.now())[:-7], 
                ": BGfit and BGsub for waterfall patterns even if they are displayed.\n",
                "Yes this is a bit of waste.  Future fix needed.")
            n_skipped = 0
            for pattern in self.model.waterfall_ptn:
                x_raw = getattr(pattern, "x_raw", None)
                y_raw = getattr(pattern, "y_raw", None)
                if (x_raw is None) or (y_raw is None) or \
                        (len(x_raw) == 0) or (len(y_raw) == 0):
                    n_skipped += 1
                    continue
                pattern.subtract_bg(bg_roi, bg_params, yshift=0)
            if n_skipped > 0:
                print(str(datetime.datetime.now())[:-7],
                    ": Skipped BG subtraction for {0:d} waterfall item(s) "
                    "without raw data.".format(n_skipped))
        if self._plot_update_deferred():
            return
        self.plot_new_graph()

    def reset_bg_params_to_default(self):
        self.widget.spinBox_BGParam0.setValue(20)
        self.widget.spinBox_BGParam1.setValue(10)
        self.widget.spinBox_BGParam2.setValue(20)

    def apply_pt_to_graph(self):
        """
        if self.model.jcpds_exist():
            self.plot_ctrl.update_jcpds_only()
        else:
        """
        if self._plot_update_deferred():
            return
        self.plot_ctrl.update()

    def _plot_update_deferred(self):
        return self._defer_plot_update_count > 0

    @contextmanager
    def _defer_plot_updates(self):
        self._defer_plot_update_count += 1
        try:
            yield
        finally:
            self._defer_plot_update_count -= 1

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
        use_dpp_nav = bool(
            hasattr(self.widget, "checkBox_NavDPP") and
            self.widget.checkBox_NavDPP.isChecked())
        if use_dpp_nav:
            self._goto_dpp_next_file(move)
        else:
            self._goto_chi_next_file(move)
        return

    def _goto_chi_next_file(self, move):
        nav_state = self._capture_nav_carry_state()
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
            with self._defer_plot_updates():
                self.base_ptn_ctrl._load_a_new_pattern(new_filename_chi)
                self._apply_nav_carry_state(nav_state)
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

        auto_save_move = True
        if hasattr(self.widget, "checkBox_SaveDPPMove"):
            auto_save_move = bool(self.widget.checkBox_SaveDPPMove.isChecked())
        if auto_save_move:
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
            auto_gen_dpp = False
            if hasattr(self.widget, "checkBox_AutoGenDPP"):
                auto_gen_dpp = bool(self.widget.checkBox_AutoGenDPP.isChecked())
            if auto_gen_dpp:
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
            auto_gen_dpp = False
            if hasattr(self.widget, "checkBox_AutoGenDPP"):
                auto_gen_dpp = bool(self.widget.checkBox_AutoGenDPP.isChecked())
            auto_gen_only_missing = True
            if hasattr(self.widget, "checkBox_AutogenMissing"):
                auto_gen_only_missing = bool(self.widget.checkBox_AutogenMissing.isChecked())
            if auto_gen_dpp and (not auto_gen_only_missing):
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
