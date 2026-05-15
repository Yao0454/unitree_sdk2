cmake_minimum_required(VERSION 3.10)
project(my_g1_app VERSION 0.1.0 LANGUAGES CXX)

# ============================================================
#  通用 CMakeLists - 自动探测 unitree_sdk2 安装位置
#
#  支持以下场景（按优先级从高到低）：
#    1. 环境变量 UNITREE_SDK2_DIR=/path/to/sdk
#    2. 工程内置子目录: ./unitree_sdk2 或 ./third_party/unitree_sdk2
#    3. /opt/unitree_robotics
#    4. /usr/local
#    5. 系统默认 find_package
#
#  也可以命令行传:
#    cmake .. -DUNITREE_SDK2_DIR=/your/path
# ============================================================

# ---------------- 基本设置 ----------------
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# 让 CMake 找到自己工程的头
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# ============================================================
#  探测 unitree_sdk2 位置
# ============================================================

# 候选路径列表（按优先级）
set(_unitree_search_paths "")

# 1. 命令行 -DUNITREE_SDK2_DIR= 或环境变量
if(DEFINED UNITREE_SDK2_DIR)
    list(APPEND _unitree_search_paths "${UNITREE_SDK2_DIR}")
elseif(DEFINED ENV{UNITREE_SDK2_DIR})
    list(APPEND _unitree_search_paths "$ENV{UNITREE_SDK2_DIR}")
endif()

# 2. 工程内置子目录
list(APPEND _unitree_search_paths
    "${CMAKE_CURRENT_SOURCE_DIR}/unitree_sdk2"
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/unitree_sdk2"
    "${CMAKE_CURRENT_SOURCE_DIR}/../unitree_sdk2"
)

# 3. 系统标准位置
list(APPEND _unitree_search_paths
    "/opt/unitree_robotics"
    "/usr/local"
    "/usr"
)

# 把候选路径加到 CMAKE_PREFIX_PATH
list(APPEND CMAKE_PREFIX_PATH ${_unitree_search_paths})

# 找 SDK
find_package(unitree_sdk2 QUIET)

# 如果 find_package 没找到，尝试手动定位（适配 SDK 源码树没装的情况）
if(NOT unitree_sdk2_FOUND)
    foreach(_path IN LISTS _unitree_search_paths)
        if(EXISTS "${_path}/CMakeLists.txt" AND EXISTS "${_path}/include/unitree")
            message(STATUS "Found unitree_sdk2 source tree at: ${_path}")
            add_subdirectory(${_path} ${CMAKE_BINARY_DIR}/_unitree_sdk2_build EXCLUDE_FROM_ALL)
            set(unitree_sdk2_FOUND TRUE)
            break()
        endif()
    endforeach()
endif()

if(NOT unitree_sdk2_FOUND)
    message(FATAL_ERROR
        "\n=========================================================\n"
        " 未找到 unitree_sdk2!\n"
        " 已尝试以下路径:\n"
        "   ${_unitree_search_paths}\n"
        "\n"
        " 解决方法 (任选其一):\n"
        "   1. 把 SDK clone 到工程子目录:\n"
        "      git clone https://github.com/unitreerobotics/unitree_sdk2 ./unitree_sdk2\n"
        "\n"
        "   2. 安装 SDK 到 /opt/unitree_robotics:\n"
        "      cd unitree_sdk2 && mkdir build && cd build\n"
        "      cmake .. -DCMAKE_INSTALL_PREFIX=/opt/unitree_robotics\n"
        "      make -j && sudo make install\n"
        "\n"
        "   3. 设置环境变量:\n"
        "      export UNITREE_SDK2_DIR=/your/path/to/unitree_sdk2\n"
        "\n"
        "   4. 命令行指定:\n"
        "      cmake .. -DUNITREE_SDK2_DIR=/your/path\n"
        "=========================================================\n"
    )
endif()

message(STATUS "✓ unitree_sdk2 ready")

# ============================================================
#  可选依赖（找到就用，找不到就跳过对应功能）
# ============================================================
find_package(Eigen3 QUIET)
if(Eigen3_FOUND)
    message(STATUS "✓ Eigen3 ${Eigen3_VERSION}")
else()
    message(STATUS "✗ Eigen3 not found (低层控制不可用)")
endif()

find_package(Boost QUIET COMPONENTS program_options)
if(Boost_FOUND)
    message(STATUS "✓ Boost::program_options")
else()
    message(STATUS "✗ Boost::program_options not found (命令行解析不可用)")
endif()

# ============================================================
#  构建可执行文件
#  把所有 src/*.cpp 自动编译成同名可执行文件
# ============================================================
file(GLOB _src_files CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.cpp")

if(NOT _src_files)
    message(WARNING "src/ 下没有 .cpp 文件")
endif()

foreach(_src ${_src_files})
    get_filename_component(_name ${_src} NAME_WE)
    add_executable(${_name} ${_src})
    target_link_libraries(${_name} PRIVATE unitree_sdk2)

    # 按需链接可选依赖
    if(Eigen3_FOUND)
        target_link_libraries(${_name} PRIVATE Eigen3::Eigen)
    endif()
    if(Boost_FOUND)
        target_link_libraries(${_name} PRIVATE Boost::program_options)
    endif()

    message(STATUS "  + 目标: ${_name}  (${_src})")
endforeach()

# ============================================================
#  打印汇总信息
# ============================================================
message(STATUS "")
message(STATUS "================== Build Summary ==================")
message(STATUS "  Build type     : ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard   : C++${CMAKE_CXX_STANDARD}")
message(STATUS "  Output dir     : ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
message(STATUS "  Compile cmds   : ${CMAKE_BINARY_DIR}/compile_commands.json")
message(STATUS "===================================================")
message(STATUS "")
