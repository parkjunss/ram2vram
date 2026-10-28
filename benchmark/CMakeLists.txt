cmake_minimum_required(VERSION 3.24)
project(ram_to_vram_bench LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

add_executable(ram_to_vram_bench ram_to_vram_bench.cu)

# Reasonable default; override if desired:
# cmake -S . -B build -DCMAKE_CUDA_ARCHITECTURES=89
set_property(TARGET ram_to_vram_bench PROPERTY CUDA_ARCHITECTURES native)
