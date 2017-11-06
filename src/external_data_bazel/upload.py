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
    good = True
    for filepath in args.filepaths:
        def action():
            do_upload(project, filepath)
        if args.keep_going:
            try:
                action()
            except RuntimeError as e:
                good = False
                util.eprint(e)
                util.eprint("Continuing (--keep_going).")
        else:
            action()
    return good


def do_upload(project, filepath_in):
    filepath = os.path.abspath(filepath_in)
    if filepath.endswith(HASH_SUFFIX):
        filepath_guess = filepath[:-len(HASH_SUFFIX)]
        raise RuntimeError("Input file is a hash file. Did you mean to upload '{}' instead?".format(filepath_guess))

    info = project.get_file_info(filepath, must_have_hash=False)
    remote = info.remote
    project_relpath = info.project_relpath

    # TODO(eric.cousineau): Consider replacing `filepath` with `info.orig_filepath`, to allow
    # the hash file to be 'uploaded' (redirecting to original file).
    hash = remote.upload_file(project_relpath, filepath)
    project.update_file_info(info, hash)

    print("[ Done ]")
