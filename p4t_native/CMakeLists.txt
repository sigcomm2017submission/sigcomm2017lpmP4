cmake_minimum_required(VERSION 2.8)

project(p4t_native)

find_package(OpenMP)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS} -std=c++14 -Wall -Werror -O2")
set(CMAKE_EXPORT_COMPILE_COMMANDS 1)

find_package(PythonLibs 2.7 REQUIRED)
include_directories( ${PYTHON_INCLUDE_DIRS} )

find_package(Boost COMPONENTS python REQUIRED)
include_directories( ${Boost_INCLUDE_DIRES} ${CMAKE_SOURCE_DIR} )

add_library(p4t_native SHARED 
    common.cpp
    p4t_native.cpp 
    p4t_native_ext.cpp
    chain_algos.cpp
    oi_algos.cpp
    )
set_target_properties(p4t_native PROPERTIES PREFIX "")
target_link_libraries(p4t_native ${Boost_LIBRARIES} ${PYTHON_LIBRARIES})
