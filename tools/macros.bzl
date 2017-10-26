ENABLE_WARN = True
VERBOSE = False

SHA_SUFFIX = ".sha512"

# TODO(eric.cousineau): If this is made into a Bazel external, we can specify a different
# `tool`.
# Downstream projects can call these as implementation methods, so that way they can fold
# in their own configurations / project sentinels.

def external_data(file, mode='normal'):
    """
    Macro for defining a large file.

    file: Name of the file to be downloaded.
    mode:
        'normal' - Use cached file if possible. Otherwise download the file.
        'devel' - Use local workspace (for development).
        'no_cache' - Download the file, do not use the cache.
    """

    # Cannot access environment for this file...
    # Use this?
    # https://docs.bazel.build/versions/master/skylark/lib/actions.html#run_shell
    # Nope. Only allows using existing PATH / LD_LIBRARY_PATH or not.
    # Would have to specify environment variables here, and would prefer to not need
    # this...

    if mode == 'devel':
        # TODO(eric.cousineau): It'd be nice if there is a way to (a) check if there is
        # a `*.sha512` file, and if so, (b) check the sha of the input file.
        if ENABLE_WARN:
            # TODO(eric.cousineau): Print full location of given file?
            print("\nexternal_data(file = '{}', mode = 'devel'):".format(file) +
                  "\n  Using local workspace file in development mode." +
                  "\n  Please upload this file and commit the *{} file.".format(SHA_SUFFIX))
        native.exports_files([file])
    elif mode in ['normal', 'no_cache']:
        name = "download_{}".format(file)
        sha_file = file + SHA_SUFFIX
        tool_name = "download"
        tool = "//tools/external_data:{}".format(tool_name)

        # Binary:
        cmd = "$(location {}) ".format(tool)
        # Argument: Ensure that we can permit relative paths.
        cmd += "--allow_relpath "
        # Argument: Caching.
        if mode == 'no_cache':
            cmd += "--no_cache "
        else:
            # Use symlinking to avoid needing to copy data to sandboxes.
            # The cache files are made read-only, so even if a test is run
            # with `--spawn_strategy=standalone`, there should be a permission error
            # when attempting to write to the file.
            cmd += "--symlink_from_cache "
        # Argument: SHA file or SHA.
        cmd += "$(location {}) ".format(sha_file)
        # Argument: Output file.
        cmd += "--output $@ "

        if VERBOSE:
            print("\nexternal_data(file = '{}', mode = '{}'):".format(file, mode) +
                  "\n  cmd: {}".format(cmd))

        native.genrule(
          name = name,
          srcs = [sha_file],
          outs = [file],
          cmd = cmd,
          tools = [tool],
          tags = ["external_data"],
          local = 1,  # Just changes `execroot`, but paths are still Bazel-fied.
          visibility = ["//visibility:public"],
        )
    else:
        fail("Invalid mode: {}".format(mode))


def external_data_group(name, files, files_devel = [], mode='normal'):
    """ @see external_data """
    if ENABLE_WARN and files_devel and mode == "devel":
        print('WARNING: You are specifying `files_devel` and `mode="devel"`, which is redundant. Try choosing one.')

    for file in files:
        if file not in files_devel:
            external_data(file, mode)
        else:
            external_data(file, "devel")

    # Consume leftover `files_devel`.
    devel_only = []
    for file in files_devel:
        if file not in files:
            devel_only.append(file)
            external_data(file, "devel")
    if devel_only:
        print("\nWARNING: The following `files_devel` files are not in `files`:\n" +
              "    {}\n".format("\n  ".join(devel_only)) +
              "  If you remove `files_devel`, then these files will not be part of the target.\n" +
              "  If you are using a `glob`, they may not have a corresponding *{} file\n".format(SHA_SUFFIX))

    all_files = files + devel_only
    native.filegroup(
        name = name,
        srcs = all_files,
    )


def strip_sha(sha_files):
    files = []
    for sha_file in sha_files:
        if not sha_file.endswith(SHA_SUFFIX):
            fail("SHA file does end with '{}': '{}'".format(SHA_SUFFIX, sha_file))
        file = sha_file[:-len(SHA_SUFFIX)]
        files.append(file)
    return files


# def external_data_sha_group(name, sha_files, **kwargs):
#     """ Enable globbing of *.sha512 files.
#     @see external_data """
#     external_data_group(
#         name = name,
#         files = strip_sha(sha_files),
#         **kwargs
#     )
