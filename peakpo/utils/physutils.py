import numpy as np
import scipy.constants as const

def convert_wl_to_energy(wavelength):
    """
    wavelength in anstrom
    """
    return np.ceil(const.speed_of_light * const.Planck /
           const.electron_volt / (wavelength * 1.e-10)) * 1.e-3
