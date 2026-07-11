import numpy as np

from peakpo.control.mplcontroller import (
    _azimuth_shift_rows,
    _bragg_dspacing,
    _coordinate_edges,
    _coordinates_are_uniform,
    _nearest_coordinate_index,
)


def test_coordinate_edges_expand_pixel_centers_by_half_a_bin():
    centers = np.asarray([10.0, 10.5, 11.0])

    np.testing.assert_allclose(
        _coordinate_edges(centers), [9.75, 10.25, 10.75, 11.25])


def test_coordinate_edges_support_nonuniform_monotonic_centers():
    centers = np.asarray([1.0, 2.0, 4.0])

    np.testing.assert_allclose(
        _coordinate_edges(centers), [0.5, 1.5, 3.0, 5.0])
    assert not _coordinates_are_uniform(centers)


def test_uniform_coordinates_use_fast_image_rendering_path():
    assert _coordinates_are_uniform(np.linspace(-180.0, 180.0, 361))


def test_nearest_coordinate_index_uses_real_ascending_coordinates():
    centers = np.asarray([1.0, 2.0, 4.0, 8.0])

    assert _nearest_coordinate_index(centers, 3.6) == 2


def test_nearest_coordinate_index_supports_descending_coordinates():
    centers = np.asarray([8.0, 4.0, 2.0, 1.0])

    assert _nearest_coordinate_index(centers, 3.6) == 1


def test_azimuth_shift_uses_actual_chi_spacing():
    chi = np.linspace(-90.0, 90.0, 181)

    assert _azimuth_shift_rows(chi, 10.0) == 10


def test_bragg_dspacing_validates_domain_and_uses_two_theta():
    assert _bragg_dspacing(0.0, 0.3344) is None
    assert _bragg_dspacing(181.0, 0.3344) is None
    assert _bragg_dspacing(20.0, -1.0) is None

    expected = 0.3344 / (2.0 * np.sin(np.deg2rad(10.0)))
    assert np.isclose(_bragg_dspacing(20.0, 0.3344), expected)
