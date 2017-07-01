import pickle
import os
from ds_cake import DiffImg
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ds_jcpds import JCPDSplt, Session, UnitCell, convert_tth
from ds_powdiff import PatternPeakPo, get_DataSection
from utils import samefilename, make_filename


class PeakPoModel(object):
    """
    session is only for reading/writing/referencing.
    components of the models are not part of session.
    session is a reference object
    """

    def __init__(self):
        self.base_ptn = None
        self.waterfall_ptn = []
        self.jcpds_lst = []
        self.ucfit_lst = []
        self.diff_img = None
        self.poni = None
        self.session = None
        self.jcpds_path = ''
        self.chi_path = ''

    def reset_base_ptn(self):
        self.base_ptn = PatternPeakPo()

    def reset_waterfall_ptn(self):
        self.waterfall_patterns = []

    def reset_jcpds_lst(self):
        self.jcpds_lst = []

    def reset_ucfit_lst(self):
        self.ucfit_lst = []

    def reset_diff_img(self):
        self.diff_img = DiffImg()

    def reset_poni(self):
        self.poni = None

    def base_ptn_exist(self):
        if self.base_ptn is None:
            return False
        else:
            if self.base_ptn.fname is None:
                return False
            else:
                return True

    def waterfall_exist(self):
        if self.waterfall_ptn == []:
            return False
        else:
            return True

    def jcpds_exist(self):
        if self.jcpds_lst == []:
            return False
        else:
            return True

    def ucfit_exist(self):
        if self.ucfit_lst == []:
            return False
        else:
            return True

    def diff_img_exist(self):
        if self.diff_img is None:
            return False
        else:
            return True

    def poni_exist(self):
        if self.poni is None:
            return False
        else:
            return True

    def make_filename(self, extension):
        """
        :param extension: extension without a dot
        """
        return make_filename(self.base_ptn.fname, extension)

    def same_filename_as_base_ptn(self, filename):
        return samefilename(self.base_ptn.fname, filename)

    def set_base_ptn(self, new_base_ptn):
        """
        :param new_base_ptn: PatternPeakPo object
        """
        self.reset_base_ptn()
        self.base_ptn.read_file(new_base_ptn)
        self.set_chi_path(os.path.split(new_base_ptn)[0])

    def get_base_ptn(self):
        return self.base_ptn

    def append_a_waterfall_ptn(self, filename, wavelength, bg_roi, bg_params):
        pattern = PatternPeakPo()
        pattern.read_file(filename)
        pattern.wavelength = wavelength
        pattern.display = False
        pattern.get_chbg(bg_roi, bg_params, yshift=0)
        self.waterfall_ptn.append(pattern)

    def set_waterfall_ptn(
            self, filenames, wavelength, display, bg_roi, bg_params):
        new_waterfall_ptn = []
        for f, wl, dp in zip(filenames, wavelength, display):
            pattern = PatternPeakPo()
            pattern.read_file(f)
            pattern.wavelength = wl
            pattern.display = dp
            pattern.get_chbg(bg_roi, bg_params, yshift=0)
            new_waterfall_ptn.append(pattern)
        self.waterfall_ptn = new_waterfall_ptn

    def append_a_jcpds(self, filen, color):
        phase = JCPDSplt()
        phase.read_file(filen)  # phase.file = f
        phase.color = color
        self.jcpds_lst.append(phase)

    def write_as_session(self,
                         fname, pressure, temperature):
        session = Session()
        session.pattern = self.get_base_ptn()
        session.waterfallpatterns = self.waterfall_ptn
        session.wavelength = self.base_ptn.wavelength
        session.pressure = pressure
        session.temperature = temperature
        session.jlist = self.jcpds_lst
        session.bg_roi = self.base_ptn.roi
        session.bg_params = self.base_ptn.params_chbg
        session.jcpds_path = self.jcpds_path
        session.chi_path = self.chi_path
        f = open(fname, 'wb')
        pickle.dump(session, f)
        f.close()

    def read_session(self, fname):
        f = open(fname, 'rb')
        session = pickle.load(f, encoding='latin1')
        f.close()
        self.session = session

    def set_jcpds_from_session(self):
        if self.session is not None:
            self.jcpds_lst = self.session.jlist
            self.set_jcpds_path(self.session.jcpds_path)
        else:
            self.set_jcpds_path('')

    def set_chi_path(self, chi_path):
        self.chi_path = chi_path

    def set_jcpds_path(self, jcpds_path):
        self.jcpds_path = jcpds_path
