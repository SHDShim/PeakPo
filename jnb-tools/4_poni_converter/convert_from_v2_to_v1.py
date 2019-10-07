#!/usr/bin/env python
# coding: utf-8

# # Poni converter to version 1

# At least between `pyFAI` `0.18.0` and `0.14.2` we found conversion in `PONI` file format.  At synchrotron, we often find latest `PONI` but not in our own computers.  
# 
# This notebook allow you to convert `PONI` to older version.

# In[16]:


import collections


# In[17]:


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


# In[88]:


def write_to_v1(filename_v2):
    filename_v1 = filename_v2+'.v1.poni'
    data_v2 = read_from_file(filename_v2)
    fd = open(filename_v1, "w") 
    fd.write(("# Nota: C-Order, 1 refers to the Y axis," 
             " 2 to the X axis \n"))
    fd.write("# Converted from %s\n" % filename_v2)
    pixel1 = data_v2['detector_config'].split(",")[0].split(":")[1]
    pixel2 = data_v2['detector_config'].split(",")[1].split(":")[1]
    fd.write('PixelSize1: %s \n' % pixel1)
    fd.write('PixelSize2: %s \n' % pixel2)
    fd.write("Distance: %s\n" % data_v2['distance'])
    fd.write("Poni1: %s\n" % data_v2['poni1'])
    fd.write("Poni2: %s\n" % data_v2['poni2'])
    fd.write("Rot1: %s\n" % data_v2['rot1'])
    fd.write("Rot2: %s\n" % data_v2['rot2'])
    fd.write("Rot3: %s\n" % data_v2['rot3'])
    fd.write("Wavelength: %s\n" % data_v2['wavelength'])


# In[89]:


get_ipython().run_line_magic('ls', 'examples')


# In[90]:


v2_poni_file = './examples/LaB6_30keV_P_cen_p30_w_003.poni'


# In[91]:


get_ipython().run_line_magic('cat', '$v2_poni_file')


# In[92]:


v2_poni_info = read_from_file(v2_poni_file)
v2_poni_info


# In[93]:


filename_v2 = v2_poni_file


# In[94]:


write_to_v1(filename_v2)


# In[95]:


get_ipython().run_line_magic('ls', './examples')


# In[96]:


get_ipython().run_line_magic('cat', './examples/LaB6_30keV_P_cen_p30_w_003.poni.v1.poni')


# In[ ]:




