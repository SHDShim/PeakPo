# -*- coding: utf-8 -*-
"""
Created on Sun Jan 18 08:31:09 2015

@author: DanShim
"""

import numpy as np


def get_DataSection(x, y, roi):
    """
    return a section for viewing and processing
    """
    r0, r1 = float(roi[0]), float(roi[1])
    if r0 > r1:
        r0, r1 = r1, r0
    if r0 >= x.min() and r1 <= x.max():
        i_roimin = np.abs(x - r0).argmin()
        i_roimax = np.abs(x - r1).argmin()
        if i_roimin > i_roimax:
            i_roimin, i_roimax = i_roimax, i_roimin
        # Include both edge points.
        x_roi = x[i_roimin:i_roimax + 1]
        y_roi = y[i_roimin:i_roimax + 1]
        return x_roi, y_roi
    else:
        return x, y
