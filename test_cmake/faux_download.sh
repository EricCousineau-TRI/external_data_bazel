#!/bin/bash
set -e -u

src_dir=${1}
tgt_dir=${2}

srcs="src tools BUILD.bazel WORKSPACE"
for src in ${srcs}; do
    cp -r ${src_dir}/${src} ${tgt_dir}
done

# Add a fake CMakeLists.txt
touch ${tgt_dir}/CMakeLists.txt
