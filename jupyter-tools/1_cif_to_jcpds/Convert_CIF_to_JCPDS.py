#!/usr/bin/env python
# coding: utf-8

# In[1]:


get_ipython().run_line_magic('matplotlib', 'inline')


# In[2]:


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# In[3]:


import pymatgen.core as mg
from pymatgen.core import Lattice, Structure
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


# # Convert CIF to JCPDS

# ## Input parameters
# 
# `cif` should exist in the `./cif` folder.  `jcpds` will be created in the `./jcpds` folder.

# In[4]:


get_ipython().run_line_magic('ls', './cif')


# In[5]:


cif_name = 'Fe2S'


# Elastic and thermal parameters.  Make changes for your phase.

# In[36]:


k0 = 200. # 200.
k0p = 4.00 # 4.
alpha = 3.16e-5 # 1.e-5


# The same file name will be used for `jcpds` file.

# In[37]:


fn_cif = "./cif/"+cif_name+'.cif'
fn_jcpds = './jcpds/'+cif_name+'.jcpds'
comments_jcpds = cif_name


# <font color='red'> __(NOTE)__ Make sure _symmetry_space_group_name_H-M is not `P1` below. </font>

# In[38]:


get_ipython().system('head {fn_cif}')


# <font color='red'> __Note:__ Make sure the pymatgen version is later than 2019.4.11. </font>

# In[39]:


from pymatgen.core import __version__
print(__version__)


# In[40]:


wl_xray = 0.3344
xrange = (0,40)


# In[41]:


verbose = True


# In[42]:


import sys
sys.path.append('../../peakpo/')
sys.path.append('../local_modules/')
import ds_jcpds
import quick_plots as quick


# ## Read CIF

# In[43]:


material = mg.Structure.from_file(fn_cif)


# ## Show CIF content

# In[45]:


if verbose:
    print(material)


# In[46]:


lattice = material.lattice
if verbose:
    print('Lattice parameters = ', lattice.a, lattice.b, lattice.c, \
          lattice.alpha, lattice.beta, lattice.gamma)
crystal_system = SpacegroupAnalyzer(material).get_crystal_system()
if verbose:
    print(crystal_system)


# In[47]:


SpacegroupAnalyzer(material).get_space_group_symbol()


# In[48]:


from pymatgen.io.cif import CifParser
parser = CifParser(fn_cif)
structure = parser.get_structures()
structure


# In[49]:


with open(fn_cif, 'r') as f:
    cif_data = f.readlines()


# In[50]:


cif_data


# In[51]:


for line in cif_data:
    if '_symmetry_space_group_name_H-M' in line:
        a = line.replace('_symmetry_space_group_name_H-M', '')
        if 'P 1' in a:
            print('Got it')


# ## Get diffraction pattern

# In[52]:


c = XRDCalculator(wavelength=wl_xray)


# In[53]:


pattern = c.get_pattern(material, two_theta_range = xrange)


# ## Extract twotheta, d-sp, int, hkl

# In[54]:


h = []; k = []; l = []
for i in range(pattern.hkls.__len__()):
    h.append(pattern.hkls[i][0]['hkl'][0])
    k.append(pattern.hkls[i][0]['hkl'][1])
    l.append(pattern.hkls[i][0]['hkl'][2])


# In[55]:


d_lines = [pattern.x, pattern.d_hkls, pattern.y, h, k, l ]
diff_lines = np.transpose(np.asarray(d_lines))


# ## Table output

# We can make a nice looking table using the `pandas` package.  `pandas` is more than looking-good table producer.  It is a powerful statistics package popular in data science.

# In[56]:


if verbose:
    table = pd.DataFrame(data = diff_lines,    # values
        columns=['Two Theta', 'd-spacing', 'intensity', 'h', 'k', 'l'])  
    # 1st row as the column names
    table.head()


# ## Plot peak positions generated from pymatgen

# In[57]:


f, ax = plt.subplots(figsize=(8,3))
ax.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b');


# ## Convert to JCPDS

# Setup an `jcpds` object from a `cif` file

# In[58]:


material_jcpds = ds_jcpds.JCPDS()
material_jcpds.set_from_cif(fn_cif, k0, k0p, \
                      thermal_expansion=alpha, 
                        two_theta_range=xrange)


# Calculate diffraction pattern at a pressure.

# In[59]:


material_jcpds.cal_dsp(pressure = 100., temperature = 1000.)
dl = material_jcpds.get_DiffractionLines()
tth, inten = material_jcpds.get_tthVSint(wl_xray)


# In[61]:


f, ax = plt.subplots(2, 1, figsize=(7,3), sharex=True)
ax[0].vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b')
ax[1].vlines(tth, 0., inten, color = 'r')
ax[0].set_xlim(7.5,20)


# ## Save to a JCPDS file

# In[62]:


material_jcpds.write_to_file(fn_jcpds, comments=comments_jcpds)


# In[63]:


get_ipython().system('head {fn_jcpds}')


# # Read back the written JCPDS for test

# In[64]:


material_test = ds_jcpds.JCPDS(filename = fn_jcpds)


# In[65]:


material_test.cal_dsp(pressure = 100.)
material_test.get_DiffractionLines()
tth, inten = material_test.get_tthVSint(wl_xray)


# In[66]:


f = plt.figure(figsize=(8,3))
plt.vlines(diff_lines[:,0], 0., diff_lines[:,2], color='b', label='0 GPa')
plt.vlines(tth, 0., inten, color = 'r', label='100 GPa')
plt.legend();


# # Check for possible errors in conversion

# The most common error in converting `cif` to `jcpds` is incorrect symmetry conversion.  The cell below check the symmetry conversion.

# In[35]:


if crystal_system != material_jcpds.symmetry:
    print('symmetry is different')
else:
    print('symmetry seems to be fine')


# In[ ]:




