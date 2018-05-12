"""
2018/03/07 Attempt was made to speed up, but failed.  This is the attempt.
"""
import os
import time
import datetime
import numpy as np
import numpy.ma as ma
from matplotlib.widgets import MultiCursor
import matplotlib.transforms as transforms
# import matplotlib.colors as colors
import matplotlib.patches as patches
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from ds_jcpds import convert_tth


class MplController(object):

    def __init__(self, model, widget):

        self.model = model
        self.widget = widget
        self.obj_color = 'k'
        self.jbars = []
        self.jbars_cake = []
        self.hkl_ptn = []
        self.hkl_cake = []

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
        if self.widget.checkBox_ShowCake.isChecked():
            return self.widget.mpl.canvas.ax_cake.get_xlim(),\
                self.widget.mpl.canvas.ax_cake.get_ylim()
        else:
            return None, None

    def _read_azilist(self):
        n_row = self.widget.tableWidget_DiffImgAzi.rowCount()
        if n_row == 0:
            return None, None, None
        azi_list = []
        tth_list = []
        note_list = []
        for i in range(n_row):
            azi_min = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 2).text())
            azi_max = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 4).text())
            tth_min = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 1).text())
            tth_max = float(
                self.widget.tableWidget_DiffImgAzi.item(i, 3).text())
            note_i = self.widget.tableWidget_DiffImgAzi.item(i, 0).text()
            tth_list.append([tth_min, tth_max])
            azi_list.append([azi_min, azi_max])
            note_list.append(note_i)
        return tth_list, azi_list, note_list

    def zoom_out_graph(self):
        if not self.model.base_ptn_exist():
            return
        data_limits = self._get_data_limits()
        self.update(limits=data_limits,
                    cake_ylimits=(-180, 180))

    def update_to_gsas_style(self):
        if not self.model.base_ptn_exist():
            return
        data_limits = self._get_data_limits(y_margin=0.10)
        self.update(limits=data_limits, gsas_style=True)

    def _get_data_limits(self, y_margin=0.):
        if self.widget.checkBox_BgSub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
        else:
            x, y = self.model.base_ptn.get_raw()
        return (x.min(), x.max(),
                y.min() - (y.max() - y.min()) * y_margin,
                y.max() + (y.max() - y.min()) * y_margin)

    def update(self, limits=None, gsas_style=False, cake_ylimits=None):
        """Updates the graph"""
        t_start = time.time()
        self.widget.setCursor(QtCore.Qt.WaitCursor)
        if limits is None:
            limits = self.widget.mpl.canvas.ax_pattern.axis()
        if cake_ylimits is None:
            c_limits = self.widget.mpl.canvas.ax_cake.axis()
            cake_ylimits = c_limits[2:4]
        if (not self.model.base_ptn_exist()) and \
                (not self.model.jcpds_exist()):
            return
        if self.widget.checkBox_ShowCake.isChecked() and \
                self.model.diff_img_exist():
            self.widget.mpl.canvas.resize_axes(
                self.widget.horizontalSlider_CakeAxisSize.value())
            self._plot_cake()
        else:
            self.widget.mpl.canvas.resize_axes(1)
        self._set_nightday_view()
        if self.model.base_ptn_exist():
            if self.widget.checkBox_ShortPlotTitle.isChecked():
                title = os.path.basename(self.model.base_ptn.fname)
            else:
                title = self.model.base_ptn.fname
            self.widget.mpl.canvas.fig.suptitle(
                title, color=self.obj_color)
            self._plot_diffpattern(gsas_style)
            if self.model.waterfall_exist():
                self._plot_waterfallpatterns()
        # if self.model.jcpds_exist():
        #    self._plot_jcpds(limits)
        if self.model.ucfit_exist():
            self._plot_ucfit()
        if (self.widget.tabWidget.currentIndex() == 8):
            if gsas_style:
                self._plot_peakfit_in_gsas_style()
            else:
                self._plot_peakfit()
        self.widget.mpl.canvas.ax_pattern.set_xlim(limits[0], limits[1])
        if not self.widget.checkBox_AutoY.isChecked():
            self.widget.mpl.canvas.ax_pattern.set_ylim(limits[2], limits[3])
        self.widget.mpl.canvas.ax_cake.set_ylim(cake_ylimits)
        if self.model.jcpds_exist():
            self._plot_jcpds(limits)
            if not self.widget.checkBox_Intensity.isChecked():
                new_low_limit = -1.1 * limits[3] * \
                    self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
                self.widget.mpl.canvas.ax_pattern.set_ylim(
                    new_low_limit, limits[3])
        """
        if self.widget.checkBox_ShowLargePnT.isChecked():
            xlabel = "Two Theta (degrees), {: 6.4f} A".\
                format(self.widget.doubleSpinBox_SetWavelength.value())
            label_p_t = "{0: 5.1f} GPa\n{1: 4.0f} K".\
                format(self.widget.doubleSpinBox_Pressure.value(),
                       self.widget.doubleSpinBox_Temperature.value())
            self.widget.mpl.canvas.ax_pattern.text(
                0.01, 0.98, label_p_t, horizontalalignment='left',
                verticalalignment='top',
                transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                fontsize=int(
                    self.widget.comboBox_PnTFontSize.currentText()))
        else:
            xlabel = 'Two Theta (degrees), ' + \
                "{0: 5.1f} GPa, {1: 4.0f} K, {2: 6.4f} A".\
                format(self.widget.doubleSpinBox_Pressure.value(),
                       self.widget.doubleSpinBox_Temperature.value(),
                       self.widget.doubleSpinBox_SetWavelength.value())
        """
        xlabel = "Two Theta (degrees), {: 6.4f} A".\
            format(self.widget.doubleSpinBox_SetWavelength.value())
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
        self.widget.mpl.canvas.ax_pattern.format_coord = lambda x, y: \
            "{0:.2f},{1:.2e},dsp={2:.3f}".\
            format(x, y, self.widget.doubleSpinBox_SetWavelength.value() / 2. /
                   np.sin(np.radians(x / 2.)))
        self.widget.mpl.canvas.ax_cake.format_coord = lambda x, y: \
            "{0:.2f},{1:.2e},dsp={2:.3f}".\
            format(x, y, self.widget.doubleSpinBox_SetWavelength.value() / 2. /
                   np.sin(np.deg2rad(x / 2.)))
        self.widget.mpl.canvas.draw()
        print("Plot takes {0:.2f}s at".format(time.time() - t_start),
              str(datetime.datetime.now())[:-7])
        self.widget.unsetCursor()
        if self.widget.checkBox_LongCursor.isChecked():
            self.widget.cursor = MultiCursor(
                self.widget.mpl.canvas,
                (self.widget.mpl.canvas.ax_pattern,
                 self.widget.mpl.canvas.ax_cake), color='r',
                lw=float(
                    self.widget.comboBox_VertCursorThickness.
                    currentText()),
                ls='--', useblit=False)  # useblit not supported for pyqt5 yet
            """
            self.widget.cursor_pattern = Cursor(
                self.widget.mpl.canvas.ax_pattern, useblit=False,
                lw = 1, ls=':')
            self.widget.cursor_cake = Cursor(
                self.widget.mpl.canvas.ax_cake, useblit=False, c= 'r',
                lw = 1, ls=':')
            """

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
                        colors=phase.color,
                        lw=float(
                            self.widget.comboBox_PtnJCPDSBarThickness.
                            currentText()))
                else:
                    self.widget.mpl.canvas.ax_pattern.vlines(
                        tth, bar_min, 100. * bar_scale,
                        colors=phase.color,
                        lw=float(
                            self.widget.comboBox_PtnJCPDSBarThickness.
                            currentText()))
            i += 1

    def _plot_cake(self):
        intensity_cake, tth_cake, chi_cake = self.model.diff_img.get_cake()
        min_slider_pos = self.widget.horizontalSlider_VMin.value()
        max_slider_pos = self.widget.horizontalSlider_VMax.value()
        if (max_slider_pos <= min_slider_pos):
            self.widget.horizontalSlider_VMin.setValue(1)
            self.widget.horizontalSlider_VMax.setValue(99)
        intensity_cake_plot = ma.masked_values(intensity_cake, 0.)
        prefactor = \
            self.widget.spinBox_MaxCakeScale.value() / \
            (10. ** self.widget.horizontalSlider_MaxScaleBars.value())
        # intensity_cake_plot.max() / \
        climits = np.asarray([
            self.widget.horizontalSlider_VMin.value(),
            self.widget.horizontalSlider_VMax.value()]) / \
            1000. * prefactor
        if self.widget.checkBox_WhiteForPeak.isChecked():
            cmap = 'gray'
        else:
            cmap = 'gray_r'
        mid_angle = self.widget.spinBox_AziShift.value()
        if mid_angle != 0:
            int_new = np.array(intensity_cake_plot)
            int_new[0:mid_angle] = intensity_cake[360 - mid_angle:361]
            int_new[mid_angle:361] = intensity_cake[0:360 - mid_angle]
        else:
            int_new = np.array(intensity_cake_plot)
        self.widget.mpl.canvas.ax_cake.imshow(
            int_new, origin="lower",
            extent=[tth_cake.min(), tth_cake.max(),
                    chi_cake.min(), chi_cake.max()],
            aspect="auto", cmap=cmap, clim=climits)  # gray_r
        tth_list, azi_list, note_list = self._read_azilist()
        tth_min = tth_cake.min()
        tth_max = tth_cake.max()
        if azi_list is not None:
            for tth, azi, note in zip(tth_list, azi_list, note_list):
                rect = patches.Rectangle(
                    (tth_min, azi[0]), (tth_max - tth_min), (azi[1] - azi[0]),
                    linewidth=0, edgecolor='b', facecolor='b', alpha=0.2)
                rect1 = patches.Rectangle(
                    (tth[0], azi[0]), (tth[1] - tth[0]), (azi[1] - azi[0]),
                    linewidth=1, edgecolor='b', facecolor='None')
                self.widget.mpl.canvas.ax_cake.add_patch(rect)
                self.widget.mpl.canvas.ax_cake.add_patch(rect1)
                if self.widget.checkBox_ShowCakeLabels.isChecked():
                    self.widget.mpl.canvas.ax_cake.text(
                        tth[1], azi[1], note, color=self.obj_color)
        rows = self.widget.tableWidget_DiffImgAzi.selectionModel().\
            selectedRows()
        if rows != []:
            for r in rows:
                azi_min = float(
                    self.widget.tableWidget_DiffImgAzi.item(r.row(), 2).text())
                azi_max = float(
                    self.widget.tableWidget_DiffImgAzi.item(r.row(), 4).text())
                rect = patches.Rectangle(
                    (tth_min, azi_min), (tth_max - tth_min),
                    (azi_max - azi_min),
                    linewidth=0, facecolor='r', alpha=0.2)
                self.widget.mpl.canvas.ax_cake.add_patch(rect)

    def _plot_jcpds_old(self, axisrange):
        # t_start = time.time()
        if (not self.widget.checkBox_JCPDSinPattern.isChecked()) and \
                (not self.widget.checkBox_JCPDSinCake.isChecked()):
            return
        i = 0
        for phase in self.model.jcpds_lst:
            if phase.display:
                i += 1
        if i == 0:
            return
        else:
            n_displayed_jcpds = i
        # axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        bar_scale = 1. / 100. * axisrange[3] * \
            self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
        i = 0
        for phase in self.model.jcpds_lst:
            if phase.display:
                phase.cal_dsp(self.widget.doubleSpinBox_Pressure.value(),
                              self.widget.doubleSpinBox_Temperature.value())
                tth, inten = phase.get_tthVSint(
                    self.widget.doubleSpinBox_SetWavelength.value())
                """
                if self.widget.tabWidget.currentIndex() == 8:
                    bar_min = 90. * bar_scale
                    bar_max = 100. * bar_scale
                    self.widget.mpl.canvas.ax_pattern.set_ylim(
                        axisrange[2], axisrange[3])
                """
                if self.widget.checkBox_JCPDSinPattern.isChecked():
                    intensity = inten * phase.twk_int
                    if self.widget.checkBox_Intensity.isChecked():
                        bar_min = np.ones(tth.shape) * axisrange[2] + \
                            self.widget.horizontalSlider_JCPDSBarPosition.\
                            value() / 100. * axisrange[3]
                        bar_max = intensity * bar_scale + bar_min
                    else:
                        data_limits = self._get_data_limits()
                        starting_intensity = np.ones(tth.shape) * data_limits[2] + \
                            self.widget.horizontalSlider_JCPDSBarPosition.\
                            value() / 100. * axisrange[3]
                        bar_max = starting_intensity - \
                            i * 100. * bar_scale / n_displayed_jcpds
                        i += 1
                        bar_min = starting_intensity - \
                            i * 100. * bar_scale / n_displayed_jcpds
                    pressure = self.widget.doubleSpinBox_Pressure.value()
                    if pressure == 0.:
                        self.widget.mpl.canvas.ax_pattern.vlines(
                            tth, bar_min, bar_max, colors=phase.color,
                            label="{0:}, {1:.3f} A^3".format(
                                phase.name, phase.v),
                            lw=float(
                                self.widget.comboBox_PtnJCPDSBarThickness.
                                currentText()))
                    else:
                        self.widget.mpl.canvas.ax_pattern.vlines(
                            tth, bar_min, bar_max, colors=phase.color,
                            label="{0:}, {1:.3f} A^3".format(
                                phase.name, phase.v.item()),
                            lw=float(
                                self.widget.comboBox_PtnJCPDSBarThickness.
                                currentText()))
                    # hkl
                    if self.widget.checkBox_ShowMillerIndices.isChecked():
                        hkl_list = phase.get_hkl_in_text()
                        j = 0
                        for hkl in hkl_list:
                            self.widget.mpl.canvas.ax_pattern.text(
                                tth[j], bar_max[j], hkl, color=phase.color,
                                rotation=90, verticalalignment='bottom',
                                horizontalalignment='center',
                                fontsize=int(
                                    self.widget.comboBox_HKLFontSize.currentText()))
                            j += 1
                    # phase.name, phase.v.item()))
                if self.widget.checkBox_ShowCake.isChecked() and \
                        self.widget.checkBox_JCPDSinCake.isChecked():
                    """
                    for tth_i in tth:
                        self.widget.mpl.canvas.ax_cake.axvline(
                            x=tth_i, color=phase.color,
                            lw=float(
                                self.widget.comboBox_CakeJCPDSBarThickness.
                                currentText()))
                    """
                    axvlines(self.widget.mpl.canvas.ax_cake, tth,
                             color=phase.color,
                             lw=float(
                                 self.widget.comboBox_CakeJCPDSBarThickness.
                                 currentText()))
                    if self.widget.checkBox_ShowMillerIndices_Cake.isChecked():
                        hkl_list = phase.get_hkl_in_text()
                        trans = transforms.blended_transform_factory(
                            self.widget.mpl.canvas.ax_cake.transData,
                            self.widget.mpl.canvas.ax_cake.transAxes)
                        j = 0
                        for hkl in hkl_list:
                            self.widget.mpl.canvas.ax_cake.text(
                                tth[j], 0.99, hkl, color=phase.color,
                                rotation=90, verticalalignment='top',
                                transform=trans, horizontalalignment='right',
                                fontsize=int(
                                    self.widget.comboBox_HKLFontSize.currentText()))
                            j += 1
            else:
                pass
        if self.widget.checkBox_JCPDSinPattern.isChecked():
            leg_jcpds = self.widget.mpl.canvas.ax_pattern.legend(
                loc=1, prop={'size': 10}, framealpha=0., handlelength=1)
            for line, txt in zip(leg_jcpds.get_lines(), leg_jcpds.get_texts()):
                txt.set_color(line.get_color())
        # print("JCPDS update takes {0:.2f}s at".format(time.time() - t_start),
        #      str(datetime.datetime.now())[:-7])

    def _plot_waterfallpatterns(self):
        if not self.widget.checkBox_ShowWaterfall.isChecked():
            return
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
        for pattern in self.model.waterfall_ptn[::-1]:
            if pattern.display:
                j += 1
                """
                self.widget.mpl.canvas.ax_pattern.text(
                    0.01, 0.97 - n_display * 0.05 + j * 0.05,
                    os.path.basename(pattern.fname),
                    transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                    color=pattern.color)
                """
                if self.widget.checkBox_BgSub.isChecked():
                    ygap = self.widget.horizontalSlider_WaterfallGaps.value() * \
                        self.model.base_ptn.y_bgsub.max() * float(j) / 100.
                    y_bgsub = pattern.y_bgsub
                    if self.widget.checkBox_IntNorm.isChecked():
                        y = y_bgsub / y_bgsub.max() * \
                            self.model.base_ptn.y_bgsub.max()
                    else:
                        y = y_bgsub
                    x_t = pattern.x_bgsub
                else:
                    ygap = self.widget.horizontalSlider_WaterfallGaps.value() * \
                        self.model.base_ptn.y_raw.max() * float(j) / 100.
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
                    x, y + ygap, c=pattern.color, lw=float(
                        self.widget.comboBox_WaterfallLineThickness.
                        currentText()))
                if self.widget.checkBox_ShowWaterfallLabels.isChecked():
                    self.widget.mpl.canvas.ax_pattern.text(
                        (x[-1] - x[0]) * 0.01 + x[0], y[0] + ygap,
                        os.path.basename(pattern.fname),
                        verticalalignment='bottom', horizontalalignment='left',
                        color=pattern.color)
        """
        self.widget.mpl.canvas.ax_pattern.text(
            0.01, 0.97 - n_display * 0.05,
            os.path.basename(self.model.base_ptn.fname),
            transform=self.widget.mpl.canvas.ax_pattern.transAxes,
            color=self.model.base_ptn.color)
        """

    def _plot_diffpattern(self, gsas_style=False):
        if self.widget.checkBox_BgSub.isChecked():
            x, y = self.model.base_ptn.get_bgsub()
            if gsas_style:
                self.widget.mpl.canvas.ax_pattern.plot(
                    x, y, c=self.model.base_ptn.color, marker='o',
                    linestyle='None', ms=3)
            else:
                self.widget.mpl.canvas.ax_pattern.plot(
                    x, y, c=self.model.base_ptn.color,
                    lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))
        else:
            x, y = self.model.base_ptn.get_raw()
            if gsas_style:
                self.widget.mpl.canvas.ax_pattern.plot(
                    x, y, c=self.model.base_ptn.color, marker='o',
                    linestyle='None', ms=3)
            else:
                self.widget.mpl.canvas.ax_pattern.plot(
                    x, y, c=self.model.base_ptn.color,
                    lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))
            x_bg, y_bg = self.model.base_ptn.get_background()
            self.widget.mpl.canvas.ax_pattern.plot(
                x_bg, y_bg, c=self.model.base_ptn.color, ls='--',
                lw=float(
                    self.widget.comboBox_BkgnLineThickness.
                    currentText()))

    def _plot_peakfit(self):
        if not self.model.current_section_exist():
            return
        if self.model.current_section.peaks_exist():
            for x_c in self.model.current_section.get_peak_positions():
                self.widget.mpl.canvas.ax_pattern.axvline(
                    x_c, ls='--', dashes=(10, 5))
        if self.model.current_section.fitted():
            bgsub = self.widget.checkBox_BgSub.isChecked()
            x_plot = self.model.current_section.x
            profiles = self.model.current_section.get_individual_profiles(
                bgsub=bgsub)
            for key, value in profiles.items():
                self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, value, ls='-', c=self.obj_color, lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))
            total_profile = self.model.current_section.get_fit_profile(
                bgsub=bgsub)
            residue = self.model.current_section.get_fit_residue(bgsub=bgsub)
            self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, total_profile, 'r-', lw=float(
                    self.widget.comboBox_BasePtnLineThickness.
                    currentText()))
            y_range = self.model.current_section.get_yrange(bgsub=bgsub)
            y_shift = y_range[0] - (y_range[1] - y_range[0]) * 0.05
            #(y_range[1] - y_range[0]) * 1.05
            self.widget.mpl.canvas.ax_pattern.fill_between(
                x_plot, self.model.current_section.get_fit_residue_baseline(
                    bgsub=bgsub) + y_shift, residue + y_shift, facecolor='r')
            """
            self.widget.mpl.canvas.ax_pattern.plot(
                x_plot, residue + y_shift, 'r-')
            self.widget.mpl.canvas.ax_pattern.axhline(
                self.model.current_section.get_fit_residue_baseline(
                    bgsub=bgsub) + y_shift, c='r', ls='-', lw=0.5)
            """
        else:
            pass

    def _plot_peakfit_in_gsas_style(self):
        # get all the highlights
        # iteratively run plot
        rows = self.widget.tableWidget_PkFtSections.selectionModel().\
            selectedRows()
        if rows == []:
            return
        else:
            selected_rows = [r.row() for r in rows]
        bgsub = self.widget.checkBox_BgSub.isChecked()
        data_limits = self._get_data_limits()
        y_shift = data_limits[2] - (data_limits[3] - data_limits[2]) * 0.05
        i = 0
        for section in self.model.section_lst:
            if i in selected_rows:
                x_plot = section.x
                total_profile = section.get_fit_profile(bgsub=bgsub)
                residue = section.get_fit_residue(bgsub=bgsub)
                self.widget.mpl.canvas.ax_pattern.plot(
                    x_plot, total_profile, 'r-', lw=float(
                        self.widget.comboBox_BasePtnLineThickness.
                        currentText()))
                self.widget.mpl.canvas.ax_pattern.fill_between(
                    x_plot, section.get_fit_residue_baseline(bgsub=bgsub) +
                    y_shift, residue + y_shift, facecolor='r')
            i += 1

    def update_jcpds_only(self):
        t_start = time.time()
        axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        self._plot_jcpds(axisrange)
        print("JCPDS update takes {0:.2f}s at".format(time.time() - t_start),
              str(datetime.datetime.now())[:-7])

    def _plot_jcpds(self, axisrange):
        # t_start = time.time()
        if (not self.widget.checkBox_JCPDSinPattern.isChecked()) and \
                (not self.widget.checkBox_JCPDSinCake.isChecked()):
            return
        i = 0
        phases_display = []
        for phase in self.model.jcpds_lst:
            if phase.display:
                phases_display.append(phase)
                i += 1
        if i == 0:
            return
        else:
            n_displayed_jcpds = i
        #axisrange = self.widget.mpl.canvas.ax_pattern.axis()
        cakerange = self.widget.mpl.canvas.ax_cake.axis()
        # print(cakerange)
        bar_scale = 1. / 100. * axisrange[3] * \
            self.widget.horizontalSlider_JCPDSBarScale.value() / 100.
        pressure = self.widget.doubleSpinBox_Pressure.value()
        temperature = self.widget.doubleSpinBox_Temperature.value()
        wavelength = self.widget.doubleSpinBox_SetWavelength.value()
        bar_position = self.widget.horizontalSlider_JCPDSBarPosition.value()
        bar_thickness = float(self.widget.comboBox_PtnJCPDSBarThickness.
                              currentText())
        hkl_fontsize = int(self.widget.comboBox_HKLFontSize.currentText())
        hkl_fontsize_cake = int(self.widget.comboBox_HKLFontSize.currentText())
        bar_thickness_cake = float(self.widget.comboBox_CakeJCPDSBarThickness.
                                   currentText())
        i = 0
        jbars = []
        jbars_cake = []
        hkl_ptn = []
        hkl_cake = []
        for phase in phases_display:
            phase.cal_dsp(pressure, temperature)
            tth, inten = phase.get_tthVSint(wavelength)
            if self.widget.checkBox_JCPDSinPattern.isChecked():
                intensity = inten * phase.twk_int
                if self.widget.checkBox_Intensity.isChecked():
                    bar_min = np.ones(tth.shape) * axisrange[2] + \
                        bar_position / 100. * axisrange[3]
                    bar_max = intensity * bar_scale + bar_min
                else:
                    data_limits = self._get_data_limits()
                    starting_intensity = np.ones(tth.shape) * data_limits[2] + \
                        bar_position / 100. * axisrange[3]
                    bar_max = starting_intensity - \
                        i * 100. * bar_scale / n_displayed_jcpds
                    i += 1
                    bar_min = starting_intensity - \
                        i * 100. * bar_scale / n_displayed_jcpds
                if pressure == 0.:
                    volume = phase.v
                else:
                    volume = phase.v.item()
                j_ptn_bar = self.widget.mpl.canvas.ax_pattern.vlines(
                    tth, bar_min, bar_max, colors=phase.color,
                    label="{0:}, {1:.3f} A^3".format(
                        phase.name, volume),
                    lw=bar_thickness)
                jbars.append(j_ptn_bar)
                # hkl
                if self.widget.checkBox_ShowMillerIndices.isChecked():
                    hkl_list = phase.get_hkl_in_text()
                    for j, hkl in enumerate(hkl_list):
                        hkl_text_ptn = self.widget.mpl.canvas.ax_pattern.text(
                            tth[j], bar_max[j], hkl, color=phase.color,
                            rotation=90, verticalalignment='bottom',
                            horizontalalignment='center',
                            fontsize=hkl_fontsize)
                        hkl_ptn.append(hkl_text_ptn)
                # phase.name, phase.v.item()))
            if self.widget.checkBox_ShowCake.isChecked() and \
                    self.widget.checkBox_JCPDSinCake.isChecked():
                j_cake_bar = self.widget.mpl.canvas.ax_cake.vlines(
                    tth, np.ones_like(tth) * cakerange[2],
                    np.ones_like(tth) * cakerange[3], colors=phase.color,
                    lw=bar_thickness_cake)
                jbars_cake.append(j_cake_bar)
                if self.widget.checkBox_ShowMillerIndices_Cake.isChecked():
                    hkl_list = phase.get_hkl_in_text()
                    trans = transforms.blended_transform_factory(
                        self.widget.mpl.canvas.ax_cake.transData,
                        self.widget.mpl.canvas.ax_cake.transAxes)
                    for j, hkl in enumerate(hkl_list):
                        hkl_text_cake = self.widget.mpl.canvas.ax_cake.text(
                            tth[j], 0.99, hkl, color=phase.color,
                            rotation=90, verticalalignment='top',
                            transform=trans, horizontalalignment='right',
                            fontsize=hkl_fontsize_cake)
                        hkl_cake.append(hkl_text_cake)
        if self.widget.checkBox_JCPDSinPattern.isChecked():
            leg_jcpds = self.widget.mpl.canvas.ax_pattern.legend(
                loc=1, prop={'size': 10}, framealpha=0., handlelength=1)
            for line, txt in zip(leg_jcpds.get_lines(), leg_jcpds.get_texts()):
                txt.set_color(line.get_color())
        if self.widget.checkBox_ShowLargePnT.isChecked():
            label_p_t = "{0: 5.1f} GPa\n{1: 4.0f} K".\
                format(pressure, temperature)
            self.widget.mpl.canvas.ax_pattern.text(
                0.01, 0.98, label_p_t, horizontalalignment='left',
                verticalalignment='top',
                transform=self.widget.mpl.canvas.ax_pattern.transAxes,
                fontsize=int(
                    self.widget.comboBox_PnTFontSize.currentText()))
        self.jbars = jbars
        self.jbars_cake = jbars_cake
        self.hkl_ptn = hkl_ptn
        self.hkl_cake = hkl_cake
        # print("JCPDS update takes {0:.2f}s at".format(time.time() - t_start),
        #      str(datetime.datetime.now())[:-7])


def axvlines(ax, xs, **kwargs):
    """
    Draw vertical lines on plot
    :param xs: A scalar, list, or 1D array of horizontal offsets
    :param plot_kwargs: Keyword arguments to be passed to plot
    :return: The plot object corresponding to the lines.
    """
    xs = np.array((xs, ) if np.isscalar(xs) else xs, copy=False)
    ylims = ax.get_ylim()
    x_points = np.repeat(xs[:, None], repeats=3, axis=1).flatten()
    y_points = np.repeat(np.array(ylims + (np.nan, ))[None, :],
                         repeats=len(xs), axis=0).flatten()
    obj = ax.plot(x_points, y_points, **kwargs)
    return obj
