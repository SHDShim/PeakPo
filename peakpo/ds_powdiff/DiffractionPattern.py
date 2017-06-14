import numpy as np
import os
from .background import fit_bg_cheb_auto
from utils import writechi
import time


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
        self.y_bgsub = None
        self.x_bg = None
        self.y_bg = None
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
            return x_roi, y_roi
        else:
            print("Error: ROI should be smaller than the data range")
            return x, y

    def get_section(self, roi, bgsub=True):
        """
        return a section for viewing and processing
        """
        if bgsub:
            return self._get_section(self.x_bgsub, self.y_bgsub, roi)
        else:
            return self._get_section(self.x_raw, self.y_raw, roi)

    def _get_bg(self, roi, params=None, yshift=0.):
        if params is not None:
            self.params_chbg = params
        x, y = self._get_section(self.x_raw, self.y_raw, roi)
        t_start = time.time()
        y_bg = fit_bg_cheb_auto(x, y, self.params_chbg[0],
                                self.params_chbg[1], self.params_chbg[2])
        print("Bg sub update takes: %.4f second" % (time.time() - t_start))
        self.x_bg = x
        self.x_bgsub = x
        y_bgsub = y - y_bg
        """
        if y_bgsub.min() <= 0:
            y_bgsub = y_bgsub - y_bgsub.min() + yshift
        """
        self.y_bgsub = y_bgsub
        self.y_bg = y_bg

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


class PatternPeakPo(Pattern):
    '''
    Do not update this, this is obsolte.
    Exist only for reading old PPSS files.
    Do not delete this, if so old PPSS cannot be read.
    This is used only for old PPSS file.
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
