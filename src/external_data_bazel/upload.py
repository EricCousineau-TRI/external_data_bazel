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

from external_data_bazel import base, util

SHA_SUFFIX = base.SHA_SUFFIX


def add_arguments(parser):
    parser.add_argument('filepaths', type=str, nargs='+')


def run(args, project, remote_in):
    for filepath in args.filepaths:
        def action():
            do_upload(project, filepath, remote_in)
        if args.keep_going:
            try:
                action()
            except RuntimeError as e:
                util.eprint(e)
                util.eprint("Continuing (--keep_going).")
        else:
            action()


def do_upload(project, filepath, remote_in):
    filepath = os.path.abspath(filepath)
    if filepath.endswith(SHA_SUFFIX):
        filepath_guess = filepath[:-len(SHA_SUFFIX)]
        raise RuntimeError("Input file is a SHA file. Did you mean to upload '{}' instead?".format(filepath_guess))

    if remote_in:
        remote = remote_in
    else:
        remote = project.load_remote(filepath)
    sha = remote.upload_file(filepath)

    # Write SHA512
    sha_file = filepath + SHA_SUFFIX
    with open(sha_file, 'w') as fd:
        print("Updating sha file: {}".format(sha_file))
        fd.write(sha + "\n")

    print("[ Done ]")
