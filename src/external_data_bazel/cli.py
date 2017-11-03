#!/usr/bin/env python

import sys
import os
import yaml
import argparse

from external_data_bazel import core, util, config_helpers
from external_data_bazel import download, upload

assert __name__ == '__main__'

if util.in_bazel_runfiles():
    util.eprint("ERROR: Do not run this command via `bazel run`.")
    exit(1)

parser = argparse.ArgumentParser()
parser.add_argument('--project_root_guess', type=str, default='.',
                    help='File path to guess the project root.')
parser.add_argument('--user_config', type=str, default=None,
                    help='Override user configuration (useful for testing).')
parser.add_argument('-k', '--keep_going', action='store_true',
                    help='Attempt to keep going.')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='Dump configuration and show command-line arguments. WARNING: Will print out information in user configuration (e.g. keys) as well!')
parser.add_argument('--remote', type=str, default=None,
                    help='Configuration defining a custom override remote. Useful for direct, single-file downloads.')

# Credit here: https://stackoverflow.com/a/10913734/7829525
subparsers = parser.add_subparsers(dest="command")

download_parser = subparsers.add_parser("download")
download.add_arguments(download_parser)

upload_parser = subparsers.add_parser("upload")
upload.add_arguments(upload_parser)

args = parser.parse_args()

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

remote_in = None
if args.remote:
    remote_config = yaml.load(args.remote)
    remote_in = project.load_remote_command_line(remote_config)

# Execute command.
if args.command == 'download':
    download.run(args, project, remote_in)
elif args.command == 'upload':
    upload.run(args, project, remote_in)
