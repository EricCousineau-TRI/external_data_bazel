#!/bin/bash
set -e -u
set -x

cd $(dirname $0)

bazel() {
    $(which bazel) --bazelrc=/dev/null "$@"
}

echo "[ Example Interface ]"
(
    cd bazel_pkg_test
    bazel test //...
)

echo "[ Downstream Consumption ]"
(
    cd bazel_pkg_downstream_test
    bazel test //...
)

echo "[ Mock Storage ]"
(
    cd bazel_pkg_advanced_test
    bazel test //...
)

echo "[ Workflows ]"
(
    bazel test --test_output=streamed :workflows_test
)

echo "[ Backends ]"
(
    cd backends
    (
        cd girder
        ./run_tests.sh
    )
)
