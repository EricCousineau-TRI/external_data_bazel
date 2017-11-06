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


def add_arguments(parser):
    parser.add_argument('filepaths', type=str, nargs='+')
    parser.add_argument('--update_only', action='store_true',
                        help="Only update the file information (e.g. hash file), but do not upload the file.")

def run(args, project):
    good = True
    for filepath in args.filepaths:
        def action():
            do_upload(args, project, filepath)
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


def do_upload(args, project, filepath_in):
    filepath = os.path.abspath(filepath_in)

    hash_orig_file = project.is_hash_file(filepath)
    if hash_orig_file:
        raise RuntimeError("Input file is a hash file. Did you mean to upload '{}' instead?".format(hash_orig_file))

    info = project.get_file_info(filepath, must_have_hash=False)
    remote = info.remote
    project_relpath = info.project_relpath

    # TODO(eric.cousineau): Consider replacing `filepath` with `info.orig_filepath`, to allow
    # the hash file to be 'uploaded' (redirecting to original file).
    if not args.update_only:
        hash = remote.upload_file(info.hash.hash_type, project_relpath, filepath)
    else:
        # ... Hmm... This looks ugly.
        hash = info.hash.compute(filepath)
    project.update_file_info(info, hash)
