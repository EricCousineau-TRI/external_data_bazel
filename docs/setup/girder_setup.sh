#!/bin/bash
set -e -u

cur=$(cd $(dirname ${BASH_SOURCE}) && pwd)

cd ${cur}/../../..
mkdir -p build
cd build
# Set up virtualenv
virtualenv .
set +x
source bin/activate
set -x
# Install girder client.
pip install girder-client
