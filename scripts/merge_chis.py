#!/usr/bin/python

import sys
import os
import getopt
"""
import pymatgen as mg
from pymatgen import Lattice, Structure
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import numpy as np
"""
import glob
sys.path.insert(0, '../peakpo')
from utils import writechi
import numpy as np


def main(argv):
    inputfolder = ''
    outputfile = ''
    try:
        opts, __ = getopt.getopt(argv, "hi:o:", ["ifolder=", "ofile="])
    except getopt.GetoptError:
        help()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            help()
            sys.exit()
        elif opt in ("-i", "--ifolder"):
            inputfolder = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    print('merge_chis by S.-H. Dan Shim, 2017')
    print('Input folder is: ', inputfolder)

    '''
    if os.path.dirname(inputfile) == '':
        ifile = inputfile  # os.path.join('cifs', inputfile)
    '''
    if not os.path.isdir(inputfolder):
        print('[Error] Cannot find the input folder')
        return
    chi_file = os.path.join(inputfolder, '*.chi')
    files = glob.glob(chi_file)
    n_files = files.__len__()
    if n_files == 1:
        print('[Error] There is only one file.  So no need to merge.')
        return
    twoth_list = []
    intensity_list = []
    print('Input files are:')
    for f in files:
        print(f)
        data = np.loadtxt(f, skiprows=4)
        twoth, intensity = data.T
        twoth_list.append(twoth)
        intensity_list.append(intensity)
    intensity_merged = np.zeros_like(intensity_list[0])
    for twoth_i, intensity_i in zip(twoth_list, intensity_list):
        if not np.array_equal(twoth_i, twoth_list[0]):
            print('[Error] Some of the files do not have the same two theta.')
            return
        intensity_merged = intensity_merged + intensity_i
    writechi(outputfile, twoth_list[0], intensity_merged)
    print('Output file is: ', outputfile)


def help():
    print('merge_chis.py -i <folder_for_input_files> -o <outputfile>')
    print("e.x.) $ merge_chis.py -i './chi/' -o './output.chi'")
    print('by S.-H. Dan Shim, 2017.')
    print("Merge chi files integrated from different azimuthal angle.")
    print("Two theta angle array should be the same among the input chi files.")
    print("Do not move this script out of this folder.")
    print("If you do so, you need to modify the script.")
    print("Recommended output filename, for example, hStv030_101.merged.chi")


if __name__ == "__main__":
    main(sys.argv[1:])
