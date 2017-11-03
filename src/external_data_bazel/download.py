from __future__ import absolute_import, print_function
import sys
import os
import yaml
import argparse

from external_data_bazel import base, util, config_helpers

HASH_SUFFIX = base.HASH_SUFFIX

# TODO(eric.cousineau): Make a `--quick` option to ignore checking SHAs, if the files are really large.

def add_arguments(parser):
    # TODO(eric.cousineau): Consider making this interpret inputs/outputs as pairs.
    parser.add_argument('-o', '--output', dest='output_file', type=str,
                        help='Output destination. If specified, only one input file may be provided.')
    parser.add_argument('hash_files', type=str, nargs='+',
                        help='Files containing the SHA-512 of the desired contents. If --output is not provided, the output destination is inferred from the input path.')

    parser.add_argument('-f', '--force', action='store_true',
                        help='Overwrite existing output file.')

    parser.add_argument('--no_cache', action='store_true',
                        help='Always download, and do not cache the result.')
    parser.add_argument('--symlink', action='store_true',
                        help='Use a symlink from the cache rather than copying the file.')
    parser.add_argument('--check_file', choices=['none', 'only', 'extra'], default='none',
                        help='Will check if the remote (or its overlays) has a desired file, ignoring the cache. For integrity checks. '
                             + 'If "only", it will only check that the file exists, and move on. If "extra", it will check, then still fetch the file as normal.')

def run(args, project, remote_in):
    if args.output_file:
        if len(args.hash_files) != 1:
            raise RuntimeError("Can only specify one input file with --output")
        do_download(args, project, args.hash_files[0], args.output_file, remote_in=remote_in)
    else:
        for hash_file in args.hash_files:
            output_file = hash_file[:-len(HASH_SUFFIX)]
            def action():
                do_download(args, project, hash_file, output_file, remote_in=remote_in)
            if args.keep_going:
                try:
                    action()
                except RuntimeError as e:
                    util.eprint(e)
                    util.eprint("Continuing (--keep_going).")
            else:
                action()


def do_download(args, project, hash_file, output_file, remote_in=None):
    # Ensure that we have absolute file paths.
    hash_file = os.path.abspath(hash_file)
    output_file = os.path.abspath(output_file)

    # Get project-relative path. (This will assert if the file is
    # not part of this project).
    project_relpath = project.get_canonical_path(base.strip_hash(hash_file))

    # Get the hash.
    if not os.path.isfile(hash_file):
        raise RuntimeError("ERROR: File not found: {}".format(hash_file))
    if not hash_file.endswith(HASH_SUFFIX):
        raise RuntimeError("ERROR: File does not end with '{}': '{}'".format(HASH_SUFFIX, hash_file))
    hash = util.subshell("cat {}".format(hash_file))
    use_cache = not args.no_cache

    # Common arguments for `format`.
    if remote_in is None:
        remote = project.load_remote(hash_file)
    else:
        remote = remote_in

    def dump_remote_config():
        dump = [{
            "file": project.get_relpath(hash_file),
            "remote": project.debug_dump_remote_config(remote),
        }]
        yaml.dump(dump, sys.stdout, default_flow_style=False)

    if args.verbose:
        dump_remote_config()

    if args.check_file != 'none':
        if not remote.has_file(hash, project_relpath):
            if not args.verbose:
                dump_remote_config()
            raise RuntimeError("Remote does not have '{}' ({})".format(hash_file, hash))
        if args.check_file == 'only':
            # Skip fetching the file.
            return

    # Ensure that we do not overwrite existing files.
    if os.path.isfile(output_file):
        if args.force:
            os.remove(output_file)
        else:
            raise RuntimeError("Output file already exists: {}".format(output_file) + "\n  (Use `--keep_going` to ignore or `--force` to overwrite.)")

    download_type = remote.download_file(
        hash, project_relpath, output_file,
        use_cache=use_cache,
        symlink=args.symlink)
