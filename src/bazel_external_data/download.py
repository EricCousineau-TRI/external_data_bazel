#!/usr/bin/env python

# @note This does not use `girder_client`, to minimize dependencies.
# @see util.py for more notes.

from __future__ import absolute_import, print_function
import sys
import os
import argparse

assert __name__ == '__main__'

# TODO(eric.cousineau): Make a `--quick` option to ignore checking SHA-512s, if the files are really large.

# TODO(eric.cousineau): Allow this to handle multiple files to download. Add a `--batch` argument, that will infer
# the output paths.

# TODO(eric.cousineau): Ensure that we do not need immediate authentication in configuration, e.g. when in road warrior mode.

parser = argparse.ArgumentParser()
parser.add_argument('--no_cache', action='store_true',
                    help='Always download, and do not cache the result.')
parser.add_argument('--symlink_from_cache', action='store_true',
                    help='Use a symlink from the cache rather than copying the file.')
parser.add_argument('--allow_relpath', action='store_true',
                    help='Permit relative paths. Having this on by default makes using Bazel simpler.')
parser.add_argument('-f', '--force', action='store_true',
                    help='Overwrite existing output file if it already exists.')
parser.add_argument('-o', '--output', dest='output_file', type=str,
                    help='Output destination. If specified, only one input file may be provided.')
parser.add_argument('--remote', type=str, default=None,
                    help='Configuration defining a custom override remote. Useful for direct, single-file downloads.')
parser.add_argument('sha_files', type=str, nargs='+',
                    help='Files containing the SHA-512 of the desired contents. If --output is not provided, the output destination is inferred from the input path.')

args = parser.parse_args()

# Hack to permit running from command-line easily.
# TODO(eric.cousineau): Require that this is only run from Bazel.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from bazel_external_data import util

SHA_SUFFIX = util.SHA_SUFFIX

def do_download(project, output_file, sha_file, remote_in=None):
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
            raise RuntimeError("Output file already exists (use `--force` to overwrite): {}".format(output_file))

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
    remote.download_file(sha, output_file,
                         use_cache=use_cache,
                         symlink_from_cache=args.symlink_from_cache)

project = util.load_project(os.getcwd())
project.debug_dump_config(sys.stdout)

remote_in = None
if args.remote:
    remote_config = yaml.load(args.remote)
    remote_in = util.Remote(project, 'command_line', remote_config)

if args.output_file:
    if len(args.sha_files) != 1:
        raise RuntimeError("Can only specify one input file with --output")
    do_download(project, output_file=args.output_file, sha_file=args.sha_files[0], remote_in=remote_in)
else:
    for sha_file in args.sha_files:
        output_file = sha_file[:-len(SHA_SUFFIX)]
        do_download(project, output_file=output_file, sha_file=sha_file, remote_in=remote_in)
