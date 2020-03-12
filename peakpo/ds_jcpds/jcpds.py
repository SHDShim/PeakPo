import numpy as np
import os
from pytheos import bm3_v
from .xrd import cal_UnitCellVolume, cal_dspacing
import pymatgen as mg
from pymatgen.analysis.diffraction.xrd import XRDCalculator
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from .jcpds_dioptas import jcpds

# import numpy.ma as ma


class DiffractionLine:
    """
    Class that defines a single diffraction line.
    Attributes:
      dsp0: d-spacing at reference conditions (P = 0 GPa and T = 300 K)
      dsp:  d-spacing at high PT
      intensity:  diffraction intensity read from the file
      h, k, l: Miller index
    """

    def __init__(self):
        self.dsp0 = 0.
        self.dsp = 0.
        self.intensity = 0.
        self.h = 0.
        self.k = 0.
        self.l = 0.


class UnitCell(object):
    """
    Class that defines a unit cell properties
    """

    def __init__(self):
        self.name = ''
        self.a = 0.
        self.b = 0.
        self.c = 0.
        self.alpha = 0.
        self.beta = 0.
        self.gamma = 0.
        self.v = 0.
        self.DiffLines = []
        self.symmetry = ''
        self.color = ''
        self.display = True

    def cal_dsp(self):
        """
        b_a and c_a are newly included for adjusting axial ratios.
        For cubic structure, these two inputs are ignored.
        For tetragonal and hexagonal, only c_a will be used.
        """
#            a = self.a; b = self.b; c = self.c;
#            alpha = self.alpha; beta = self.beta; gamma = self.gamma
        self.v = cal_UnitCellVolume(self.symmetry, self.a, self.b, self.c,
                                    self.alpha, self.beta, self.gamma)
        for dl in self.DiffLines:
            dsp = cal_dspacing(self.symmetry, dl.h, dl.k, dl.l,
                               self.a, self.b, self.c,
                               self.alpha, self.beta, self.gamma)
            dl.dsp = dsp

    def get_tthVSint(self, wavelength):
        """
        Returns twoth and intensity for bar plots in PyPeakPo
        Note that tth and intensity are numpy array not list
        If P, T, b_a, c_a have changed, run cal_dsp first for update
        """
#        self.cal_dsp(pressure, temperature, b_a, c_a)
        dsp = []
        intensity = []
        for line in self.DiffLines:
            d = line.dsp
            i = line.intensity
            dsp.append(d)
            intensity.append(i)
        tth = 2. * np.degrees(np.arcsin(wavelength / 2. / np.array(dsp)))
        return tth, np.array(intensity)

    def find_DiffLine(self, tth_c, wavelength):
        """
        Returns index of the cloest diffraction line, its difference
            in abs tth
        If P, T, b_a, c_a have changed, run cal_dsp first for update
        """
        tth, intensity = self.get_tthVSint(wavelength)

        idx = (np.abs(tth - tth_c)).argmin()

        return idx, abs(tth[idx] - tth_c), tth[idx]

    def make_TextOutput(self, pressure, temperature):
        textout = self.name + '\n'
        textout += self.symmetry + '\n'
        textout += '******************\n'
        textout += \
            'Values for Ucfit\n'
        textout += 'a = {0: .5f} A, b = {1: .5f} A, c = {2: .5f} A\n'.\
            format(float(self.a), float(self.b), float(self.c))
        textout += 'alpha = {0: .5f}, beta = {1: .5f}, gamma = {2: .5f}\n'.\
            format(self.alpha, self.beta, self.gamma)
        textout += 'b/a = {0: .5f}, c/a = {1: .5f}\n'.\
            format(self.b / self.a, self.c / self.a)
        textout += 'V = {0: .5f} A^3\n\n'.format(float(self.v))
        textout += 'Below are the peaks at {0: 6.1f} GPa, {1: 5.0f} K\n'.\
            format(pressure, temperature)
        textout += 'd-spacing (A), intensity (%), h, k, l\n'
        for dl in self.DiffLines:
            textout += \
                "{0: .5f}, {1: .1f}, {2: .0f}, {3: .0f}, {4: .0f}\n".\
                format(float(dl.dsp), dl.intensity, dl.h, dl.k, dl.l)
        return textout


