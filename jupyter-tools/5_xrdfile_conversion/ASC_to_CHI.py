#!/usr/bin/env python
# coding: utf-8

# In[1]:


get_ipython().run_line_magic('ls', '')


# In[2]:


import numpy as np
import matplotlib.pyplot as plt


# In[4]:


filen = 'feooh'


# In[5]:


data = np.loadtxt(filen+'.ASC')


# In[6]:


plt.plot(data[:,0], data[:,1])


# In[7]:


plt.plot(data[:,0], data[:,2])


# In[8]:


import sys

sys.path.append('../../peakpo/')
import utils


# In[9]:


utils.writechi(filen+'.chi', data[:,0], data[:,1])


# In[ ]:




