#!/bin/bash
set -e -u
set -x

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
    _bazel test //test_workflow/...
)

# TODO: Run backend tests.
