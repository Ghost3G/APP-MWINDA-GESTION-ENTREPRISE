@echo off
set "PYTHON_EXE=C:\Program Files\PostgreSQL\18\pgAdmin 4\python\python.exe"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%PYTHON_EXE%" (
    echo Python introuvable: %PYTHON_EXE%
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0manage_local.py" %*
