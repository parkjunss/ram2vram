@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
python "%ROOT%\scripts\python\desktop\launch.py"
exit /b %errorlevel%
