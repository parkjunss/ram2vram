@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "BIN=%ROOT%\llama.cpp-hybrid-cache\build\bin\llama-server.exe"
set "MODEL=%ROOT%\models\Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
if not exist "%MODEL%" (
  echo Model missing. Run setup_qwen36.bat first.
  exit /b 1
)
set "GGML_CUDA_MOE_CACHE=1"
echo Server starting. Default URL: http://127.0.0.1:8080 ; see listening address below for overrides.
"%BIN%" -m "%MODEL%" --alias qwen3.6-35b-a3b -ngl 99 --cpu-moe --moe-cache 8192 -c 4096 --parallel 1 --jinja --reasoning off --temp 0.7 --top-p 0.8 --top-k 20 --host 127.0.0.1 --port 8080 %*
exit /b %errorlevel%
