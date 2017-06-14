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
    if roi[0] >= x.min() and roi[1] <= x.max():
        i_roimin = np.abs(x - roi[0]).argmin()
        i_roimax = np.abs(x - roi[1]).argmin()
        x_roi = x[i_roimin:i_roimax]
        y_roi = y[i_roimin:i_roimax]
        return x_roi, y_roi
    else:
        return x, y
