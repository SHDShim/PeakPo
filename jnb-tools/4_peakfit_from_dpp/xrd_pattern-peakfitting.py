#!/usr/bin/env python
# coding: utf-8

# # Peak fitting for XRD pattern from dpp

# - Please check [setup_for_notebooks](../0_setup/setup_for_notebooks.ipynb) file if you have problem using the notebooks in this folder.  
# - In this notebook, we will learn how to plot XRD patterns using the information saved in `dpp`.  
# - `dpp` is a project file saved in `PeakPo`.  You may plot, jcpds information and cake as well as many other information.

# In[1]:


import sys
sys.path.append('../local_modules')
sys.path.append('../../peakpo')


# ## Check the versio of pyFAI in your conda environment

# In[2]:


import pyFAI
pyFAI.version


# Note that the example data files I provided are made with `pyFAI` version `0.14`.  If you see version higher than `0.15` here, you will get error when you read the example `dpp` file.  In that case, you either follow the instruction in [setup_for_notebooks.ipynb](./setup_for_notebooks.ipynb) or you may use your own dpp for this note book.

# ## Read dpp

# In[3]:


import dill
import numpy as np


# In[4]:


get_ipython().run_line_magic('ls', '../data/hStv/*.dpp')


# In[5]:


filen_dpp = '../data/hStv/hSiO2_404_009.dpp'


# In[6]:


with open(filen_dpp, 'rb') as f:
    model_dpp = dill.load(f)


# ## Setup a new PeakPo model and assign info from dpp

# In[7]:


from model import PeakPoModel
model = PeakPoModel()


# Make sure to reset the chi folder location using the `new_chi_path` option.

# In[8]:


model.set_from(model_dpp, new_chi_path='../data/hStv')


# See `xrd_pattern.ipynb` file for basic operations.

# ## Make a simple plot

# The following three modules are all in the `../local_modules` folder.

# In[9]:


from xrd_unitconv import * # Make conversios between different x-axis units


# In[10]:


import quick_plots as quick # A function to plot XRD pattern
import fancy_plots as fancy # A function to plot XRD pattern


# In[11]:


get_ipython().run_line_magic('matplotlib', 'inline')
get_ipython().run_line_magic('config', "InlineBackend.figure_format = 'retina'")


# In[12]:


import matplotlib.pyplot as plt


# In[13]:


f, ax = plt.subplots(figsize=(9,3.5))
fancy.plot_diffpattern(ax, model)
print(ax.axis())
fancy.plot_jcpds(ax, model, bar_position=0.1, bar_height=5, 
           show_index=True, 
           phase_names = ['hStv', 'Au', 'Ne', 'hCt'], bar_vsep=5.)
print(ax.axis())
pressure = model.get_saved_pressure()
temperature = model.get_saved_temperature()
ax.text(0.01,0.9, "(a) {0:.0f} GPa, {1: .0f} K".format(pressure, temperature), 
        transform = ax.transAxes, fontsize=16)
plt.savefig('test.pdf', bbox_inches='tight')


# ## Choose ROI

# Check by changing the `xrange` for `plot_diffpattern`.

# In[14]:


f, ax = plt.subplots(figsize=(9,5))
fancy.plot_diffpattern(ax, model, xrange=[6, 11])
fancy.plot_jcpds(ax, model, bar_position=0.1, bar_height=5, 
           show_index=True, 
           phase_names = ['hStv', 'Au', 'Ne', 'hCt'], bar_vsep=5.)
pressure = model.get_saved_pressure()
temperature = model.get_saved_temperature()
ax.text(0.01,0.9, "(a) {0:.0f} GPa, {1: .0f} K".format(pressure, temperature), 
        transform = ax.transAxes, fontsize=16)
plt.savefig('test.pdf', bbox_inches='tight')


# Get background subtracted pattern for masking.

# In[15]:


x, y = model.base_ptn.get_bgsub()
x


# Masking for ROI

# In[16]:


import numpy.ma as ma

x_ma = ma.masked_outside(x, 6., 11.)
x_roi = x_ma.compressed()
y_roi = ma.masked_where(np.ma.getmask(x_ma), y).compressed()


# Quick plot to check

# In[17]:


figure = plt.subplots(figsize=(10,3))
plt.plot(x_roi, y_roi)


# ## Setup fitting model

# In[18]:


from lmfit.models import PseudoVoigtModel, LinearModel
from lmfit import Parameters


# ## Make initial peak position array

# In[19]:


from scipy.signal import find_peaks

peaks, _ = find_peaks(y_roi, height=30.)
peaks


# Plot to see if the search positions are reasonable.

# In[20]:


figure = plt.subplots(figsize=(10,3))
plt.plot(x_roi, y_roi)
plt.plot(x_roi[peaks], y_roi[peaks], 'o')


# ## Setup fitting model

# In[21]:


from lmfit.models import PseudoVoigtModel, LinearModel
from lmfit import Parameters


# ## Define some functions for peak fitting

# Define functions for peakfitting.  Here we use `LMFIT` module.

# In[22]:


from xrd_pkfit import *


# ## First fitting attempt without any restriction

# In[23]:


mod, pars = make_model(x_roi[peaks])
out = mod.fit(y_roi, pars, x=x_roi, fit_kws={'maxfev': 500})
print(out.fit_report(min_correl=0.5))


# Plot the fitting results

# In[24]:


n_peaks = len(x_roi[peaks])
figure, ax = plt.subplots(figsize=(12,4))
plot_fitresult(ax, x_roi, y_roi, out, n_peaks)


# ## Do better initial guess

# Pereform new fitting

# In[25]:


mod, pars = make_model(x_roi[peaks], fwhm=0.03, amplitude=100.)
out = mod.fit(y_roi, pars, x=x_roi, fit_kws={'maxfev': 500})
print(out.fit_report(min_correl=0.5))


# In[26]:


n_peaks = len(x_roi[peaks])
figure, ax = plt.subplots(figsize=(12,4))
plot_fitresult(ax, x_roi, y_roi, out, n_peaks)


# ## Use the last fitting results for the next fitting

# In[27]:


pars_new = out.params


# In[28]:


out = mod.fit(y_roi, pars_new, x=x_roi, fit_kws={'maxfev': 500})
print(out.fit_report(min_correl=0.5))


# In[29]:


n_peaks = len(x_roi[peaks])
figure, ax = plt.subplots(figsize=(12,4))
plot_fitresult(ax, x_roi, y_roi, out, n_peaks)


# ## Fix some parameters for fitting

# In[30]:


pars_new = out.params
pars_new


# In[31]:


pars_new['pk1_center'].set(min=8.3, max=8.4, vary=True)
pars_new['pk1_amplitude'].set(1000., vary=True)


# In[32]:


out = mod.fit(y_roi, pars_new, x=x_roi, fit_kws={'maxfev': 500})
print(out.fit_report(min_correl=0.5))


# In[33]:


n_peaks = len(peaks)
figure, ax = plt.subplots(figsize=(12,4))
plot_fitresult(ax, x_roi, y_roi, out, n_peaks)


# In[ ]:




