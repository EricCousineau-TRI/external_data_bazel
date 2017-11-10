#!/bin/bash
set -e -u -x

cd /mnt/build

cd ./bazel_pkg_girder_test

cd data

cp /mnt/build/small_dragon.obj ./dragon.obj
../tools/external_data upload ./dragon.obj

rm dragon.obj
../tools/external_data download ./dragon.obj

rm dragon.obj
cp /mnt/build/large_dragon.obj ./dragon.obj
../tools/external_data upload ./dragon.obj

rm dragon.obj
../tools/external_data download ./dragon.obj
