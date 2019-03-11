import pickle
import os
import copy
import xlwt
from ds_cake import DiffImg
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ds_jcpds import JCPDSplt, Session
from ds_powdiff import PatternPeakPo, get_DataSection
from ds_section import Section
from utils import samefilename, make_filename, change_file_path


class PeakPoModel(object):
    """
    session is only for reading/writing/referencing.
    components of the models are not part of session.
    session is a reference object
    """

    def __init__(self):
        self.base_ptn = None
        self.waterfall_ptn = []
        self.jcpds_lst = []
        self.ucfit_lst = []
        self.diff_img = None
        self.poni = None
        self.session = None
        self.jcpds_path = ''
        self.chi_path = ''
        self.current_section = None
        self.section_lst = []
        self.saved_pressure = 10.
        self.saved_temperature = 300.

    def exist_in_waterfall(self, filename):
        if not self.waterfall_exist():
            return False
        for f in self.waterfall_ptn:
            if filename == f.fname:
                return True
        return False

    def get_saved_pressure(self):
        return self.saved_pressure

    def get_saved_temperature(self):
        return self.saved_temperature

    def save_pressure(self, pressure):
        self.saved_pressure = pressure

    def save_temperature(self, temperature):
        self.saved_temperature = temperature

    def set_this_section_current(self, index):
        self.current_section = None
        self.current_section = copy.deepcopy(self.section_lst[index])

    def clear_section_list(self):
        self.section_list[:] = []

    def get_number_of_section(self):
        return self.section_lst.__len__()

    def set_current_section(self, roi):
        x_section_bg, y_section_bg = get_DataSection(
            self.base_ptn.x_bg, self.base_ptn.y_bg, roi)
        __, y_section_bgsub = get_DataSection(
            self.base_ptn.x_bgsub, self.base_ptn.y_bgsub, roi)
        self.current_section.set(x_section_bg, y_section_bgsub, y_section_bg)

    def current_section_exists_in_list(self):
        for section in self.section_lst:
            if self.current_section.get_timestamp() == section.get_timestamp():
                return True
        return False

    def current_section_saved(self):
        if self.get_number_of_section() == 0:
            return False
        if self.current_section.timestamp is None:
            return False
        if self.current_section_exists_in_list():
            return True
        else:
            return False

    def initialize_current_section(self):
        if self.current_section_exist():
            self.current_section = None
        self.current_section = Section()

    def save_current_section(self):
        new_section = copy.deepcopy(self.current_section)
        self.section_lst.append(new_section)
        self.current_section = None

    def current_section_exist(self):
        if self.current_section is None:
            return False
        if self.current_section.x is None:
            return False
        else:
            return True

    def set_from(self, model_r, new_chi_path=None, jlistonly=False):
        self.jcpds_lst = model_r.jcpds_lst
        if jlistonly:
            return
        if new_chi_path is None:
            pass
        else:
            new_base_ptn_fname = change_file_path(model_r.base_ptn.fname,
                                                  new_chi_path)
            model_r.base_ptn.fname = new_base_ptn_fname
            if model_r.waterfall_ptn != []:
                new_waterfall_ptn = []
                for ptn in model_r.waterfall_ptn:
                    new_fname = change_file_path(ptn.fname, new_chi_path)
                    if os.path.exists(new_fname):
                        ptn.fname = new_fname
                        new_waterfall_ptn.append(ptn)
                if new_waterfall_ptn != []:
                    model_r.waterfall_ptn = new_waterfall_ptn
            if model_r.diff_img is not None:
                new_img_fname = change_file_path(
                    model_r.diff_img.img_filename,
                    new_chi_path)
                model_r.diff_img.img_filename = new_img_fname
            if model_r.poni is not None:
                new_poni_fname = change_file_path(model_r.poni,
                                                  new_chi_path)
                model_r.poni = new_poni_fname
            model_r.chi_path = new_chi_path
        self.base_ptn = model_r.base_ptn
        self.waterfall_ptn = model_r.waterfall_ptn
        self.diff_img = model_r.diff_img
        self.section_lst = model_r.section_lst
        self.saved_pressure = model_r.get_saved_pressure()
        self.saved_temperature = model_r.get_saved_temperature()
        self.poni = model_r.poni
        self.ucfit_lst = model_r.ucfit_lst
        self.session = model_r.session
        self.jcpds_path = model_r.jcpds_path
        self.chi_path = model_r.chi_path

    def import_section_list(self, model_r):
        new_section_lst = copy.deepcopy(model_r.section_lst)
        if new_section_lst == []:
            return
        for section in new_section_lst:
            section.invalidate_fit_result()
            roi = section.get_xrange()
            x, y_bgsub, y_bg = self.get_single_section(roi)
            section.set(x, y_bgsub, y_bg)
        existing_section_lst = copy.deepcopy(self.section_lst)
        self.section_lst[:] = []
        self.section_lst = existing_section_lst + new_section_lst

    def get_single_section(self, roi):
        x_section_bg, y_section_bg = get_DataSection(
            self.base_ptn.x_bg, self.base_ptn.y_bg, roi)
        __, y_section_bgsub = get_DataSection(
            self.base_ptn.x_bgsub, self.base_ptn.y_bgsub, roi)
        return x_section_bg, y_section_bgsub, y_section_bg

    def reset_base_ptn(self):
        self.base_ptn = PatternPeakPo()

    def reset_waterfall_ptn(self):
        self.waterfall_ptn[:] = []

    def reset_jcpds_lst(self):
        self.jcpds_lst[:] = []

    def reset_ucfit_lst(self):
        self.ucfit_lst[:] = []

    def reset_diff_img(self):
        self.diff_img = DiffImg()

    def reset_poni(self):
        self.poni = None

    def base_ptn_exist(self):
        if self.base_ptn is None:
            return False
        else:
            if self.base_ptn.fname is None:
                return False
            else:
                return True

    def waterfall_exist(self):
        if self.waterfall_ptn == []:
            return False
        else:
            return True

    def jcpds_exist(self):
        if self.jcpds_lst == []:
            return False
        else:
            return True

    def ucfit_exist(self):
        if self.ucfit_lst == []:
            return False
        else:
            return True

    def diff_img_exist(self):
        if self.diff_img is None:
            return False
        else:
            return True

    def poni_exist(self):
        if self.poni is None:
            return False
        else:
            return True

    def make_filename(self, extension, original=False):
        """
        :param extension: extension without a dot
        """
        return make_filename(self.base_ptn.fname, extension, original=original)

    def same_filename_as_base_ptn(self, filename):
        return samefilename(self.base_ptn.fname, filename)

    def set_base_ptn(self, new_base_ptn_filen, wavelength):
        """
        :param new_base_ptn: PatternPeakPo object
        """
        self.reset_base_ptn()
        self.base_ptn.read_file(new_base_ptn_filen)
        self.set_chi_path(os.path.split(new_base_ptn_filen)[0])
        self.set_base_ptn_wavelength(wavelength)
        self.base_ptn.display = True

    def get_base_ptn(self):
        return self.base_ptn

    def append_a_waterfall_ptn(self, filename, wavelength,
                               bg_roi, bg_params, temp_dir=None):
        pattern = PatternPeakPo()
        pattern.read_file(filename)
        pattern.wavelength = wavelength
        pattern.display = False
        if temp_dir is None:
            pattern.get_chbg(bg_roi, params=bg_params, yshift=0)
        else:
            success = pattern.read_bg_from_tempfile(temp_dir=temp_dir)
            if not success:
                pattern.get_chbg(bg_roi, params=bg_params, yshift=0)
        self.waterfall_ptn.append(pattern)

    def replace_a_waterfall(self, new_pattern, index_to_replace):
        self.waterfall_ptn[index_to_replace] = new_pattern

    def set_waterfall_ptn(
            self, filenames, wavelength, display, bg_roi, bg_params,
            temp_dir=None):
        new_waterfall_ptn = []
        for f, wl, dp in zip(filenames, wavelength, display):
            pattern = PatternPeakPo()
            pattern.read_file(f)
            pattern.wavelength = wl
            pattern.display = dp
            if temp_dir is None:
                pattern.get_chbg(bg_roi, params=bg_params, yshift=0)
            else:
                success = pattern.read_bg_from_tempfile(temp_dir=temp_dir)
                if not success:
                    pattern.get_chbg(bg_roi, params=bg_params, yshift=0)
            new_waterfall_ptn.append(pattern)
        self.waterfall_ptn = new_waterfall_ptn

    def append_a_jcpds(self, filen, color):
        try:
            phase = JCPDSplt()
            phase.read_file(filen)  # phase.file = f
            phase.color = color
        except:
            return False
        self.jcpds_lst.append(phase)
        return True

    def write_as_ppss(self,
                      fname, pressure, temperature):
        session = Session()
        session.pattern = self.get_base_ptn()
        session.waterfallpatterns = self.waterfall_ptn
        session.wavelength = self.base_ptn.wavelength
        session.pressure = pressure
        session.temperature = temperature
        session.jlist = self.jcpds_lst
        session.bg_roi = self.base_ptn.roi
        session.bg_params = self.base_ptn.params_chbg
        session.jcpds_path = self.jcpds_path
        session.chi_path = self.chi_path
        f = open(fname, 'wb')
        pickle.dump(session, f)
        f.close()

    def read_ppss(self, fname):
        f = open(fname, 'rb')
        session = pickle.load(f, encoding='latin1')
        f.close()
        self.session = session

    def set_jcpds_from_ppss(self):
        if self.session is not None:
            self.jcpds_lst = self.session.jlist
        else:
            self.set_jcpds_path('')

    def set_chi_path(self, chi_path):
        self.chi_path = chi_path

    def set_jcpds_path(self, jcpds_path):
        self.jcpds_path = jcpds_path

    def get_base_ptn_wavelength(self):
        return self.base_ptn.wavelength

    def set_base_ptn_wavelength(self, wavelength):
        self.base_ptn.wavelength = wavelength

    def get_base_ptn_filename(self):
        return self.base_ptn.fname

    def set_base_ptn_color(self, color):
        self.base_ptn.color = color

    def associated_image_exists(self):
        filen_tif = self.make_filename('tif', original=True)
        filen_mar3450 = self.make_filename('mar3450', original=True)
        filen_cbf = self.make_filename('cbf', original=True)
        if os.path.exists(filen_tif) or os.path.exists(filen_mar3450) or \
                os.path.exists(filen_cbf):
            return True
        else:
            return False

    def load_associated_img(self):
        filen_tif = self.make_filename('tif', original=True)
        filen_mar3450 = self.make_filename('mar3450', original=True)
        filen_cbf = self.make_filename('cbf', original=True)
        self.reset_diff_img()
        if os.path.exists(filen_tif):
            filen_toload = filen_tif
        elif os.path.exists(filen_mar3450):
            filen_toload = filen_mar3450
        elif os.path.exists(filen_cbf):
            filen_toload = filen_cbf
        self.diff_img.load(filen_toload)

    def section_list_exist(self):
        if self.section_lst == []:
            return False
        else:
            return True

    def save_peak_fit_results_to_xls(self, xls_filen):
        """
        returns boolean for success
        """
        if not self.section_list_exist():
            return False
        if str(xls_filen) == '':
            return
        num_sec = 0
        workbook = xlwt.Workbook()
        sheet_num = 0
        for section in self.section_lst:
            x_range = section.get_xrange()
            xmin = x_range[0]
            xmax = x_range[1]
            sheet_name = "{0:d}_at_{1:.2f}-{2:.2f}".format(
                sheet_num, xmin, xmax)
            sheet_num += 1
            sheet = workbook.add_sheet(sheet_name)
            sheet.write(0, 0, section.timestamp)
            sheet.write(1, 0, 'Pressure (GPa)')
            sheet.write(2, 0, 'Temperature (K)')
            sheet.write(1, 1, self.get_saved_pressure())
            sheet.write(2, 1, self.get_saved_temperature())
            sheet.write(3, 0, 'Section x range')
            sheet.write(3, 1, xmin)
            sheet.write(3, 2, xmax)
            sheet.write(4, 0, 'Chisqr')
            sheet.write(4, 1, section.fit_result.chisqr)
            sheet.write(5, 0, 'Reduced Chisqr')
            sheet.write(5, 1, section.fit_result.redchi)
            sheet.write(6, 0, 'Akaike info crit')
            sheet.write(6, 1, section.fit_result.aic)
            sheet.write(7, 0, 'Bayesian info crit')
            sheet.write(7, 1, section.fit_result.bic)
            # write peak params and errors first
            lineno = 8
            sheet.write(lineno, 1, 'Phase')
            sheet.write(lineno, 2, 'h')
            sheet.write(lineno, 3, 'k')
            sheet.write(lineno, 4, 'l')
            sheet.write(lineno, 5, 'Area value')
            sheet.write(lineno, 6, 'Area stderr')
            sheet.write(lineno, 7, 'Area vary')
            sheet.write(lineno, 8, 'Pos value')
            sheet.write(lineno, 9, 'Pos stderr')
            sheet.write(lineno, 10, 'Pos vary')
            sheet.write(lineno, 11, 'FWHM value')
            sheet.write(lineno, 12, 'FWHM stderr')
            sheet.write(lineno, 13, 'FWHM vary')
            sheet.write(lineno, 14, 'nL value')
            sheet.write(lineno, 15, 'nL stderr')
            sheet.write(lineno, 16, 'nL vary')
            lineno += 1
            n_peak = section.get_number_of_peaks_in_queue()
            for i in range(n_peak):
                prefix = "p{0:d}_".format(i)
                sheet.write(lineno, 0, prefix)
                sheet.write(lineno, 1, section.peakinfo[prefix + 'phasename'])
                sheet.write(lineno, 2, section.peakinfo[prefix + 'h'])
                sheet.write(lineno, 3, section.peakinfo[prefix + 'k'])
                sheet.write(lineno, 4, section.peakinfo[prefix + 'l'])
                sheet.write(lineno, 5, section.fit_result.
                            params[prefix + 'amplitude'].value)
                sheet.write(lineno, 6, section.fit_result.
                            params[prefix + 'amplitude'].stderr)
                sheet.write(lineno, 7, section.fit_result.
                            params[prefix + 'amplitude'].vary)
                sheet.write(lineno, 8, section.fit_result.
                            params[prefix + 'center'].value)
                sheet.write(lineno, 9, section.fit_result.
                            params[prefix + 'center'].stderr)
                sheet.write(lineno, 10, section.fit_result.
                            params[prefix + 'center'].vary)
                sheet.write(lineno, 11, section.fit_result.
                            params[prefix + 'sigma'].value * 2.)
                sheet.write(lineno, 12, section.fit_result.
                            params[prefix + 'sigma'].stderr * 2.)
                sheet.write(lineno, 13, section.fit_result.
                            params[prefix + 'sigma'].vary)
                sheet.write(lineno, 14, section.fit_result.
                            params[prefix + 'fraction'].value)
                sheet.write(lineno, 15, section.fit_result.
                            params[prefix + 'fraction'].stderr)
                sheet.write(lineno, 16, section.fit_result.
                            params[prefix + 'fraction'].vary)
                lineno += 1
            lineno += 1
            sheet.write(lineno, 0, 'Baseline factors')
            lineno += 1
            n_order = section.get_order_of_baseline_in_queue()
            sheet.write(lineno, 1, 'value')
            sheet.write(lineno, 2, 'stderr')
            sheet.write(lineno, 3, 'vary')
            lineno += 1
            for i in range(n_order + 1):
                prefix = "b_c{0:d}".format(i)
                sheet.write(lineno, 0, prefix)
                sheet.write(lineno, 1, section.fit_result.params[prefix].value)
                sheet.write(lineno, 2, section.fit_result.params[prefix].stderr)
                sheet.write(lineno, 3, section.fit_result.params[prefix].vary)
                lineno += 1
            lineno += 2
            sheet.write(lineno, 0, 'x_data')
            sheet.write(lineno, 1, 'y_data')
            sheet.write(lineno, 2, 'y_bgsub')
            sheet.write(lineno, 3, 'y_bg')
            sheet.write(lineno, 4, 'y_fit_profile')
            y_total_profile = section.get_fit_profile(bgsub=False)
            y_single_profiles = section.get_individual_profiles(bgsub=False)
            k = 0
            for key, value in y_single_profiles.items():
                sheet.write(lineno, 5 + k, key + 'profile')
                k += 1
            lineno += 1
            for i in range(section.x.__len__()):
                sheet.write(lineno, 0, section.x[i])
                sheet.write(lineno, 1, section.y_bg[i] + section.y_bgsub[i])
                sheet.write(lineno, 2, section.y_bgsub[i])
                sheet.write(lineno, 3, section.y_bg[i])
                sheet.write(lineno, 4, y_total_profile[i])
                j = 0
                for key, value in y_single_profiles.items():
                    sheet.write(lineno, 5 + j, value[i])
                    j += 1
                lineno += 1
        workbook.save(xls_filen)
