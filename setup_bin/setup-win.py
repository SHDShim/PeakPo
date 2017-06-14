# -*- coding: utf-8 -*-
"""
Created on Tue Feb 10 16:43:57 2015

@author: Antonio Buono
"""
'''
python setup.py py2exe
Some missing DLL should be placed in 
C:\Users\Antonio Buono\Anaconda\Lib\site-packages\numpy\core
see the following for matplotlib error
http://www.py2exe.org/index.cgi/MatPlotLib
'packages': ['matplotlib']: causes some problem
'''
from distutils.core import setup
from py2exe.build_exe import py2exe

from distutils.filelist import findall
import os
import matplotlib

includes = ["sip", "scipy.sparse.csgraph._validation",\
            "scipy.special._ufuncs_cxx"]
excludes = []

opts = {"py2exe": {"includes": includes, "excludes": excludes}}

#matplotlibdatadir = matplotlib.get_data_path()
#matplotlibdata = findall(matplotlibdatadir)
#matplotlibdata_files = []

#for f in matplotlibdata:
#    dirname = os.path.join('matplotlibdata', f[len(matplotlibdatadir)+1:])
#    matplotlibdata_files.append((os.path.split(dirname)[0], [f]))

#py2exe_options={"py2exe":{"includes":[],\
#        "dll_excludes":['libifcoremd.dll']}}
#py2exe_options={"py2exe":{"dll_excludes":['libifcoremd.dll', 'libiomp5md.dll',\
#                'libmmd.dll']}}
#py2exe_options={"py2exe":{"dll_excludes":[], 'packages': ['matplotlib'],\
#                "includes": includes}}

setup( options=opts, windows=[{"script": "peakpo.py",
    "icon_resources": [(1, "icon\PeakPo.ico")]}],
    data_files = matplotlib.get_py2exe_datafiles())
#setup(console=['peakpo.py'], options = opts, \
#        data_files = matplotlib.get_py2exe_datafiles())      
