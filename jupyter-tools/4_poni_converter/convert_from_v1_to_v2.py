#!/usr/bin/env python
# coding: utf-8

# # Poni converter to version 2

# At least between `pyFAI` `0.18.0` and `0.14.2` we found conversion in `PONI` file format.  At synchrotron, we often find latest `PONI` but not in our own computers.  
# 
# This notebook allow you to convert `PONI` to older version.

# In[11]:


import collections


# In[12]:


def read_from_file(filename):
    data = collections.OrderedDict()
    with open(filename) as opened_file:
        for line in opened_file:
            if line.startswith("#") or (":" not in line):
                continue
            words = line.split(":", 1)

            key = words[0].strip().lower()
            try:
                value = words[1].strip()
            except Exception as error:  # IGNORE:W0703:
                _logger.error("Error %s with line: %s", error, line)
            data[key] = value
    return data


# In[13]:


def write_to_v2(filename_v1):
    filename_v2 = filename_v1+'.v2.poni'
    data_v1 = read_from_file(filename_v1)
    fd = open(filename_v2, "w") 
    fd.write(("# Nota: C-Order, 1 refers to the Y axis," 
             " 2 to the X axis \n"))
    fd.write("# Converted from %s\n" % filename_v1)
    fd.write("poni_version: 2\n")
    fd.write("Detector: %s\n" % 'detector unknown')
    fd.write('Detector_config: {{ "pixel1": {0:s}, "pixel2": {1:s}, "max_shape": null }} \n'.format(data_v1['pixelsize1'], data_v1['pixelsize2']))
    fd.write("Distance: %s\n" % data_v1['distance'])
    fd.write("Poni1: %s\n" % data_v1['poni1'])
    fd.write("Poni2: %s\n" % data_v1['poni2'])
    fd.write("Rot1: %s\n" % data_v1['rot1'])
    fd.write("Rot2: %s\n" % data_v1['rot2'])
    fd.write("Rot3: %s\n" % data_v1['rot3'])
    fd.write("Wavelength: %s\n" % data_v1['wavelength'])


# In[14]:


get_ipython().run_line_magic('ls', 'examples')


# In[15]:


old_poni_file = './examples/LaB6_30keV_P_cen_p30_w_003_v1.poni'
#new_poni_file = './examples/LaB6_30keV_P_cen_p30_w_003_v1.poni'+'v2.poni'


# In[16]:


old_poni_info = read_from_file(old_poni_file)
old_poni_info


# In[17]:


filename_v1 = old_poni_file


# In[18]:


write_to_v2(filename_v1)


# In[19]:


get_ipython().run_line_magic('ls', './examples')


# In[20]:


get_ipython().run_line_magic('cat', './examples/LaB6_30keV_P_cen_p30_w_003_v1.poni.v2.poni')


# In[ ]:





# In[ ]:




