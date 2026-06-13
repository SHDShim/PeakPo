import numpy as np
import numpy.ma as ma


def convert_tth(tth, wl1, wl2):
    if wl1 == wl2:
        return tth
    else:
        dsp = wl1 / np.sin(np.deg2rad(tth))
        tth_new = np.rad2deg(np.arcsin(wl2 / dsp))
        return tth_new


def cal_dspacing(symmetry, h, k, l, a, b, c, alpha, beta, gamma):

    if symmetry == 'cubic':
        dsp = 1. / np.sqrt((h * h + k * k + l * l) / (a * a))
    elif symmetry == 'hexagonal':
        dsp = 1. / np.sqrt((4.0 / 3.0) * (h * h + h * k + k * k) / (a * a)
                           + l * l / (c * c))
    elif symmetry == 'tetragonal':
        dsp = 1. / np.sqrt(((h * h) + (k * k)) / (a * a) + (l * l) / (c * c))
    elif symmetry == 'orthorhombic':
        dsp = 1. / np.sqrt((h * h) / (a * a) + (k * k) / (b * b) + (l * l) / (c * c))
    elif symmetry == 'monoclinic':
        dsp = np.sin(np.radians(beta)) / np.sqrt(h * h / a / a +
                                                 k * k * ((np.sin(np.radians(beta)))**2.) / b / b +
                                                 l * l / c / c - 2. * h * l * np.cos(np.radians(beta)) / a / c)
    elif symmetry == 'triclinic':
        v = cal_UnitCellVolume(symmetry, a, b, c, alpha, beta, gamma)
        s11 = (b * c * np.sin(np.radians(alpha)))**2.
        s22 = (a * c * np.sin(np.radians(beta)))**2.
        s33 = (a * b * np.sin(np.radians(gamma)))**2.
        s12 = a * b * c**2. * (np.cos(np.radians(alpha))
                               * np.cos(np.radians(beta)) - np.cos(np.radians(gamma)))
        s23 = a**2. * b * c * (np.cos(np.radians(beta))
                               * np.cos(np.radians(gamma)) - np.cos(np.radians(alpha)))
        s13 = a * b**2. * c * (np.cos(np.radians(gamma))
                               * np.cos(np.radians(alpha)) - np.cos(np.radians(beta)))
        dsp = v / np.sqrt(s11 * h**2. + s22 * k**2. + s33 * l**2.
                          + 2. * s12 * h * k + 2. * s23 * k * l + 2. * s13 * h * l)
    else:
        dsp = []
    return dsp


def cal_UnitCellVolume(symmetry, a, b, c, alpha, beta, gamma):
    """
    calculate Unit cell volume.
    No matter what the symmetry is all 6 parameters are required, but
        depending on symmetry, some unit-cell parameters will not be used.
    """
    v = a * b * c  # works for cubic, tetragonal, orthorhombic

    if (symmetry == 'hexagonal'):
        v = v * np.sqrt(3.) / 2.
    elif (symmetry == 'monoclinic'):
        v = v * np.sin(np.radians(beta))
    elif (symmetry == 'triclinic'):
        v = v * np.sqrt(1. - (np.cos(np.radians(alpha)))**2.
                        - (np.cos(np.radians(beta)))**2. - (np.cos(np.radians(gamma)))**2.
                        + 2. * np.cos(np.radians(alpha)) * np.cos(np.radians(beta))
                        * np.cos(np.radians(gamma)))
    return v

# The following six functions are adapted from xrayutilities python package


def read_csvlplt(filename, normalize=True):
    # Columns are X I(obs) I(calc) I(bkg) Obs-Calc cum-chi**2 refpos ref-phase ref-hkl
    data = np.genfromtxt(filename, skip_header=5, delimiter=',', unpack=True)

    if normalize:
        ymax = data[2].max()
    else:
        ymax = 1.0

    return data[1], data[2] / ymax, data[3] / ymax, data[4] / ymax, data[5] / ymax, data[7], data[8]
#    return x, yobs, yfit, ybg, ydiff, xbar, ybar


def mask_gaps(x):
    # To find abnormal gaps in twotheta
    pnts_l = x[0: x.size - 2]
    pnts_h = x[1: x.size - 1]
    gaps = pnts_h - pnts_l
    medi = np.median(gaps)

    idx = np.nonzero(gaps > medi * 2.)

    xmasked = ma.array(x)
    xmasked[idx] = ma.masked

    return xmasked
