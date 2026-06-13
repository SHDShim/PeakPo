@echo off
setlocal EnableExtensions
rem PeakPo launcher for Windows
rem Works with pip installs and Conda installs without editing.

call :run_peakpo
if %errorlevel%==0 goto :done

call :init_conda
if not %errorlevel%==0 goto :failed

if not "%PEAKPO_CONDA_ENV%"=="" (
    call conda activate "%PEAKPO_CONDA_ENV%"
    if not %errorlevel%==0 goto :failed
)

call :run_peakpo
if %errorlevel%==0 goto :done
goto :failed

:run_peakpo
where peakpo >nul 2>&1
if %errorlevel%==0 (
    peakpo
    exit /b %errorlevel%
)
where python >nul 2>&1
if %errorlevel%==0 (
    python -m peakpo
    exit /b %errorlevel%
)
where py >nul 2>&1
if %errorlevel%==0 (
    py -m peakpo
    exit /b %errorlevel%
)
exit /b 127

:init_conda
where conda >nul 2>&1
if %errorlevel%==0 exit /b 0

if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" (
    call "%USERPROFILE%\miniconda3\condabin\conda.bat" activate base >nul 2>&1
    where conda >nul 2>&1
    if %errorlevel%==0 exit /b 0
)
if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" (
    call "%USERPROFILE%\anaconda3\condabin\conda.bat" activate base >nul 2>&1
    where conda >nul 2>&1
    if %errorlevel%==0 exit /b 0
)
if exist "C:\ProgramData\Miniconda3\condabin\conda.bat" (
    call "C:\ProgramData\Miniconda3\condabin\conda.bat" activate base >nul 2>&1
    where conda >nul 2>&1
    if %errorlevel%==0 exit /b 0
)
if exist "C:\ProgramData\Anaconda3\condabin\conda.bat" (
    call "C:\ProgramData\Anaconda3\condabin\conda.bat" activate base >nul 2>&1
    where conda >nul 2>&1
    if %errorlevel%==0 exit /b 0
)
exit /b 127

:failed
echo PeakPo launch failed.
echo Tried: peakpo, python -m peakpo, and conda fallback.
echo If needed, set PEAKPO_CONDA_ENV to your environment name.
pause
exit /b 1

:done
exit /b 0
