@echo off
setlocal EnableDelayedExpansion

:: 1. Find Python 3.11
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
    set PYTHON_CMD=py -3.11
) else (
    python3.11 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python3.11"
)

if not defined PYTHON_CMD (
    echo.
    echo [ERROR] Python 3.11 not found.
    echo Please install Python 3.11.x from https://www.python.org/downloads/
    echo and make sure to check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

:: 2. Create virtual environment if it doesn't exist
if exist ".venv\Scripts\python.exe" (
    echo Virtual environment already exists, skipping creation.
) else (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create virtual environment.
        echo.
        pause
        exit /b 1
    )
)

:: 3: Activate virtual environment
call .venv\Scripts\activate.bat

:: 4: Install requirements if venv was just created
if not exist .venv\Scripts\pip.exe (
    echo Could not find pip in the virtual environment. Something went wrong.
    pause
    exit /b 1
)

if exist requirements.txt (
    echo Installing requirements...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    echo [WARNING] requirements.txt not found. Skipping dependency installation.
)

echo.
echo All done.
echo.
call cmd
