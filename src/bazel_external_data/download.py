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
parser.add_argument('sha_files', type=str, nargs='+',
                    help='Files containing the SHA-512 of the desired contents. If --output is not provided, the output destination is inferred from the input path.')

args = parser.parse_args()

# Hack to permit running from command-line easily.
# TODO(eric.cousineau): Require that this is only run from Bazel.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from external_data import util

project_root = util.find_project_root(os.getcwd())
# Get configuration.
conf = util.Config(project_root, mode='download')

SHA_SUFFIX = '.sha512'

def do_download(pair):
    if not args.allow_relpath:
        # Ensure that we have absolute file paths.
        files = [pair.sha_file, pair.output_file]
        if not all(map(os.path.isabs, files)):
            raise RuntimeError("Must specify absolute paths:\n  {}".format("\n".join(files)))

    # Ensure that we do not overwrite existing files.
    if os.path.isfile(pair.output_file):
        if args.force:
            os.remove(pair.output_file)
        else:
            raise RuntimeError("Output file already exists (use `--force` to overwrite): {}".format(pair.output_file))

    # Get the sha.
    if not os.path.isfile(pair.sha_file):
        raise RuntimeError("ERROR: File not found: {}".format(pair.sha_file))
    if not pair.sha_file.endswith(SHA_SUFFIX):
        raise RuntimeError("ERROR: File does not end with '{}': '{}'".format(SHA_SUFFIX, pair.sha_file))
    sha = util.subshell("cat {}".format(pair.sha_file))
    use_cache = not args.no_cache

    # Common arguments for `format`.
    d = dict(conf=conf, pair=pair, sha=sha)

    def check_sha(throw_on_error=True):
        # Test the SHA.
        out = util.runc("sha512sum -c --status", input="{sha} {pair.output_file}".format(**d))
        if out[0] != 0 and throw_on_error:
            raise RuntimeError("SHA-512 mismatch")
        return out[0]

    def get_cached(skip_sha=False):
        # Can use cache. Copy to output path.
        if args.symlink_from_cache:
            util.subshell(['ln', '-s', cache_path, pair.output_file])
        else:
            util.subshell(['cp', cache_path, pair.output_file])
            util.subshell(['chmod', '+w', pair.output_file])
        # TODO(eric.cousineau): On error, remove cached file, and re-download.
        if check_sha(throw_on_error=False) != 0:
            util.eprint("SHA-512 mismatch. Removing old cached file, re-downloading.")
            # `os.remove()` will remove read-only files, reguardless.
            os.remove(cache_path)
            if os.path.islink(pair.output_file):
                # In this situation, the cache was corrupted (somehow), and Bazel
                # triggered a recompilation, and we still have a symlink in Bazel-space.
                # Remove this symlink, so that we do not download into a symlink (which
                # complicates the logic in `get_download_and_cache`). This also allows
                # us to "reset" permissions.
                os.remove(pair.output_file)
            get_download_and_cache()

    def get_download(output_file):
        # Defer authentication so that we can use only the cache if necessary.
        conf.authenticate_if_needed()
        # TODO: Pipe progress bar and file name to stderr.
        util.subshell((
            'curl -L --progress-bar -H "Girder-Token: {conf.token}" ' +
            '-o {output_file} -O {conf.api_url}/file/hashsum/sha512/{sha}/download'
        ).format(output_file=output_file, **d))
        check_sha()

    def get_download_and_cache():
        with util.FileWriteLock(cache_path):
            get_download(cache_path)
            # Make cache file read-only.
            util.subshell(['chmod', '-w', cache_path])
        # Use cached file - `get_download()` has already checked the sha.
        get_cached(skip_sha=True)

    # Check if we need to download.
    if use_cache:
        cache_path = util.get_sha_cache_path(conf, sha, create_dir=True)

        util.wait_file_read_lock(cache_path)
        if os.path.isfile(cache_path):
            print("Using cached file")
            get_cached()
        else:
            get_download_and_cache()
    else:
        get_download(pair.output_file)


if args.output_file:
    if len(args.sha_files) != 1:
        raise RuntimeError("Can only specify one input file with --output")
    pair = util.Bunch(output_file=args.output_file, sha_file=args.sha_files[0])
    do_download(pair)
else:
    for sha_file in args.sha_files:
        output_file = sha_file[:-len(SHA_SUFFIX)]
        pair = util.Bunch(output_file=output_file, sha_file=sha_file)
        do_download(pair)
