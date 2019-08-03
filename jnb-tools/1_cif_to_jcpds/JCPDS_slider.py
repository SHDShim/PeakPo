#!/usr/bin/env python
# coding: utf-8

# # Interactive JCPDS

# In[1]:


get_ipython().run_line_magic('matplotlib', 'inline')


# * This notebook shows how to make jupyter notebook interactive.

# In[2]:


get_ipython().run_line_magic('ls', './jcpds/')


# In[3]:


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# In[4]:


from ipywidgets import interactive
import ipywidgets as widgets


# In[5]:


import pymatgen as mg
from pymatgen import Lattice, Structure
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


# In[7]:


import sys
sys.path.append('../../peakpo/')
sys.path.append('../local_modules')
import ds_jcpds


# In[8]:


fn_jcpds = './jcpds/MgSiO3-bm.jcpds'


# In[9]:


wl_xray = 0.3344
xrange = (0,40)


# ## Read back the written JCPDS for test

# In[10]:


bm_high_p = ds_jcpds.JCPDS(filename = fn_jcpds)


# In[11]:


def f(pressure=0., temperature=300.):
    plt.figure(figsize=(7,3))
    bm_high_p.cal_dsp(pressure = pressure, temperature=temperature)
    bm_high_p.get_DiffractionLines()
    tth, inten = bm_high_p.get_tthVSint(wl_xray)
    plt.vlines(tth, 0., inten, color = 'r')
    plt.ylim(0, 100)
    plt.xlim(1,30)
    plt.grid(True)
    plt.show()

interactive_plot = interactive(f, 
                               pressure=widgets.FloatSlider(min=0, max=100, step=1, readout_format='.0f'), 
                               temperature=widgets.FloatSlider(min=300, max=3000, step=10, readout_format='.0f'))
output = interactive_plot.children[-1]
#output.layout.height = '300px'
interactive_plot


# ## Can we also change unit-cell parameters?

# In[12]:


a_0 = bm_high_p.a0
b_0 = bm_high_p.b0
c_0 = bm_high_p.c0


# In[13]:


v_0 = bm_high_p.v0


# In[14]:


get_ipython().run_line_magic('pinfo', 'bm_high_p.cal_dsp')


# In[15]:


def f(pressure=0., temperature=300., a0=a_0, b0=b_0, c0=c_0):
    plt.figure(figsize=(7,3))
    bm_high_p.a0 = a0
    bm_high_p.b0 = b0
    bm_high_p.c0 = c0
    bm_high_p.cal_dsp(pressure = pressure, temperature=temperature,
                     use_table_for_0GPa=False)
    bm_high_p.get_DiffractionLines()
    tth, inten = bm_high_p.get_tthVSint(wl_xray)
    plt.vlines(tth, 0., inten, color = 'r')
    plt.ylim(0, 100)
    plt.xlim(1,30)
    plt.grid(True)
    plt.show()

min_frac=0.9
max_frac=1.1
interactive_plot = interactive(f, 
                               pressure=widgets.FloatSlider(min=0, max=100, step=1, readout_format='.0f'), 
                               temperature=widgets.FloatSlider(min=300, max=3000, step=10, readout_format='.0f'),
                               a0=widgets.FloatSlider(value=a_0, min=a_0*min_frac, max=a_0*max_frac, step=0.001, readout_format='.3f'),
                               b0=widgets.FloatSlider(value=b_0, min=b_0*min_frac, max=b_0*max_frac, step=0.001, readout_format='.3f'),
                               c0=widgets.FloatSlider(value=c_0, min=c_0*min_frac, max=c_0*max_frac, step=0.001, readout_format='.3f'))
output = interactive_plot.children[-1]
#output.layout.height = '300px'
interactive_plot


# In[ ]:





# In[ ]:




