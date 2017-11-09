#!/bin/bash
set -e -u -x

cd /mnt/build

mkdir -p ~/.config/external_data_bazel
cp ./external_data.user.yml ~/.config/external_data_bazel/config.yml

cd ./bazel-large-files-with-girder

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
