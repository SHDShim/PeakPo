import statsmodels.api as sm
from statsmodels.formula.api import ols
import statsmodels.stats.outliers_influence

import pandas as pd
import numpy as np

from uncertainties import ufloat
import uncertainties.umath as umath

from lmfit import Minimizer, Parameters, report_fit


def cal_twoth(dsp, wavelength):
    """
    dsp = d-spacing
    wavelength = wavelength, can we replace with get_base_ptn_wavelength()
    returns twoth
    """
    return 2. * np.rad2deg(np.arcsin(wavelength/2./dsp))


def make_output_table(res_lin, res_nlin, data_df):
    """
    res_lin = output from linear fit using statsmodels
    res_nlin = output from non-linear fit using lmfit
    data_df = fit result data in pandas dataframe
    returns pandas dataframe with data_df and point by point statistics
    """
    output = data_df.copy()
    output['twoth residue'] = res_nlin.residual
    out = statsmodels.stats.outliers_influence.OLSInfluence(res_lin)
    # influence for the fit result, 1 ~ large influence, 0 ~ no influence.
    output['hat'] = out.hat_diag_factor
    # how much the parameter would change if deleted
    output['Rstudent'] = out.resid_studentized
    # deletion diagnostic giving the change in the predicted value y
    # upon deletion of the data point as a multiple of the
    # standard deviation for Q^2
    output['dfFits'] = out.dffits[0]
    # normalized residual
    output['dfBetas'] = np.asarray(out.dfbetas)[:, 1]

    return output


def cal_dspacing(symmetry, h, k, l, a, b, c, alpha, beta, gamma):

    if symmetry == 'cubic':
        dsp = 1. / np.sqrt((h * h + k * k + l * l) / (a * a))
    elif symmetry == 'hexagonal':
        dsp = 1. / np.sqrt((4.0 / 3.0) * (h * h + h * k + k * k) / (a * a) +
                           l * l / (c * c))
    elif symmetry == 'tetragonal':
        dsp = 1. / np.sqrt(((h * h) + (k * k)) / (a * a) + (l * l) / (c * c))
    elif symmetry == 'orthorhombic':
        dsp = 1. / np.sqrt((h * h) / (a * a) + (k * k) / (b * b) +
                           (l * l) / (c * c))
    """
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
    """
    return dsp


"""
cubic
"""


def fit_cubic_cell(data_df, wavelength, verbose=True):
    """
    data_df = data in pandas DataFrame
    wavelength = wavelength, can we get this from .get_bast_ptn_wavelength
    verbose
    returns unit cell fit results and statistics for a cubic cell
    """

    res_lin = fit_l_cubic_cell(data_df, verbose=verbose)
    a_lin_star = ufloat(res_lin.params['Prefactor'], res_lin.bse['Prefactor'])
    a_lin = umath.sqrt(1./a_lin_star)

    res_nlin = fit_nl_cubic_cell(data_df, a_lin.nominal_value,
                                 wavelength, verbose=verbose)
    a_res_nlin = ufloat(res_nlin.params['a'].value, res_nlin.params['a'].stderr)
    v_res_nlin = a_res_nlin * a_res_nlin * a_res_nlin
    a_nlin = a_res_nlin.nominal_value
    s_a_nlin = a_res_nlin.std_dev
    v_nlin = v_res_nlin.nominal_value
    s_v_nlin = v_res_nlin.std_dev

    if np.abs(a_lin.nominal_value - a_nlin) > a_lin.std_dev:
        print('Difference between nonlinear and linear results exceed the error bar.')

    return a_nlin, s_a_nlin, v_nlin, s_v_nlin, res_lin, res_nlin


def fit_l_cubic_cell(data_df, verbose=True):
    """
    subfuction to return linear fitting result using statsmodels
    data_df = data in pandas DataFrame
    """
    prefactor = data_df['h'] * data_df['h'] + data_df['k'] * data_df['k'] + \
        data_df['l'] * data_df['l']
    q = data_df['Q'].values
    df = pd.DataFrame(list(zip(prefactor, q)), columns=['Prefactor', 'Q'])
    mod = ols('Q ~ Prefactor', data=df)
    res_lin = mod.fit()
    if verbose:
        print(res_lin.summary())
    return res_lin


def fcn2min_cubic(pars, h, k, l, twoth_data, wavelength):
    """
    function for non-linear regression
    pars = cell parameters
    h, k, l = Miller index
    twoth_data = twoth data
    wavelength = this can be replaced with .get_base_ptn_wavelength()
    """
    hkl_sq = h * h + k * k + l * l
    param = pars.valuesdict()
    a = param['a']
    inv_dsp_sq = hkl_sq / (a * a)
    model = cal_twoth(np.sqrt(1. / inv_dsp_sq), wavelength)
    return model - twoth_data


