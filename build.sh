#!/usr/bin/env bash
# ============================================================
#  通用编译脚本
#
#  用法:
#    ./build.sh                    增量编译
#    ./build.sh debug              Debug 模式
#    ./build.sh clean              清理
#    ./build.sh rebuild            清理后完整重编
#    ./build.sh run <网卡> [程序]  编译并运行 (默认跑 main 程序)
#    ./build.sh sdk=/your/path     指定 SDK 路径
# ============================================================

set -e

# ---------------- 解析参数 ----------------
BUILD_TYPE="Release"
SDK_DIR=""
ACTION="build"
RUN_IFACE=""
RUN_BIN=""

for arg in "$@"; do
    case "$arg" in
        debug)         BUILD_TYPE="Debug" ;;
        release)       BUILD_TYPE="Release" ;;
        clean)         ACTION="clean" ;;
        rebuild)       ACTION="rebuild" ;;
        run)           ACTION="run" ;;
        sdk=*)         SDK_DIR="${arg#sdk=}" ;;
        eth*|enp*|lo|wlan*|wlp*) RUN_IFACE="$arg" ;;
        *)             RUN_BIN="$arg" ;;
    esac
done

# ---------------- 清理 ----------------
if [ "$ACTION" = "clean" ] || [ "$ACTION" = "rebuild" ]; then
    echo ">>> 清理 build/"
    rm -rf build compile_commands.json
    [ "$ACTION" = "clean" ] && exit 0
fi

# ---------------- 配置 ----------------
CMAKE_ARGS=(
    -S .
    -B build
    -DCMAKE_BUILD_TYPE="${BUILD_TYPE}"
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
)

# 优先级: 命令行 sdk= > 环境变量 UNITREE_SDK2_DIR > CMake 自己探测
if [ -n "$SDK_DIR" ]; then
    CMAKE_ARGS+=(-DUNITREE_SDK2_DIR="$SDK_DIR")
fi

if [ ! -d build ] || [ "$ACTION" = "rebuild" ]; then
    echo ">>> 配置 CMake (${BUILD_TYPE})"
    cmake "${CMAKE_ARGS[@]}"
fi

# ---------------- 编译 ----------------
echo ">>> 编译 (使用 $(nproc) 核)"
cmake --build build -j"$(nproc)"

# 软链给 clangd
ln -sf build/compile_commands.json compile_commands.json

echo ""
echo ">>> 完成. 可执行文件:"
ls -1 build/bin/ 2>/dev/null | sed 's/^/    /' || echo "    (空)"

# ---------------- 运行 ----------------
if [ "$ACTION" = "run" ]; then
    [ -z "$RUN_IFACE" ] && RUN_IFACE="lo"

    # 没指定程序就跑第一个
    if [ -z "$RUN_BIN" ]; then
        RUN_BIN=$(ls -1 build/bin/ 2>/dev/null | head -n1)
    fi

    if [ -z "$RUN_BIN" ] || [ ! -x "build/bin/$RUN_BIN" ]; then
        echo ""
        echo "✗ 找不到可执行文件: build/bin/$RUN_BIN"
        exit 1
    fi

    echo ""
    echo ">>> 运行: build/bin/$RUN_BIN $RUN_IFACE"
    ./build/bin/"$RUN_BIN" "$RUN_IFACE"
fi
