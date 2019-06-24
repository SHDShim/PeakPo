"""
PeakPo version

Todo:
    Add option to use diffraction file for background subtraction
    Better system should be implemented, such as pbr.
"""
__version__ = "7.7.23"
"""
7.7.23: UI change for the JCPDS setup. Fix bug for the max twotheta for cake. 
7.7.22: Bug fix for gsas style jpds bar plot.  Provide [environment].yml
    for MacOS, Windows, and Ubuntu.  Add cbf support for cake.
7.7.21: Update with large size window at start.  Provide [environment].yml
7.7.20: Update ds_jcpds for new pymatgen update.
7.7.20a: Matplotlib 2.2 compatible.  But incompatible with Matplotlib 2.1
    For matplotlib 2.1 you may delete the existing mplwidget.py file and rename
    the mplwidget-matplotlib_2_1.py to mplwidget.py
    This version needs to beta test.
7.7.19: Add warning message for bad jcpds files and ignore them.
	Add "save twk jcpds" function.
	Improve output information, adding tweak v0, unit cell parameter information.
	Add checkbox to control the behavior of 1 bar calculation.
	Change default behavior for 1 bar to calculation rather than table viewing.
	This version is still limited to matplotlib 2.1.
7.7.18: Bug fix for empty last line jcpds problem.
7.7.17: Add options to save cake formats into .cakeformat file.
7.7.16: Add shortcut icons for frequently used functions.
        Improve icons using Unicode.
        Add bookmarking function for diffraction files.
        Add more tabs to distribute functions better.
        Change the step size mechanism for pressure and temperature.
        Change Waterfall label style changes and match with table.
        Restore large pressure-temperature values at the top left corner.
        Option to add hkl indices to the cake view.
        Option to add/remove waterfall file name labels.
        Add option to add azimuthal integration directly to waterfall.
        Add step size control for the JCPDS tweaks and UCFit.
        Remove separate tab for information and help.  They are now popups.
7.7.15: Change inner working of Cake JCPDS.
        I changed from for loop to array operation for fast plot.
7.7.14: change cake scale adjustment option.
        I have some weird unsaved message to peakfitcontroller.
        In case we found bug, go back to peakfitcontroller for 7.7.12
7.7.12: change PONI input method
7.7.11: fix bug with cake azimuthal integration
7.7.10: add cake azimuthal angle shift
7.7.9: fix issues in peakfit.  add GSAS style view.
7.7.8: fix issues with bgsub behavior.  now PeakPo will not overwrite previous
       bgsub results in dpp.  add cake marker functions to save.
7.7.7: add Miller indices option
7.7.6: add output textbox for ucfit
7.7.5: switch positions for better tweak in JCPDS.  I grouped V0, b_a and c_a.
7.7.4: add GSAS style bar plot option.  Now the jcpds in vertical bar option
       is gone.
"""
