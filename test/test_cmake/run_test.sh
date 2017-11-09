#!/bin/bash
set -e -u

mkdir -p build
cd build

cmake ..
make

ctest --output-on-failure -R test_basics
