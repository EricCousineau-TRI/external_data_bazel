#!/usr/bin/env python

# @note This does not use `girder_client`, to minimize dependencies.
# @see util.py for more notes.

from __future__ import absolute_import, print_function
import sys
import os
import yaml
import argparse

from bazel_external_data import base, util

assert __name__ == '__main__'

# TODO(eric.cousineau): Make a `--quick` option to ignore checking SHA-512s, if the files are really large.

parser = argparse.ArgumentParser()
# TODO(eric.cousineau): Consider making this interpret inputs/outputs as pairs.
parser.add_argument('-o', '--output', dest='output_file', type=str,
                    help='Output destination. If specified, only one input file may be provided.')
parser.add_argument('-k', '--keep_going', action='store_true',
                    help='Attempt to keep going.')
parser.add_argument('-f', '--force', action='store_true',
                    help='Overwrite existing output file.')
parser.add_argument('--no_cache', action='store_true',
                    help='Always download, and do not cache the result.')
parser.add_argument('--symlink_from_cache', action='store_true',
                    help='Use a symlink from the cache rather than copying the file.')
parser.add_argument('--allow_relpath', action='store_true',
                    help='Permit relative paths. Having this on by default makes using Bazel simpler.')
parser.add_argument('--check_file', choices=['none', 'only', 'extra'], default='none',
                    help='Will check if the remote (or its overlays) has a desired file, ignoring the cache. For integrity checks. '
                         + 'If "only", it will only check that the file exists, and move on. If "extra", it will check, then still fetch the file as normal.')
parser.add_argument('--remote', type=str, default=None,
                    help='Configuration defining a custom override remote. Useful for direct, single-file downloads.')
parser.add_argument('--debug_project_config', action='store_true',
                    help='Dump configuration output for the project.')
parser.add_argument('--debug_user_config', action='store_true',
                    help='Dump configuration output for user configuration files. WARNING: Will print out information in user configuration (e.g. keys) as well!')
parser.add_argument('--debug_remote_config', action='store_true',
                    help='Dump configuration for the remotes used for the each file.')
parser.add_argument('sha_files', type=str, nargs='+',
                    help='Files containing the SHA-512 of the desired contents. If --output is not provided, the output destination is inferred from the input path.')

args = parser.parse_args()

SHA_SUFFIX = base.SHA_SUFFIX

def do_download(project, sha_file, output_file, remote_in=None):
    # Ensure that we have absolute file paths.
    if not args.allow_relpath:
        files = [sha_file, output_file]
        if not all(map(os.path.isabs, files)):
            raise RuntimeError("Must specify absolute paths:\n  {}".format("\n".join(files)))
    else:
        sha_file = os.path.abspath(sha_file)
        output_file = os.path.abspath(output_file)

    # Get the sha.
    if not os.path.isfile(sha_file):
        raise RuntimeError("ERROR: File not found: {}".format(sha_file))
    if not sha_file.endswith(SHA_SUFFIX):
        raise RuntimeError("ERROR: File does not end with '{}': '{}'".format(SHA_SUFFIX, sha_file))
    sha = util.subshell("cat {}".format(sha_file))
    use_cache = not args.no_cache

    # Common arguments for `format`.
    if remote_in is None:
        remote = project.load_remote(sha_file)
    else:
        remote = remote_in

    def dump_remote_config():
        dump = [{
            "file": project.get_relpath(sha_file),
            "remote": project.debug_dump_remote(remote),
        }]
        yaml.dump(dump, sys.stdout, default_flow_style=False)

    if args.debug_remote_config:
        dump_remote_config()

    if args.check_file != 'none':
        if not remote.has_file(sha):
            if not args.debug_remote_config:
                dump_remote_config()
            raise RuntimeError("Remote does not have '{}' ({})".format(sha_file, sha))
        if args.check_file == 'only':
            # Skip fetching the file.
            return

    # Ensure that we do not overwrite existing files.
    if os.path.isfile(output_file):
        if args.force:
            os.remove(output_file)
        else:
            raise RuntimeError("Output file already exists: {}".format(output_file) + "\n  (Use `--keep_going` to ignore or `--force` to overwrite.)")

    remote.download_file(sha, output_file,
                         use_cache=use_cache,
                         symlink_from_cache=args.symlink_from_cache)

project = base.load_project(os.getcwd())
if args.debug_user_config:
    yaml.dump({"user_config": project.debug_dump_user_config()}, sys.stdout, default_flow_style=False)
if args.debug_project_config:
    yaml.dump({"project_config": project.debug_dump_config()}, sys.stdout, default_flow_style=False)

remote_in = None
if args.remote:
    remote_config = yaml.load(args.remote)
    remote_in = project.load_remote_command_line(remote_config)

if args.output_file:
    if len(args.sha_files) != 1:
        raise RuntimeError("Can only specify one input file with --output")
    do_download(project, args.sha_files[0], args.output_file, remote_in=remote_in)
else:
    for sha_file in args.sha_files:
        output_file = sha_file[:-len(SHA_SUFFIX)]
        def action():
            do_download(project, sha_file, output_file, remote_in=remote_in)
        if args.keep_going:
            try:
                action()
            except RuntimeError as e:
                util.eprint(e)
                util.eprint("Continuing (--keep_going).")
        else:
            action()
