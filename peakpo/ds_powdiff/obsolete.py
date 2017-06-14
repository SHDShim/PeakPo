# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 08:31:09 2015

@author: DanShim
"""

#from __future__ import division

# the end of the version is the date: year-mo-day
#__version__ = "0.0.1 r2012-08-18"

import os.path
import copy
import numpy as np
import ds_xrd
from numpy.polynomial.polynomial import polyval
from scifuncs import fit_bg_cheb_auto
# from mpfit import mpfit
# import ds_em as em
# import JEOL_asw.JEOL_EDS


class Peak(object):
    """
    Single pseudo-Voigt peak from my IDL routine
    coeffs are prefactors in Voigt function, not physically meaningful
    s_... = error bars
    params are physically meaningful parameters
    """

    def __init__(self, coeffs=np.zeros(4), s_coeffs=np.zeros(4),
                 constraints=np.zeros(4)):
        if (s_coeffs.__len__() != 4) and (coeffs.__len__() != 4):
            print('prm should be list or numpy array with 4 elements')
            self.coeffs = np.zeros(4)
            self.s_coeffs = np.zeros(4)
            self.params = np.zeros(4)
            self.s_params = np.zeros(4)
        else:
            self.coeffs = coeffs
            self.s_coeffs = s_coeffs
            self.constraints = constraints
            self.cal_params()

    def cal_profile(self, x):
        return ds_xrd.VoigtPk(x, self.coeffs)

    def cal_params(self):
        params, s_params = ds_xrd.VoigtPkParam(self.coeffs, self.s_coeffs)
        self.params = params
        self.s_params = s_params
        return self.params, self.s_params


class Peak1d(Peak):
    """
    PseudoVoigt function copied from xrayunitilies package
    coeffs are defined differently from the Peak class
    Params made from this Class is identical to the Params from the
        Peak class.
    Clear drawback of this is that number can underflow for data points
        far away from the peak positions.
    """

    def cal_profile(self, x):
        return ds_xrd.PseudoVoigt1d(x, self.coeffs)

    def cal_params(self):
        area = ds_xrd.PseudoVoigt1dArea(self.coeffs)
        fwhm = self.coeffs[2] / (2. * np.sqrt(2. * np.log(2.)))
        self.params = [area, self.coeffs[1], fwhm, self.coeffs[3]]
        self.s_params = self.s_coeffs
        return self.params, self.s_params


class SPeak(object):
    """
    split voigt peak from my IDL.
    """

    def __init__(self, coeffs=np.zeros(6), s_coeffs=np.zeros(6),
                 constraints=np.zeros(6)):
        if (s_coeffs.__len__() != 6) and (coeffs.__len__() != 6):
            print('prm should be list or numpy array with 6 elements')
            self.coeffs = np.zeros(6)
            self.s_coeffs = np.zeros(6)
            self.params = np.zeros(6)
            self.s_params = np.zeros(6)
        else:
            self.coeffs = coeffs
            self.s_coeffs = s_coeffs
            self.constraints = constraints
            self.cal_params()

    def cal_profile(self, x):
        return ds_xrd.SVoigtPk(x, self.coeffs)

    def cal_params(self):
        params, s_params = ds_xrd.SVoigtPkParam(self.coeffs, self.s_coeffs)
        self.params = params
        self.s_params = s_params
        return self.params, self.s_params


class Background(object):
    """
    Polynomial background function.  But it can be easily modified to other
    type of background functions (only change cal_profile return).
    """

    def __init__(self, factors=np.zeros(2), s_factors=np.zeros(2),
                 constraints=np.zeros(2)):
        self.factors = factors
        self.s_factors = s_factors
        self.constraints = constraints

    def cal_profile(self, x):
        return polyval(x, self.factors)


class MPFitParameters:
    """
    This class is for interfacing with MPFit.
    """

    def __init__(self):
        self.parfac = None  # PARams and FACtors
        self.s_parfac = None
        self.parinfo = None


class PeakSection(object):
    """
    Object containing the Peak(s) and Background classes
    peaks is a list with a Peak object
    background is a Background object
    """

    def __init__(self):
        self.peaks = []
        self.background = None
        self.fitparfac = None

    def setup(self, peaks, background):
        self.peaks = peaks
        self.background = background

    def _separate_components(self, p, s_p=None):
        """
        separate parameters from prm and setup Peak and Background objects and
            return them
        """
        peaks_new = copy.copy(self.peaks)
        background_new = copy.copy(self.background)
        if s_p is None:
            i = 0
            for pk in peaks_new:
                n_coeff = pk.coeffs.__len__()
                pk.coeffs = p[i:i + n_coeff]
                i = i + n_coeff
            background_new.factors = p[i:]
        else:
            i = 0
            for pk in peaks_new:
                n_coeff = pk.coeffs.__len__()
                pk.coeffs = p[i:i + n_coeff]
                pk.s_coeffs = s_p[i:i + n_coeff]
                i = i + n_coeff
            background_new.factors = p[i:]
            background_new.s_factors = s_p[i:]

        return peaks_new, background_new

    def cal_profile(self, x):
        """
        peaks is a list of Peak class objects
        background is a Background class object
        peaks, background should not be given for most of time
        """
        return self._cal_profile(x, self.peaks, self.background)

    def _cal_profile(self, x, peaks=None, background=None):
        if peaks is None:
            peaks = self.peaks
        if background is None:
            background = self.background
        y = 0.
        for pks in peaks:
            y = y + pks.cal_profile(x)
        return y + background.cal_profile(x)

    def cal_profile_singles(self, x):
        """
        returns individual peak + bg profiles mainly for plotting
        """
        # get the number of peaks
        y_singles = []
        for pks in self.peaks:
            y = pks.cal_profile(x) + self.background.cal_profile(x)
            y_singles.append(y)
        return y_singles

    def _prepare_fit(self, roi):
        """
        prepare MPFitParameters object
        """
        # count number of peaks and order of bg function
        n_pkprms = 0
        for pk in self.peaks:
            n = pk.coeffs.__len__()
            n_pkprms = n_pkprms + n

        fitparfac = MPFitParameters()
        order_bg = self.background.factors.__len__()
        # make fitresult.params and fitresult.parinfo
        parfac = np.zeros(n_pkprms + order_bg)
        i = 0
        for pk in self.peaks:
            n_pk = pk.coeffs.__len__()
            parfac[i:i + n_pk] = pk.coeffs
            i = i + n_pk
        parfac[i:] = self.background.factors

        # construct parinfo
        parbase = {'value': 0., 'fixed': 0, 'limited': [0, 0], 'limits': [0., 0.]}
        parinfo = []
        for i in range(len(parfac)):
            parinfo.append(copy.deepcopy(parbase))

        j = 0
        for pk in self.peaks:
            n_pk = pk.coeffs.__len__()
            if n_pk == 4:  # symmetric peaks
                parinfo[j]['fixed'] = pk.constraints[0]
                parinfo[j]['value'] = pk.coeffs[0]
                parinfo[j + 1]['fixed'] = pk.constraints[1]
                parinfo[j + 1]['value'] = pk.coeffs[1]
                parinfo[j + 2]['fixed'] = pk.constraints[2]
                parinfo[j + 2]['value'] = pk.coeffs[2]
                parinfo[j + 3]['fixed'] = pk.constraints[3]
                parinfo[j + 3]['value'] = pk.coeffs[3]
                parinfo[j]['limited'] = [1, 0]
                parinfo[j]['limits'] = [0., 0.]  # intensity larger than 0
                parinfo[j + 1]['limited'] = [1, 1]
                parinfo[j + 1]['limits'] = roi  # peakposition within x
                parinfo[j + 2]['limited'] = [1, 0]
                parinfo[j + 2]['limits'] = [0., 0.]  # peak width greater than 0
                parinfo[j + 3]['limited'] = [1, 1]
                parinfo[j + 3]['limits'] = [0., 1.]  # n factor between 0 and 1
            if n_pk == 6:  # asymmetric peaks
                parinfo[j]['fixed'] = pk.constraints[0]
                parinfo[j]['value'] = pk.coeffs[0]
                parinfo[j + 1]['fixed'] = pk.constraints[1]
                parinfo[j + 1]['value'] = pk.coeffs[1]
                parinfo[j + 2]['fixed'] = pk.constraints[2]
                parinfo[j + 2]['value'] = pk.coeffs[2]
                parinfo[j + 3]['fixed'] = pk.constraints[3]
                parinfo[j + 3]['value'] = pk.coeffs[3]
                parinfo[j + 4]['fixed'] = pk.constraints[4]
                parinfo[j + 4]['value'] = pk.coeffs[4]
                parinfo[j + 5]['fixed'] = pk.constraints[5]
                parinfo[j + 5]['value'] = pk.coeffs[5]
                parinfo[j]['limited'] = [1, 0]
                parinfo[j]['limits'] = [0., 0.]  # intensity larger than 0
                parinfo[j + 1]['limited'] = [1, 1]
                parinfo[j + 1]['limits'] = roi  # peakposition within x
                parinfo[j + 2]['limited'] = [1, 0]
                parinfo[j + 2]['limits'] = [0., 0.]  # peak width greater than 0
                parinfo[j + 3]['limited'] = [1, 0]
                parinfo[j + 3]['limits'] = [0., 0.]  # peak width greater than 0
                parinfo[j + 4]['limited'] = [1, 1]
                parinfo[j + 4]['limits'] = [0., 1.]  # n factor between 0 and 1
                parinfo[j + 5]['limited'] = [1, 1]
                parinfo[j + 5]['limits'] = [0., 1.]  # n factor between 0 and 1
            j += n_pk
        for bg in range(order_bg):
            parinfo[j + bg]
            parinfo[j + bg]['fixed'] = self.background.constraints[bg]
            parinfo[j + bg]['value'] = self.background.factors[bg]
        fitparfac.parfac = parfac
        fitparfac.s_parfac = np.zeros(parfac.shape)
        fitparfac.parinfo = parinfo
        self.fitparfac = fitparfac
#    def set_fitconstraints(self): no need for this, do it directly by
#   PeakSection.MPFitParameters.parinfo = xxx

    def fit(self, x, y, update=True, parinfo=None):
        """
        perform fitting for given x,y and update peak and bg parameters
        if update is set True, object peaks and background will be updated,
            and therefore the old information will get lost.
        this function returns peaks and background
        for constrained fits, this accepts parinfo
        """
        roi = [x.min(), x.max()]
        self._prepare_fit(roi)

        if parinfo is not None:
            self.fitparfac.parinfo = parinfo
        # contruct parinfo array
        fa = {'x': x, 'y': y, 'err': np.ones(x.size)}

        m = mpfit(self.fitpks, self.fitparfac.parfac,
                  parinfo=self.fitparfac.parinfo, functkw=fa, quiet=True)

        peaks, background = self._separate_components(m.params, s_p=m.perror)

        if update == True:
            # update fitprm
            self.fitparfac.parfac = m.params
            self.fitparfac.s_parfac = m.perror
            # update peaks and background
            self.peaks = peaks
            self.background = background
        else:
            return peaks, background

    def fitpks(self, p, fjac=None, x=None, y=None, err=None):
        peaks, background = self._separate_components(p)
        model = self._cal_profile(x, peaks=peaks, background=background)
        status = 0
        return [status, (y - model) / err]


class Pattern(object):
    """
    This modified from the same object in ds_* modules
    """

    def __init__(self, filename=None):
        if filename is None:
            self.x_raw = None
            self.y_raw = None
        else:
            self.fname = filename
            self.read_file(filename)
        self.x_bgsub = None
        self.y_bg = None
        self.y_bgsub = None
        self.params_chbg = np.asarray([10, 10, 50])

    def read_file(self, fname):
        """
        read a chi file and get raw xy
        """
        if fname.endswith('.chi'):
            data = np.loadtxt(fname, skiprows=4)
            twotheta, intensity = data.T
        else:
            raise ValueError('Only support CHI, MSA, and EDS formats')
        # set file name information
        self.fname = fname

        self.x_raw = twotheta
        self.y_raw = intensity

    def _get_section(self, x, y, roi):
        if roi[0] >= x.min() and roi[1] <= x.max():
            i_roimin = np.abs(x - roi[0]).argmin()
            i_roimax = np.abs(x - roi[1]).argmin()
            x_roi = x[i_roimin:i_roimax]
            y_roi = y[i_roimin:i_roimax]
        else:
            print("Error: ROI should be smaller than the data range")
        return x_roi, y_roi

    def get_section(self, roi, bgsub=True):
        """
        return a section for viewing and processing
        """
        if bgsub:
            return self._get_section(self.x_bgsub, self.y_bgsub, roi)
        else:
            return self._get_section(self.x_raw, self.y_raw, roi)

    def _get_bg(self, roi, params=None, yshift=10.):
        if params is not None:
            self.params_chbg = params
        x, y = self._get_section(self.x_raw, self.y_raw, roi)
        y_bg = fit_bg_cheb_auto(x, y, self.params_chbg[0],
                                self.params_chbg[1], self.params_chbg[2])
        self.x_bg = x
        self.x_bgsub = x
        y_bgsub = y - y_bg
        if y_bgsub.min() <= 0:
            y_bgsub = y_bgsub - y_bgsub.min() + yshift
        self.y_bgsub = y_bgsub
        self.y_bg = y - y_bgsub

    def subtract_bg(self, roi, params=None, yshift=10.):
        self._get_bg(roi, params=params, yshift=yshift)

    def get_raw(self):
        return self.x_raw, self.y_raw

    def get_background(self):
        return self.x_bg, self.y_bg

    def get_bgsub(self):
        return self.x_bgsub, self.y_bgsub

    def get_chbg(self, roi, params=None, chiout=False, yshift=10.):
        """
        subtract background from raw data for a roi and then store in
        chbg xy
        """
        self._get_bg(roi, params=params, yshift=yshift)

        if chiout:
            # write background file
            f_bg = os.path.splitext(self.fname)[0] + '.bg.chi'
            text = "Background\n" + "CHEB BG:" + \
                ' '.join(map(str, self.params_chbg)) + "\n\n"
            writechi(f_bg, self.x_bgsub, self.y_bg, preheader=text)
            # write background subtracted file
            f_bgsub = os.path.splitext(self.fname)[0] + '.bgsub.chi'
            text = "Background subtracted diffraction pattern\n" + \
                "CHEB BG:" + ' '.join(map(str, self.params_chbg)) + "\n\n"
            writechi(f_bgsub, self.x_bgsub, self.y_bgsub, preheader=text)


"""
class Pattern(object):

    This class loads powder diffraction patterns from chi format(but expandable)
    and do basic pattern operations, such as background subtraction, peak fitting,
    normalization, etc.


    def __init__(self, filename=None):
        if filename is None:
            self.x_raw = None
            self.y_raw = None
        else:
            self.fname = filename
            self.read_file(filename)
        self.x_bgsub = None
        self.y_bg = None
        self.y_bgsub = None
        self.params_chbg = np.asarray([10, 10, 50])

    def read_file(self, fname):

        read a chi file and get raw xy

        if fname.endswith('.chi'):
            data = np.loadtxt(fname, skiprows=4)
            twotheta, intensity = data.T
        elif fname.endswith('.msa'):
            twotheta, intensity = em.read_msa(fname)
        elif fname.endswith('.eds') or fname.endswith('.EDS'):
            eds = JEOL_asw.JEOL_EDS.JEOL_ED_spectrum()
            eds.readfile(fname)
            intensity = np.asarray(eds.spectrum_cps)
            twotheta = np.arange(4096) * float(eds.keV_per_channel)
        else:
            raise ValueError('Only support CHI, MSA, and EDS formats')
        # set file name information
        self.fname = fname

        self.x_raw = twotheta
        self.y_raw = intensity

    def get_section(self, roi, bgsub=True):

        return a section for viewing and processing

        if bgsub:
            x_temp = self.x_bgsub
            y_temp = self.y_bgsub
        else:
            x_temp = self.x_raw
            y_temp = self.y_raw

        if roi[0] >= x_temp.min() and roi[1] <= x_temp.max():
            i_roimin = np.abs(x_temp - roi[0]).argmin()
            i_roimax = np.abs(x_temp - roi[1]).argmin()
            x_roi = x_temp[i_roimin:i_roimax]
            y_roi = y_temp[i_roimin:i_roimax]
        else:
            print("Error: ROI should be smaller than the data range")

        return x_roi, y_roi

    def get_chbg(self, roi, params=None, chiout=False, yshift=10.):

        subtract background from raw data for a roi and then store in
        chbg xy

        if params is not None:
            self.params_chbg = params
        '''
        if self.fname.endswith('.msa'):
            self.y_bgsub = self.y_raw
            self.x_bgsub = self.x_raw
            self.y_bg = np.zeros(self.x_raw.__len__())
            return
        '''
        idx_xmin = np.abs(self.x_raw - roi[0]).argmin()
        idx_xmax = np.abs(self.x_raw - roi[1]).argmin()

        x_roi = self.x_raw[idx_xmin:idx_xmax]
        y_roi = self.y_raw[idx_xmin:idx_xmax]

        y_bg = ds_xrd.fit_bg_cheb_auto(x_roi, y_roi, self.params_chbg[0],
                                       self.params_chbg[1], self.params_chbg[2])

        self.x_bgsub = x_roi
        y_bgsub = y_roi - y_bg
        if y_bgsub.min() <= 0:
            y_bgsub = y_bgsub - y_bgsub.min() + yshift
        self.y_bgsub = y_bgsub
        self.y_bg = y_bg

        if chiout:
            # write background file
            f_bg = os.path.splitext(self.fname)[0] + '.bg.chi'
            text = "Background\n" + "CHEB BG:" + \
                ' '.join(map(str, self.params_chbg)) + "\n\n"
            writechi(f_bg, self.x_bgsub, self.y_bg, preheader=text)
            # write background subtracted file
            f_bgsub = os.path.splitext(self.fname)[0] + '.bgsub.chi'
            text = "Background subtracted diffraction pattern\n" + \
                "CHEB BG:" + ' '.join(map(str, self.params_chbg)) + "\n\n"
            writechi(f_bgsub, self.x_bgsub, self.y_bgsub, preheader=text)
