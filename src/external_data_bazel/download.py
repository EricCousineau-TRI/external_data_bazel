from __future__ import absolute_import, print_function
import sys
import os
import yaml
import argparse

from external_data_bazel import core, util, config_helpers

HASH_SUFFIX = core.HASH_SUFFIX

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

def run(args, project):
    good = True
    if args.output_file:
        if len(args.hash_files) != 1:
            raise RuntimeError("Can only specify one input file with --output")
        do_download(args, project, args.hash_files[0], args.output_file)
    else:
        for hash_file in args.hash_files:
            output_file = hash_file[:-len(HASH_SUFFIX)]
            def action():
                do_download(args, project, hash_file, output_file)
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


def do_download(args, project, hash_file, output_file):
    # Ensure that we have absolute file paths.
    hash_file = os.path.abspath(hash_file)
    output_file = os.path.abspath(output_file)

    # Get project-relative path. (This will assert if the file is
    # not part of this project).
    project_relpath = project.get_relpath(core.strip_hash(hash_file))

    # Get the hash.
    if not os.path.isfile(hash_file):
        raise RuntimeError("ERROR: File not found: {}".format(hash_file))
    if not hash_file.endswith(HASH_SUFFIX):
        raise RuntimeError("ERROR: File does not end with '{}': '{}'".format(HASH_SUFFIX, hash_file))
    hash = util.subshell("cat {}".format(hash_file))
    use_cache = not args.no_cache

    remote = project.load_remote(project_relpath)

    def dump_remote_config():
        dump = [{
            "file": project.get_relpath(hash_file),
            "remote": project.debug_dump_remote_config(remote),
        }]
        yaml.dump(dump, sys.stdout, default_flow_style=False)

    if args.verbose:
        dump_remote_config()

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
