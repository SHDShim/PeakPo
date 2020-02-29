import os.path
import glob
import numpy as np
import re


def writechi(filen, x, y, preheader=None):
    """
    header should be string list.  Only first three will be used
    """
    if preheader is None:
        preheader = "\n 2-theta\n\n"
    header = str(x.__len__())
    np.savetxt(filen, np.asarray([x, y]).T,
               fmt='%1.7e', header=header, comments=preheader)


def readchi(filen):
    """
    read chi with BG ROI and BG PARAMS
    """
    with open(filen) as f:
        content = f.readlines()
    roi = re.findall(r"[-+]?\d*\.\d+|\d+", content[0])
    bg_params = re.findall(r"[-+]?\d*\.\d+|\d+", content[1])
    data = np.loadtxt(filen, skiprows=4)
    x, y = data.T
    return [float(r) for r in roi], [int(b) for b in bg_params], x, y


def find_from_filelist(flist, filen):
    i = 0
    for s in flist:
        if s.find(filen) != -1:
            return i
        i += 1
    return -1


def get_sorted_filelist(path, search_ext='*.chi', sorted_by_name=True):
    filelist = glob.glob(os.path.join(path, search_ext))
    if sorted_by_name:
        return sorted(filelist)
    else:  # sorted by time
        return sorted(filelist, key=os.path.getmtime)


def samefilename(filen1, filen2):
    """
    take out filenames and compare
    :param filen1: filename 1
    :param filen2: filename 2
    """
    f1 = extract_filename(filen1)
    f2 = extract_filename(filen2)
    return (f1 == f2)


def breakdown_filename(filen):
    """
    breakdown filename to path, name, extension

    :param filen: filename
    :return: path, filename without extension, extension
    """
    path, filen_ext = os.path.split(filen)
    filen, ext = os.path.splitext(filen_ext)

    return path, filen, ext


def extract_filename(filen):
    """
    extract filename without extension

    :param filen: filename
    :return: filename without extension
    """
    path, filen, ext = breakdown_filename(filen)
    return filen


def get_directory(filen_path, branch):
    path, filen, __ = breakdown_filename(filen_path)
    return os.path.join(path, filen+branch)


def extract_extension(filen):
    """
    extract extension without dot

    :param filen: filename
    :return: extension without a dot
    """
    path, filen, ext = breakdown_filename(filen)
    return ext[1:]


def make_filename(filename, ext, temp_dir=None, original=False):
    """
    make a new filename with different extension in the same folder

    :param filen: filename with path
    :param ext: new extension without dot
    :return: new filename
    """
    path, filen = os.path.split(filename)
    if original:
        new_filen = filen.split(os.extsep)[0] + '.' + ext
        # new_filen = (os.extsep).join(filen.split(os.extsep)[0:-1]) + '.' + ext
    else:
        new_filen = os.path.splitext(filen)[0] + '.' + ext
    if temp_dir is None:
        new_filename = os.path.join(path, new_filen)
    else:
        new_filename = os.path.join(path, temp_dir, new_filen)
    return new_filename


def change_file_path(filename, new_path):
    path, filen_ext1 = os.path.split(filename)
    # the if statement below is very rare case where path breakdown is incomplete
    # when moving files from windows to osx
    if filen_ext1.find("\\") != -1:
        filen_ext = filen_ext1.split("\\")[-1]
    else:
        filen_ext = filen_ext1
    new_filename = os.path.join(new_path, filen_ext)
    return new_filename

def get_temp_dir(base_ptn_filename, branch='-param'):
    temp_dir = get_directory(base_ptn_filename, branch)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    return temp_dir
