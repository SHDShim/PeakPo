#!/usr/bin/env python
# coding: utf-8

# # Convert JCPDS from Dioptas to PeakPo

# ## Input parameters
# 
# dioptas `jcpds` should exist in the `./jcpds-dioptas` folder.  
# peakpo `jcpds` will be created in the `./jcpds-peakpo` folder.

# In[1]:


get_ipython().run_line_magic('ls', './jcpds-dioptas')


# In[33]:


jcpds_name = 'fesi'


# In[34]:


fn_dioptas = "./jcpds-dioptas/"+jcpds_name+'.jcpds'
fn_peakpo = './jcpds-peakpo/'+jcpds_name+'-pkpo.jcpds'


# ## Content of the dioptas JCPDS file

# In[35]:


get_ipython().system('head {fn_dioptas}')


# In[36]:


get_ipython().run_line_magic('matplotlib', 'inline')


# In[37]:


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# `ds_jcpds` is written by Dan Shim for making a jcpds file.

# In[38]:


import sys
sys.path.append('../../peakpo/')
sys.path.append('../local_modules/')
import ds_jcpds
import quick_plots as quick


# import `jcpds-dioptas`

# In[39]:


import jcpds_dioptas as jcpds_dioptas


# ## The function below test if the jcpds style is dioptas

# In[40]:


def check_dioptas_jcpds(fn):
    with open(fn) as fp:
        line = fp.readline()
        if "VERSION:" in line:
            return True
        else:
            return False


# ## Read JCPDS-dioptas

# The `cif` file below was downloaded from American mineralogist crystal structure database.

# In[41]:


check_dioptas_jcpds(fn_dioptas)


# ## Read dioptas style JCPDS

# In[42]:


jcpds_dioptas = jcpds_dioptas.jcpds()


# In[43]:


jcpds_dioptas.load_file(fn_dioptas)


# ## Read dioptas JCPDS and attach to Peakpo JCPDS object

# In[44]:


jcpds_peakpo = ds_jcpds.JCPDS()

jcpds_peakpo.version = 4
jcpds_peakpo.symmetry = jcpds_dioptas.params['symmetry'].lower()
jcpds_peakpo.k0 = jcpds_dioptas.params['k0']
jcpds_peakpo.k0p = jcpds_dioptas.params['k0p']
jcpds_peakpo.thermal_expansion = jcpds_dioptas.params['alpha_t0']
jcpds_peakpo.a0 = jcpds_dioptas.params['a0']
jcpds_peakpo.b0 = jcpds_dioptas.params['b0']
jcpds_peakpo.c0 = jcpds_dioptas.params['c0']
jcpds_peakpo.alpha0 = jcpds_dioptas.params['alpha0']
jcpds_peakpo.beta0 = jcpds_dioptas.params['beta0']
jcpds_peakpo.gamma0 = jcpds_dioptas.params['gamma0']
jcpds_peakpo.v0 = jcpds_dioptas.params['v0']

diff_lines = []

for line in jcpds_dioptas.reflections:
    DiffLine = ds_jcpds.DiffractionLine()
    DiffLine.dsp0 = line.d0
    DiffLine.intensity = line.intensity
    DiffLine.h = line.h
    DiffLine.k = line.k
    DiffLine.l = line.l
    diff_lines.append(DiffLine)

jcpds_peakpo.DiffLines = diff_lines


# ## Save to a PeakPo style JCPDS file

# In[45]:


jcpds_peakpo.write_to_file(fn_peakpo, 
                           comments=jcpds_dioptas.params['comments'][0])


# In[46]:


get_ipython().system('head {fn_peakpo}')


# In[ ]:





# In[ ]:




