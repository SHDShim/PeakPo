from PIL import Image
import numpy.ma as ma
import numpy as np
import pyFAI
import matplotlib.pyplot as plt


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
        data = Image.open(self.img_filename)
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
        return int(max_dist)

    def calculate_max_twotheta(self):
        d = self.poni.dist
        r = self.calculate_n_azi_pnts() * \
            np.max([self.poni.pixel1, self.poni.pixel2])
        tth_max = np.rad2deg(np.arctan(r / d))
        return tth_max

    def integrate_to_1d(self, **kwargs):
        n_azi_pnts = self.calculate_n_azi_pnts() * 2
        radial_range = (0., self.calculate_max_twotheta())
        tth, intensity = self.poni.integrate1d(
            self.img, n_azi_pnts, radial_range=radial_range,
            mask=self.mask, unit="2th_deg", method='csr',
            **kwargs)
        self.tth = tth
        self.intensity = intensity

    def integrate_to_cake(self, **kwargs):
        n_azi_pnts = self.calculate_n_azi_pnts() * 2
        radial_range = (0., self.calculate_max_twotheta())
        intensity_cake, tth_cake, chi_cake = self.poni.integrate2d(
            self.img, n_azi_pnts, 360, unit="2th_deg", method='csr',
            radial_range=radial_range, mask=self.mask,
            **kwargs)
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
