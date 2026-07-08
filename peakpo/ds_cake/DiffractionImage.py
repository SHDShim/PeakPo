import os
import sys
import time
from PIL import Image
import fabio
import numpy.ma as ma
import numpy as np
import pyFAI
from dioptas.model.Configuration import Configuration
# import matplotlib.pyplot as plt
import datetime
import collections
import re

from ..utils import make_filename, extract_extension


def _disable_dioptas_file_watcher_on_windows():
    if not sys.platform.startswith("win"):
        return
    try:
        from dioptas.model.util.NewFileWatcher import NewFileInDirectoryWatcher
    except Exception:
        return
    if getattr(NewFileInDirectoryWatcher, "_peakpo_windows_disabled", False):
        return

    def _no_op(self, *args, **kwargs):
        try:
            self.active = False
        except Exception:
            pass

    NewFileInDirectoryWatcher.activate = _no_op
    NewFileInDirectoryWatcher.deactivate = _no_op
    NewFileInDirectoryWatcher._start_observing = _no_op
    NewFileInDirectoryWatcher._stop_observing = _no_op
    NewFileInDirectoryWatcher._peakpo_windows_disabled = True


_disable_dioptas_file_watcher_on_windows()


class DiffImg(object):
    def __init__(self):
        self.img_filename = None
        self.poni = None
        self.img = None
        # mask for self.img, not self.intensity_cake (cake image)
        self.mask = None 
        # self.intensity is for intersity of 1D pattern
        self.intensity = None
        self.tth = None
        # the following three are for cake
        self.intensity_cake = None
        self.tth_cake = None
        self.chi_cake = None
        self._dioptas_config = None

    def load(self, img_filename):
        self.img_filename = img_filename
        self._dioptas_config = Configuration()
        self._dioptas_config.img_model.blockSignals(True)
        try:
            self._dioptas_config.img_model.load(self.img_filename, 0)
        finally:
            self._dioptas_config.img_model.blockSignals(False)
        self.img = np.asarray(self._dioptas_config.img_model.img_data)
        print(str(datetime.datetime.now())[:-7], 
                ": Load ", self.img_filename)

    def shutdown(self):
        config = self._dioptas_config
        if config is None:
            return
        self._dioptas_config = None

        img_model = getattr(config, "img_model", None)
        watcher = getattr(img_model, "_directory_watcher", None)
        if watcher is not None:
            try:
                watcher.deactivate()
            except Exception:
                pass

    def histogram(self):
        import matplotlib.pyplot as plt

        if self.img is None:
            return
        f, ax = plt.subplots(figsize=(10, 4))
        ax.hist(self.img.ravel(), bins=256, fc='k', ec='k')
        f.show()

    def show(self, clim=(0, 8e3)):
        import matplotlib.pyplot as plt
        
        f, ax = plt.subplots(figsize=(10, 10))
        cax = ax.imshow(self.img, origin="lower", cmap="gray_r", clim=clim)
        cbar = f.colorbar(cax, orientation='horizontal')
        f.show()

    def set_calibration(self, poni_filename):
        self.poni = pyFAI.load(poni_filename)
        if self._dioptas_config is None:
            self._dioptas_config = Configuration()
        self._dioptas_config.calibration_model.load(poni_filename)
        print(str(datetime.datetime.now())[:-7], 
            ": Load ", poni_filename)

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
        """
        2019/06/20 decrease r by a factor of 2 and
        decrease tth_max by a factor of 2.
        """
        d = self.poni.dist
        r = self.calculate_n_azi_pnts() * \
            np.max([self.poni.pixel1, self.poni.pixel2]) / 2.  # / 2.
        tth_max = np.rad2deg(np.arctan(r / d))  # * 2.  # * 10.
        print(str(datetime.datetime.now())[:-7], 
            ": Two theta max for integration = {:.3f} ".format(tth_max))
        return tth_max

    def integrate_to_1d(self, **kwargs):
        """
        Integrate to 1D pattern
        self.mask is used for self.img
        """
        n_azi_pnts = self.calculate_n_azi_pnts()  # * 2 reduced number for Mar345 data
        radial_range = kwargs.pop(
            "radial_range", (0., self.calculate_max_twotheta()))

        # integrate to 1 D using pyFAI
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
        """
        Make cake image from original img data.
        Note that self.mask is used here and therefore self.mask
        should be for self.img
        """
        t_start = time.time()
        if self._dioptas_config is None:
            self.load(self.img_filename)
        if self.poni is None:
            raise RuntimeError("Cannot make cake without loaded PONI calibration.")

        calibration_model = self._dioptas_config.calibration_model
        radial_points = calibration_model.calculate_number_of_pattern_points(
            self.img.shape, 2)
        mask = self.mask
        if mask is not None and np.asarray(mask).shape != self.img.shape:
            mask = None
        calibration_model.integrate_2d(
            mask=mask,
            rad_points=radial_points,
            azimuth_points=360,
            azimuth_range=getattr(self._dioptas_config, "cake_azimuth_range", None),
            **kwargs)
        intensity_cake = calibration_model.cake_img
        tth_cake = calibration_model.cake_tth
        chi_cake = calibration_model.cake_azi
        print(str(datetime.datetime.now())[:-7], 
            ": Caking takes {0:.2f}s".format(time.time() - t_start))
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
        
    def get_img_zrange(self):
        if self.img is None:
            return None
        else:
            zmin = self.img.min()
            zmax = self.img.max()
            return [zmin, zmax]

    def set_mask(self, range):
        """
        Calculate mask array for self.img.
        Mask pixels below range[0] and pixels above range[1]
        """
        if (self.img is None):
            # here returns array used for mask without any masked points
            self.mask = None
            return
        if (range is None):
            self.mask = np.zeros_like(self.img, dtype=bool)
            return
        # print('set_mask', self.img.max(), range)
        masked = ma.masked_where(
            (self.img < range[0]) | (self.img > range[1]), self.img)
        self.mask = masked.mask
        #self.integrate_to_cake()

    def get_mask(self):
        """
        Get mask for self.img
        If there is no img or mask, then return None
        """
        if (self.img is None):
            self.mask = None
        return self.mask
        
    def get_mask_range(self):
        """
        Return the numeric range spanned by the *unmasked* pixels.

        Returns:
            [vmin, vmax] (floats) for the unmasked data, or None if
            self.img or self.mask is missing or there are no unmasked pixels.
        """
        if self.mask is None or self.img is None:
            return None

        # Ensure mask is a boolean array of same shape as img
        mask = self.mask
        try:
            # If mask came from a MaskedArray, it might be a boolean array or MaskedConstant
            if np.ma.isMaskedArray(mask):
                mask = mask.mask
        except Exception:
            pass

        mask = np.asarray(mask, dtype=bool)

        # Compute unmasked boolean selection
        unmasked_sel = ~mask

        # If no unmasked pixels, nothing to return
        if not np.any(unmasked_sel):
            return None

        # Extract unmasked data, ignore NaN/Inf safely
        unmasked_vals = self.img[unmasked_sel]
        # Mask invalid float values
        unmasked_vals = unmasked_vals[np.isfinite(unmasked_vals)]

        if unmasked_vals.size == 0:
            return None

        vmin = float(np.nanmin(unmasked_vals))
        vmax = float(np.nanmax(unmasked_vals))

        return [vmin, vmax]

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
