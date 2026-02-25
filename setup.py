from pathlib import Path

from setuptools import find_packages, setup


about = {}
exec(Path("peakpo/version.py").read_text(encoding="utf-8"), about)

readme = Path("README.md").read_text(encoding="utf-8")


setup(
    name="PeakPo",
    version=about["__version__"],
    description="X-ray diffraction analysis for high pressure science",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/SHDShim/PeakPo",
    author="S.-H. Dan Shim",
    author_email="shdshim@gmail.com",
    license="Apache-2.0",
    packages=find_packages(exclude=("deletables", "setup_bin")),
    include_package_data=False,
    package_data={"peakpo": ["mplstyle/*.mplstyle"]},
    exclude_package_data={"": ["__pycache__/*", "*.py[cod]"], "peakpo": ["error.log"]},
    python_requires=">=3.11",
    install_requires=[
        "matplotlib==3.7.5",
        "pymatgen==2023.12.18",
        "numpy==1.26.4",
        "scipy==1.16.3",
        "pandas==2.3.3",
        "pyqt5==5.15.10",
        "pyqt5-qt5==5.15.18",
        "pyqt5-sip==12.17.2",
        "pyfai==2025.12.1",
        "pytheos==0.0.2",
        "lmfit==1.3.4",
        "periodictable==2.0.2",
        "silx==2.2.2",
        "h5py==3.15.1",
        "hdf5plugin==6.0.0",
        "spglib==2.6.0",
        "statsmodels==0.14.6",
        "uncertainties==3.2.3",
        "xlwt==1.3.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="xrd analysis pressure",
    entry_points={
        "console_scripts": [
            "peakpo=peakpo.__main__:main",
        ],
    },
)
