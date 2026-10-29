@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
if not exist "%ROOT%\desktop\dist\RAM2VRAM-Workspace.exe" (
  echo Workspace build is missing. See desktop\README.md.
  exit /b 1
)
start "" "%ROOT%\desktop\dist\RAM2VRAM-Workspace.exe"
