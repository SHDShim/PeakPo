import pandas as pd
import numpy as np
import lmfit
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui
import datetime
from .mplcontroller import MplController
from .ucfittablecontroller import UcfitTableController
from utils import SpinBoxFixStyle
from utils import xls_ucfitlist, dialog_savefile, fit_cubic_cell, \
    fit_hexagonal_cell, fit_tetragonal_cell, fit_orthorhombic_cell, \
    make_output_table, get_directory, make_filename, cal_dspacing, get_temp_dir


class UcfitController(object):

    def __init__(self, model, widget):
        self.model = model
        self.ucfit_model = None
        self.phase = None
        self.widget = widget
        self.ucfittable_ctrl = None
        self.template_jcpds = None
        self.plot_ctrl = MplController(self.model, self.widget)
        self.connect_channel()

    def connect_channel(self):
        self.widget.pushButton_CollectPeakFitResults.clicked.connect(
            self.collect_peakfit)
        self.widget.pushButton_PerformUCFit.clicked.connect(self.perform_ucfit)
        self.widget.comboBox_PeakFitLabels.currentIndexChanged.connect(
            self.select_phase_to_ucfit)
        """
        self.widget.pushButton_RemoveUClist.clicked.connect(self.remove_ucfit)
        self.widget.pushButton_ExportXLS_2.clicked.connect(self.export_to_xls)
        self.widget.pushButton_ViewUcfit.clicked.connect(self.view_ucfit)
        self.widget.pushButton_RefreshUCfitTable.clicked.connect(
            self.update_ucfittable)
        """

    def collect_peakfit(self):
        if self.model.section_lst == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "There is no peak fitting results to collect.")
            return
        self.widget.comboBox_PeakFitLabels.clear()  # without this I will have previous record in it.
        # read data4ucfit
        # self.ucfit_model = None # without this I will have previous record in it.
        # self.phase = None # without this I will have previous record in it.
        self.ucfit_model = self._get_peaks_by_phase()
        # update comboBox_PeakFitLabels
        self.phase = list(self.ucfit_model.keys())[0]
        self.ucfittable_ctrl = UcfitTableController(self.model,
                                                    self.ucfit_model,
                                                    self.phase,
                                                    self.widget)
        self.widget.comboBox_PeakFitLabels.addItems(self.ucfit_model.keys())
        # self.update_ucfittable()

    def select_phase_to_ucfit(self):
        phase = self.widget.comboBox_PeakFitLabels.currentText()
        if (phase is None):
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "Select a phase from " +
                " the comboBox first.")
            return
        elif (phase == ''):
            return
        self.phase = phase
        # display in table
        self.update_ucfittable()
        # find matching jcpds and get symmetry
        t_jcpds = self._get_matching_jcpds()
        if t_jcpds is None:
            # warning message that matching jcpds was not found in the list
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No matching jcpds was found.\n" +
                "Choose a crystal system in the comboBox")
        else:
            self.template_jcpds = t_jcpds
            # update combo box for symmetry
            if ((t_jcpds.symmetry == 'cubic') or
                    (t_jcpds.symmetry == 'tetragonal') or
                    (t_jcpds.symmetry == 'hexagonal') or
                    (t_jcpds.symmetry == 'orthorhombic')):
                self.widget.comboBox_Symmetry.setCurrentText(t_jcpds.symmetry)
            else:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "The symmetry found in the related JCPDS file\n" +
                    "is not currently supported by PeakPo.")
                self.widget.comboBox_Symmetry.setCurrentText('cubic')

    def _get_peaks_by_phase(self):
        peaks = self._get_all_peakfit_results()
        peaks_by_phase = {}
        for peak_i in peaks:
            peaks_by_phase[peak_i['phase']] = []
        for peak_i in peaks:
            peaks_by_phase[peak_i['phase']].append(peak_i)
        return peaks_by_phase

    def _get_all_peakfit_results(self, verbose=False):
        """
        return all peak fitting result in one list
        """
        peaks = []
        for section in self.model.section_lst:
            peaks_i = []
            peaks_i = self._get_peakfit_result(section)
            peaks += peaks_i
        return peaks

    def _get_peakfit_result(self, section, verbose=False):
        """
        return peak fitting result for a chosen section
        i_section = index for a section
        """
        peaks = []
        n_peaks = int(len(section.peakinfo) / 4)
        if verbose:
            print(str(datetime.datetime.now())[:-7], 
                ": Twoth between {0:.4f} and {1:.4f} degrees " +
                  " created in {2:} has {3:d} peaks".format(
                      section.x.min(), section.x.max(),
                      section.timestamp, n_peaks))
        for i in range(int(n_peaks)):
            label = "p{:d}_".format(i)
            section.fit_result.params[label+'center'].value
            twoth = section.fit_result.params[label+'center'].value
            dsp = self.model.get_base_ptn_wavelength() / 2. / \
                np.sin(np.deg2rad(twoth / 2.))
            q = np.power((1./dsp), 2.)
            if verbose:
                print(str(datetime.datetime.now())[:-7], ': ',
                    section.peakinfo[label+'phasename'],
                      section.peakinfo[label+'h'],
                      section.peakinfo[label+'k'],
                      section.peakinfo[label+'l'],
                      section.fit_result.params[label+'center'].value)
            peak_i = {'phase': section.peakinfo[label+'phasename'],
                      'h': section.peakinfo[label+'h'],
                      'k': section.peakinfo[label+'k'],
                      'l': section.peakinfo[label+'l'],
                      'display': True,
                      'twoth': twoth,
                      'dsp': dsp,
                      'Q': q}
            peaks.append(peak_i)
        return peaks

    def update_ucfittable(self):
        self.ucfittable_ctrl.update(self.phase)

    def _apply_changes_to_graph(self):
        self.plot_ctrl.update()

    def _make_table_for_input_data(self):
        text_table = '\n'
        for peak in self.ucfit_model[self.phase]:
            if peak['display']:
                text_table += \
                    '{0:s} {1:s} {2:.0f} {3:.0f} {4:.0f} {5:.4f} \n'.format(
                        peak['phase'], str(peak['display']),
                        peak['h'], peak['k'], peak['l'], peak['dsp'])
        return text_table

    def _get_all_peakfit_results_df(self):
        peaks_by_phase = self.ucfit_model
        data_by_phase_df = {}
        for key in peaks_by_phase:
            data_by_phase_df[key] = pd.DataFrame(peaks_by_phase[key])
        return data_by_phase_df

    def _get_matching_jcpds(self):
        for jcpds_i in self.model.jcpds_lst:
            if jcpds_i.name == self.phase:
                return jcpds_i
        return None

    def perform_ucfit(self):
        # get jcpds data in df.  use display to choose data points
        if self.model.section_lst == []:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "No peak fitting result exist for this file.")
            return
        if self.phase == None:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning", "No phase has been chosen for fitting")
            return
        data_by_phase_df = self._get_all_peakfit_results_df()
        data_to_fit_df = data_by_phase_df[self.phase].loc[
            data_by_phase_df[self.phase]['display'] == True]
        # number of data point check
        n_data_points = len(data_to_fit_df.index)
        if n_data_points < 2:
            QtWidgets.QMessageBox.warning(
                self.widget, "Warning",
                "You need at least 2 data points.")
            return
        # perform ucfit
        text_output = self.phase + '\n\n'
        text_output += 'Fitted unit cell parameters \n'
        text_output += 'Crystal system = ' + \
            self.widget.comboBox_Symmetry.currentText() + '\n'
        wavelength = self.model.get_base_ptn_wavelength()
        if self.widget.comboBox_Symmetry.currentText() == 'cubic':
            a, s_a, v, s_v, res_lin, res_nlin = fit_cubic_cell(
                data_to_fit_df, wavelength, verbose=False)
            cell_params = [a, a, a]
            text_output += "a = {0:.5f} +/- {1:.5f} \n".format(a, s_a)
            text_output += "V = {0:.5f} +/- {1:.5f} \n\n".format(v, s_v)
        elif self.widget.comboBox_Symmetry.currentText() == 'tetragonal':
            if n_data_points < 3:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You need at least 3 data points for tetragonal.")
                return
            a, s_a, c, s_c, v, s_v, res_lin, res_nlin = \
                fit_tetragonal_cell(data_to_fit_df, wavelength,
                                    verbose=False)
            cell_params = [a, a, c]
            text_output += "a = {0:.5f} +/- {1:.5f} \n".format(a, s_a)
            text_output += "c = {0:.5f} +/- {1:.5f} \n".format(c, s_c)
            text_output += "V = {0:.5f} +/- {1:.5f} \n\n".format(v, s_v)
        elif self.widget.comboBox_Symmetry.currentText() == 'hexagonal':
            if n_data_points < 3:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You need at least 3 data points for hexagonal.")
                return
            a, s_a, c, s_c, v, s_v, res_lin, res_nlin = \
                fit_hexagonal_cell(data_to_fit_df, wavelength,
                                  verbose=False)
            cell_params = [a, a, c]
            text_output += "a = {0:.5f} +/- {1:.5f} \n".format(a, s_a)
            text_output += "c = {0:.5f} +/- {1:.5f} \n".format(c, s_c)
            text_output += "V = {0:.5f} +/- {1:.5f} \n\n".format(v, s_v)
        elif self.widget.comboBox_Symmetry.currentText() == 'orthorhombic':
            if n_data_points < 4:
                QtWidgets.QMessageBox.warning(
                    self.widget, "Warning",
                    "You need at least 4 data points for orthorhombic.")
                return
            a, s_a, b, s_b, c, s_c, v, s_v, res_lin, res_nlin = \
                fit_orthorhombic_cell(data_to_fit_df, wavelength,
                                      verbose=False)
            cell_params = [a, b, c]
            text_output += "a = {0:.5f} +/- {1:.5f} \n".format(a, s_a)
            text_output += "b = {0:.5f} +/- {1:.5f} \n".format(b, s_b)
            text_output += "c = {0:.5f} +/- {1:.5f} \n".format(c, s_c)
            text_output += "V = {0:.5f} +/- {1:.5f} \n\n".format(v, s_v)
        # output results
        output_df = make_output_table(res_lin, res_nlin, data_to_fit_df)
        text_output += 'Output table\n'
        text_output += output_df[['h', 'k', 'l', 'twoth', 'dsp',
                                  'twoth residue']].to_string()
        text_output += '\n\nHat: influence for the fit result. \n'
        text_output += '     1 ~ large influence, 0 ~ no influence.\n'
        text_output += output_df[['h', 'k', 'l', 'twoth', 'dsp',
                                  'hat']].to_string()
        text_output += '\n\nRstudent: how much the parameter would change' + \
            ' if deleted.\n'
        text_output += output_df[['h', 'k', 'l', 'twoth', 'dsp',
                                  'Rstudent']].to_string()
        text_output += '\n\ndfFits: deletion diagnostic giving' + \
            ' the change in\n'
        text_output += '        the predicted value twotheta.\n'
        text_output += '        upon deletion of the data point as a ' + \
            'multiple of\n'
        text_output += '        the standard deviation for 1/d-spacing^2.\n'
        text_output += output_df[['h', 'k', 'l', 'twoth', 'dsp',
                                  'dfFits']].to_string()
        text_output += '\n\ndfBetas: normalized residual\n'
        text_output += output_df[['h', 'k', 'l', 'twoth', 'dsp',
                                  'dfBetas']].to_string()
        text_output += '\n\nNon-linear fit statistics \n'
        text_output += lmfit.fit_report(res_nlin)

        self.widget.plainTextEdit_UCFitOutput.setPlainText(text_output)

        # save jcpds and save output file automatically.
        # ask for filename.  at the moment, simply overwrite
        temp_dir = get_temp_dir(self.model.get_base_ptn_filename())
        ext = "ucfit.jcpds"
        #filen_t = self.model.make_filename(ext)
        filen_t = make_filename(self.template_jcpds.file, ext,
                                temp_dir=temp_dir)
        filen_j = dialog_savefile(self.widget, filen_t)
        if str(filen_j) == '':
            return
        self._write_to_jcpds(filen_j, cell_params)

        # write to a textfile
        ext = "ucfit.output"
        #filen_t = self.model.make_filename(ext)
        filen_t = make_filename(self.template_jcpds.file, ext,
                                temp_dir=temp_dir)
        filen_o = dialog_savefile(self.widget, filen_t)
        if str(filen_o) == '':
            return

        with open(filen_o, "w") as f:
            f.write(text_output)

    def _write_to_jcpds(self, filename, cell_params):
        """
        filename = filename for new JCPDS
        cell_params = [a, b, c]
        template_jcpds = template JCPDS object to copy the information from.
        """
        f = open(filename, 'w')
        f.write("4\n")
        f.write('hkl copied from' + self.template_jcpds.file + "\n")

        symmetry = self.template_jcpds.symmetry

        # 7 manual P, d-sp input
        # K, K0 fake values
        str_el = "{0:.2f} {1:.2f}".format(self.template_jcpds.k0,
                                          self.template_jcpds.k0p)
        crystal_system = '7 '
        a_fit = cell_params[0]
        b_fit = cell_params[1]
        c_fit = cell_params[2]
        alpha = 90.
        beta = 90.
        gamma = 90.

        if symmetry == 'cubic':  # cubic
            str_uc = "{0:.5f}".format(a_fit)
        elif symmetry == 'hexagonal' or symmetry == 'trigonal':
            str_uc = "{0:.5f} {1:.5f}".format(a_fit, c_fit)
        elif symmetry == 'tetragonal':  # tetragonal
            str_uc = "{0:.5f} {1:.5f}".format(a_fit, c_fit)
        elif symmetry == 'orthorhombic':  # orthorhombic
            str_uc = "{0:.5f} {1:.5f} {2:.5f}".format(a_fit,
                                                      b_fit, c_fit)

        f.write(crystal_system + str_el + " \n")
        f.write(str_uc + " \n")
        f.write("{:.4e} \n".format(self.template_jcpds.alpha))
        f.write("d-spacing    I/I0     h   k   l \n")

        # self.cal_dsp(0., 300., use_table_for_0GPa=False)
        for line in self.template_jcpds.DiffLines:
            h = line.h
            k = line.k
            l = line.l
            dsp = cal_dspacing(symmetry, h, k, l, a_fit, b_fit, c_fit,
                               alpha, beta, gamma)
            f.write("{0:.6f} {1:.2f} {2:.1f} {3:.1f} {4:.1f} \n".format(
                    dsp, line.intensity, h, k, l))
        f.close()
