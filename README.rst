PeakPo
======

A `Python` application for X-ray diffraction analysis for samples at high
pressure and high temperature.

Install this application
------------------------

You may download zipped file and unzip with folder structure maintained.
First make a folder to save `peakpo`, for example, peakpo-v7.  Then save
the zip file under the folder and unzip it.  You may see a few folders and
one of them is `peakpo`.


Install required packages
-------------------------

I provide a conda environment in a file: `py35pkpo.yml`.

Under the `PeakPo-v7` folder, run the following command to create an
environment works for peakpo from::

  $ conda env create -f py35pkpo.yml

This should install all the necessary packages if the process ends without
an error.

However, if the method above does not work, particuarly for windows,
you need to create an envinronment first::

  $ conda create --name py35pkpo python=3.5

Then switch to that environment.  For windows::

  $ activate py35pkpo

For Linux and Mac::

  $ source activate py35pkpo

Install the following packages: `matplotlib > 2.0`, `pyqt5`, `pytheos`,
`pymatgen`, `periodictable`, `uncertainties`, `pyfai`,  and `lmfit`.

First, for basic science packages::

  $ conda install anaconda

For pytheos::

  $ conda install -c shdshim pytheos

For pymatgen::

  $ conda install -c matsci pymatgen

Others are available from `conda-forge`.


Run this application
--------------------

Activate `py35pkpo`::

  $ source activate py35pkpo

or in windows::

  $ activate py35pkpo

Go to the folder where you unzip the package.  In the terminal app, you
navigate to the folder where you unzip the package.  Go into the `peakpo`
folder and run the following::

  $ python -m peakpo

In a very rare case, you might have to do `sudo`::

  $ sudo python -m peakpo


Run this application (for Mac users)
------------------------------------

1. Install anaconda and make an environment following the instruction in the
`Install required packages` section above.

2. Copy and paste `peakpo.command` file in your applications folder.

3. Double click the file and you will see `peakpo` opening.

3a. If step 3 does not work, it is likely because you do not have permission
to execute the `.command` file.  Open a terminal and go to applications folder
and run the command below::

  $ chmod +ux peakpo.command

Now try step 3 again.  It should work.

3b. The `peakpo.command` file assumes you have `peakpo` in
`~/python/peakpo-v7/peakpo`.  If not, you should either locate peakpo in the
same path or you should modify the second line of the script.


Theme
-----

Version 7 adapted a dark theme from::

  https://github.com/ColinDuquesnoy/QDarkStyleSheet


Unresolved issue
----------------

- Even if I install `pyopencl`, `pyfai` still complains that it cannot be found.

Future
------

More information needs to be added when this project is finally published.