"""


def writechi(filen, x, y, preheader=None):
    """
    header should be string list.  Only first three will be used
    """
    if preheader is None:
        preheader = "\n\n\n"
    header = str(x.__len__())
    np.savetxt(filen, np.asarray([x, y]).T,
               fmt='%1.7e', header=header, comments=preheader)


def get_DataSection(x, y, roi):
    """
    return a section for viewing and processing
    """
    if roi[0] >= x.min() and roi[1] <= x.max():
        i_roimin = np.abs(x - roi[0]).argmin()
        i_roimax = np.abs(x - roi[1]).argmin()
        x_roi = x[i_roimin:i_roimax]
        y_roi = y[i_roimin:i_roimax]
        return x_roi, y_roi
    else:
        return x, y


class PatternPeakPo(Pattern):
    '''
    Do not update this, this is obsolte.  Exist only for reading old PPSS files.
    Do not delete this, if so old PPSS cannot be read.  This is used only for old PPSS file.
    '''

    def __init__(self):
        self.color = 'white'
        self.display = False
        self.wavelength = 0.3344

    def get_invDsp(self):
        self.invDsp_raw = np.sin(np.radians(self.x_raw / 2.)) \
            * 2. / self.wavelength
        self.invDsp_bgsub = np.sin(np.radians(self.x_bgsub / 2.)) \
            * 2. / self.wavelength
