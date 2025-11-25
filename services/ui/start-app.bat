@echo off

REM Change to the directory where the script is located
cd /d %~dp0

REM Creation, installation & activation of local venv
IF NOT EXIST .venv (
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) ELSE (
    call .venv\Scripts\activate.bat
)

start cmd /k npm run dev