def fit_nl_cubic_cell(data_df, a, wavelength, verbose=True):
    """
    perform non-linear fit
    data_df = data in pandas DataFrame
    a = cell parameter
    wavelength = this ca be replaced with .get_base_ptn_wavelength()
    """
    h = data_df['h']
    k = data_df['k']
    l = data_df['l']
    param = Parameters()
    param.add('a', value=a, min=0)
    twoth_data = data_df['twoth']
    minner = Minimizer(fcn2min_cubic, param,
                       fcn_args=(h, k, l, twoth_data, wavelength))
    result = minner.minimize()
    # calculate final result

    # write error report
    if verbose:
        report_fit(result)

    return result


"""
tetragonal
"""


def fit_tetragonal_cell(data_df, wavelength, verbose=True):
    """
    data_df = data in pandas DataFrame
    wavelength = wavelength, can we get this from .get_bast_ptn_wavelength
    verbose
    returns unit cell fit results and statistics for a tetragonal cell
    """
    res_lin = fit_l_tetragonal_cell(data_df, verbose=verbose)
    a_lin_star = ufloat(res_lin.params['Prefactor0'],
                        res_lin.bse['Prefactor0'])
    c_lin_star = ufloat(res_lin.params['Prefactor1'],
                        res_lin.bse['Prefactor1'])
    a_lin = umath.sqrt(1./a_lin_star)
    c_lin = umath.sqrt(1./c_lin_star)

    if verbose:
        print(a_lin, c_lin)

    res_nlin = fit_nl_tetragonal_cell(data_df, a_lin.nominal_value,
                                      c_lin.nominal_value,
                                      wavelength, verbose=verbose)

    a_res_nlin = ufloat(res_nlin.params['a'].value,
                        res_nlin.params['a'].stderr)
    c_res_nlin = ufloat(res_nlin.params['c'].value,
                        res_nlin.params['c'].stderr)
    v_res_nlin = a_res_nlin * a_res_nlin * c_res_nlin
    a_nlin = a_res_nlin.nominal_value
    s_a_nlin = a_res_nlin.std_dev
    c_nlin = c_res_nlin.nominal_value
    s_c_nlin = c_res_nlin.std_dev
    v_nlin = v_res_nlin.nominal_value
    s_v_nlin = v_res_nlin.std_dev

    if verbose:
        print(a_res_nlin, c_res_nlin)

    if np.abs(a_lin.nominal_value - a_nlin) > a_lin.std_dev:
        print('Difference between nonlinear and linear results exceed the error bar.')

    return a_nlin, s_a_nlin, c_nlin, s_c_nlin, v_nlin, s_v_nlin, res_lin, res_nlin


def fit_l_tetragonal_cell(data_df, verbose=True):
    """
    subfuction to return linear fitting result using statsmodels
    data_df = data in pandas DataFrame
    """
    prefactor0 = data_df['h'] * data_df['h'] + data_df['k'] * data_df['k']
    prefactor1 = data_df['l'] * data_df['l']
    q = data_df['Q'].values
    df = pd.DataFrame(list(zip(prefactor0, prefactor1, q)),
                      columns=['Prefactor0', 'Prefactor1', 'Q'])
    mod = ols('Q ~ Prefactor0 + Prefactor1', data=df)
    res_lin = mod.fit()
    if verbose:
        print(res_lin.summary())
    return res_lin


def fcn2min_tetragonal(pars, h, k, l, twoth_data, wavelength):
    """
    function for non-linear regression
    pars = cell parameters
    h, k, l = Miller index
    twoth_data = twoth data
    wavelength = this can be replaced with .get_base_ptn_wavelength()
    """
    hk_sq = h * h + k * k
    l_sq = l * l
    param = pars.valuesdict()
    a = param['a']
    c = param['c']
    inv_dsp_sq = hk_sq / (a * a) + l_sq / (c * c)
    model = cal_twoth(np.sqrt(1. / inv_dsp_sq), wavelength)
    return model - twoth_data


def fit_nl_tetragonal_cell(data_df, a, c, wavelength, verbose=True):
    """
    perform non-linear fit
    data_df = data in pandas DataFrame
    a, c = cell parameter
    wavelength = this ca be replaced with .get_base_ptn_wavelength()
    """
    h = data_df['h']
    k = data_df['k']
    l = data_df['l']
    param = Parameters()
    param.add('a', value=a, min=0)
    param.add('c', value=c, min=0)
    twoth_data = data_df['twoth']
    minner = Minimizer(fcn2min_tetragonal, param,
                       fcn_args=(h, k, l, twoth_data, wavelength))
    result = minner.minimize()
    # calculate final result

    # write error report
    if verbose:
        report_fit(result)

    return result


"""
hexagonal
"""


def fit_hexagonal_cell(data_df, wavelength, verbose=True):
    """
    data_df = data in pandas DataFrame
    wavelength = wavelength, can we get this from .get_bast_ptn_wavelength
    verbose
    returns unit cell fit results and statistics for a hexagonal cell
    """
    res_lin = fit_l_hexagonal_cell(data_df, verbose=verbose)
    a_lin_star = ufloat(res_lin.params['Prefactor0'],
                        res_lin.bse['Prefactor0'])
    c_lin_star = ufloat(res_lin.params['Prefactor1'],
                        res_lin.bse['Prefactor1'])
    a_lin = umath.sqrt(1./a_lin_star)
    c_lin = umath.sqrt(1./c_lin_star)

    if verbose:
        print(a_lin, c_lin)

    res_nlin = fit_nl_hexagonal_cell(data_df, a_lin.nominal_value,
                                     c_lin.nominal_value,
                                     wavelength, verbose=verbose)

    a_res_nlin = ufloat(res_nlin.params['a'].value,
                        res_nlin.params['a'].stderr)
    c_res_nlin = ufloat(res_nlin.params['c'].value,
                        res_nlin.params['c'].stderr)
    v_res_nlin = a_res_nlin * a_res_nlin * c_res_nlin * np.sqrt(3.)/2.
    a_nlin = a_res_nlin.nominal_value
    s_a_nlin = a_res_nlin.std_dev
    c_nlin = c_res_nlin.nominal_value
    s_c_nlin = c_res_nlin.std_dev
    v_nlin = v_res_nlin.nominal_value
    s_v_nlin = v_res_nlin.std_dev

    if verbose:
        print(a_res_nlin, c_res_nlin)

    if np.abs(a_lin.nominal_value - a_nlin) > a_lin.std_dev:
        print('Difference between nonlinear and linear results exceed the error bar.')

    return a_nlin, s_a_nlin, c_nlin, s_c_nlin, \
        v_nlin, s_v_nlin, res_lin, res_nlin


def fit_l_hexagonal_cell(data_df, verbose=True):
    """
    subfuction to return linear fitting result using statsmodels
    data_df = data in pandas DataFrame
    """
    prefactor0 = 4./3. * (data_df['h'] * data_df['h'] +
                          data_df['h'] * data_df['k'] +
                          data_df['k'] * data_df['k'])
    prefactor1 = data_df['l'] * data_df['l']
    q = data_df['Q'].values
    df = pd.DataFrame(list(zip(prefactor0, prefactor1, q)),
                      columns=['Prefactor0', 'Prefactor1', 'Q'])
    mod = ols('Q ~ Prefactor0 + Prefactor1', data=df)
    res_lin = mod.fit()
    if verbose:
        print(res_lin.summary())
    return res_lin


def fcn2min_hexagonal(pars, h, k, l, twoth_data, wavelength):
    """
    function for non-linear regression
    pars = cell parameters
    h, k, l = Miller index
    twoth_data = twoth data
    wavelength = this can be replaced with .get_base_ptn_wavelength()
    """
    hk_sq = 4./3. * (h * h + h * k + k * k)
    l_sq = l * l
    param = pars.valuesdict()
    a = param['a']
    c = param['c']
    inv_dsp_sq = hk_sq / (a * a) + l_sq / (c * c)
    model = cal_twoth(np.sqrt(1. / inv_dsp_sq), wavelength)
    return model - twoth_data


def fit_nl_hexagonal_cell(data_df, a, c, wavelength, verbose=True):
    """
    perform non-linear fit
    data_df = data in pandas DataFrame
    a, c = cell parameter
    wavelength = this ca be replaced with .get_base_ptn_wavelength()
    """
    h = data_df['h']
    k = data_df['k']
    l = data_df['l']
    param = Parameters()
    param.add('a', value=a, min=0)
    param.add('c', value=c, min=0)
    twoth_data = data_df['twoth']
    minner = Minimizer(fcn2min_hexagonal, param,
                       fcn_args=(h, k, l, twoth_data, wavelength))
    result = minner.minimize()
    # calculate final result

    # write error report
    if verbose:
        report_fit(result)

    return result


"""
orthorhombic
"""


