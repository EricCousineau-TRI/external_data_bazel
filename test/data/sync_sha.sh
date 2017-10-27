#!/bin/bash
set -e -u

mock_backend=$(dirname $BASH_SOURCE)/../mock_backend

for f in ${mock_backend}/*; do
    sha=$(sha512sum ${f} | cut -f 1 -d' ')
    name=$(basename ${f})
    sha_file="${name}.sha512"
    echo ${sha} > ${sha_file}
done
