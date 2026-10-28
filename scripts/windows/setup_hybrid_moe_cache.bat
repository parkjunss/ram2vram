@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "TARGET=%ROOT%\llama.cpp-hybrid-cache"
set "REVISION=e3096b046bb809f7f80bc47801f6579aed1cbc60"
if not defined RAM2VRAM_CUDA_ARCH set "RAM2VRAM_CUDA_ARCH=native"
for %%T in (git cmake ninja nvcc cl) do (
  where %%T >nul 2>nul
  if errorlevel 1 (
    echo Missing %%T. Use an x64 Native Tools Command Prompt with CUDA on PATH.
    exit /b 1
  )
)
if not exist "%TARGET%" (
  git clone --no-checkout https://github.com/leloch/llama.cpp.git "%TARGET%"
  if errorlevel 1 exit /b 1
  git -C "%TARGET%" checkout --detach %REVISION%
  if errorlevel 1 exit /b 1
)
if not exist "%TARGET%\.git" (
  echo Existing target is not a Git checkout. Inspect it manually.
  exit /b 1
)
set "CURRENT="
for /f %%R in ('git -C "%TARGET%" rev-parse HEAD') do set "CURRENT=%%R"
if not "%CURRENT%"=="%REVISION%" (
  echo Existing engine differs from the pinned revision. No checkout was changed.
  exit /b 1
)
cmake -S "%TARGET%" -B "%TARGET%\build" -G Ninja -DGGML_CUDA=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_BORINGSSL=ON -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=%RAM2VRAM_CUDA_ARCH%
if errorlevel 1 exit /b 1
cmake --build "%TARGET%\build" --parallel
if errorlevel 1 exit /b 1
"%TARGET%\build\bin\llama-cli.exe" --help | findstr /I /C:"moe-cache"
exit /b %errorlevel%
