#!/usr/bin/env python

import sys
import os
import yaml
import argparse

from external_data_bazel import core, util, config_helpers
from external_data_bazel import download, upload, check

assert __name__ == '__main__'

parser = argparse.ArgumentParser()
parser.add_argument('--project_root_guess', type=str, default='.',
                    help='File path to guess the project root.')
# TODO(eric.cousineau): If we are crossing project boundaries, consider checking project name as well.
# This would allow a parent project to use `--project_root_guess`, given a child project's files, but
# without thinking that it's the child project. This is normally handled by PWD, but is not the case
# with Bazel.
parser.add_argument('--user_config', type=str, default=None,
                    help='Override user configuration (useful for testing).')
parser.add_argument('-k', '--keep_going', action='store_true',
                    help='Attempt to keep going.')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='Dump configuration and show command-line arguments. WARNING: Will print out information in user configuration (e.g. keys) as well!')

# Credit here: https://stackoverflow.com/a/10913734/7829525
subparsers = parser.add_subparsers(dest="command")

download_parser = subparsers.add_parser("download")
download.add_arguments(download_parser)

upload_parser = subparsers.add_parser("upload")
upload.add_arguments(upload_parser)

check_parser = subparsers.add_parser("check")
check.add_arguments(check_parser)

args = parser.parse_args()

# Do not allow running under Bazel unless we have a guess for the project root from an input file.
if util.in_bazel_runfiles() and not args.project_root_guess:
    util.eprint("ERROR: Do not run this command via `bazel run`. Use a wrapper to call the binary.")
    util.eprint("  (If you are writing a test in Bazel, ensure that you pass `--project_root_guess=$(location <target>)`.)")
    exit(1)

if args.verbose:
    util.eprint("cmdline:")
    util.eprint("  pwd: {}".format(os.getcwd()))
    util.eprint("  argv[0]: {}".format(sys.argv[0]))
    util.eprint("  argv[1:]: {}".format(sys.argv[1:]))

user_config = None
if args.user_config is not None:
    user_config = config_helpers.parse_config_file(args.user_config)

project = core.load_project(os.path.abspath(args.project_root_guess), user_config)
if args.verbose:
    yaml.dump({"user_config": project.debug_dump_user_config()}, sys.stdout, default_flow_style=False)
    yaml.dump({"project_config": project.debug_dump_config()}, sys.stdout, default_flow_style=False)

# Execute command.
if args.command == 'download':
    status = download.run(args, project)
elif args.command == 'upload':
    status = upload.run(args, project)
elif args.command == "check":
    status = check.run(args, project)

if status is not None and status is not True:
    util.eprint("Encountered error")
    exit(1)
