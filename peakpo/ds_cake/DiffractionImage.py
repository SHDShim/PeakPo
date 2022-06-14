import os
import time
from PIL import Image
import fabio
import numpy.ma as ma
import numpy as np
import pyFAI
import matplotlib.pyplot as plt
from utils import make_filename, extract_extension


class DiffImg(object):
    def __init__(self):
        self.img_filename = None
        self.poni = None
        self.img = None
        self.intensity = None
        self.tth = None
        self.intensity_cake = None
        self.tth_cake = None
        self.chi_cake = None
        self.mask = None

    def load(self, img_filename):
        self.img_filename = img_filename
        if extract_extension(self.img_filename) == 'tif':
            data = Image.open(self.img_filename)
        elif extract_extension(self.img_filename) == 'tiff':
            data = Image.open(self.img_filename)
        elif extract_extension(self.img_filename) == 'mar3450':
            data_fabio = fabio.open(img_filename)
            data = data_fabio.data
        elif extract_extension(self.img_filename) == 'cbf':
            data_fabio = fabio.open(img_filename)
            data = data_fabio.data
            #print('cbf detected')
            # print(data)
        self.img = np.array(data)[::-1]

    def histogram(self):
        if self.img is None:
            return
        f, ax = plt.subplots(figsize=(10, 4))
        ax.hist(self.img.ravel(), bins=256, fc='k', ec='k')
        f.show()

    def show(self, clim=(0, 8e3)):
        f, ax = plt.subplots(figsize=(10, 10))
        cax = ax.imshow(self.img, origin="lower", cmap="gray_r", clim=clim)
        cbar = f.colorbar(cax, orientation='horizontal')
        f.show()

    def set_calibration(self, poni_filename):
        self.poni = pyFAI.load(poni_filename)

    def calculate_n_azi_pnts(self):
        """
        circular for mar3450 style detector.
        """
        x_dim = self.img.shape[0]
        y_dim = self.img.shape[1]
        fit2d_parameter = self.poni.getFit2D()
        center_x = fit2d_parameter['centerX']
        center_y = fit2d_parameter['centerY']

        if center_x < x_dim and center_x > 0:
            side1 = np.max([abs(x_dim - center_x), center_x])
        else:
            side1 = x_dim
        if center_y < y_dim and center_y > 0:
            side2 = np.max([abs(y_dim - center_y), center_y])
        else:
            side2 = y_dim
        max_dist = np.sqrt(side1 ** 2 + side2 ** 2)
        return int(max_dist * 2)

    def calculate_max_twotheta(self):
        # 2019/06/20 decrease r by a factor of 2 and
        # decrease tth_max by a factor of 2.
        d = self.poni.dist
        r = self.calculate_n_azi_pnts() * \
            np.max([self.poni.pixel1, self.poni.pixel2]) / 2.  # / 2.
        tth_max = np.rad2deg(np.arctan(r / d))  # * 2.  # * 10.
        print("two theta max for integration = {:.3f} ".format(tth_max))
        return tth_max

    def integrate_to_1d(self, **kwargs):
        n_azi_pnts = self.calculate_n_azi_pnts()  # * 2 reduced number for Mar345 data
        radial_range = (0., self.calculate_max_twotheta())
        tth, intensity = self.poni.integrate1d(
            self.img, n_azi_pnts, radial_range=radial_range,
            mask=self.mask, unit="2th_deg", polarization_factor=0.99,
            method='csr', **kwargs)
        """
        self.tth = tth
        self.intensity = intensity
        """
        return tth, intensity

    def integrate_to_cake(self, **kwargs):
        t_start = time.time()
        n_azi_pnts = self.calculate_n_azi_pnts() * 2
        radial_range = (0., self.calculate_max_twotheta())
        intensity_cake, tth_cake, chi_cake = self.poni.integrate2d(
            self.img, n_azi_pnts, 360, unit="2th_deg", method='csr',
            radial_range=radial_range, polarization_factor=0.99, mask=self.mask,
            **kwargs)
        print("Caking takes {0:.2f}s".format(time.time() - t_start))
        self.intensity_cake = intensity_cake
        self.tth_cake = tth_cake
        self.chi_cake = chi_cake

    def get_pattern(self):
        if self.tth is None:
            return None, None
        else:
            return self.tth, self.intensity

    def get_cake(self):
        if self.tth_cake is None:
            return None, None, None
        else:
            return self.intensity_cake, self.tth_cake, self.chi_cake

    def set_mask(self, range):
        if self.img is None:
            return False
        masked = ma.masked_where(
            (self.img <= range[0]) | (self.img >= range[1]), self.img)
        self.mask = masked.mask

    def write_to_npy(self, chi_filen_wo_ext_in_temp):
        """
        filen = base filename without extension
        """
        f_tth = chi_filen_wo_ext_in_temp + '.tth.cake.npy'
        f_chi = chi_filen_wo_ext_in_temp + '.chi.cake.npy'
        f_int = chi_filen_wo_ext_in_temp + '.int.cake.npy'

    def read_cake_from_tempfile(self, temp_dir=None):
        tth_filen, azi_filen, int_filen = \
            self.make_temp_filenames(temp_dir=temp_dir)
        if os.path.exists(tth_filen) and os.path.exists(azi_filen) and \
                os.path.exists(int_filen):
            self.tth_cake = np.load(tth_filen)
            self.chi_cake = np.load(azi_filen)
            self.intensity_cake = np.load(int_filen)
            return True
        else:
            return False

    def make_temp_filenames(self, temp_dir=None):
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        tth_filen = make_filename(self.img_filename, 'tth.cake.npy',
                                  temp_dir=temp_dir)
        azi_filen = make_filename(self.img_filename, 'azi.cake.npy',
                                  temp_dir=temp_dir)
        int_filen = make_filename(self.img_filename, 'int.cake.npy',
                                  temp_dir=temp_dir)
        return tth_filen, azi_filen, int_filen

    def write_temp_cakefiles(self, temp_dir):
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        tth_filen, azi_filen, int_filen = self.make_temp_filenames(
            temp_dir=temp_dir)
        np.save(tth_filen, self.tth_cake)
        np.save(azi_filen, self.chi_cake)
        np.save(int_filen, self.intensity_cake)
