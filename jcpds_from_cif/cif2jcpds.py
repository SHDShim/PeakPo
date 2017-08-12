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
sys.path.insert(0, '../peakpo')
import ds_jcpds


def main(argv):
    inputfile = ''
    outputfile = ''
    try:
        opts, __ = getopt.getopt(argv, "hi:o:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        help()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            help()
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    print('cif2jcpds by S.-H. Dan Shim, 2017')
    print('Input file is: ', inputfile)
    print('Output file is: ', outputfile)

    k0 = 200.
    k0p = 4.00
    alpha = 1.00e-5
    xrange = (0, 40)

    '''
    if os.path.dirname(inputfile) == '':
        ifile = inputfile  # os.path.join('cifs', inputfile)
    '''
    if not os.path.exists(inputfile):
        print('[Error] Cannot find the input file')
        return
    material_jcpds = ds_jcpds.JCPDS()
    material_jcpds.set_from_cif(inputfile, k0, k0p, thermal_expansion=alpha,
                                two_theta_range=xrange)
    material_jcpds.write_to_file(
        outputfile,
        comments='From cif2jcpds. Write comment here.' +
        ' Update the k0, k0p, and alpha values in lines 3 and 5.')


def help():
    print('cif2jcpds.py -i <inputfile> -o <outputfile>')
    print('by S.-H. Dan Shim, 2017.')
    print("New jcpds has: k0=200, k0p=4, and alpha=1e-5.")
    print("Open the jcpds file and adjust those numbers.")
    print("Do not move this script out of this folder.")
    print("If you do so, you need to modify the script.")


if __name__ == "__main__":
    main(sys.argv[1:])
