# source/move/CMakeLists.txt
# 跟 example/g1/CMakeLists.txt 是一个写法

add_executable(move main.cpp)
target_link_libraries(move PRIVATE unitree_sdk2)

# 如果用到 Eigen（terminations.hpp 之类）：
# find_package(Eigen3 QUIET)
# if(Eigen3_FOUND)
#     target_link_libraries(move PRIVATE Eigen3::Eigen)
# endif()

# 如果有第二个程序：
# add_executable(another_demo another.cpp)
# target_link_libraries(another_demo PRIVATE unitree_sdk2)
