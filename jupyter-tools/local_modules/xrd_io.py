import numpy as np

def write_chi(filen, x, y, preheader = None):
    """
    write a chi file
    
    :filen = string, filename and path
    :x = two theta array
    :y = intensity array
    :preheader = header.  Each component of a list represents a line of header.  
                 Only first three will be used
    """
    if preheader is None:
        preheader = "\n\n\n" 
    header = str(x.__len__())
    np.savetxt(filen, np.asarray([x,y]).T, \
               fmt='%1.7e', header = header, comments = preheader)    
    
def read_chi(fname):
    """
    read a chi file and return two arrays: twotheta and intensity
    
    :fname = string, filename and path
    """
    data = np.loadtxt(fname, skiprows = 4)
    twotheta, intensity = data.T
    return twotheta, intensity