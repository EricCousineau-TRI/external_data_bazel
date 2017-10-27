#!/usr/bin/env python

import os

expected_files = {
    "backend_root": [
        "basic.bin",
        "direct.bin",
        "glob_1.bin",
        "glob_2.bin",
        "glob_3.bin",
    ],
    "backend_child": [
        "extra.bin",
    ],
}

data_dir = 'test/data'
mock_dir = 'test/mock'

# Go through each file and ensure that we have the desired contents.
for file in find_files('*.bin'):
    contents = open(file).read()
    file_name = os.path.basename(file)
    for mock_name, mock_file_names in expected_files.iteritems():
        if file_name in mock_file_names:
            mock_file = os.path.join(mock_dir, mock_name, file_name)
            mock_contents = open(mock_file).read()
            break
    assert contents == mock_contents
