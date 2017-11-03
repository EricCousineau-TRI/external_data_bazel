cmake_minimum_required(VERSION 3.5)

# https://cmake.org/cmake/help/v3.5/module/ExternalProject.html
include(ExternalProject)

set(_external_data_bazel_pkg ${PROJECT_BINARY_DIR}/external/external_data_bazel_pkg)

ExternalProject_Add(external_data_bazel_pkg
    DOWNLOAD_COMMAND
        ${PROJECT_SOURCE_DIR}/faux_download.sh ${PROJECT_SOURCE_DIR}/.. ${_external_data_bazel_pkg}
    SOURCE_DIR
        ${_external_data_bazel_pkg}
    BUILD_COMMAND
        # We only care about the command-line.
        bazel --bazelrc=/dev/null build //:cli
    BUILD_IN_SOURCE 1
    INSTALL_COMMAND :
)

# https://cmake.org/cmake/help/v3.5/module/ExternalData.html
include(ExternalData)

set(ExternalData_CUSTOM_SCRIPT_bazel
    ${PROJECT_SOURCE_DIR}/external_data_bazel.cmake
)
set(ExternalData_URL_TEMPLATES
    "ExternalDataCustomScript://bazel/%(algo)/%(hash)"
)

enable_testing()

ExternalData_Add_Test(
    NAME
        test_basics
    COMMAND
        ${PROJECT_SOURCE_DIR}/test_basics.py
            DATA{direct.bin}
)
ExternalData_Add_Target(test_basics)
