#!/bin/bash
set -e -u
set -x

cd $(dirname $0)

_bazel() {
    bazel --bazelrc=/dev/null "$@"
}

echo "[ Example Interface ]"
(
    cd test_simple
    _bazel test //...
)

echo "[ Downstream Consumption ]"
(
    cd test_simple_downstream
    _bazel test //...
)

echo "[ Mock Storage ]"
(
    cd test_mock
    _bazel test //...
)

echo "[ Edge Case Workflow ]"
(
    _bazel run :test_workflows
    # _bazel test :test_workflows
)

# TODO: Run backend tests (e.g. GirderHashsum).

# TODO: Not yet complete.
# echo "[ CMake/ExternalData Workflow ]"
# (
#     cd test_cmake
#     ./run_test.sh
# )
