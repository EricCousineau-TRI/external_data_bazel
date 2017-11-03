"""
This script allows to upload data file revisoned based on a canonical path.
"""

import os
import sys
import yaml

from external_data_bazel import core, util

HASH_SUFFIX = core.HASH_SUFFIX

def add_arguments(parser):
    parser.add_argument('hash_files', type=str, nargs='+')


def run(args, project, remote_in):
    bad = False
    for hash_file in args.hash_files:
        def action():
            do_check(args, project, hash_file, remote_in)
        if args.keep_going:
            try:
                action()
            except RuntimeError as e:
                bad = True
                util.eprint(e)
                util.eprint("Continuing (--keep_going).")
        else:
            action()
    if bad:
        return False
    else:
        return True


def do_check(args, project, hash_file, remote_in):
    hash_file = os.path.abspath(hash_file)
    if not hash_file.endswith(HASH_SUFFIX):
        raise RuntimeError("File does not match *{}: {}".format(HASH_SUFFIX, hash_file))
    filepath = hash_file[:-len(HASH_SUFFIX)]
    project_relpath = project.get_canonical_path(filepath)

    with open(hash_file) as fd:
        hash = fd.read().strip()

    if remote_in:
        remote = remote_in
    else:
        remote = project.load_remote(hash_file)

    def dump_remote_config():
        dump = [{
            "file": project.get_relpath(hash_file),
            "remote": project.debug_dump_remote_config(remote),
        }]
        yaml.dump(dump, sys.stdout, default_flow_style=False)

    if not remote.has_file(hash, project_relpath):
        if not args.verbose:
            dump_remote_config()
        raise RuntimeError("Remote does not have '{}' ({})".format(hash_file, hash))
