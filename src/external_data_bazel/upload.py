"""
This script allows to upload data file revisoned based on a canonical path.
"""

from __future__ import absolute_import, print_function

import os
import sys
import argparse

from external_data_bazel import core, util


def add_arguments(parser):
    parser.add_argument('filepaths', type=str, nargs='+')
    parser.add_argument(
        '--update_only', action='store_true',
        help="Only update the file information (e.g. hash file), but do not" +
             "upload the file.")


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


def do_upload(args, project, filepath):
    info = project.frontend.get_file_info(
        os.path.abspath(filepath), must_have_hash=False)
    remote = info.remote
    hash = info.hash
    project_relpath = info.project_relpath
    orig_filepath = info.orig_filepath

    if args.verbose:
        yaml.dump(info.debug_config(), sys.stdout, default_flow_style=False)

    if not args.update_only:
        hash = remote.upload_file(
            hash.hash_type, project_relpath, orig_filepath)
    else:
        hash = hash.compute(orig_filepath)
    project.frontend.update_file_info(info, hash)
