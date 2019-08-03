#!/usr/bin/env python
# coding: utf-8

# # Convert CIF to JCPDS

# * This notebook shows how to calculate a theoretical diffraction pattern  using `pymatgen`.  
# * This also aims to show how to read `CIF` files, convert them to `JCPDS`.  
# * Note that `ds_jcpds` is differernt from that in `PeakPo`, but it produces readable jcpds for PeakPo.  
# * Some `jcpds` files can be downloaded from: https://github.com/SHDShim/JCPDS

# In[1]:


get_ipython().run_line_magic('matplotlib', 'inline')


# ## What is CIF file
# 
# https://en.wikipedia.org/wiki/Crystallographic_Information_File
# 
# 

# In[2]:


get_ipython().run_line_magic('ls', './cif/*.cif')


# In[3]:


get_ipython().run_line_magic('cat', './cif/MgSiO3_bm.cif')


# ## What is a JCPDS file
# 
# What is lacking in cif?

# In[4]:


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ## What is `pymatgen`?
# 
# https://pymatgen.org

# In[5]:


import pymatgen as mg
from pymatgen import Lattice, Structure
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


# In[6]:


mg.__version__


# This works with `pymatgen` version `2019.4.11`.

# `ds_jcpds` is written by Dan Shim for making a jcpds file.

# In[7]:


get_ipython().run_line_magic('ls', '../../peakpo')


# In[8]:


import sys
sys.path.append('../../peakpo/')
sys.path.append('../local_modules/')
import ds_jcpds
import quick_plots as quick


# ## Input parameters

# In[9]:


get_ipython().run_line_magic('ls', './cif/')


# In[10]:


fn_cif = "./cif/MgSiO3_bm.cif"
fn_jcpds = './jcpds/MgSiO3-bm.jcpds'
comments_jcpds = "Bridgmanite"


# Parameters for the equation of state of bridgmanite.

# In[11]:


k0 = 260. # 200.
k0p = 4.00 # 4.
alpha = 3.16e-5 # 1.e-5


# In[12]:


wl_xray = 0.3344
xrange = (0,40)


# ## Read CIF

# The `cif` file below was downloaded from American mineralogist crystal structure database.

# In[13]:


material = mg.Structure.from_file(fn_cif)


# ## Get some parameters in CIF

# In[14]:


print('Unit-cell volume = ', material.volume)
print('Density = ', material.density)
print('Chemical formula = ', material.formula)


# In[15]:


lattice = material.lattice
print('Lattice parameters = ', lattice.a, lattice.b, lattice.c,       lattice.alpha, lattice.beta, lattice.gamma)
crystal_system = SpacegroupAnalyzer(material).get_crystal_system()
print(crystal_system)


# ## Get diffraction pattern

# In[16]:


c = XRDCalculator(wavelength=wl_xray)


# In[17]:


pattern = c.get_pattern(material, two_theta_range = xrange)


# ## Extract twotheta, d-sp, int, hkl

# In[18]:


pattern.hkls[0][0]['hkl']


# In[19]:


pattern.hkls.__len__()


# In[20]:


h = []; k = []; l = []
for i in range(pattern.hkls.__len__()):
    h.append(pattern.hkls[i][0]['hkl'][0])
    k.append(pattern.hkls[i][0]['hkl'][1])
    l.append(pattern.hkls[i][0]['hkl'][2])


# In[21]:


d_lines = [pattern.x, pattern.d_hkls, pattern.y, h, k, l ]
diff_lines = np.transpose(np.asarray(d_lines))
print(diff_lines[1,:])


# ## Table output

# We can make a nice looking table using the `pandas` package.  `pandas` is more than looking-good table producer.  It is a powerful statistics package popular in data science.

# In[22]:


table = pd.DataFrame(data = diff_lines,    # values
    columns=['Two Theta', 'd-spacing', 'intensity', 'h', 'k', 'l'])  # 1st row as the column names
table.head()


# ## Plot peak positions generated from pymatgen

# In[23]:


f, ax = plt.subplots(figsize=(8,3))
quick.plot_diffpattern(ax, [0], [0])
ax.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b');


# ## Convert to JCPDS

# Setup an `jcpds` object from a `cif` file

# In[ ]:


material_jcpds = ds_jcpds.JCPDS()
material_jcpds.set_from_cif(fn_cif, k0, k0p,                       thermal_expansion=alpha, 
                        two_theta_range=xrange)


# Calculate diffraction pattern at a pressure.

# In[ ]:


material_jcpds.cal_dsp(pressure = 100.)
dl = material_jcpds.get_DiffractionLines()
tth, inten = material_jcpds.get_tthVSint(wl_xray)


# In[ ]:


f, ax = plt.subplots(2, 1, figsize=(7,3), sharex=True)
ax[0].vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b')
ax[1].vlines(tth, 0., inten, color = 'r')
ax[0].set_xlim(7.5,9)


# ## Save to a JCPDS file

# In[ ]:


material_jcpds.write_to_file(fn_jcpds, comments=comments_jcpds)


# In[ ]:


get_ipython().run_line_magic('cat', '{fn_jcpds}')


# # Read back the written JCPDS for test

# In[ ]:


material_test = ds_jcpds.JCPDS(filename = fn_jcpds)


# Calculate a pattern at a pressure

# In[ ]:


material_test.cal_dsp(pressure = 100.)
material_test.get_DiffractionLines()
tth, inten = material_test.get_tthVSint(wl_xray)


# In[ ]:


f = plt.figure(figsize=(8,3))
plt.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b', label='0 GPa')
plt.vlines(tth, 0., inten, color = 'r', label='100 GPa')
plt.legend();


# In[ ]:




