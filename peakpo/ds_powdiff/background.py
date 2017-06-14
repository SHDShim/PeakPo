import numpy as np


def fit_bg_cheb_auto(x, y_obs, n_points=20, n_iteration=10, n_cheborder=20,
                     accurate=True):
    """
    this returns cheb parameter for fitted background
    best for synchrotron XRD is:
        N_points = 20, N_iteration = 10, N_cheborder = 20
    :param x: x
    :param y_obs: observed y
    :param n_points:
    :param n_iteration:
    :param n_cheborder:
    :param accurate:
    """
    y_bg_smooth = smooth_bruckner(x, y_obs, n_points, n_iteration)

    # get cheb input parameters
    x_cheb = 2. * (x - x[0]) / (x[-1] - x[0]) - 1.
    cheb_parameters = np.polynomial.chebyshev.chebfit(
        x_cheb, y_bg_smooth, n_cheborder)
    if accurate:
        return np.polynomial.chebyshev.chebval(x_cheb, cheb_parameters)
    else:
        return cheb_parameters


def smooth_bruckner(x, y_obs, n_smooth, n_iter):
    y_original = y_obs

    n_data = y_obs.size
    n = n_smooth
    y = np.empty(n_data + n + n)

    y[n:n + n_data] = y_original[0:n_data]
    y[0:n].fill(y_original[n])
    y[n + n_data:n_data + n + n].fill(y_original[-1])
    y_new = y

    y_avg = np.average(y)
    y_min = np.min(y)

    y_c = y_avg + 2. * (y_avg - y_min)

    y[np.where(y > y_c)] = y_c

    for j in range(0, n_iter):
        for i in range(n, n_data - 1 - n - 1):
            y_new[i] = np.min([y[i], np.average(y[i - n:i + n + 1])])
        y = y_new

    return y[n:n + n_data]
