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
    y_original = np.asarray(y_obs, dtype=float)
    n_data = y_original.size
    if n_data == 0:
        return y_original
    n = max(int(n_smooth), 1)
    n_iter = max(int(n_iter), 0)
    y = np.empty(n_data + 2 * n, dtype=float)
    y[n:n + n_data] = y_original
    left_idx = min(n, n_data - 1)
    y[:n].fill(y_original[left_idx])
    y[n + n_data:].fill(y_original[-1])
    y_avg = np.average(y)
    y_min = np.min(y)
    y_c = y_avg + 2.0 * (y_avg - y_min)
    y = np.minimum(y, y_c)
    kernel = np.ones(2 * n + 1, dtype=float) / float(2 * n + 1)
    core_slice = slice(n, n + n_data)
    for _ in range(n_iter):
        y_avg_window = np.convolve(y, kernel, mode="same")
        y[core_slice] = np.minimum(y[core_slice], y_avg_window[core_slice])
    return y[core_slice]
