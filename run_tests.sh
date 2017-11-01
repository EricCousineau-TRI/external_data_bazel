#!/bin/bash
set -e -u

_bazel() {
    bazel --bazelrc=/dev/null "$@"
}

# Run basic interface tests
(
    cd test_simple
    _bazel test //...
)

# Run downstream consumption example
(
    cd test_simple_downstream
    _bazel test //...
)

# Run more advanced mock storage tests
(
    cd test_mock
    _bazel test //...
)

# TODO: Run workflow tests.


# TODO: Run backend tests.

