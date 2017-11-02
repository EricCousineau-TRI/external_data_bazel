#!/bin/bash
set -e -u

# Follow `WORKFLOWS.md`
mock_dir=$PWD/bazel_external_data_mock

# TODO: Prevent this from running outside of Bazel.

# Copy what's needed for modifiable `test_mock` directory.
srcs="src tools test_mock BUILD.bazel WORKSPACE"
rm -rf ${mock_dir}
mkdir ${mock_dir}
for src in ${srcs}; do
    cp -r $(readlink ${src}) ${mock_dir}
done

cd ${mock_dir}/test_mock
# Clean workspace.
find data/ -name '*.bin' | xargs rm

find . -type f

bazel run //:test_basics

# 1. Create file for development.

# 2. etc.
