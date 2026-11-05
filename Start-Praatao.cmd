@echo off
rem ---------------------------------------------------------------------
rem  Praatao - start Praat and the coach with one double-click.
rem
rem  This file does NOT open a console window: it starts the packaged
rem  executable when it exists, and otherwise the program through
rem  pythonw.exe (also without a window).  The coach writes what it is
rem  doing into %LOCALAPPDATA%\praatao\coach.log.
rem
rem  Extra arguments are passed on to run.py, e.g.
rem      Start-Praatao.cmd --no-llm
rem      Start-Praatao.cmd --lang en
rem
rem  Developers who want to see the output should run
rem      python run.py
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

rem --- the packaged build wins ---------------------------------------------
if exist "%~dp0dist\Praatao\Praatao.exe" (
    start "" "%~dp0dist\Praatao\Praatao.exe" %*
    exit /b 0
)

rem --- otherwise the program itself, without a console window --------------
set "PYW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=pythonw"
if not defined PYW for /f "delims=" %%i in ('where python 2^>nul') do if not defined PYW set "PYW=python"
if not defined PYW (
    echo.
    echo   [Praatao] Python was not found on PATH.
    echo   Install Python 3.12 or newer, then run this file again.
    echo.
    pause
    exit /b 1
)

start "" %PYW% "%~dp0run.py" %*
exit /b 0
