import numpy as np
import datetime
import copy
from lmfit.models import PolynomialModel, PseudoVoigtModel


class Section(object):
    def __init__(self):
        self.x = None
        self.y_bgsub = None
        self.y_bg = None  # this is the bg from peakpo
        self.timestamp = None
        self.baseline = None
        self.parameters = None
        self.fit_result = None
        self.x_c_lst = []
        self.y_c_lst = []
        self.phase_lst = []
        self.hkl_lst = []
        self.peakinfo = {}

    def clear_picks(self):
        self.x_c_lst = []
        self.y_c_lst = []
        self.phase_lst = []
        self.hkl_lst = []

    def invalidate_fit_result(self):
        """use with caution"""
        self.fit_result = None

    def fitted(self):
        if (self.fit_result is None):
            return False
        else:
            return True

    def get_peak_positions(self):
        return self.x_c_lst

    def set(self, x, y_bgsub, y_bg):
        """
        it accepts sectioned x, y_bgsub, y_bg only
        """
        self.x = x
        self.y_bgsub = y_bgsub
        self.y_bg = y_bg

    def set_single_peak(self, x_center, hkl=[0, 0, 0], phase_name=''):
        if (x_center > self.x.max()) or (x_center < self.x.min()):
            return False
        y_center = self.get_nearest_intensity(x_center)
        self.x_c_lst.append(x_center)
        self.y_c_lst.append(y_center)
        self.hkl_lst.append(hkl)
        self.phase_lst.append(phase_name)
        return True

    def peaks_exist(self):
        if self.x_c_lst == []:
            return False
        else:
            return True

    def remove_single_peak_nearby(self, x):
        diffs = []
        index = (np.abs(np.asarray(self.x_c_lst) - x)).argmin()
        self.x_c_lst.pop(index)
        self.y_c_lst.pop(index)
        self.phase_lst.pop(index)
        self.hkl_lst.pop(index)

    def set_peaks(self, x_center, y_center, fwhm, poly_order, hkl,
                  phase_name):
        """
        :param x_center: numpy array of initial x values at picked centers
        :param y_center: numpy array of initial y values at picked centers
        :param fwhm: single float number for initial fwhm value
        """
        baseline_mod = PolynomialModel(poly_order, prefix='b_')
        mod = baseline_mod
        pars = baseline_mod.make_params()
        peakinfo = {}
        for i in range(poly_order + 1):
            prefix = "b_c{0:d}".format(i)
            pars[prefix].set(1)
        i = 0
        for x, y, phase_name_i, hkl_i \
                in zip(x_center, y_center, phase_name, hkl):
            prefix = "p{0:d}_".format(i)
            peak_mod = PseudoVoigtModel(prefix=prefix, )
            pars.update(peak_mod.make_params())
            pars[prefix + 'center'].set(
                x, min=self.x.min(), max=self.x.max())
            pars[prefix + 'sigma'].set(fwhm, min=0.0)
            pars[prefix + 'amplitude'].set(y, min=0)
            pars[prefix + 'fraction'].set(0.5, min=0., max=1.)
            peakinfo[prefix + 'phasename'] = phase_name_i
            peakinfo[prefix + 'h'] = hkl_i[0]
            peakinfo[prefix + 'k'] = hkl_i[1]
            peakinfo[prefix + 'l'] = hkl_i[2]
            mod += peak_mod
            i += 1
        self.parameters = pars
        self.peakinfo = peakinfo
        self.fit_model = mod
        self.baseline = baseline_mod

    def prepare_for_fitting(self, fwhm, poly_order):
        self.set_peaks(self.x_c_lst, self.y_c_lst, fwhm, poly_order,
                       self.hkl_lst, self.phase_lst)

    def conduct_fitting(self):
        out = self.fit_model.fit(
            self.y_bgsub, self.parameters, x=self.x)
        self.fit_result = copy.deepcopy(out)
        self.timestamp = str(datetime.datetime.now())[:-7]
        print(self.timestamp)
        self.copy_fit_result_to_queue()
        if self.fit_result is None:
            return False
        else:
            return True

    def get_fit_result(self):
        return self.fit_result.params

    def get_timestamp(self):
        return self.timestamp

    def copy_fit_result_to_queue(self):
        n_peaks = self.get_number_of_peaks_in_queue()
        x_c_lst = []
        y_c_lst = []
        phase_lst = []
        hkl_lst = []
        self.clear_picks()
        for i in range(n_peaks):
            prefix = "p{0:d}_".format(i)
            x_c = self.fit_result.params[prefix + 'center'].value
            y_c = self.fit_result.params[prefix + 'amplitude'].value
            phase = self.peakinfo[prefix + 'phasename']
            hkl = [self.peakinfo[prefix + 'h'], self.peakinfo[prefix + 'k'],
                   self.peakinfo[prefix + 'l']]
            x_c_lst.append(x_c)
            y_c_lst.append(y_c)
            phase_lst.append(phase)
            hkl_lst.append(hkl)
        self.x_c_lst = x_c_lst
        self.y_c_lst = y_c_lst
        self.phase_lst = phase_lst
        self.hkl_lst = hkl_lst
        print(self.x_c_lst)

    def get_number_of_peaks_in_queue(self):
        return self.x_c_lst.__len__()

    def get_individual_profiles(self, bgsub=False):
        """
        return_value['p1_']
        return_value['b_']
        """
        comps = self.fit_result.eval_components(x=self.x)
        if bgsub:
            return comps
        else:
            bg_comps = {}
            for key, value in comps.items():
                bg_comps[key] = value + self.y_bg
            return bg_comps

    def get_fit_profile(self, bgsub=False):
        if bgsub:
            return self.fit_result.best_fit
        else:
            return self.fit_result.best_fit + self.y_bg

    def get_fit_residue(self, bgsub=False):
        if bgsub:
            return self.y_bgsub - self.fit_result.best_fit
        else:
            return self.y_bgsub - self.fit_result.best_fit + \
                self.get_fit_residue_baseline()

    def get_fit_residue_baseline(self, bgsub=False):
        if bgsub:
            return self.y_bgsub.min()
        else:
            return self.y_bg.min()

    def get_peak_parameters(self):
        peak_parameters = {}
        for key, value in self.parameters.items():
            if key[0] == 'p':
                peak_parameters[key] = value
        return peak_parameters

    def get_nearest_intensity(self, x_pick):
        index = (np.abs(np.asarray(self.x) - x_pick)).argmin()
        return self.y_bgsub[index]


class PeakModel(PseudoVoigtModel):

    def __init__(self, **kwargs):
        PseudoVoigtModel.__init__(self, **kwargs)
        self.set_phase(None)
        self.set_hkl(None)
        self.y_profile = None

    def set_phase(self, phase_name):
        self.phase_name = phase_name

    def set_hkl(self, hkl):
        if hkl is None:
            self.h = 0
            self.k = 0
            self.l = 0
        else:
            self.h = hkl[0]
            self.k = hkl[1]
            self.l = hkl[2]

    def set_y_profile(self, y_profile):
        self.y_profile = y_profile
