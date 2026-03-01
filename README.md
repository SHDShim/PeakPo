# PeakPo

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.810401.svg)](https://doi.org/10.5281/zenodo.810401)

PeakPo is a Python application for X-ray diffraction analysis of samples at high pressure and high temperature.

Major features include:

- Pressure and temperature estimation
- Phase identification
- Two-dimensional data analysis
- Visual equation-of-state fitting
- Peak fitting
- Visual unit-cell fitting
- Generation of Excel files containing all calculation results

## How to install

For `PeakPo 7.10.x`, use a separate environment from `PeakPo 7.9.x`.

If you already installed `PeakPo 7.9.x` with pip in an environment named `peakpo`, rename that environment to `pkpo709` first:

```
conda create -n pkpo709 --clone peakpo -y
conda remove -n peakpo --all -y
```

Then create a new environment for `PeakPo 7.10.x`:

```
conda create -n pkpo710 python=3.11 -y
```

Activate `pkpo710`:

```
conda activate pkpo710
```

Install `PeakPo 7.10.x`:

```
python -m pip install --upgrade pip
python -m pip install peakpo
```

## Upgrading from 7.9.x to 7.10.x

`PeakPo 7.9.x` is based on `PyQt5`, while `PeakPo 7.10.x` is based on `PyQt6`.

Because of this Qt transition, do not upgrade in-place in your old `7.9.x` environment.
Keep `7.9.x` in `pkpo709`, and install `7.10.x` in `pkpo710`.

Recommended setup:

```
conda create -n pkpo709 --clone peakpo -y
conda remove -n peakpo --all -y
conda create -n pkpo710 python=3.11 -y
conda activate pkpo710
python -m pip install --upgrade pip
python -m pip install peakpo
```

Use environments like this:

```
conda activate pkpo709   # old 7.9.x
conda activate pkpo710   # new 7.10.x
```

## How to upgrade

Upgrade inside the target environment:

```
conda activate pkpo710
```

```
python -m pip install --upgrade --upgrade-strategy eager peakpo
```

## How to reinstall

Reinstall inside the target environment:

```
conda activate pkpo710
```


```
python -m pip install --force-reinstall peakpo
```

## How to install before 7.9.x

[Installation wiki page](https://github.com/SHDShim/PeakPo/wiki/Installation-and-Update) 

[Installation Google Slides](https://docs.google.com/presentation/d/11nTraMvenpO7E3Cg7NAH2Qa4UpTwjJVcexdU-CPNE9Q/edit?usp=sharing) 


## Where to download executables

I no longer provide executable files. You can still download previous versions from [this Google Drive folder](https://drive.google.com/drive/folders/0B0kkQLbYpQDYfjBGT21uMkx5cU1JMHJIUUhGR1FkdDVUdzFYVUdKR0Zya2NRcFYtUmRVUGM?resourcekey=0-FT-Lc6ZeuUBMaqHzzjZSbg&usp=sharing).

## Where to get help

See [the PeakPo wiki](https://github.com/SHDShim/peakpo/wiki) for detailed instructions on installation, setup, operation, and updates.

## How to cite

S.-H. Shim (2017). PeakPo: A Python software package for X-ray diffraction analysis at high pressure and high temperature. Zenodo. https://doi.org/10.5281/zenodo.810199
