@echo off
setlocal
if "%~1"=="" (
  echo Usage: inspect_moe_path.bat C:\path\to\llama.cpp
  exit /b 1
)
python "%~dp0inspect_moe_path.py" "%~1" > "%~dp0moe_path_report.txt" 2>&1
type "%~dp0moe_path_report.txt"
echo.
echo Saved: %~dp0moe_path_report.txt
