#!/usr/bin/env python

import os
from bazel_external_data.util import subshell

expected_files = {
    "backend_root": [
        "basic.bin",
        "glob_1.bin",
        "glob_2.bin",
        "glob_3.bin",
    ],
    "backend_child": [
        "extra.bin",
    ],
    None: [
        "direct.bin",
    ],
}

data_dir = 'test/data'
mock_dir = 'test/mock'

# Go through each file and ensure that we have the desired contents.
files = subshell("find test/data -name '*.bin'")
for file in files.split('\n'):
    contents = open(file).read()
    file_name = os.path.basename(file)
    for mock_name, mock_file_names in expected_files.iteritems():
        if file_name in mock_file_names:
            if mock_name is not None:
                mock_file = os.path.join(mock_dir, mock_name, file_name)
                mock_contents = open(mock_file).read()
            else:
                mock_contents = "Content for '{}'\n".format(file_name)
            break
    assert contents == mock_contents
