@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "BIN=%ROOT%\llama.cpp-hybrid-cache\build\bin\llama-cli.exe"
set "MODEL=%ROOT%\models\Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
set "LOGDIR=%ROOT%\qwen36_cache_logs"
if not exist "%MODEL%" (
  echo Model missing. Run setup_qwen36.bat first.
  exit /b 1
)
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "GGML_CUDA_MOE_CACHE=0"
"%BIN%" -m "%MODEL%" -lv 4 -ngl 99 --cpu-moe --moe-cache off -c 4096 -n 128 --jinja --reasoning off --temp 0 --seed 42 --single-turn -p "Write a short Java function that returns the nth Fibonacci number and briefly explain it." > "%LOGDIR%\off.txt" 2>&1
if not "%errorlevel%"=="0" exit /b 1
set "GGML_CUDA_MOE_CACHE=1"
"%BIN%" -m "%MODEL%" -lv 4 -ngl 99 --cpu-moe --moe-cache 8192 -c 4096 -n 128 --jinja --reasoning off --temp 0 --seed 42 --single-turn -p "Write a short Java function that returns the nth Fibonacci number and briefly explain it." > "%LOGDIR%\8192.txt" 2>&1
if not "%errorlevel%"=="0" exit /b 1
echo === OFF ===
findstr /I /C:"Generation:" /C:"eval time" "%LOGDIR%\off.txt"
echo === 8192 MiB ===
findstr /I /C:"Generation:" /C:"eval time" /C:"hit" /C:"miss" "%LOGDIR%\8192.txt"
exit /b 0
