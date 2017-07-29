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
        self.peaks_in_queue = []

    def get_xrange(self):
        return (self.x.min(), self.x.max())

    def get_yrange(self, bgsub=False):
        if bgsub:
            return (self.y_bgsub.min(), self.y_bgsub.max())
        else:
            return ((self.y_bgsub + self.y_bg).min(),
                    (self.y_bgsub + self.y_bg).max())

    def clear_picks(self):
        self.peaks_in_queue = []

    def invalidate_fit_result(self):
        """use with caution"""
        self.fit_result = None

    def fitted(self):
        if (self.fit_result is None):
            return False
        else:
            return True

    def get_peak_positions(self):
        if self.get_number_of_peaks_in_queue() == 0:
            return []
        else:
            x_c_lst = []
            for peak in self.peaks_in_queue:
                x_c_lst.append(peak['center'])
            return x_c_lst

    def set(self, x, y_bgsub, y_bg):
        """
        it accepts sectioned x, y_bgsub, y_bg only
        """
        self.x = x
        self.y_bgsub = y_bgsub
        self.y_bg = y_bg

    def set_single_peak(self, x_center, fwhm, hkl=[0, 0, 0], phase_name=''):
        if (x_center > self.x.max()) or (x_center < self.x.min()):
            return False
        y_center = self.get_nearest_intensity(x_center)
        peak = {}
        peak['center'] = x_center
        peak['amplitude'] = y_center
        peak['sigma'] = fwhm
        peak['fraction'] = 0.5
        peak['phasename'] = phase_name
        peak['h'] = hkl[0]
        peak['k'] = hkl[1]
        peak['l'] = hkl[2]
        self.peaks_in_queue.append(peak)
        return True

    def peaks_exist(self):
        if self.peaks_in_queue == []:
            return False
        else:
            return True

    def remove_single_peak_nearby(self, x):
        diffs = []
        x_c_lst = self.get_peak_positions()
        index = (np.abs(np.asarray(x_c_lst) - x)).argmin()
        self.peaks_in_queue.pop(index)

    def prepare_for_fitting(self, poly_order):
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
        for peak in self.peaks_in_queue:
            prefix = "p{0:d}_".format(i)
            peak_mod = PseudoVoigtModel(prefix=prefix, )
            pars.update(peak_mod.make_params())
            pars[prefix + 'center'].set(
                peak['center'], min=self.x.min(), max=self.x.max())
            pars[prefix + 'sigma'].set(peak['sigma'], min=0.0)
            pars[prefix + 'amplitude'].set(peak['amplitude'], min=0)
            pars[prefix + 'fraction'].set(peak['fraction'], min=0., max=1.)
            peakinfo[prefix + 'phasename'] = peak['phasename']
            peakinfo[prefix + 'h'] = peak['h']
            peakinfo[prefix + 'k'] = peak['k']
            peakinfo[prefix + 'l'] = peak['l']
            mod += peak_mod
            i += 1
        self.parameters = pars
        self.peakinfo = peakinfo
        self.fit_model = mod
        self.baseline = baseline_mod

    def conduct_fitting(self):
        out = self.fit_model.fit(
            self.y_bgsub, self.parameters, x=self.x)
        self.fit_result = copy.deepcopy(out)
        self.timestamp = str(datetime.datetime.now())[:-7]
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
        self.clear_picks()
        for i in range(n_peaks):
            peak = {}
            prefix = "p{0:d}_".format(i)
            peak['center'] = self.fit_result.params[prefix + 'center'].value
            peak['amplitude'] = self.fit_result.params[
                prefix + 'amplitude'].value
            peak['sigma'] = self.fit_result.params[
                prefix + 'sigma'].value
            peak['fraction'] = self.fit_result.params[
                prefix + 'fraction'].value
            peak['phasename'] = self.peakinfo[prefix + 'phasename']
            peak['h'] = self.peakinfo[prefix + 'h']
            peak['k'] = self.peakinfo[prefix + 'k']
            peak['l'] = self.peakinfo[prefix + 'l']
            self.peaks_in_queue.append(peak)

    def get_number_of_peaks_in_queue(self):
        return self.peaks_in_queue.__len__()

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
        return self.y_bgsub - self.fit_result.best_fit + \
            self.get_fit_residue_baseline(bgsub=bgsub)

    def get_fit_residue_baseline(self, bgsub=False):
        if bgsub:
            return 0
            # return self.y_bgsub.min()
        else:
            return self.y_bg.min()

    def get_nearest_intensity(self, x_pick):
        index = (np.abs(np.asarray(self.x) - x_pick)).argmin()
        return self.y_bgsub[index]

    def get_nearest_xy(self, x_pick):
        index = (np.abs(np.asarray(self.x) - x_pick)).argmin()
        return self.x_bgsub[index], self.y_bgsub[index]


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
