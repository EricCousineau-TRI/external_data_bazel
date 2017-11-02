#!/bin/bash
set -e -u -x

eecho() { echo "$@" >&2; }
mkcd() { mkdir -p ${1} && cd ${1}; }
_bazel() { bazel --bazelrc=/dev/null "$@"; }
# For testing, we should be able to both (a) test and (b) run the target.
_bazel-test() { _bazel test "$@" && _bazel run "$@"; }

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

# Clear out any old cache and upload in mock directory.
rmsy() {
    cur_dir=${1}
    if [[ -d ${cur_dir} ]]; then
        eecho "Removing: ${cur_dir}";
        rm -rf ${cur_dir}
    fi
}

cache_dir=/tmp/bazel_external_data/test_cache
rmsy ${cache_dir}
upload_dir=/tmp/bazel_external_data/upload
rmsy ${upload_dir}

# Start modifying.
cd ${mock_dir}/test_mock

# Create a new package.
mkcd data_new

# Create the expected contents.
cat > expected.txt <<EOF
Expected contents.
EOF
# Create the new file.
cp expected.txt new.bin
sha=$(sha512sum new.bin | cut -f1 -d' ')

# Write a test that consumes the file.
cat > test_basics.py <<EOF
with open('data_new/new.bin') as f:
    contents = f.read()
with open('data_new/expected.txt') as f:
    contents_expected = f.read()
assert contents == contents_expected
EOF

# Declare this file as a development file, and write our test.
cat > BUILD.bazel <<EOF
load("//tools:external_data.bzl", "external_data")

external_data(
    file = "new.bin",
    mode = "devel",
)

py_test(
    name = "test_basics",
    srcs = ["test_basics.py"],
    data = [
        ":expected.txt",
        ":new.bin"
    ],
)
EOF

# Ensure that we can build the file.
_bazel build :new.bin

# Ensure that we can run the test with the file in development mode.
_bazel-test :test_basics

# Ensure that our cache and upload directory is empty.
[[ ! -d ${cache_dir} ]]
[[ ! -d ${upload_dir} ]]

# Now upload the file.
../tools/external_data upload ./new.bin

# Ensure our upload directory has the file (and only this file).
[[ -d ${upload_dir} ]]
upload_file=$(find ${upload_dir} -type f)
# - We should have the hash name.
# - The contents should be the same as the original.
diff ${upload_file} ./new.bin > /dev/null
# We should NOT have created a cache at this point.
[[ ! -d ${cache_dir} ]]

# Ensure that we have created the hash file accurately.
[[ $(cat ./new.bin.sha512) == ${sha} ]]

# - Change the original, such that it'd fail the test, and ensure failure.
echo "User changed the file" > ./new.bin
! _bazel-test :test_bascis
[[ ! -d ${cache_dir} ]]

# Now switch to 'no_cache' mode.
sed -i 's#mode = "devel",#mode = "no_cache",#g' ./BUILD.bazel
cat BUILD.bazel
# Ensure that we can now run the binary with the external data setup.
_bazel-test :test_basics
# No cache should have been used.
[[ ! -d ${cache_dir} ]]

# Switch to 'normal' mode.
sed -i 's/mode = "no_cache",/# Normal is implicit./g' ./BUILD.bazel
cat BUILD.bazel
# - Clean so that we re-trigger a download.
bazel clean
_bazel-test :test_basics

# This should have encountered a cache-miss.
[[ -d ${cache_dir} ]]
# - This should be the *only* file in the cache.
cache_file=$(find ${cache_dir} -type f)
# Should have been indexed by the SHA.
[[ $(basename ${cache_file}) == ${sha} ]]
# Contents should be the same.
diff ${cache_file} ./expected.txt > /dev/null

# Now download the file via the command line.
# - This should fail since we already have the file.
! ../tools/external_data download ./new.bin.sha512
# - Try it with -f
../tools/external_data download -f ./new.bin.sha512
diff new.bin ./expected.txt > /dev/null
# - Try it without -f
rm new.bin
../tools/external_data download ./new.bin.sha512
diff new.bin ./expected.txt > /dev/null

# Now we wish to actively modify the file.
cat > expected.txt <<EOF
New contents!
EOF
# - Must be different.
! diff new.bin expected.txt > /dev/null
# - Now update local workspace version.
cp expected.txt new.bin
# Change to development mode.
sed -i 's/# Normal is implicit./mode = "devel",/g' ./BUILD.bazel
cat ./BUILD.bazel
# The test should pass.
_bazel-test :test_basics

# Now upload the newest version.
# - Trying to upload the SHA-512 file should fail.
! ../tools/external_data upload ./new.bin.sha512
../tools/external_data upload ./new.bin

# There should be two files uploaded.
[[ $(find ${upload_dir} -type f | wc -l) -eq 2 ]]

# Switch back to normal mode.
sed -i 's/mode = "devel",/# Normal is implicit./g' ./BUILD.bazel
cat ./BUILD.bazel

# Now remove the file. It should still pass the test.
rm new.bin
_bazel-test :test_basics

# Download and check the file, but as a symlink now.
../tools/external_data download --symlink_from_cache ./new.bin.sha512
[[ -L new.bin ]]
diff new.bin expected.txt > /dev/null

# Make sure symlink is read-only.
! echo 'Try to overwrite' > ./new.bin

# Corrupt the cache.
cache_file=$(readlink ./new.bin)
chmod +w ${cache_file}
echo "Corrupted" > ${cache_file}
! diff new.bin expected.txt > /dev/null
# - Bazel should have recognized the write on the internally built file.
# It will re-trigger a download.
_bazel-test :test_basics
# Ensure our symlink is now correct.
diff new.bin expected.txt > /dev/null

# Remove the cache.
rm -rf ${cache_dir}
# - Bazel should have a bad symlink, and should recognize this and re-trigger a download.
_bazel-test :test_basics
# - The cache directory should have been re-created.
[[ -d ${cache_dir} ]]

# Ensure that we have all the files we want.
rm new.bin
find . -name '*.sha512' | xargs ../tools/external_data download --check_file=only
# --check_file=only should not have written a new file.
[[ ! -f new.bin ]]

echo "[ Done ]"