def fit_orthorhombic_cell(data_df, wavelength, verbose=True):
    """
    data_df = data in pandas DataFrame
    wavelength = wavelength, can we get this from .get_bast_ptn_wavelength
    verbose
    returns unit cell fit results and statistics for an orthorhombic cell
    """
    res_lin = fit_l_orthorhombic_cell(data_df, verbose=verbose)
    a_lin_star = ufloat(res_lin.params['Prefactor0'],
                        res_lin.bse['Prefactor0'])
    b_lin_star = ufloat(res_lin.params['Prefactor1'],
                        res_lin.bse['Prefactor1'])
    c_lin_star = ufloat(res_lin.params['Prefactor2'],
                        res_lin.bse['Prefactor2'])
    a_lin = umath.sqrt(1./a_lin_star)
    b_lin = umath.sqrt(1./b_lin_star)
    c_lin = umath.sqrt(1./c_lin_star)

    if verbose:
        print(a_lin, b_lin, c_lin)

    res_nlin = fit_nl_orthorhombic_cell(data_df, a_lin.nominal_value,
                                        b_lin.nominal_value,
                                        c_lin.nominal_value,
                                        wavelength, verbose=verbose)

    a_res_nlin = ufloat(res_nlin.params['a'].value,
                        res_nlin.params['a'].stderr)
    b_res_nlin = ufloat(res_nlin.params['b'].value,
                        res_nlin.params['b'].stderr)
    c_res_nlin = ufloat(res_nlin.params['c'].value,
                        res_nlin.params['c'].stderr)
    v_res_nlin = a_res_nlin * b_res_nlin * c_res_nlin
    a_nlin = a_res_nlin.nominal_value
    s_a_nlin = a_res_nlin.std_dev
    b_nlin = b_res_nlin.nominal_value
    s_b_nlin = b_res_nlin.std_dev
    c_nlin = c_res_nlin.nominal_value
    s_c_nlin = c_res_nlin.std_dev
    v_nlin = v_res_nlin.nominal_value
    s_v_nlin = v_res_nlin.std_dev

    if verbose:
        print(a_res_nlin, b_res_nlin, c_res_nlin)

    if np.abs(a_lin.nominal_value - a_nlin) > a_lin.std_dev:
        print('Difference between nonlinear and linear results exceed the error bar.')

    return a_nlin, s_a_nlin, b_nlin, s_b_nlin, c_nlin, s_c_nlin, \
        v_nlin, s_v_nlin, res_lin, res_nlin


def fit_l_orthorhombic_cell(data_df, verbose=True):
    """
    subfuction to return linear fitting result using statsmodels
    data_df = data in pandas DataFrame
    """
    prefactor0 = data_df['h'] * data_df['h']
    prefactor1 = data_df['k'] * data_df['k']
    prefactor2 = data_df['l'] * data_df['l']
    q = data_df['Q'].values
    df = pd.DataFrame(list(zip(prefactor0, prefactor1, prefactor2, q)),
                      columns=['Prefactor0', 'Prefactor1', 'Prefactor2', 'Q'])
    mod = ols('Q ~ Prefactor0 + Prefactor1 + Prefactor2', data=df)
    res_lin = mod.fit()
    if verbose:
        print(res_lin.summary())
    return res_lin


def fcn2min_orthorhombic(pars, h, k, l, twoth_data, wavelength):
    """
    function for non-linear regression
    pars = cell parameters
    h, k, l = Miller index
    twoth_data = twoth data
    wavelength = this can be replaced with .get_base_ptn_wavelength()
    """
    h_sq = h * h
    k_sq = k * k
    l_sq = l * l
    param = pars.valuesdict()
    a = param['a']
    b = param['b']
    c = param['c']
    inv_dsp_sq = h_sq / (a * a) + k_sq / (b * b) + l_sq / (c * c)
    model = cal_twoth(np.sqrt(1. / inv_dsp_sq), wavelength)
    return model - twoth_data


def fit_nl_orthorhombic_cell(data_df, a, b, c, wavelength, verbose=True):
    """
    perform non-linear fit
    data_df = data in pandas DataFrame
    a, b, c = cell parameter
    wavelength = this ca be replaced with .get_base_ptn_wavelength()
    """
    h = data_df['h']
    k = data_df['k']
    l = data_df['l']
    param = Parameters()
    param.add('a', value=a, min=0)
    param.add('b', value=b, min=0)
    param.add('c', value=c, min=0)
    twoth_data = data_df['twoth']
    minner = Minimizer(fcn2min_orthorhombic, param,
                       fcn_args=(h, k, l, twoth_data, wavelength))
    result = minner.minimize()
    # calculate final result

    # write error report
    if verbose:
        report_fit(result)

    return result
