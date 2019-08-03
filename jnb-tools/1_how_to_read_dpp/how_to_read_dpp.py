#!/usr/bin/env python
# coding: utf-8

# # How to read dpp from PeakPo

# - Please check [setup_for_notebooks](../0_setup/setup_for_notebooks.ipynb) file if you have problem using the notebooks in this folder.  
# - In this notebook, we will learn how to plot XRD patterns using the information saved in `dpp`.  
# - `dpp` is a project file saved in `PeakPo`.  You may plot, jcpds information and cake as well as many other information.

# This notebook takes advantage of the `PeakPo` modules and other local modules.  They can be found in `../local_modules` folder.  
# The cell below defined the search path for this local module folder.

# In[1]:


import sys
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


# ### Change the following two cells for your own dpp file

# Data files should be in the `../data` folder.  You need: `dpp`, `chi`, `tif`, and `poni` files.

# In[4]:


get_ipython().run_line_magic('ls', '../data/hStv/*.dpp')


# In[5]:


filen_dpp = '../data/hStv/hSiO2_404_009.dpp'


# In[6]:


with open(filen_dpp, 'rb') as f:
    model_dpp = dill.load(f)


# The cells below show how to look into the data structure of the `model_dpp` and get values from it.

# In[7]:


model_dpp.__dict__


# ## Setup a new PeakPo model and assign info from dpp

# In[8]:


from model import PeakPoModel
model = PeakPoModel()


# Make sure to reset the chi folder location using the `new_chi_path` option.

# In[9]:


model.set_from(model_dpp, new_chi_path='../data/hStv')


# ## Some basic model methods

# In[10]:


get_ipython().run_line_magic('pinfo', 'model')


# In[11]:


model.get_saved_pressure()


# In[12]:


model.get_saved_temperature()


# In[13]:


print(model.base_ptn.fname)


# In[14]:


print(model.base_ptn.wavelength)


# In[15]:


print(model.waterfall_ptn)


# In[16]:


for phase in model.jcpds_lst:
    print(phase.name)


# In[17]:


for phase in model.jcpds_lst:
    if phase.display:
        print(phase.name)


# In[18]:


print(model.poni)


# In[ ]:




