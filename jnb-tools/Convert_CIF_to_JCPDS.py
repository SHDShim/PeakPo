
# coding: utf-8

# In[1]:


get_ipython().magic('matplotlib inline')


# # 0. General note

# * `pymatgen` works only with `py35`
# 
# * This notebook shows how to make an XRD plot using `pymatgen`.
# 
# * This also aims to show how to read `CIF` files, convert them to `JCPDS`.

# # 1. General setup

# In[2]:


import pymatgen as mg
from pymatgen import Lattice, Structure
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# Import `ds_jcpds` which is used by `peakpo`.  Because of this, if you move this notebook out of its original directory, this notebook needs modification to function properly.

# In[3]:


import sys
sys.path.insert(0, '../peakpo')
import ds_jcpds


# In[4]:


fn_cif = "../jcpds_from_cif/CIFs/corundum_Kirfel1990.cif"
fn_jcpds = '../jcpds_from_cif/Al2O3.jcpds'
comments_jcpds = "corundum by Kirfel 1990"


# In[5]:


k0 = 160.
k0p = 4.00
alpha = 3.16e-5


# In[6]:


wl_xray = 0.3344
xrange = (0,40)


# # 2. Read CIF of Bridgmanite

# The `cif` file below was downloaded from American mineralogist crystal structure database.

# In[7]:


material = mg.Structure.from_file(fn_cif)


# # 3. Get some contents from CIF

# In[8]:


print('Unit-cell volume = ', material.volume)
print('Density = ', material.density)
print('Chemical formula = ', material.formula)


# # 4. Get lattice parameters

# In[9]:


lattice = material.lattice
print('Lattice parameters = ', lattice.a, lattice.b, lattice.c,       lattice.alpha, lattice.beta, lattice.gamma)
crystal_system = SpacegroupAnalyzer(material).get_crystal_system()
print(crystal_system)


# # 5. Get diffraction pattern

# In[10]:


c = XRDCalculator(wavelength=wl_xray)
pattern = c.get_xrd_data(material, two_theta_range = xrange)


# ## 5.1. Extract twotheta, d-sp, int, hkl

# In[11]:


d_lines = []
for values in pattern:
    hkl_key = values[2].keys()
    hkl_txt = str(hkl_key)[12:-3].split(",")
    # print(hkl_txt[0], hkl_txt[1], hkl_txt[-1])
    d_lines.append([values[0], values[3], values[1],                         int(hkl_txt[0]), int(hkl_txt[1]), int(hkl_txt[-1]) ])

diff_lines = np.asarray(d_lines)
print(diff_lines)


# ## 5.2. Table output

# In[12]:


table = pd.DataFrame(data = diff_lines,    # values
    columns=['Two Theta', 'd-spacing', 'intensity', 'h', 'k', 'l'])  # 1st row as the column names
table.head()


# ## 5.3. Plot peak positions generated from pymatgen

# In[13]:


f = plt.figure(figsize=(10,3))
plt.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b');


# # 6. Convert to JCPDS

# Setup an `jcpds` object from a `cif` file

# In[14]:


material_jcpds = ds_jcpds.JCPDS()
material_jcpds.set_from_cif(fn_cif, k0, k0p,                       thermal_expansion=alpha, two_theta_range=xrange)


# Calculate diffraction pattern at a pressure.

# In[15]:


material_jcpds.cal_dsp(pressure = 100.)
dl = material_jcpds.get_DiffractionLines()
tth, inten = material_jcpds.get_tthVSint(wl_xray)


# In[16]:


f = plt.figure(figsize=(10,3))
plt.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b')
plt.vlines(tth, 0., inten, color = 'r');


# # 7. Save to a JCPDS file

# In[17]:


material_jcpds.write_to_file(fn_jcpds, comments=comments_jcpds)


# # 8. Read back the written JCPDS for test

# In[18]:


material_test = ds_jcpds.JCPDS(filename = fn_jcpds)


# Calculate a pattern at a pressure

# In[19]:


material_test.cal_dsp(pressure = 10.)
material_test.get_DiffractionLines()
tth, inten = material_test.get_tthVSint(wl_xray)


# In[20]:


f = plt.figure(figsize=(10,3))
plt.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b')
plt.vlines(tth, 0., inten, color = 'r');


# In[ ]:




