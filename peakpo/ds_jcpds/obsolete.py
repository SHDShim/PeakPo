import numpy as np
import ds_eos
import ds_xrd
import os
#import numpy.ma as ma


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
        self.v = ds_xrd.cal_UnitCellVolume(self.symmetry, self.a, self.b, self.c,
                                           self.alpha, self.beta, self.gamma)
        for dl in self.DiffLines:
            dsp = ds_xrd.cal_dspacing(self.symmetry, dl.h, dl.k, dl.l,
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

        inp = open(file, 'r').readlines()
#        my_list = [] # get all the text first and throw into my_list

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
            self.symmetry = 'manual'
        # 1 cubic, 2 hexagonal, 3 tetragonal, 4 orthorhombic
        # 5 monoclinic, 6 triclinic, 7 manual P, d-sp input

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
            DiffLine = DiffractionLine()
            DiffLine.dsp0 = float(item[0])
            DiffLine.intensity = float(item[1])
            DiffLine.h = float(item[2])
            DiffLine.k = float(item[3])
            DiffLine.l = float(item[4])
            self.DiffLines.append(DiffLine)

        self._cal_v0()
        self.a = self.a0
        self.b = self.b0
        self.c = self.c0
        self.alpha = self.alpha0
        self.beta = self.beta0
        self.gamma = self.gamma0
        self.v = self.v0

    def _cal_v0(self):
        """
        Computes the unit cell volume of the material at zero pressure and
        temperature from the unit cell parameters.
        """
        self.v0 = ds_xrd.cal_UnitCellVolume(self.symmetry,
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
            if self.symmetry == 'manual':
                self.v = self.v0
            else:
                self.v = ds_eos.cal_v_bm3(pressure_st,
                                          [self.v0, self.k0, self.k0p])

    def cal_dsp(self, pressure=0., temperature=300., b_a=None, c_a=None):
        """
        b_a and c_a are newly included for adjusting axial ratios.
        For cubic structure, these two inputs are ignored.
        For tetragonal and hexagonal, only c_a will be used.
        """
        self._cal_v(pressure, temperature)
        if b_a == None:
            b_a = self.b0 / self.a0
        if c_a == None:
            c_a = self.c0 / self.a0

        # angles are always set to original values, so no need to reset
        # self.alpha = self.alpha0 ; self.beta = self.beta0 ; self.gamma = self.gamma0

        if ((pressure == 0.0) or (self.symmetry == 'manual')):  # p = 0 GPa, resetting to uc0 is necessary
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
                dsp = ds_xrd.cal_dspacing(self.symmetry, dl.h, dl.k, dl.l,
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
        elif self.symmetry == 'hexagonal':
            # self.a = (2. * self.v / (np.sqrt(3.)*self.c0/self.a0) )**(1./3.)
            self.a = (2. * self.v / (np.sqrt(3.) * c_a))**(1. / 3.)
            self.b = self.a
            self.c = self.a * c_a
        elif self.symmetry == 'tetragonal':
             #self.a = (self.v/(self.c0/self.a0))**(1./3.) ; self.b = self.a
            self.a = (self.v / (c_a))**(1. / 3.)
            self.b = self.a
            self.c = c_a * self.a
        elif self.symmetry == 'orthorhombic':
            #self.a = (self.v/(self.b0/self.a0*self.c0/self.a0))**(1./3.)
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
            a_term = np.sqrt(1. - (np.cos(np.radians(self.alpha0)))**2.
                             - (np.cos(np.radians(self.beta0)))**2.
                             - (np.cos(np.radians(self.gamma0)))**2.
                             + 2. * np.cos(np.radians(self.alpha0))
                             * np.cos(np.radians(self.beta0))
                             * np.cos(np.radians(self.gamma0)))
            #self.a = (self.v/(self.b0/self.a0*self.c0/self.a0*a_term))**(1./3.)
            self.a = (self.v / (b_a * c_a * a_term))**(1. / 3.)
            self.c = c_a * self.a
            self.b = b_a * self.a
        else:
            print('no symmetry is given')

#    return {'ver': ver, 'header': header, 'crystal_system': crystal_system, \
#            'K0': K0, 'K0p': K0p, 'u_param': np.asarray([a,b,c,alpha,beta,gamma]), \
#            'alpha': thermal_expansion, 'peaks': np.asarray([dsp, intensity, h, k, l]).T, \
#            'b_a': b_a, 'c_a': c_a}


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
        self.bg_params = [10, 10, 50]
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

    def cal_dsp(self, pressure, temperature, b_a=None, c_a=None):
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
        super(JCPDSplt, self).cal_dsp(pressure, temperature, self.b_a, self.c_a)

    def get_dsp(self):
        dsp = []
        for dl in self.DiffLines:
            d = float(dl.dsp)
            dsp.append(d)
        return dsp

    def make_TextOutput(self, pressure, temperature):
        textout = self.file + '\n'
        textout += self.name + '\n'
        textout += 'Version: ' + str(self.version) + '\n'
        textout += self.comments + '\n'
        textout += self.symmetry + '\n'
        textout += '******************\n'
        textout += 'Values in original JCPDS file\n'
        textout += 'K0 = ' + str(self.k0_org) + ' GPa, K0p = ' + \
            str(self.k0p_org) + '\n'
        textout += 'Thermal expansion = ' + str(self.thermal_expansion_org) + '\n'
        textout += 'a0 = ' + str(self.a0) + \
            ' A, b0 = ' + str(self.b0) + ' A, c0 = ' + str(self.c0) + ' A\n'
        textout += 'alpha0 = ' + str(self.alpha0) + \
            ', beta0 = ' + str(self.beta0) + ', gamma0 = ' + \
            str(self.gamma0) + '\n'
        textout += 'V0 = {0: 12.5f} A^3\n'.format(self.v0_org)
        textout += '******************\n'
        textout += 'Values after tweak (tweak is only reflected in the d-spacing, not unit cell parameters)\n'
        textout += 'K0 = ' + str(self.k0) + ' GPa, K0p = ' + \
            str(self.k0p) + '\n'
        textout += 'Thermal expansion = ' + str(self.thermal_expansion) + '\n'
        textout += 'V0 = {0: 12.5f} A^3\n'.format(self.v0)

        textout += 'a = {0: 10.5f} A, b = {1: 10.5f} A, c = {2: 10.5f} A\n'.format(
            float(self.a), float(self.b), float(self.c))
        textout += 'alpha = ' + str(self.alpha) + \
            ', beta = ' + str(self.beta) + ', gamma = ' + \
            str(self.gamma) + '\n'
        textout += 'V = {0: 12.5f} A^3\n\n'.format(float(self.v))
        textout += 'Below are the peaks at {0: 6.1f} GPa, {1: 5.0f} K\n'.format(
            pressure, temperature)
        textout += 'd-spacing (A), intensity (%), h, k, l\n'
        for dl in self.DiffLines:
            textout += "{0: 10.5f}, {1: 10.1f}, {2: 5.0f}, {3: 5.0f}, {4: 5.0f}\n".format(
                float(dl.dsp), dl.intensity, dl.h, dl.k, dl.l)
        return textout
