import os.path
import glob
import numpy as np


def writechi(filen, x, y, preheader=None):
    """
    header should be string list.  Only first three will be used
    """
    if preheader is None:
        preheader = "\n\n\n"
    header = str(x.__len__())
    np.savetxt(filen, np.asarray([x, y]).T,
               fmt='%1.7e', header=header, comments=preheader)


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


def extract_extension(filen):
    """
    extract extension without dot

    :param filen: filename
    :return: extension without a dot
    """
    path, filen, ext = breakdown_filename(filen)
    return ext[1:]


def make_filename(filename, ext):
    """
    make a new filename with different extension in the same folder

    :param filen: filename with path
    :param ext: new extension without dot
    :return: new filename
    """
    path, filen = os.path.split(filename)
    new_filen = os.path.splitext(filen)[0] + '.' + ext
    new_filename = os.path.join(path, new_filen)
    return new_filename