class JCPDS(object):
    """
    Class that defines a single JCPDS card.
    see __init__ for the involved parameters
    """

    def __init__(self, filename=None):
        if filename is None:
            self.file = ' '
            self.name = ' '
            self.version = 0
            self.comments = []
            self.symmetry = ''
            self.k0 = 0.
            self.k0p = 0.  # k0p at 298K
            self.thermal_expansion = 0.  # alphat at 298K
            self.a0 = 0.
            self.b0 = 0.
            self.c0 = 0.
            self.alpha0 = 0.
            self.beta0 = 0.
            self.gamma0 = 0.
            self.v0 = 0.
            self.DiffLines = []
        else:
            self.file = filename
            self.read_file(self.file)
        self.a = 0.
        self.b = 0.
        self.c = 0.
        self.alpha = 0.
        self.beta = 0.
        self.gamma = 0.
        self.v = 0.

    def _check_dioptas_jcpds(self, file):
        with open(file) as fp:
            line = fp.readline()
            if "VERSION:" in line:
                return True
            else:
                return False


    def read_file(self, file):
        """
        read a jcpds file
        """
        self.file = file
        # Construct base name = file without path and without extension
        name = os.path.splitext(os.path.basename(self.file))[0]
        self.name = name
#        line = '', nd=0
        version = 0.
        self.comments = []
        self.DiffLines = []

#        my_list = [] # get all the text first and throw into my_list

        if self._check_dioptas_jcpds(file): # dioptas
            jcpds_dioptas = jcpds()
            jcpds_dioptas.load_file(file)
            self.version = 4
            self.comments = jcpds_dioptas.params['comments'][0] + \
                ': This is from Dioptas style jcpds'
            self.symmetry = jcpds_dioptas.params['symmetry'].lower()
            self.k0 = jcpds_dioptas.params['k0']
            self.k0p = jcpds_dioptas.params['k0p']
            self.thermal_expansion = jcpds_dioptas.params['alpha_t0']
            self.a0 = jcpds_dioptas.params['a0']
            self.b0 = jcpds_dioptas.params['b0']
            self.c0 = jcpds_dioptas.params['c0']
            self.alpha0 = jcpds_dioptas.params['alpha0']
            self.beta0 = jcpds_dioptas.params['beta0']
            self.gamma0 = jcpds_dioptas.params['gamma0']
            self.v0 = jcpds_dioptas.params['v0']
            diff_lines = []

            for line in jcpds_dioptas.reflections:
                DiffLine = DiffractionLine()
                DiffLine.dsp0 = line.d0
                DiffLine.intensity = line.intensity
                DiffLine.h = line.h
                DiffLine.k = line.k
                DiffLine.l = line.l
                self.DiffLines.append(DiffLine)
        else:
            inp = open(file, 'r').readlines()
            version = int(inp[0])  # JCPDS version number
            self.version = version
            header = inp[1]  # header
            self.comments = header

            item = str.split(inp[2])
            crystal_system = int(item[0])
            if crystal_system == 1:
                self.symmetry = 'cubic'
            elif crystal_system == 2:
                self.symmetry = 'hexagonal'
            elif crystal_system == 3:
                self.symmetry = 'tetragonal'
            elif crystal_system == 4:
                self.symmetry = 'orthorhombic'
            elif crystal_system == 5:
                self.symmetry = 'monoclinic'
            elif crystal_system == 6:
                self.symmetry = 'triclinic'
            elif crystal_system == 7:
                self.symmetry = 'nosymmetry'
            # 1 cubic, 2 hexagonal, 3 tetragonal, 4 orthorhombic
            # 5 monoclinic, 6 triclinic, 7 no nosymmetry P, d-sp input

            k0 = float(item[1])
            k0p = float(item[2])
            self.k0 = k0
            self.k0p = k0p

            item = str.split(inp[3])  # line for unit-cell parameters

            if crystal_system == 1:  # cubic
                a = float(item[0])
                b = a
                c = a
                alpha = 90.
                beta = 90.
                gamma = 90.
            elif crystal_system == 7:  # P, d-sp input
                a = float(item[0])
                b = a
                c = a
                alpha = 90.
                beta = 90.
                gamma = 90.
            elif crystal_system == 2:  # hexagonal
                a = float(item[0])
                c = float(item[1])
                b = a
                alpha = 90.
                beta = 90.
                gamma = 120.
            elif crystal_system == 3:  # tetragonal
                a = float(item[0])
                c = float(item[1])
                b = a
                alpha = 90.
                beta = 90.
                gamma = 90.
            elif crystal_system == 4:  # orthorhombic
                a = float(item[0])
                b = float(item[1])
                c = float(item[2])
                alpha = 90.
                beta = 90.
                gamma = 90.
            elif crystal_system == 5:  # monoclinic
                a = float(item[0])
                b = float(item[1])
                c = float(item[2])
                beta = float(item[3])
                alpha = 90.
                gamma = 90.
            elif crystal_system == 6:  # triclinic
                a = float(item[0])
                b = float(item[1])
                c = float(item[2])
                alpha = float(item[3])
                beta = float(item[4])
                gamma = float(item[5])

            self.a0 = a
            self.b0 = b
            self.c0 = c
            self.alpha0 = alpha
            self.beta0 = beta
            self.gamma0 = gamma

            item = str.split(inp[4])

            if self.version == 3:
                thermal_expansion = 0.
            else:
                thermal_expansion = float(item[0])
            self.thermal_expansion = thermal_expansion

            for line in inp[6:]:
                item = str.split(line)
                if len(item) != 5:
                    break
                DiffLine = DiffractionLine()
                DiffLine.dsp0 = float(item[0])
                DiffLine.intensity = float(item[1])
                DiffLine.h = float(item[2])
                DiffLine.k = float(item[3])
                DiffLine.l = float(item[4])
                self.DiffLines.append(DiffLine)

        self._cal_v0()
        self.v = self.v0
        self.a = self.a0
        self.b = self.b0
        self.c = self.c0
        self.alpha = self.alpha0
        self.beta = self.beta0
        self.gamma = self.gamma0

    def _cal_v0(self):
        """
        Computes the unit cell volume of the material at zero pressure and
        temperature from the unit cell parameters.
        """
        self.v0 = cal_UnitCellVolume(self.symmetry,
                                     self.a0, self.b0, self.c0,
                                     self.alpha0, self.beta0, self.gamma0)

    def _cal_v(self, pressure=0., temperature=300.):
        """
        Calculate volume at high pressure
        """
        pressure_st = pressure - self.thermal_expansion * \
            self.k0 * (temperature - 300.)
        if pressure == 0.0:  # p = 0 GPa
            self.v = self.v0
        else:
            if self.symmetry == 'nosymmetry':
                self.v = self.v0
            else:
                # print(pressure_st, self.v0, self.k0, self.k0p)
                self.v = bm3_v(pressure_st, self.v0, self.k0, self.k0p,
                               min_strain=0.3)

    def cal_dsp(self, pressure=0., temperature=300.,
                b_a=None, c_a=None, use_table_for_0GPa=True):
        """
        b_a and c_a are newly included for adjusting axial ratios.
        For cubic structure, these two inputs are ignored.
        For tetragonal and hexagonal, only c_a will be used.

        recalculate_zero = False: use the table d-spacing value for 0 GPa
        """

        # angles are always set to original values, so no need to reset
        # self.alpha = self.alpha0;
        # self.beta = self.beta0; self.gamma = self.gamma0
        self._cal_v(pressure, temperature)
        if b_a is None:
            b_a = self.b0 / self.a0
        if c_a is None:
            c_a = self.c0 / self.a0

        if (((pressure == 0.0) and (use_table_for_0GPa))
                or (self.symmetry == 'nosymmetry')):
            # p = 0 GPa, resetting to uc0 is necessary
            self.v = self.v0
            self.a = self.a0
            self.b = self.b0
            self.c = self.c0
            for dl in self.DiffLines:
                dsp = dl.dsp0
                dl.dsp = dsp
#            DLines = self.get_DiffractionLines()
#            for dl in DLines:
#                dsp = dl.dsp0
#                dl.dsp = dsp
        else:
            self._cal_UCPatPT(b_a, c_a)
            DLines = self.get_DiffractionLines()
#            a = self.a; b = self.b; c = self.c;
#            alpha = self.alpha; beta = self.beta; gamma = self.gamma
            for dl in DLines:
                dsp = cal_dspacing(self.symmetry, dl.h, dl.k, dl.l,
                                   self.a, self.b, self.c,
                                   self.alpha, self.beta, self.gamma)
                dl.dsp = dsp
            # the code worked without the following line, perhaps
            # due to the referencing or copy issue in python list
            self.DiffLines = DLines[:]

    def get_DiffractionLines(self):
        """
        Returns the information for each reflection for the material.
        This information is an array of elements of class jcpds_reflection
        """
        return self.DiffLines

    def get_tthVSint(self, wavelength):
        """
        Returns twoth and intensity for bar plots in PyPeakPo
        Note that tth and intensity are numpy array not list
        If P, T, b_a, c_a have changed, run cal_dsp first for update
        """
#        self.cal_dsp(pressure, temperature, b_a, c_a)
        DLines = self.get_DiffractionLines()

        dsp = []
        intensity = []
        for line in DLines:
            d = line.dsp
            i = line.intensity
            dsp.append(d)
            intensity.append(i)
        tth = 2. * np.degrees(np.arcsin(wavelength / 2. / np.array(dsp)))
        return tth, np.array(intensity)

    def get_hkl_in_text(self):
        hkl = []
        for line in self.DiffLines:
            hkl.append("{0:.0f} {1:.0f} {2:.0f}".format(line.h, line.k, line.l))
        return hkl

    def find_DiffLine(self, tth_c, wavelength):
        """
        Returns index of the cloest diffraction line, its difference
            in abs tth
        If P, T, b_a, c_a have changed, run cal_dsp first for update
        """
        tth, intensity = self.get_tthVSint(wavelength)

        idx = (np.abs(tth - tth_c)).argmin()

        return idx, abs(tth[idx] - tth_c), tth[idx]

    def _cal_UCPatPT(self, b_a, c_a):
        if self.symmetry == 'cubic':
            self.a = (self.v)**(1. / 3.)
            self.b = self.a
            self.c = self.a
        elif (self.symmetry == 'hexagonal') or (self.symmetry == 'trigonal'):
            # self.a = (2. * self.v / (np.sqrt(3.)*self.c0/self.a0) )**(1./3.)
            self.a = (2. * self.v / (np.sqrt(3.) * c_a))**(1. / 3.)
            self.b = self.a
            self.c = self.a * c_a
        elif self.symmetry == 'tetragonal':
            # self.a = (self.v/(self.c0/self.a0))**(1./3.) ; self.b = self.a
            self.a = (self.v / (c_a))**(1. / 3.)
            self.b = self.a
            self.c = c_a * self.a
        elif self.symmetry == 'orthorhombic':
            # self.a = (self.v/(self.b0/self.a0*self.c0/self.a0))**(1./3.)
            self.a = (self.v / (b_a * c_a))**(1. / 3.)
            self.c = c_a * self.a
            self.b = b_a * self.a
        elif self.symmetry == 'monoclinic':
            # self.a = ( self.v / (self.b0/self.a0*self.c0/self.a0*\
            #        np.sin(np.radians(self.beta0))))**(1./3.)
            self.a = (self.v / (b_a * c_a *
                                np.sin(np.radians(self.beta0))))**(1. / 3.)
            self.c = c_a * self.a
            self.b = b_a * self.a
        elif self.symmetry == 'triclinic':
            a_term = np.sqrt(1. - (np.cos(np.radians(self.alpha0)))**2. -
                             (np.cos(np.radians(self.beta0)))**2. -
                             (np.cos(np.radians(self.gamma0)))**2. +
                             2. * np.cos(np.radians(self.alpha0)) *
                             np.cos(np.radians(self.beta0)) *
                             np.cos(np.radians(self.gamma0)))
            # self.a = (self.v/(self.b0/self.a0*self.c0/self.a0*a_term))
            # **(1./3.)
            self.a = (self.v / (b_a * c_a * a_term))**(1. / 3.)
            self.c = c_a * self.a
            self.b = b_a * self.a
        else:
            print('no symmetry is given')

#    return {'ver': ver, 'header': header, 'crystal_system': crystal_system, \
#            'K0': K0, 'K0p': K0p, 'u_param':
#               np.asarray([a,b,c,alpha,beta,gamma]), \
#            'alpha': thermal_expansion, 'peaks':
#           np.asarray([dsp, intensity, h, k, l]).T, \
#            'b_a': b_a, 'c_a': c_a}
    def set_from_cif(self, fn_cif, k0, k0p, file=None, name='',
                     version=4, comments='', thermal_expansion=0.,
                     two_theta_range=(0., 40.)):
        """
        define a JCPDS from CIF file.  made for jupyter notebook

        Parameters
        ----------
        fn_cif = file name and path of cif
        k0 = bulk modulus
        k0p = pressure derivative of k0
        file = name of file, optional (default = None)
        name = name of JCPDS, optional (default = '')
        version = version for JCPDS format, optional (default = 4)
        comments = comments for JCPDS file, optional (default = '')
        thermal_expansion = thermal expansion, optional (default = 0.)

        Returns
        -------

        """

        structure = mg.Structure.from_file(fn_cif)
        self.set_from_pymatgen(structure, k0, k0p, file=file,
                               name=name, version=version,
                               comments=comments,
                               thermal_expansion=thermal_expansion)

    def set_from_pymatgen(self, structure, k0, k0p, file=None,
                          name='', version=4,
                          comments='', thermal_expansion=0.,
                          two_theta_range=(0., 40.)):
        """
        set parameters from pymatgen outputs

        Parameters
        ----------
        structure = pymatgen structure object
        k0 = bulk modulus
        k0p = pressure derivative of bulk modulus
        file = file name (optional)
        name = name (optional)
        version = version (optional)
        comments = comments (optional)
        thermal_expansion = 0 (optional)

        Returns
        -------

        """
        lattice = structure.lattice
        self.k0 = k0
        self.k0p = k0p
        self.a0 = lattice.a
        self.b0 = lattice.b
        self.c0 = lattice.c
        self.alpha0 = lattice.alpha
        self.beta0 = lattice.beta
        self.gamma0 = lattice.gamma
        self.symmetry = SpacegroupAnalyzer(structure).get_crystal_system()
        self.file = file
        self.name = name
        self.version = version
        self.comments = comments
        self.thermal_expansion = thermal_expansion
        self.v0 = cal_UnitCellVolume(self.symmetry,
                                     self.a0, self.b0, self.c0,
                                     self.alpha0, self.beta0,
                                     self.gamma0)
        c = XRDCalculator(wavelength=0.3344)
        pattern = c.get_pattern(structure, two_theta_range=two_theta_range)
        h = []
        k = []
        l = []
        for i in range(pattern.hkls.__len__()):
            h.append(pattern.hkls[i][0]['hkl'][0])
            k.append(pattern.hkls[i][0]['hkl'][1])
            l.append(pattern.hkls[i][0]['hkl'][-1])
        d_lines = np.transpose([pattern.x, pattern.d_hkls, pattern.y, h, k, l])
        DiffLines = []
        for line in d_lines:
            d_line = DiffractionLine()
            d_line.dsp0 = line[1]
            d_line.dsp = line[1]
            d_line.intensity = line[2]
            d_line.h = int(line[3])
            d_line.k = int(line[4])
            d_line.l = int(line[5])
            DiffLines.append(d_line)
        self.DiffLines = DiffLines

    def write_to_file(self, filename, comments=" "):
        """
        write a JCPDS file

        Parameters
        ----------
        filename = path and name of file

        Returns
        -------

        """
        f = open(filename, 'w')
        f.write("{:d}\n".format(self.version))
        f.write(comments + "\n")

        # 1 cubic, 2 hexagonal, 3 tetragonal, 4 orthorhombic
        # 5 monoclinic, 6 triclinic, 7 nosymmetry P, d-sp input

        str_el = "{0:.2f} {1:.2f}".format(self.k0, self.k0p)

        if self.symmetry == 'cubic':  # cubic
            crystal_system = '1 '
            str_uc = "{0:.5f}".format(self.a0)
        elif self.symmetry == 'nosymmetry':  # P, d-sp input
            crystal_system = '7 '
            str_uc = "{0:.5f}".format(self.a0)
        elif self.symmetry == 'hexagonal' or self.symmetry == 'trigonal':
            crystal_system = '2 '
            str_uc = "{0:.5f} {1:.5f}".format(self.a0, self.c0)
        elif self.symmetry == 'tetragonal':  # tetragonal
            crystal_system = '3 '
            str_uc = "{0:.5f} {1:.5f}".format(self.a0, self.c0)
        elif self.symmetry == 'orthorhombic':  # orthorhombic
            crystal_system = '4 '
            str_uc = "{0:.5f} {1:.5f} {2:.5f}".format(self.a0,
                                                      self.b0, self.c0)
        elif self.symmetry == 'monoclinic':  # monoclinic
            crystal_system = '5 '
            str_uc = "{0:.5f} {1:.5f} {2:.5f} {3:.5f}".format(
                self.a0, self.b0, self.c0, self.beta0)
        elif self.symmetry == 'triclinic':  # triclinic
            crystal_system = '6 '
            str_uc = "{0:.5f} {1:.5f} {2:.5f} {3:.5f} {4:.5f} \
                {5:.5f}".format(
                self.a0, self.b0, self.c0,
                self.alpha0, self.beta0, self.gamma0)

        f.write(crystal_system + str_el + " \n")
        f.write(str_uc + " \n")
        f.write("{:.4e} \n".format(self.thermal_expansion))
        f.write("d-spacing    I/I0     h   k   l \n")

        for line in self.DiffLines:
            f.write("{0:.6f} {1:.2f} {2:.1f} {3:.1f} {4:.1f} \n".format(
                line.dsp0, line.intensity, line.h, line.k, line.l))
        f.close()


class Session(object):
    '''
    Developed for PeakPo and shared with PeakFt
    From 2015/3/15, PeakPo save using this class
    '''

    def __init__(self):
        self.pattern = None  # diffraction pattern powdiff.Pattern object
        self.waterfallpatterns = []  # list of pattern object
        self.wavelength = 0.0  # normal value at GSECARS
        self.pressure = 0.0  # DONOT CHANGE, matches with Qt Designer file
        self.temperature = 300.  # DONOT CHANGE, matches with Qt Designer file
        self.jlist = []  # list for JCPDS
        self.bg_roi = [4., 16.]
        self.bg_params = [20, 10, 20]
        self.jcpds_path = ''  # redundant, but easier to code
        self.chi_path = ''  # reduendant, but easier to code


class JCPDSplt(JCPDS):
    """
    Define new JPCDS for plot.  Add two attributes, color and show switch
    Developed for supporting PeakPo but used and shared with PeakFt
    """

    def __init__(self):
        ''' _org parameter needed : self.k0, self.k0p,
        self.thermal_expansion, self.v0
        '''
        self.color = ''
        self.display = True
        self.maxint = 1.0
        self.twk_b_a = 1.0
        self.twk_c_a = 1.0
        self.twk_v0 = 1.0
        self.twk_k0 = 1.0
        self.twk_k0p = 1.0
        self.twk_thermal_expansion = 1.0
        self.twk_int = 1.0

    def read_file(self, file):
        '''
        *_twk are tweaked parameters, and twk_* are tweaking coefficients
        a0, b0, c0, alpha, beta, gamma, v0 should not be tweaked
        '''
        super(JCPDSplt, self).read_file(file)
        # make originals
        self.k0_org = self.k0
        self.k0p_org = self.k0p
        self.v0_org = self.v0
        self.thermal_expansion_org = self.thermal_expansion

    def cal_dsp(self, pressure, temperature, b_a=None, c_a=None,
                use_table_for_0GPa=True):
        '''DiffLines are tweaked one unlike other notations'''
        # set tweaked parameters
        self.k0 = self.k0_org * self.twk_k0
        self.k0p = self.k0p_org * self.twk_k0p
        self.v0 = self.v0_org * self.twk_v0
        self.thermal_expansion = self.thermal_expansion_org * \
            self.twk_thermal_expansion
        self.b_a = (self.b0 / self.a0) * self.twk_b_a
        self.c_a = (self.c0 / self.a0) * self.twk_c_a
        # get DiffLines
        super(JCPDSplt, self).cal_dsp(pressure, temperature,
                                      self.b_a, self.c_a,
                                      use_table_for_0GPa=use_table_for_0GPa)

    def get_dsp(self):
        dsp = []
        for dl in self.DiffLines:
            d = float(dl.dsp)
            dsp.append(d)
        return dsp

    def make_TextOutput(self, pressure, temperature):
        textout = 'Name: ' + self.name +'\n'
        textout += 'Crystal system: ' + self.symmetry + '\n'
        textout += '\n'
        textout += 'Values at high P-T after tweak \n'
        textout += ' a = {0:.5f} A, b = {1:.5f} A, c = {2:.5f} A\n'.\
            format(float(self.a), float(self.b), float(self.c))
        textout += ' alpha = {0:.2f}, beta = {1:.2f}, gamma = {2:.2f}\n'.\
            format(self.alpha, self.beta, self.gamma)
        textout += ' V = {0:.5f} A^3\n'.format(float(self.v))
        textout += '\n'
        if self.symmetry != 'nosymmetry':
            textout += 'Values at 1 bar and 300 K after tweak \n'
            a0_twk, b0_twk, c0_twk = get_cell_prm_twk(
                self.symmetry, self.v0, self.a0, self.b0, self.c0,
                self.alpha0, self.beta0, self.gamma0, self.twk_b_a, self.twk_c_a)
            textout += ' a0 = {0:.5f} A, b0 = {1:.5f} A, c0 = {2:.5f} A\n'.\
                format(float(a0_twk), float(b0_twk), float(c0_twk))
            textout += ' V0 = {0:.5f} A^3\n'.format(self.v0)  # v0 is tweaked value
            textout += ' K0 = {0:.1f} GPa, K0p = {1:.2f}, alpha = {2:.2e}\n'.\
                format(self.k0, self.k0p, self.thermal_expansion)
            textout += ' b/a = {0:.5f}, c/a = {1:.5f}\n'.\
                format(self.b / self.a, self.c / self.a)
            textout += ' Tweak for b/a = {0:.5f}, Tweak for c/a = {1:.5f}\n'.\
                format(self.twk_b_a, self.twk_c_a)
            textout += '\n'
            textout += 'Values in original JCPDS file\n'
            textout += ' a0 = {0:.5f} A, b0 = {1:.5f} A, c0 = {2:.5f} A\n'.\
                format(self.a0, self.b0, self.c0)
            textout += ' alpha0 = {0:.2f}, beta0 = {1:.2f}, gamma0 = {2:.2f}\n'.\
                format(self.alpha0, self.beta0, self.gamma0)
            textout += ' b0/a0 = {0:.5f}, c0/a0 = {1:.5f}\n'.\
                format(self.b0 / self.a0, self.c0 / self.a0)
            textout += ' V0 = {0:.5f} A^3\n'.format(self.v0_org)
            textout += ' K0 = {0:.1f} GPa, K0p = {1:.2f}, alpha = {2:.2e}\n'.\
                format(self.k0_org, self.k0p_org, self.thermal_expansion_org)
        textout += '\nBelow are the peaks at {0:6.2f} GPa, {1:5.0f} K\n'.\
            format(pressure, temperature)
        textout += ' d-spacing (A), intensity (%), h, k, l\n'
        for dl in self.DiffLines:
            textout += \
                " {0:10.5f}, {1:10.1f}, {2:5.0f}, {3:5.0f}, {4:5.0f}\n".\
                format(float(dl.dsp), dl.intensity, dl.h, dl.k, dl.l)
        textout += '\n'
        textout += 'File from: ' + self.file + '\n'
        textout += 'Version: ' + str(self.version) + '\n'
        textout += 'Comment from original file: ' + self.comments + '\n'

        return textout

    def write_to_twk_jcpds(self, filename, comments=" "):
        """
        write a twk JCPDS file

        Parameters
        ----------
        filename = path and name of file

        Returns
        -------

        """
        f = open(filename, 'w')
        f.write("{:d}\n".format(self.version))
        f.write(comments + "\n")

        # 1 cubic, 2 hexagonal, 3 tetragonal, 4 orthorhombic
        # 5 monoclinic, 6 triclinic, 7 nosymmetry P, d-sp input

        str_el = "{0:.2f} {1:.2f}".format(self.k0, self.k0p)

        a0_twk, b0_twk, c0_twk = get_cell_prm_twk(
            self.symmetry, self.v0, self.a0, self.b0, self.c0,
            self.alpha0, self.beta0, self.gamma0, self.twk_b_a, self.twk_c_a)

        if self.symmetry == 'cubic':  # cubic
            crystal_system = '1 '
            str_uc = "{0:.5f}".format(a0_twk)
        elif self.symmetry == 'nosymmetry':  # P, d-sp input
            crystal_system = '7 '
            str_uc = "{0:.5f}".format(a0_twk)
        elif self.symmetry == 'hexagonal' or self.symmetry == 'trigonal':
            crystal_system = '2 '
            str_uc = "{0:.5f} {1:.5f}".format(a0_twk, c0_twk)
        elif self.symmetry == 'tetragonal':  # tetragonal
            crystal_system = '3 '
            str_uc = "{0:.5f} {1:.5f}".format(a0_twk, c0_twk)
        elif self.symmetry == 'orthorhombic':  # orthorhombic
            crystal_system = '4 '
            str_uc = "{0:.5f} {1:.5f} {2:.5f}".format(a0_twk,
                                                      b0_twk, c0_twk)
        elif self.symmetry == 'monoclinic':  # monoclinic
            crystal_system = '5 '
            str_uc = "{0:.5f} {1:.5f} {2:.5f} {3:.5f}".format(
                a0_twk, b0_twk, c0_twk, self.beta0)
        elif self.symmetry == 'triclinic':  # triclinic
            crystal_system = '6 '
            str_uc = "{0:.5f} {1:.5f} {2:.5f} {3:.5f} {4:.5f} \
                {5:.5f}".format(
                a0_twk, b0_twk, c0_twk,
                self.alpha0, self.beta0, self.gamma0)

        f.write(crystal_system + str_el + " \n")
        f.write(str_uc + " \n")
        f.write("{:.4e} \n".format(self.thermal_expansion))
        f.write("d-spacing    I/I0     h   k   l \n")

        self.cal_dsp(0., 300., use_table_for_0GPa=False)
        for line in self.DiffLines:
            f.write("{0:.6f} {1:.2f} {2:.1f} {3:.1f} {4:.1f} \n".format(
                line.dsp0, line.intensity, line.h, line.k, line.l))
        f.close()


def get_cell_prm_twk(symmetry, v_twk, a0, b0, c0, alpha0, beta0, gamma0,
                     twk_b_a, twk_c_a):
    b_a_twk = b0 / a0 * twk_b_a
    c_a_twk = c0 / a0 * twk_c_a
    if symmetry == 'cubic':
        a_twk = (v_twk)**(1. / 3.)
        b_twk = a_twk
        c_twk = a_twk
    elif (symmetry == 'hexagonal') or (symmetry == 'trigonal'):
        a_twk = (2. * v_twk / (np.sqrt(3.) * c_a_twk))**(1. / 3.)
        b_twk = a_twk
        c_twk = a_twk * c_a_twk
    elif symmetry == 'tetragonal':
        a_twk = (v_twk / (c_a_twk))**(1. / 3.)
        b_twk = a_twk
        c_twk = c_a_twk * a_twk
    elif symmetry == 'orthorhombic':
        a_twk = (v_twk / (b_a_twk * c_a_twk))**(1. / 3.)
        c_twk = c_a_twk * a_twk
        b_twk = b_a_twk * a_twk
    elif symmetry == 'monoclinic':
        a_twk = (v_twk / (b_a_twk * c_a_twk *
                          np.sin(np.radians(beta0))))**(1. / 3.)
        c_twk = c_a_twk * a_twk
        b_twk = b_a_twk * a_twk
    elif symmetry == 'triclinic':
        a_term = np.sqrt(1. - (np.cos(np.radians(alpha0)))**2. -
                         (np.cos(np.radians(beta0)))**2. -
                         (np.cos(np.radians(gamma0)))**2. +
                         2. * np.cos(np.radians(alpha0)) *
                         np.cos(np.radians(beta0)) *
                         np.cos(np.radians(gamma0)))
        a_twk = (v_twk / (b_a_twk * c_a_twk * a_term))**(1. / 3.)
        c_twk = c_a_twk * a_twk
        b_twk = b_a_twk * a_twk
    else:
        #print('no symmetry is given')
        a_twk = a0
        b_twk = b0
        c_twk = c0

    return a_twk, b_twk, c_twk
