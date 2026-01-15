#!/usr/bin/env python
# coding: utf-8

# # Folder structure

# The example here assumes that the `local_modules` folder exists above the individual folders. If you decide to move the folder, please also update the notebooks to reflect the new locations.
# 
# ```python
# import sys
# sys.path.append('../local_modules')
# ```

# # How to setup kernel for the notebooks in this folder
# 
# Run this notebook file in a conda environment set up for `PeakPo`. For details, refer to the installation instructions and environment files provided there.

# # How to resolve dpp version issue (update needed)

# - As of April 2019, we have an issue with `dpp` incompatibility caused by `pyFAI`.  If you made your `dpp` with `pyFAI` older than version `0.15`, then you cannot read them with `pyFAI` version `0.17` or later.  The example files I provide here is made with an old `pyFAI`.
# 
# - If you have an error in reading your dpp by: `model_dpp = dill.load(f)`, please follow the instruction below.
# 
#     - Do not change or remove your working `PeakPo` conda environment.  Instead, we will clone it.
#     ```bash
#     conda create --name <new-env-with-old-pyFAI> --clone <your-existing-env-for-peakpo>
#     
#     conda activate <your-existing-env-for-peakpo>
#     
#     conda install pyfai==0.14.2
#     ```
# 
# 
#     - Now you can run `jupyter lab` and try this notebook with the new clonned environment.
#     
#     - If you do not see your new conda environment in the kernel list, please add your new conda environment following the instruction below.
# 
# - How to add a conda kernel
# 
# ```bash
# $ conda install ipykernel  # only if you do not have ipykernel installed.
# 
# $ python -m ipykernel install --user --name <conda-env-to-add> --display-name <conda-env-to-add>
# 
# ```

# In[ ]:




