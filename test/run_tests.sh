#!/bin/bash
set -e -u
set -x

cd $(dirname $0)

_bazel() {
    bazel --bazelrc=/dev/null "$@"
}

echo "[ Example Interface ]"
(
    cd bazel_pkg_test
    _bazel test //...
)

echo "[ Downstream Consumption ]"
(
    cd bazel_pkg_downstream_test
    _bazel test //...
)

echo "[ Mock Storage ]"
(
    cd bazel_pkg_advanced_test
    _bazel test //...
)

echo "[ Edge Case Workflow ]"
(
    _bazel run :workflow_test
    # _bazel test :workflow_test
)

echo "[ Backends ]"
(
    cd backends
    (
        cd girder
        ./run_tests.sh
    )
)

# TODO: Add CMake usage.
