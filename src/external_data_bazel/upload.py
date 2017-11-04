"""
This script allows to upload data file revisoned based on a canonical path.
"""

from __future__ import absolute_import, print_function

import json
import os
import sys
import textwrap
import argparse

from datetime import datetime

from external_data_bazel import core, util

HASH_SUFFIX = core.HASH_SUFFIX


def add_arguments(parser):
    parser.add_argument('filepaths', type=str, nargs='+')


def run(args, project):
    for filepath in args.filepaths:
        def action():
            do_upload(project, filepath)
        if args.keep_going:
            try:
                action()
            except RuntimeError as e:
                util.eprint(e)
                util.eprint("Continuing (--keep_going).")
        else:
            action()


def do_upload(project, filepath):
    filepath = os.path.abspath(filepath)
    project_relpath = project.get_relpath(filepath)
    if filepath.endswith(HASH_SUFFIX):
        filepath_guess = filepath[:-len(HASH_SUFFIX)]
        raise RuntimeError("Input file is a hash file. Did you mean to upload '{}' instead?".format(filepath_guess))

    remote = project.load_remote(project_relpath)
    hash = remote.upload_file(project_relpath, filepath)

    # Write SHA512
    hash_file = filepath + HASH_SUFFIX
    with open(hash_file, 'w') as fd:
        print("Updating hash file: {}".format(hash_file))
        fd.write(hash + "\n")

    print("[ Done ]")
