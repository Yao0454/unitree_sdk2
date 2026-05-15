cmake_minimum_required(VERSION 3.16)
project(g1_motion_controller CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_BUILD_TYPE Release)

# ── LibTorch — manual (no CUDA compilation needed in our code) ────────────
set(TORCH_ROOT
    "$ENV{HOME}/anaconda3/envs/env_isaaclab/lib/python3.11/site-packages/torch")
set(NVIDIA_CUDA_ROOT
    "$ENV{HOME}/anaconda3/envs/env_isaaclab/lib/python3.11/site-packages/nvidia")

set(TORCH_INCLUDE_DIRS
    "${TORCH_ROOT}/include"
    "${TORCH_ROOT}/include/torch/csrc/api/include"
)
set(TORCH_LIB_DIR "${TORCH_ROOT}/lib")

# Exact .so files to link (avoids CMake's CUDA detection)
set(TORCH_LIBRARIES
    "${TORCH_LIB_DIR}/libtorch.so"
    "${TORCH_LIB_DIR}/libtorch_cpu.so"
    "${TORCH_LIB_DIR}/libtorch_cuda.so"
    "${TORCH_LIB_DIR}/libc10.so"
    "${TORCH_LIB_DIR}/libc10_cuda.so"
)

# ── Unitree SDK2 ──────────────────────────────────────────────────────────
find_package(unitree_sdk2 REQUIRED)

# ── Target ────────────────────────────────────────────────────────────────
add_executable(g1_motion_controller g1_motion_controller.cpp)

target_include_directories(g1_motion_controller PRIVATE
    ${TORCH_INCLUDE_DIRS}
)

target_compile_options(g1_motion_controller PRIVATE
    -O2
)

target_link_libraries(g1_motion_controller PRIVATE
    ${TORCH_LIBRARIES}
    unitree_sdk2
)

# RPATH: find libtorch*.so at runtime without LD_LIBRARY_PATH
set_target_properties(g1_motion_controller PROPERTIES
    BUILD_RPATH   "${TORCH_LIB_DIR}"
    INSTALL_RPATH "${TORCH_LIB_DIR}"
)
