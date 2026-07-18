import numpy as np
import datetime
import copy
from lmfit.models import PolynomialModel, PseudoVoigtModel

DEFAULT_CENTER_HALF_RANGE = 0.05
DEFAULT_FWHM_MIN = 0.0
DEFAULT_FWHM_MAX = 0.05
DEFAULT_NL_MIN = 0.0
DEFAULT_NL_MAX = 1.0
MAX_BACKGROUND_ANCHOR_WEIGHT = 100.0
POSITIVE_PARAMETER_MIN = 1e-15
PEAK_PARAM_VARY_KEYS = {
    'amplitude': 'amplitude_vary',
    'center': 'center_vary',
    'sigma': 'sigma_vary',
    'fraction': 'fraction_vary',
}


def pseudo_voigt_amplitude_for_height(height, sigma, fraction=0.5):
    """Convert a target center height to lmfit PseudoVoigt integrated area."""
    sigma = float(sigma)
    if not np.isfinite(sigma) or sigma <= 0.0:
        return 0.0
    gaussian_factor = np.sqrt(np.log(2.0) / np.pi)
    lorentzian_factor = 1.0 / np.pi
    height_per_area = (
        (1.0 - float(fraction)) * gaussian_factor +
        float(fraction) * lorentzian_factor
    ) / sigma
    return float(height) / height_per_area


def normalize_peak_phase_name(phase_name):
    if not isinstance(phase_name, str):
        return phase_name
    phase_name = phase_name.strip()
    if phase_name.endswith(".jcpds"):
        phase_name = phase_name[:-len(".jcpds")]
    if ".ucfit" in phase_name:
        return phase_name.split(".ucfit", 1)[0]
    return phase_name


