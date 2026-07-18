import unittest

import numpy as np

from peakpo.view.cakehistwidget import CakeHistogramWidget


class CakeHistogramEdgeTests(unittest.TestCase):
    def test_largest_drop_edge_ignores_sparse_high_intensity_tail(self):
        values = np.concatenate([
            np.linspace(100.0, 1000.0, 20000),
            np.linspace(1050.0, 4500.0, 600),
            np.linspace(5000.0, 6000.0, 30),
            np.array([380000.0]),
        ])

        edge = CakeHistogramWidget._detect_largest_drop_edge(
            values, float(values.max()))

        self.assertIsNotNone(edge)
        self.assertGreater(edge, 950.0)
        self.assertLess(edge, 1100.0)

    def test_largest_drop_edge_detects_clean_histogram_step(self):
        values = np.concatenate([
            np.linspace(1.0, 1200.0, 24000),
            np.linspace(1250.0, 2000.0, 1000),
        ])

        edge = CakeHistogramWidget._detect_largest_drop_edge(
            values, float(values.max()))

        self.assertIsNotNone(edge)
        self.assertGreater(edge, 1150.0)
        self.assertLess(edge, 1300.0)

    def test_largest_drop_edge_uses_log_intensity_axis(self):
        values = np.concatenate([
            np.linspace(80.0, 900.0, 30000),
            np.linspace(920.0, 5200.0, 6000),
            np.linspace(5300.0, 7000.0, 20),
        ])

        edge = CakeHistogramWidget._detect_largest_drop_edge(
            values, float(values.max()))

        self.assertIsNotNone(edge)
        self.assertGreater(edge, 880.0)
        self.assertLess(edge, 950.0)


if __name__ == "__main__":
    unittest.main()
