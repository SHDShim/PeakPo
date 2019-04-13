
# coding: utf-8

# In[8]:


# Set up some imports that we will need
from pymatgen import Lattice, Structure
import pymatgen as mg
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


# In[10]:


import numpy


# In[12]:


get_ipython().run_line_magic('ls', './jcpds/')


# In[6]:


import xrayutilities as xru
from xrayutilities.materials.cif import CIFFile
from xrayutilities.materials.material import Crystal


# In[7]:


from IPython.display import Image, display
from tempfile import NamedTemporaryFile
import matplotlib.pyplot as plt 
import matplotlib.ticker as ticker
get_ipython().run_line_magic('matplotlib', 'inline')
matplotlib.rcParams.update({'font.size': 18})
fig_size = [15, 12]
plt.rcParams["figure.figsize"] = fig_size


# In[ ]:


# Create beta-CsCl structure
a = 6.923 #Angstrom
latt = Lattice.cubic(a)
structure = Structure(latt, ["Cs", "Cs", "Cs", "Cs", "Cl", "Cl", 
"Cl", "Cl"], [[0, 0, 0], [0.5, 0.5, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0.5], [0, 0, 0.5], [0, 0.5, 0], [0.5, 0, 0]])

temp_cif = NamedTemporaryFile(delete=False)
structure.to("cif", temp_cif.name)
xu_cif = CIFFile(temp_cif.name)
xu_crystal = Crystal(name="b-CsCl", lat=xu_cif.SGLattice())
temp_cif.close()

two_theta = numpy.arange(0, 80, 0.01)

powder = xru.simpack.smaterials.Powder(xu_crystal, 1)
pm = xru.simpack.PowderModel(powder, I0=100)
intensities = pm.simulate(two_theta)
plt.plot(two_theta,intensities)
plt.xlim(0,80)
ax = plt.axes()
ax.xaxis.set_major_locator(ticker.MultipleLocator(5))
ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.4f'))
plt.title("XRD Pattern for " + xu_crystal.name)
plt.xlabel("2 theta (degrees)")
plt.ylabel("Intensity")
plt.show()

