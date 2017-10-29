#!/usr/bin/env python

# @note This does not use `girder_client`, to minimize dependencies.
# @see util.py for more notes.

from __future__ import absolute_import, print_function
import sys
import os
import argparse

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
parser.add_argument('--check_file', action='store_true',
                    help='Will check if the remote (or its overlays) has a desired file, ignoring the cache. For integrity checks.')
parser.add_argument('--remote', type=str, default=None,
                    help='Configuration defining a custom override remote. Useful for direct, single-file downloads.')
parser.add_argument('--debug_config', action='store_true',
                    help='Dump configuration output for the project / file. WARNING: Will print out information in user configuration (e.g. keys) as well!')
parser.add_argument('--debug_remote', action='store_true',
                    help='Dump configuration for the chain of scopes and remotes for the files.')
parser.add_argument('sha_files', type=str, nargs='+',
                    help='Files containing the SHA-512 of the desired contents. If --output is not provided, the output destination is inferred from the input path.')

args = parser.parse_args()

from bazel_external_data import util

SHA_SUFFIX = util.SHA_SUFFIX

def do_download(project, sha_file, output_file, remote_in=None):
    if not args.allow_relpath:
        # Ensure that we have absolute file paths.
        files = [sha_file, output_file]
        if not all(map(os.path.isabs, files)):
            raise RuntimeError("Must specify absolute paths:\n  {}".format("\n".join(files)))

    # Ensure that we do not overwrite existing files.
    if os.path.isfile(output_file):
        if args.force:
            os.remove(output_file)
        else:
            raise RuntimeError("Output file already exists: {}".format(output_file) + "\n  (Use `--keep_going` to ignore or `--force` to overwrite.)")

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

    if args.debug_remote:
        project.debug_dump_remote(remote, sys.stdout)

    if args.check_file:
        if not remote.has_file(sha):
            raise RuntimeError("Remote does not have '{}' ({})".format(sha_file, sha))

    remote.download_file(sha, output_file,
                         use_cache=use_cache,
                         symlink_from_cache=args.symlink_from_cache)

util.eprint("Pwd: {}".format(os.getcwd()))

project = util.load_project(os.getcwd())
if args.debug_config:
    project.debug_dump_config(sys.stdout)

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
            except Exception as e:
                util.eprint(e)
                util.eprint("Continuing (--keep_going).")
        else:
            action()
