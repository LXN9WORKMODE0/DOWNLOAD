@echo off
setlocal
rem Same Python and data directory as run.ps1 with its default settings.
set "pilot_python=%~dp0.venv\Scripts\python.exe"
if not exist "%pilot_python%" set "pilot_python=python"
"%pilot_python%" "%~dp0download.py" benchmark --group hydrodynamics --year 2024
set "pilot_exit=%errorlevel%"
if "%pilot_exit%"=="0" echo Results: "%~dp0output\full_range\hydrodynamics\surface\tape_pilot_2024.json"
if not "%pilot_exit%"=="0" echo Benchmark stopped. See the message above.
pause
exit /b %pilot_exit%
