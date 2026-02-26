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
        "matplotlib",
        "pymatgen",
        "numpy",
        "scipy",
        "pandas",
        "qtpy",
        "pyqt6",
        "pyfai",
        "pytheos",
        "lmfit",
        "periodictable",
        "silx",
        "h5py",
        "hdf5plugin",
        "spglib",
        "statsmodels",
        "uncertainties",
        "xlwt",
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
