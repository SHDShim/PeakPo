import os
import time
import datetime
import numpy as np
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from ds_jcpds import convert_tth


class MplController(object):

    def __init__(self, model, widget):

        self.model = model
        self.widget = widget

    def _set_nightday_view(self):
        if not self.widget.checkBox_NightView.isChecked():
            self.widget.mpl.canvas.set_toNight(False)
            # reset plot objects with white
            if self.model.base_ptn_exist():
                self.model.base_ptn.color = 'k'
            if self.model.waterfall_exist():
                for pattern in self.model.waterfall_ptn:
                    if (pattern.color == 'white') or \
                            (pattern.color == '#ffffff'):
                        pattern.color = 'k'
            self.obj_color = 'k'
        else:
            self.widget.mpl.canvas.set_toNight(True)
            if self.model.base_ptn_exist():
                self.model.base_ptn.color = 'white'
            if self.model.waterfall_exist():
                for pattern in self.model.waterfall_ptn:
                    if (pattern.color == 'k') or (pattern.color == '#000000'):
                        pattern.color = 'white'
            self.obj_color = 'white'

    def get_cake_range(self):
        if self.widget.pushButton_AddRemoveCake.isChecked():
            return self.widget.mpl.canvas.ax_cake.get_xlim(),\
                self.widget.mpl.canvas.ax_cake.get_ylim()
        else:
            return None, None

    def zoom_out_graph(self):
        if not self.model.base_ptn_exist():
            return
        if self.widget.ntb_Bgsub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
        else:
            x, y = self.model.base_ptn.get_raw()
        self.update(limits=[x.min(), x.max(), y.min(), y.max()])

    def update(self, limits=None):
        """Updates the graph"""
        t_start = time.time()
        self.widget.setCursor(QtCore.Qt.WaitCursor)
        if limits is None:
            limits = self.widget.mpl.canvas.ax_pattern.axis()
        if (not self.model.base_ptn_exist()) and \
                (not self.model.jcpds_exist()):
            return
        if self.widget.pushButton_AddRemoveCake.isChecked():
            self.widget.mpl.canvas.resize_axes(
                self.widget.spinBox_CakeAxisSize.value())
            self._plot_cake()
        else:
            self.widget.mpl.canvas.resize_axes(1)
        self._set_nightday_view()
        if self.model.base_ptn_exist():
            self.widget.mpl.canvas.fig.suptitle(
                self.model.base_ptn.fname, color=self.obj_color, fontsize=16)
            self._plot_diffpattern()
            if self.model.waterfall_exist():
                self._plot_waterfallpatterns()
        if self.model.jcpds_exist():
            self._plot_jcpds()
        if self.model.ucfit_exist():
            self._plot_ucfit()
        if (self.widget.tabWidget.currentIndex() == 8):
            self._plot_peakfit()
        self.widget.mpl.canvas.ax_pattern.set_xlim(limits[0], limits[1])
        if not self.widget.ntb_ResetY.isChecked():
            self.widget.mpl.canvas.ax_pattern.set_ylim(limits[2], limits[3])
        xlabel = 'Two Theta (degrees), ' + \
            "{0: 5.1f} GPa, {1: 4.0f} K, {2: 6.4f} A".\
            format(self.widget.doubleSpinBox_Pressure.value(),
                   self.widget.doubleSpinBox_Temperature.value(),
                   self.widget.doubleSpinBox_SetWavelength.value())
        self.widget.mpl.canvas.ax_pattern.set_xlabel(xlabel)
        # if I move the line below to elsewhere I cannot get ylim or axis
        # self.widget.mpl.canvas.ax_pattern.autoscale(
        # enable=False, axis=u'both', tight=True)
        """Removing the lines below for the tick reduce the plot time
        significantly.  So do not turn this on.
        x_size = limits[1] - limits[0]
        if x_size <= 50.:
            majortick_interval = 1
            minortick_interval = 0.1
        else:
            majortick_interval = 10
            minortick_interval = 1
        majorLocator = MultipleLocator(majortick_interval)
        minorLocator = MultipleLocator(minortick_interval)
        self.widget.mpl.canvas.ax_pattern.xaxis.set_major_locator(majorLocator)
        self.widget.mpl.canvas.ax_pattern.xaxis.set_minor_locator(minorLocator)
        """
        self.widget.mpl.canvas.draw()
        print("Plot takes {0:.2f}s at".format(time.time() - t_start),
              str(datetime.datetime.now())[:-7])
        self.widget.unsetCursor()

    def _plot_ucfit(self):
        i = 0
        for j in self.model.ucfit_lst:
            if j.display:
                i += 1
        if i == 0:
            return
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        bar_scale = 1. / 100. * axisrange[3]
        i = 0
        for phase in self.model.ucfit_lst:
            if phase.display:
                phase.cal_dsp()
                tth, inten = phase.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                bar_min = np.ones(tth.shape) * axisrange[2]
                intensity = inten
                bar_min = np.ones(tth.shape) * axisrange[2]
                self.widget.tableWidget_UnitCell.removeCellWidget(i, 3)
                Item4 = QtWidgets.QTableWidgetItem(
                    "{:.3f}".format(float(phase.v)))
                Item4.setFlags(
                    QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                self.widget.tableWidget_UnitCell.setItem(i, 3, Item4)
                if self.widget.checkBox_Intensity.isChecked():
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, intensity * bar_scale,
                        colors=phase.color)
                else:
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, 100. * bar_scale, colors=phase.color)
            i += 1

    def _plot_cake(self):
        climits = (self.widget.spinBox_VMin.value(),
                   self.widget.spinBox_VMax.value())
        intensity_cake, tth_cake, chi_cake = self.model.diff_img.get_cake()
        self.widget.mpl.canvas.ax_cake.imshow(
            intensity_cake, origin="lower",
            extent=[tth_cake.min(), tth_cake.max(),
                    chi_cake.min(), chi_cake.max()],
            aspect="auto", cmap="gray_r", clim=climits)

    def _plot_jcpds(self):
        i = 0
        for phase in self.model.jcpds_lst:
            if phase.display:
                i += 1
        if i == 0:
            return
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        bar_scale = 1. / 100. * axisrange[3]
        for phase in self.model.jcpds_lst:
            if phase.display:
                phase.cal_dsp(self.widget.doubleSpinBox_Pressure.value(),
                              self.widget.doubleSpinBox_Temperature.value())
                tth, inten = phase.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                intensity = inten * phase.twk_int
                bar_min = np.ones(tth.shape) * axisrange[2]
                """
                if self.widget.tabWidget.currentIndex() == 8:
                    bar_min = 90. * bar_scale
                    bar_max = 100. * bar_scale
                    self.widget.mpl.canvas.ax_pattern.set_ylim(
                        axisrange[2], axisrange[3])
                """
                if self.widget.checkBox_Intensity.isChecked():
                    bar_max = intensity * bar_scale
                else:
                    bar_max = 100. * bar_scale
                self.widget.mpl.canvas.ax_pattern.vlines(
                    tth, bar_min, bar_max, colors=phase.color,
                    label="{0:}, {1:.3f} A^3".format(
                        phase.name, phase.v.item()))
                if self.widget.pushButton_AddRemoveCake.isChecked():
                    for tth_i in tth:
                        self.widget.mpl.canvas.ax_cake.axvline(
                            x=tth_i, color=phase.color, lw=0.5)
            else:
                pass
        leg_jcpds = self.widget.mpl.canvas.ax_pattern.legend(
            loc=1, prop={'size': 10}, framealpha=0., handlelength=1)
        for line, txt in zip(leg_jcpds.get_lines(), leg_jcpds.get_texts()):
            txt.set_color(line.get_color())

    def _plot_waterfallpatterns(self):
        # t_start = time.time()
        # count how many are dispaly
        i = 0
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                i += 1
        if i == 0:
            return
        n_display = i
        j = 0  # this is needed for waterfall gaps
        # get y_max
        for pattern in self.model.waterfall_ptn:
            if pattern.display:
                j += 1
                self.widget.mpl.canvas.ax_pattern.text(
                    0.01, 0.97 - n_display * 0.05 + j * 0.05,
                    os.path.basename(pattern.fname),
                    transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                    color=pattern.color)
                if self.widget.ntb_Bgsub.isChecked():
                    ygap = self.widget.doubleSpinBox_WaterfallGaps.value() * \
                        self.model.base_ptn.y_bgsub.max() * float(j)
                    y_bgsub = pattern.y_bgsub
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = y_bgsub / y_bgsub.max() * \
                            self.model.base_ptn.y_bgsub.max()
                    else:
                        y = y_bgsub
                    x_t = pattern.x_bgsub
                else:
                    ygap = self.widget.doubleSpinBox_WaterfallGaps.value() * \
                        self.model.base_ptn.y_raw.max() * float(j)
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = pattern.y_raw / pattern.y_raw.max() *\
                            self.model.base_ptn.y_raw.max()
                    else:
                        y = pattern.y_raw
                    x_t = pattern.x_raw
                if self.widget.checkBox_SetToBasePtnLambda.isChecked():
                    x = convert_tth(x_t, pattern.wavelength,
                                    self.model.base_ptn.wavelength)
                else:
                    x = x_t
                self.widget.mpl.canvas.ax_pattern.plot(
                    x, y + ygap, c=pattern.color)
        self.widget.mpl.canvas.ax_pattern.text(
            0.01, 0.97 - n_display * 0.05,
            os.path.basename(self.model.base_ptn.fname),
            transform=self.widget.mpl.canvas.ax_pattern.transAxes,
            color=self.model.base_ptn.color)

    def _plot_diffpattern(self):
        if self.widget.ntb_Bgsub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
            self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=self.model.base_ptn.color)
        else:
            x, y = self.model.base_ptn.get_raw()
            self.widget.mpl.canvas.ax_pattern.plot(
                x, y, c=self.model.base_ptn.color)
            x_bg, y_bg = self.model.base_ptn.get_background()
            self.widget.mpl.canvas.ax_pattern.plot(
                x_bg, y_bg, c=self.model.base_ptn.color, ls='--', lw=0.5)

    def _plot_peakfit(self):
        if not self.model.current_section_exist():
            return
        if self.model.current_section.peaks_exist():
            for x_c in self.model.current_section.get_peak_positions():
                self.widget.mpl.canvas.ax_pattern.axvline(x_c, ls='--')
        if self.model.current_section.fitted():
            bgsub = self.widget.ntb_Bgsub.isChecked()
            x_plot = self.model.current_section.x
            profiles = self.model.current_section.get_individual_profiles(
                bgsub=bgsub)
            for key, value in profiles.items():
                self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, value, 'y--', lw=0.5)
            total_profile = self.model.current_section.get_fit_profile(
                bgsub=bgsub)
            residue = self.model.current_section.get_fit_residue(bgsub=bgsub)
            self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, total_profile, 'y-', lw=0.5)
            self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, residue, 'r-', lw=0.5)
            self.widget.mpl.canvas.ax_pattern.axhline(
                self.model.current_section.get_fit_residue_baseline(
                    bgsub=bgsub), c='r', ls='--', lw=0.5)
        else:
            pass