class Section(object):
    def __init__(self):
        self.x = None
        self.y_bgsub = None
        self.y_bg = None  # this is the bg from peakpo
        self.timestamp = None
        self.baseline_in_queue = []  # list of dict, value, constraints
        self.parameters = None
        self.fit_result = None
        self.fit_model = None
        self.peaks_in_queue = []  # list of dic, value, constraints
        self.background_anchor_ranges = []
        self.source_provenance = {}
        self.peakinfo = {}
        self._apply_peak_constraints_for_current_fit = True
        self._component_cache_token = None
        self._component_cache_bgsub = None
        self._component_cache_with_bg = None

    def get_xrange(self):
        return (self.x.min(), self.x.max())

    def get_yrange(self, bgsub=False):
        if bgsub:
            return (self.y_bgsub.min(), self.y_bgsub.max())
        else:
            return ((self.y_bgsub + self.y_bg).min(),
                    (self.y_bgsub + self.y_bg).max())

    def clear_queue(self):
        self.peaks_in_queue[:] = []
        self.baseline_in_queue[:] = []
        if not hasattr(self, "background_anchor_ranges"):
            self.background_anchor_ranges = []
        else:
            self.background_anchor_ranges[:] = []

    def invalidate_fit_result(self):
        """use with caution"""
        self.fit_result = None
        self.parameters = None
        self.fit_model = None
        self._invalidate_component_cache()

    def fitted(self):
        if (self.fit_result is None):
            return False
        else:
            return True

    def get_peak_positions(self):
        if self.get_number_of_peaks_in_queue() == 0:
            return []
        else:
            x_c_lst = []
            for peak in self.peaks_in_queue:
                x_c_lst.append(peak['center'])
            return x_c_lst

    def set(self, x, y_bgsub, y_bg):
        """
        it accepts sectioned x, y_bgsub, y_bg only
        """
        self.x = x
        self.y_bgsub = y_bgsub
        self.y_bg = y_bg
        self._invalidate_component_cache()

    def clone_for_editing(self):
        """
        Clone a saved section for editing without deep-copying large immutable
        arrays or lmfit results.
        """
        new_section = Section()
        new_section.x = self.x
        new_section.y_bgsub = self.y_bgsub
        new_section.y_bg = self.y_bg
        new_section.timestamp = self.timestamp
        new_section.baseline_in_queue = copy.deepcopy(self.baseline_in_queue)
        new_section.parameters = self.parameters
        new_section.fit_result = self.fit_result
        new_section.fit_model = self.fit_model
        new_section.peaks_in_queue = copy.deepcopy(self.peaks_in_queue)
        new_section.background_anchor_ranges = copy.deepcopy(
            getattr(self, "background_anchor_ranges", []))
        new_section.source_provenance = copy.deepcopy(
            getattr(self, "source_provenance", {}))
        new_section.peakinfo = copy.deepcopy(getattr(self, "peakinfo", {}))
        new_section._component_cache_token = self._component_cache_token
        new_section._component_cache_bgsub = self._component_cache_bgsub
        new_section._component_cache_with_bg = self._component_cache_with_bg
        return new_section

    def _invalidate_component_cache(self):
        self._component_cache_token = None
        self._component_cache_bgsub = None
        self._component_cache_with_bg = None

    def _get_component_cache_token(self):
        return (
            id(self.fit_result),
            id(self.x),
            id(self.y_bg),
            None if self.x is None else len(self.x),
            None if self.y_bg is None else len(self.y_bg),
        )

    def _array_on_section_x(self, values):
        if values is None or self.x is None:
            return None
        arr = np.asarray(values, dtype=float).reshape(-1)
        n_x = len(self.x)
        if n_x == 0 or arr.size == 0:
            return None
        if arr.size == n_x:
            return arr
        if arr.size > n_x:
            # lmfit results made with background anchors append anchor samples
            # after the section data; the first n_x values still match self.x.
            return arr[:n_x]
        return None

    def set_single_peak(self, x_center, fwhm, hkl=[0, 0, 0],
                        phase_name='unknown', constraint_defaults=None):
        if self.x is None or len(self.x) == 0:
            return False
        x_min = float(np.min(self.x))
        x_max = float(np.max(self.x))
        # Allow small numerical mismatch at boundaries.
        if len(self.x) > 1:
            tol = 0.5 * float(np.min(np.abs(np.diff(self.x))))
        else:
            tol = 0.0
        if (x_center > x_max + tol) or (x_center < x_min - tol):
            return False
        # Clamp near-boundary clicks into the valid section range.
        x_center = min(max(float(x_center), x_min), x_max)
        y_center = self.get_nearest_intensity(x_center)
        sigma = self.estimate_initial_peak_sigma(x_center, fwhm)
        peak = {}
        peak['center'] = x_center
        peak['amplitude'] = pseudo_voigt_amplitude_for_height(
            y_center, sigma, fraction=0.5)
        peak['sigma'] = sigma
        peak['fraction'] = 0.5
        peak['center_vary'] = True
        peak['amplitude_vary'] = True
        peak['sigma_vary'] = True
        peak['fraction_vary'] = True
        defaults = constraint_defaults or {}
        center_half_range = float(defaults.get(
            "center_half_range", DEFAULT_CENTER_HALF_RANGE))
        peak['center_min'] = x_center - center_half_range
        peak['center_max'] = x_center + center_half_range
        # These are template values only.  Optional limits must be enabled
        # deliberately for each peak before a constrained fit uses them.
        peak['center_min_enabled'] = False
        peak['center_max_enabled'] = False
        peak['sigma_min'] = float(defaults.get(
            "fwhm_min", DEFAULT_FWHM_MIN))
        peak['sigma_max'] = float(defaults.get(
            "fwhm_max", DEFAULT_FWHM_MAX))
        peak['sigma_min_enabled'] = False
        peak['sigma_max_enabled'] = False
        peak['amplitude_min'] = 0.0
        peak['amplitude_max'] = None
        peak['amplitude_max_enabled'] = False
        peak['amplitude_min_enabled'] = True
        peak['fraction_min'] = DEFAULT_NL_MIN
        peak['fraction_max'] = DEFAULT_NL_MAX
        peak['fraction_min_enabled'] = True
        peak['fraction_max_enabled'] = True
        peak['phasename'] = normalize_peak_phase_name(phase_name)
        peak['h'] = hkl[0]
        peak['k'] = hkl[1]
        peak['l'] = hkl[2]
        self.peaks_in_queue.append(peak)
        return True

    def estimate_initial_peak_sigma(self, x_center, fallback_sigma):
        """Estimate PseudoVoigt HWHM from local observed half-height crossings."""
        fallback_sigma = float(fallback_sigma)
        if not np.isfinite(fallback_sigma) or fallback_sigma <= 0.0:
            fallback_sigma = 0.01
        if self.x is None or self.y_bgsub is None or len(self.x) < 3:
            return fallback_sigma

        x = np.asarray(self.x, dtype=float)
        y = np.asarray(self.y_bgsub, dtype=float)
        finite = np.isfinite(x) & np.isfinite(y)
        if np.count_nonzero(finite) < 3:
            return fallback_sigma
        x = x[finite]
        y = y[finite]
        order = np.argsort(x)
        x = x[order]
        y = y[order]
        spacing_values = np.diff(x)
        spacing_values = spacing_values[spacing_values > 0.0]
        if spacing_values.size == 0:
            return fallback_sigma
        spacing = float(np.median(spacing_values))

        center = float(x_center)
        apex_radius = max(3.0 * fallback_sigma, 3.0 * spacing)
        apex_candidates = np.flatnonzero(np.abs(x - center) <= apex_radius)
        if apex_candidates.size == 0:
            return fallback_sigma
        peak_index = int(apex_candidates[np.argmax(y[apex_candidates])])

        crossing_radius = max(12.0 * fallback_sigma, 12.0 * spacing)
        window = np.flatnonzero(np.abs(x - x[peak_index]) <= crossing_radius)
        if window.size < 3:
            return fallback_sigma
        start = int(window[0])
        stop = int(window[-1])
        baseline = float(np.percentile(y[window], 10.0))
        peak_height = float(y[peak_index])
        if peak_height <= baseline:
            return fallback_sigma
        half_height = baseline + 0.5 * (peak_height - baseline)

        left = self._half_height_crossing(
            x, y, peak_index, start, half_height, direction=-1)
        right = self._half_height_crossing(
            x, y, peak_index, stop, half_height, direction=1)
        if left is None or right is None or right <= left:
            return fallback_sigma

        sigma = 0.5 * (right - left)
        if not np.isfinite(sigma) or sigma < 0.5 * spacing:
            return fallback_sigma
        return float(sigma)

    @staticmethod
    def _half_height_crossing(x, y, peak_index, limit, level, direction):
        index = int(peak_index)
        while index != int(limit):
            next_index = index + int(direction)
            y0 = float(y[index]) - float(level)
            y1 = float(y[next_index]) - float(level)
            if y0 == 0.0:
                return float(x[index])
            if y0 * y1 <= 0.0:
                if y1 == y0:
                    return 0.5 * float(x[index] + x[next_index])
                fraction = -y0 / (y1 - y0)
                return float(x[index] + fraction * (x[next_index] - x[index]))
            index = next_index
        return None

    def get_initial_peak_profiles(self, bgsub=False):
        """Return queued PseudoVoigt profiles before a fit result exists."""
        if self.x is None:
            return {}
        x = np.asarray(self.x, dtype=float)
        background = np.zeros_like(x)
        if not bgsub and self.y_bg is not None:
            background = np.asarray(self.y_bg, dtype=float)
        profiles = {}
        model = PseudoVoigtModel()
        for index, peak in enumerate(self.peaks_in_queue):
            params = model.make_params(
                amplitude=float(peak.get('amplitude', 0.0)),
                center=float(peak.get('center', 0.0)),
                sigma=max(float(peak.get('sigma', 0.01)), 1e-15),
                fraction=float(peak.get('fraction', 0.5)),
            )
            profiles[f"p{index:d}_"] = model.eval(params=params, x=x) + background
        return profiles

    def get_order_of_baseline_in_queue(self):
        return self.baseline_in_queue.__len__() - 1

    def set_baseline(self, poly_order):
        old_baseline = copy.deepcopy(self.baseline_in_queue)
        new_baseline = []
        for i in range(poly_order + 1):
            factor = {}
            factor['value'] = 0.
            factor['vary'] = True
            new_baseline.append(factor)
        if old_baseline.__len__() == -1:
            self.baseline_in_queue == new_baseline
            return
        if old_baseline.__len__() >= new_baseline.__len__():
            max_iter = new_baseline.__len__()
        else:
            max_iter = old_baseline.__len__()
        for i in range(max_iter):
            new_baseline[i] = old_baseline[i]
        self.baseline_in_queue = new_baseline

    def peaks_exist(self):
        if self.peaks_in_queue == []:
            return False
        else:
            return True

    def remove_single_peak_nearby(self, x):
        diffs = []
        x_c_lst = self.get_peak_positions()
        index = (np.abs(np.asarray(x_c_lst) - x)).argmin()
        self.peaks_in_queue.pop(index)

    def prepare_for_fitting(
            self, poly_order, maxwidth, centerrange,
            apply_peak_constraints=True):
        """
        :param x_center: numpy array of initial x values at picked centers
        :param y_center: numpy array of initial y values at picked centers
        :param fwhm: single float number for initial fwhm value
        """
        self.set_baseline(poly_order)
        self._apply_peak_constraints_for_current_fit = bool(
            apply_peak_constraints)
        baseline_mod = PolynomialModel(poly_order, prefix='b_')
        mod = baseline_mod
        pars = baseline_mod.make_params()
        peakinfo = {}
        for i in range(poly_order + 1):
            prefix = "b_c{0:d}".format(i)
            pars[prefix].set(
                value=self.baseline_in_queue[i]['value'],
                vary=self.baseline_in_queue[i]['vary'])
        i = 0
        for peak in self.peaks_in_queue:
            prefix = "p{0:d}_".format(i)
            peak_mod = PseudoVoigtModel(prefix=prefix, )
            pars.update(peak_mod.make_params())
            if apply_peak_constraints:
                center_min = self._peak_bound(
                    peak, 'center_min',
                    peak['center'] - DEFAULT_CENTER_HALF_RANGE,
                    enabled_key='center_min_enabled')
                center_max = self._peak_bound(
                    peak, 'center_max',
                    peak['center'] + DEFAULT_CENTER_HALF_RANGE,
                    enabled_key='center_max_enabled')
                sigma_min = self._peak_bound(
                    peak, 'sigma_min', DEFAULT_FWHM_MIN,
                    enabled_key='sigma_min_enabled', default_enabled=False)
                sigma_max = self._peak_bound(
                    peak, 'sigma_max', DEFAULT_FWHM_MAX,
                    enabled_key='sigma_max_enabled', default_enabled=False)
                amp_min = self._peak_bound(
                    peak, 'amplitude_min', 0.0,
                    enabled_key='amplitude_min_enabled')
                amp_max = self._peak_bound(
                    peak, 'amplitude_max', self._amplitude_max_bound(peak),
                    enabled_key='amplitude_max_enabled')
                frac_min = self._peak_bound(
                    peak, 'fraction_min', DEFAULT_NL_MIN,
                    enabled_key='fraction_min_enabled')
                frac_max = self._peak_bound(
                    peak, 'fraction_max', DEFAULT_NL_MAX,
                    enabled_key='fraction_max_enabled')
                center_min, center_max = self._intrinsic_peak_bounds(
                    'center', center_min, center_max)
                sigma_min, sigma_max = self._intrinsic_peak_bounds(
                    'sigma', sigma_min, sigma_max)
                amp_min, amp_max = self._intrinsic_peak_bounds(
                    'amplitude', amp_min, amp_max)
                frac_min, frac_max = self._intrinsic_peak_bounds(
                    'fraction', frac_min, frac_max)
                pars[prefix + 'center'].set(
                    value=peak['center'], min=center_min, max=center_max,
                    vary=peak['center_vary'])
                pars[prefix + 'sigma'].set(
                    value=peak['sigma'], min=sigma_min, vary=peak['sigma_vary'],
                    max=sigma_max)
                pars[prefix + 'amplitude'].set(
                    value=peak['amplitude'], min=amp_min, max=amp_max,
                    vary=peak['amplitude_vary'])
                pars[prefix + 'fraction'].set(
                    value=peak['fraction'], min=frac_min, max=frac_max,
                    vary=peak['fraction_vary'])
            else:
                pars[prefix + 'center'].set(
                    value=peak['center'], min=POSITIVE_PARAMETER_MIN,
                    vary=True)
                pars[prefix + 'sigma'].set(
                    value=peak['sigma'], min=POSITIVE_PARAMETER_MIN,
                    vary=True)
                pars[prefix + 'amplitude'].set(
                    value=peak['amplitude'], min=POSITIVE_PARAMETER_MIN,
                    vary=True)
                pars[prefix + 'fraction'].set(
                    value=peak['fraction'], min=DEFAULT_NL_MIN,
                    max=DEFAULT_NL_MAX, vary=True)
            peakinfo[prefix + 'phasename'] = peak['phasename']
            peakinfo[prefix + 'h'] = peak['h']
            peakinfo[prefix + 'k'] = peak['k']
            peakinfo[prefix + 'l'] = peak['l']
            mod += peak_mod
            i += 1
        self.parameters = pars
        self.peakinfo = peakinfo
        self.fit_model = mod

    def _peak_bound(
            self, peak, key, default, enabled_key=None, default_enabled=None):
        if enabled_key is not None:
            enabled = peak.get(enabled_key, None)
            if enabled is None:
                if default_enabled is None:
                    enabled = key not in peak or peak.get(key) is not None
                else:
                    enabled = (
                        peak.get(key) is not None
                        if key in peak else bool(default_enabled))
            if not bool(enabled):
                return None
        value = peak.get(key, default)
        if value is None:
            return None
        return float(value)

    def _amplitude_max_bound(self, peak):
        del peak
        return np.inf

    @staticmethod
    def _intrinsic_peak_bounds(param_name, minimum, maximum):
        domains = {
            'center': (POSITIVE_PARAMETER_MIN, None),
            'amplitude': (POSITIVE_PARAMETER_MIN, None),
            'sigma': (POSITIVE_PARAMETER_MIN, None),
            'fraction': (DEFAULT_NL_MIN, DEFAULT_NL_MAX),
        }
        domain_min, domain_max = domains[param_name]
        bounded_min = domain_min if minimum is None else max(
            domain_min, float(minimum))
        if domain_max is None:
            bounded_max = None if maximum is None else float(maximum)
        else:
            bounded_max = domain_max if maximum is None else min(
                domain_max, float(maximum))
        if bounded_max is not None and bounded_max <= bounded_min:
            return domain_min, domain_max
        return bounded_min, bounded_max

    def _background_anchor_samples(self):
        ranges = getattr(self, "background_anchor_ranges", [])
        if ranges == [] or self.x is None or self.y_bgsub is None:
            return None, None
        x_lst = []
        y_lst = []
        x_arr = np.asarray(self.x, dtype=float)
        y_arr = np.asarray(self.y_bgsub, dtype=float)
        for item in ranges:
            if isinstance(item, dict):
                xmin = float(item.get("xmin", item.get("x_min", 0.0)))
                xmax = float(item.get("xmax", item.get("x_max", xmin)))
                weight = float(item.get("weight", 10.0))
            else:
                xmin, xmax = float(item[0]), float(item[1])
                weight = 10.0
            xmin, xmax = min(xmin, xmax), max(xmin, xmax)
            mask = (x_arr >= xmin) & (x_arr <= xmax)
            if np.any(mask):
                x_use = x_arr[mask]
                y_use = y_arr[mask]
            else:
                x_mid = 0.5 * (xmin + xmax)
                x_use = np.asarray([x_mid], dtype=float)
                y_use = np.asarray([np.interp(x_mid, x_arr, y_arr)], dtype=float)
            n_repeat = int(round(weight))
            n_repeat = max(
                1, min(int(MAX_BACKGROUND_ANCHOR_WEIGHT), n_repeat))
            for __ in range(n_repeat):
                x_lst.extend(x_use.tolist())
                y_lst.extend(y_use.tolist())
        if x_lst == []:
            return None, None
        return np.asarray(x_lst, dtype=float), np.asarray(y_lst, dtype=float)

    def conduct_fitting(self):
        x_fit = self.x
        y_fit = self.y_bgsub
        x_anchor, y_anchor = self._background_anchor_samples()
        if x_anchor is not None and y_anchor is not None:
            x_fit = np.concatenate([np.asarray(self.x, dtype=float), x_anchor])
            y_fit = np.concatenate([np.asarray(self.y_bgsub, dtype=float), y_anchor])
        out = self.fit_model.fit(
            y_fit, self.parameters, x=x_fit)
        self.fit_result = copy.deepcopy(out)
        self._invalidate_component_cache()
        self.timestamp = str(datetime.datetime.now())[:-7]
        self.copy_fit_result_to_queue()
        if self.fit_result is None:
            return False, False
        else:
            converged = getattr(self.fit_result, 'success', False)
            return True, converged

    def get_fit_result(self):
        return self.fit_result.params

    def get_timestamp(self):
        return self.timestamp

    def get_fit_converged(self):
        if self.fit_result is None:
            return False
        return getattr(self.fit_result, 'success', False)

    def get_fit_quality_statistics(self):
        """Return fit statistics evaluated on the original section samples.

        Background-anchor samples may be appended during fitting to influence
        the baseline.  They are intentionally excluded here so the reported
        profile indices describe the measured 1D pattern only.
        """
        fit = self.fit_result
        statistics = {
            "iterations": getattr(fit, "nit", None) if fit is not None else None,
            "function_evaluations": (
                getattr(fit, "nfev", None) if fit is not None else None),
            "chi_square": getattr(fit, "chisqr", None) if fit is not None else None,
            "rp": None,
            "rwp": None,
        }
        if fit is None or self.y_bgsub is None or self.x is None:
            return statistics
        try:
            observed = np.asarray(self.y_bgsub, dtype=float).reshape(-1)
            calculated = np.asarray(
                self._fit_profile_on_section_x(), dtype=float).reshape(-1)
            if observed.size != calculated.size:
                return statistics
            finite = np.isfinite(observed) & np.isfinite(calculated)
            if not np.any(finite):
                return statistics
            observed = observed[finite]
            residual = observed - calculated[finite]
            rp_denominator = np.sum(np.abs(observed))
            rwp_denominator = np.sum(observed ** 2)
            if rp_denominator > 0.0:
                statistics["rp"] = float(np.sum(np.abs(residual)) / rp_denominator)
            if rwp_denominator > 0.0:
                statistics["rwp"] = float(
                    np.sqrt(np.sum(residual ** 2) / rwp_denominator))
        except (TypeError, ValueError, AttributeError):
            pass
        return statistics

    def sync_peak_vary_flags_from_fit_result(self, missing_only=False):
        """Restore vary flags from fit data, optionally only for legacy peaks."""
        params = getattr(getattr(self, "fit_result", None), "params", {}) or {}
        for i, peak in enumerate(self.peaks_in_queue):
            prefix = "p{0:d}_".format(i)
            for param_name, vary_key in PEAK_PARAM_VARY_KEYS.items():
                if missing_only and vary_key in peak:
                    continue
                prm = params.get(prefix + param_name)
                if prm is not None and hasattr(prm, "vary"):
                    peak[vary_key] = bool(prm.vary)

    def copy_fit_result_to_queue(self):
        n_peaks = self.get_number_of_peaks_in_queue()
        # self.clear_queue()
        i = 0
        for peak in self.peaks_in_queue:
            prefix = "p{0:d}_".format(i)
            peak['center'] = self.fit_result.params[prefix + 'center'].value
            peak['amplitude'] = self.fit_result.params[
                prefix + 'amplitude'].value
            peak['sigma'] = self.fit_result.params[
                prefix + 'sigma'].value
            peak['fraction'] = self.fit_result.params[
                prefix + 'fraction'].value
            peak['phasename'] = self.peakinfo[prefix + 'phasename']
            peak['h'] = self.peakinfo[prefix + 'h']
            peak['k'] = self.peakinfo[prefix + 'k']
            peak['l'] = self.peakinfo[prefix + 'l']
            i += 1
        i = 0
        for factor in self.baseline_in_queue:
            prefix = "b_c{0:d}".format(i)
            factor['value'] = self.fit_result.params[prefix].value
            i += 1

    def get_number_of_peaks_in_queue(self):
        return self.peaks_in_queue.__len__()

    def get_individual_profiles(self, bgsub=False):
        """
        return_value['p1_']
        return_value['b_']
        """
        token = self._get_component_cache_token()
        if token != self._component_cache_token:
            eval_components = getattr(self.fit_result, "eval_components", None)
            if callable(eval_components):
                comps = eval_components(x=self.x)
            else:
                comps = {}
            comps = {
                key: value_on_x
                for key, value in comps.items()
                for value_on_x in (self._array_on_section_x(value),)
                if value_on_x is not None
            }
            self._component_cache_bgsub = comps
            self._component_cache_with_bg = None
            self._component_cache_token = token
        if bgsub:
            return self._component_cache_bgsub
        if self._component_cache_with_bg is None:
            bg_comps = {}
            for key, value in self._component_cache_bgsub.items():
                bg_comps[key] = value + self.y_bg
            self._component_cache_with_bg = bg_comps
        return self._component_cache_with_bg

    def _fit_profile_on_section_x(self):
        eval_func = getattr(self.fit_result, "eval", None)
        if callable(eval_func):
            try:
                profile = self._array_on_section_x(eval_func(x=self.x))
                if profile is not None:
                    return profile
            except Exception:
                pass

        profile = self._array_on_section_x(
            getattr(self.fit_result, "best_fit", None))
        if profile is not None:
            return profile

        components = self.get_individual_profiles(bgsub=True)
        if components:
            stacked = [
                np.asarray(value, dtype=float)
                for value in components.values()
                if value is not None and len(value) == len(self.x)
            ]
            if stacked:
                return np.sum(stacked, axis=0)

        return np.zeros(len(self.x), dtype=float)

    def get_fit_profile(self, bgsub=False):
        profile = self._fit_profile_on_section_x()
        if bgsub:
            return profile
        else:
            return profile + self.y_bg

    def get_fit_residue(self, bgsub=False):
        profile = self._fit_profile_on_section_x()
        return self.y_bgsub - profile + \
            self.get_fit_residue_baseline(bgsub=bgsub)

    def get_fit_residue_baseline(self, bgsub=False):
        if bgsub:
            return 0
            # return self.y_bgsub.min()
        else:
            return self.y_bg.min()

    def get_nearest_intensity(self, x_pick):
        index = (np.abs(np.asarray(self.x) - x_pick)).argmin()
        return self.y_bgsub[index]

    def get_nearest_xy(self, x_pick):
        index = (np.abs(np.asarray(self.x) - x_pick)).argmin()
        return self.x_bgsub[index], self.y_bgsub[index]
