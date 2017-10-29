#!/bin/bash
set -e -u

sync_sha() {
    src_dir=${1}
    tgt_dir=${2}
    mock_backend=$(dirname $BASH_SOURCE)/../${src_dir}
    for f in ${mock_backend}/*; do
        sha=$(sha512sum ${f} | cut -f 1 -d' ')
        name=$(basename ${f})
        sha_file="${tgt_dir}/${name}.sha512"
        echo ${sha} > ${sha_file}
    done
}

sync_sha mock/backend_root .
sync_sha mock/backend_child ./package
sync_sha mock/backend_child ./package_overlay
