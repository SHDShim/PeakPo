from ds_cake import DiffImg
# do not change the module structure for ds_jcpds and ds_powdiff for
# retro compatibility
from ds_jcpds import JCPDSplt, Session, UnitCell, convert_tth
from ds_powdiff import PatternPeakPo, get_DataSection
from utils import samefilename, make_filename


class PeakPoModel(object):
    def __init__(self):
        self.base_ptn = None
        self.waterfall_ptn = []
        self.jcpds_lst = []
        self.ucfit_lst = []
        self.diff_img = None
        self.poni = None

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
        self.base_ptn = new_base_ptn

    def get_base_ptn(self):
        return self.base_ptn
