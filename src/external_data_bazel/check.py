"""
This script allows to upload data file revisoned based on a canonical path.
"""

import os
import sys
import yaml

from external_data_bazel import core, util


def add_arguments(parser):
    parser.add_argument('input_files', type=str, nargs='+')


def run(args, project):
    good = True
    for input_file in args.input_files:
        def action():
            do_check(args, project, input_file)
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


def do_check(args, project, filepath_in):
    filepath = os.path.abspath(filepath_in)
    info = project.get_file_info(filepath)
    remote = info.remote
    project_relpath = info.project_relpath
    hash = info.hash

    def dump_remote_config():
        dump = [{
            "file": project_relpath,
            "remote": project.debug_dump_remote_config(remote),
        }]
        yaml.dump(dump, sys.stdout, default_flow_style=False)

    if not remote.has_file(hash, project_relpath):
        if not args.verbose:
            dump_remote_config()
        raise RuntimeError("Remote does not have '{}' ({})".format(project_relpath, hash))
