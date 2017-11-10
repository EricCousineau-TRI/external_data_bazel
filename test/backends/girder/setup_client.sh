#!/bin/bash
set -e -u

cur_dir=$(cd $(dirname $0) && pwd)

url=${1}
out_dir=${2}

mkdir -p ${out_dir}
cd ${out_dir}

repo_name=bazel_pkg_girder_test
repo_dir=${out_dir}/${repo_name}

# Download data files.
(
    cd ${out_dir}
    [[ -f small_dragon.obj ]] || \
        curl -L --progress-bar -o small_dragon.obj -O https://github.com/jcfr/bazel-large-files-with-girder/releases/download/test-data/small_dragon.obj
    [[ -f large_dragon.obj ]] || \
        curl -L --progress-bar -o large_dragon.obj -O https://github.com/jcfr/bazel-large-files-with-girder/releases/download/test-data/large_dragon.obj
)

info_file=${out_dir}/info.yaml
config_file=${repo_dir}/.external_data.yml
user_file=${repo_dir}/tools/external_data.user.yml
${cur_dir}/setup_client.py ${url} ${info_file} ${config_file} ${user_file}
