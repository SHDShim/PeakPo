rem Step 1: Activate Miniconda or anaconda, use the actual path where your Miniconda/Ananconda is installed.
call "C:\Users\yourname\miniconda3\Scripts\activate.bat" "C:\Users\yourname\miniconda3"

rem Step 2: Activate Conda environment. 
call conda activate pkpo2022fbs

rem Step 3: Change directory to the desired folder.
cd /d "C:\Users\Shim\peakpo7.8.0\peakpo"

rem Step 4: Run the Python script.
python -m peakpo
