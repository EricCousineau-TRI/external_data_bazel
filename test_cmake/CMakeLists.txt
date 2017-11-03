cmake_minimum_required(VERSION 3.5)

# https://cmake.org/cmake/help/v3.5/module/ExternalProject.html
include(ExternalProject)

# Bazel still leaves *out in the source directory...
set(_external_data_bazel_pkg ${PROJECT_SOURCE_DIR}/..)
set(_bazel_args)  # --symlink_prefix=${PROJECT_BINARY_DIR}/external/external_data_bazel_pkg/bazel-)

ExternalProject_Add(external_data_bazel_pkg
    # TODO(eric.cousineau): Follow 'test_workflow' and copy the necessary components to the bin dir.
    SOURCE_DIR
        ${_external_data_bazel_pkg}
    # BINARY_DIR
    #     ${PROJECT_BINARY_DIR}/external/external_data_bazel_pkg
    BUILD_COMMAND
        # We only care about the command-line.
        bazel build ${_bazel_args} //:cli
    BUILD_IN_SOURCE 1
    INSTALL_COMMAND :
)

# https://cmake.org/cmake/help/v3.5/module/ExternalData.html
include(ExternalData)


