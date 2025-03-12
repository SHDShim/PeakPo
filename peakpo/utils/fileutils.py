import os.path
import glob
import numpy as np
import re
import os
import shutil
import collections

def get_unique_filename(filename):
    """Generate a unique filename by appending a number 
    if the file already exists."""
    base, ext = os.path.splitext(filename)
    counter = 1

    while os.path.exists(filename):
        filename = f"{base}_{counter}{ext}"
        counter += 1
        if counter > 100:
            return None
    new_filename = filename

    return new_filename

def backup_copy(filename):
    """Write content to a file, making a copy if the file already exists."""
    unique_filename = get_unique_filename(filename)
    if unique_filename != None:
        shutil.copy(filename, unique_filename)
    return unique_filename


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

#########################################
def read_any_poni_file(filename):
    """
    Read any version of poni file to check the version
    """
    data = collections.OrderedDict()

    with open(filename) as opened_file:
        for line in opened_file:
            if line.startswith("#") or (":" not in line):
                continue
            words = line.split(":", 1)

            key = words[0].strip().lower()
            value = words[1].strip()
            data[key] = value
    return data
    #read_from_dict(data)


def modify_poni_file(input_file_path, output_file_path):
    """
    convert poni 2.1 to poni 2 by simply removing orientation
    field in detector_config
    """
    # Read the input file as text
    with open(input_file_path, 'r') as infile:
        lines = infile.readlines()
    
    new_lines = ['# Converted from version higher than 2.\n']
    detector_config_started = False
    detector_config_lines = []
    
    # Process each line
    for line in lines:
        # If we encounter the Detector_config section, we will capture it
        if "Detector_config" in line:
                detector_config_str = ''.join(line)
                # Remove the "orientation" field using regex
                detector_config_str = re.sub(r',\s*"orientation"\s*:\s*[^,}]*', '', detector_config_str)
                
                # Reformat the Detector_config section into a valid dictionary format (JSON style)
                new_detector_config = detector_config_str.strip() + "\n"
                new_lines.append(new_detector_config)
                detector_config_lines = []  # Reset the lines for the next section
        else:
            # Modify the version number line to 'poni_version: 2'
            if "poni_version" in line:
                new_lines.append("poni_version: 2\n")
            else:
                # Otherwise, just keep the line as is
                new_lines.append(line)
    
    # Write the modified content back to the output file
    with open(output_file_path, 'w') as outfile:
        outfile.writelines(new_lines)
    
    print(f"File modified and saved as {output_file_path}")

def modify_file_name(file_path):
    """
    modify poni file name to note the backward conversion
    """
    # Extract the directory path, file name, and extension
    directory, file_name = os.path.split(file_path)
    name, extension = os.path.splitext(file_name)
    
    # Modify the name by adding '-no-orientation' before the extension
    new_name = name + '-no-orientation' + extension
    
    # Combine the directory path with the new name
    new_file_path = os.path.join(directory, new_name)
    
    return new_file_path