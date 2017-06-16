PeakPo
======

A python application for X-ray diffraction analysis for samples at high
pressure and high temperature.


Install this application
------------------------

1. Download zipped file from the github site
(https://github.com/SHDShim/peakpo-v7).

2. Under the ``~/python`` folder, unzip with the original folder structure
unchanged. For window users, ``c:\Users\YourUserName\python\peakpo-v7``.
Of course, you may locate peakpo somewhere else.  For simplicity, in this
instruction we assume that peakpo is installed in ``~/python/peakpo-v7``.

3. Rename the folder to ``peakpo-v7``.  Under the ``peakpo-v7`` folder, you
should be able to see a few folders and one of them is ``peakpo``.



Install required packages
-------------------------

I provide a conda environment file: ``py35pkpo.yml``.  This can be found
in the ``~/python/peakpo-v7`` folder.

1. Open a terminal, and in the ``peakpo-v7`` folder, create an environment by
running::

$ conda env create -f py35pkpo.yml


For window users, try ``py35pkpo-win.yml`` in the folder instead.

2. If you do not see any error messages, you are done and go to the
**Run peakpo** section below.

However, if the method above does not work, particularly for Windows,
you need to manually install necessary python modules.

1. Create a conda environment for peakpo::

    $ conda create --name py35pkpo python=3.5


2. Switch to the environment.  For windows::

    $ activate py35pkpo


For Linux and Mac::

    $ source activate py35pkpo


3. Install the anaconda meta-package.  This includes ``matplotlib`` > 2.0,
and ``pyqt5``::

    $ conda install anaconda


4. Install ``pytheos``::

    $ conda install -c shdshim pytheos


5. Install ```pymatgen``::

    $ conda install -c matsci pymatgen


6. Install ``pyfai``::

    $ conda install -c cprescher pyfai


7. Install ``qdarkstyle``::

    $ pip install qdarkstyle


8. Install some packages from ``conda-forge``, such as ``periodictable``,
``uncertainties``, and ``lmfit``.  For example::

  $ conda install -c conda-forge lmfit


Run peakpo
----------

1. Activate ``py35pkpo``::

    $ source activate py35pkpo


or in windows::

  $ activate py35pkpo


2. In the terminal app, navigate to the folder where you unzip the package.
In the example here, go into the ``peakpo-v7/peakpo`` folder and run::

  $ python -m peakpo


In a very rare case, you might have to do ``sudo``::

  $ sudo python -m peakpo


Run this application in different ways (for Mac users)
------------------------------------------------------

1. Complete the installation instruction above.

2. Find ``peakpo.command`` file in the ``peakpo-v7`` folder, and copy and paste
the file in your applications folder.

3. Double click the file and you will see ``peakpo`` running.

3a. If step 3 does not work, it is likely because you do not have permission
to execute the ``peakpo.command`` file.  Open a terminal and go to
``applications`` folder and run the command below::

  $ chmod +ux peakpo.command


Now try step 3 again.  It should work.

3b. The ``peakpo.command`` file assumes you have peakpo in
``~/python/peakpo-v7/peakpo``.  If not, you should either locate peakpo in the
same path or you should modify the second line of the script.


Theme
-----

Version 7 adapted a dark theme from::

  https://github.com/ColinDuquesnoy/QDarkStyleSheet


Unresolved issue
----------------

Even if I install ``pyopencl``, ``pyfai`` still complains that it cannot be
found.


Future
------

- More information needs to be added when this project is finally published.
