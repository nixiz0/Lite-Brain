@echo off

REM ============================
REM CPU/GPU script
REM ============================

REM Navigate to the script folder
cd /d %~dp0

REM Unique Venv Name
set "VENV_DIR=.venv"

REM If the environment doesn't exist, we request the CPU/GPU and build the environment.
IF NOT EXIST "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo ============================
    echo Launch the API (CPU / GPU)
    echo ============================
    echo [1] CPU
    echo [2] GPU
    echo.

    choice /c 12 /m "Choose the mode (1=CPU, 2=GPU)"

    IF "%ERRORLEVEL%"=="1" SET "MODE=CPU"
    IF "%ERRORLEVEL%"=="2" SET "MODE=GPU"

    echo.
    echo Selected mode : %MODE%
    echo.

    IF /I "%MODE%"=="CPU" (
        set "TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu"
    ) ELSE (
        set "TORCH_INDEX_URL=https://download.pytorch.org/whl/cu118"
    )

    echo Creation of the venv %VENV_DIR% ...
    python -m venv "%VENV_DIR%"
    call "%VENV_DIR%\Scripts\activate.bat"

    echo Pip update...
    python -m pip install --upgrade pip

    echo Installation of torch / torchvision...
    python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url %TORCH_INDEX_URL%

    echo Installation of outbuildings...
    python -m pip install -r requirements.txt
) ELSE (
    echo Activation of the existing venv %VENV_DIR% ...
    call "%VENV_DIR%\Scripts\activate.bat"
)

REM API Launch
start cmd /k uvicorn app.main:app --host 127.0.0.1 --port 9005 --reload
