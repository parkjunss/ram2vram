@echo off
setlocal
python "%~dp0..\python\download_qwen36_parallel.py"
exit /b %errorlevel%
