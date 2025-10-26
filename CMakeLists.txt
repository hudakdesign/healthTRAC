cmake_minimum_required(VERSION 4.0)
project(healthTRACpersonal)

set(CMAKE_CXX_STANDARD 14)

include_directories(.)
include_directories(firmware)

add_executable(healthTRACpersonal
        firmware/toothbrush_bridge_firmware.ino
        firmware/toothbrush_firmware.ino)
