@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
python "%ROOT%\scripts\python\strata\launch.py"
exit /b %errorlevel%
