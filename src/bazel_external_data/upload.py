#!/usr/bin/env python

"""This script allows to upload data file revisoned based on a canonical path.
"""

from __future__ import absolute_import, print_function

import json
import os
import sys
import textwrap
import argparse

from datetime import datetime

from bazel_external_data import util

SHA_SUFFIX = util.SHA_SUFFIX

def upload(project, filepath):
    if not os.path.isabs(filepath):
        raise RuntimeError("Must supply absolute path: {}".format(filepath))
    filepath = os.path.abspath(filepath)
    if filepath.endswith(SHA_SUFFIX):
        filepath_guess = filepath[:-len(SHA_SUFFIX)]
        raise RuntimeError("Input file is a SHA file. Did you mean to upload '{}' instead?".format(filepath_guess))

    remote = project.load_remote(filepath)
    sha = remote.upload_file(filepath)

    # Write SHA512
    sha_file = filepath + SHA_SUFFIX
    with open(sha_file, 'w') as fd:
        print("Updating sha file: {}".format(sha_file))
        fd.write(sha + "\n")

    print("[ Done ]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filepaths', type=str, nargs='+')
    args = parser.parse_args()

    project = util.load_project(os.getcwd())
    for filepath in args.filepaths:
        upload(project, filepath)


if __name__ == '__main__':
    main()
