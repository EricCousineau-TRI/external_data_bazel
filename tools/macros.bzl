SETTINGS_DEFAULT = struct(
    ENABLE_WARN = True,
    VERBOSE = False,
    CHECK_FILE = False,
    EXTRA_ARGS = "",
)

SHA_SUFFIX = ".sha512"
PACKAGE_CONFIG_FILE = ".external_data.package.yml"
SENTINEL_DEFAULT = "//:external_data_sentinel"

# TODO(eric.cousineau): If this is made into a Bazel external, we can specify a different
# `tool`.
# Downstream projects can call these as implementation methods, so that way they can fold
# in their own configurations / project sentinels.

def external_data(file, mode='normal', url=None, visibility=None, settings=SETTINGS_DEFAULT,
                  sentinel=SENTINEL_DEFAULT,
                  data = []):
    """
    Macro for defining a large file.

    file: Name of the file to be downloaded.
    mode:
        'normal' - Use cached file if possible. Otherwise download the file.
        'devel' - Use local workspace (for development).
        'no_cache' - Download the file, do not use the cache.
    url:
        If this is just a file that `curl` can fetch, specify this URL.
        If `None`, this will use the `.bazel_external_project` configuration files to]
        determine how to fetch the file.
    data:
        Any additional data needed to execute the download command (e.g. configuration files).
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
        if settings.ENABLE_WARN:
            # TODO(eric.cousineau): Print full location of given file?
            print("\nexternal_data(file = '{}', mode = 'devel'):".format(file) +
                  "\n  Using local workspace file in development mode." +
                  "\n  Please upload this file and commit the *{} file.".format(SHA_SUFFIX))
        native.exports_files(
            srcs = [file],
            visibility = visibility,
        )
    elif mode in ['normal', 'no_cache']:
        name = "{}__download".format(file)
        sha_file = file + SHA_SUFFIX
        tool = "@org_drake_bazel_external_data//:cli"

        # Binary:
        cmd = "$(location {}) ".format(tool)
        # Argument: Verbosity.
        if settings.VERBOSE:
            cmd += "--verbose "
        # Argument: Project root. Guess from the input file rather than PWD, so that a file could
        # consumed by a downstream Bazel project.
        # (Otherwise, PWD will point to downstream project, which will make a conflict.)
        cmd += "--project_root_guess=$(location {}) ".format(sha_file)
        # Argument: Specific URL.
        if url:
            # TODO(eric.cousineau): Consider removing this, and keeping all config in files.
            cmd += "--remote='{{backend: url, url: \"{}\"}}' ".format(url)
        # Extra Arguments (for project settings).
        extra_args = getattr(settings, 'EXTRA_ARGS', None)
        if extra_args:
            cmd += extra_args + " "
        # Subcommand: Download.
        cmd += "download "
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
        if settings.CHECK_FILE:
            cmd += "--check_file=extra "

        if settings.VERBOSE:
            print("\nexternal_data(file = '{}', mode = '{}'):".format(file, mode) +
                  "\n  cmd: {}".format(cmd))

        # TODO: Presently, this could be set to `glob([PACKAGE_CONFIG_FILE])`; however, this would not include sub-package
        # directories. Example: sha_file = "test.bin.sha512" will find the appropriate file, but
        # sha_file = "a/b/c/test.bin.sha512" will not also search {"a/", "a/b/", "a/b/c/"}.
        package_data = [
            sentinel,
        ]

        native.genrule(
            name = name,
            srcs = [sha_file] + data + package_data,
            outs = [file],
            cmd = cmd,
            tools = [tool],
            tags = ["external_data"],
            # Changes `execroot`, and symlinks the files that we need to crawl the directory
            # structure and get hierarchical packages.
            local = 1,
            visibility = visibility,
        )
    else:
        fail("Invalid mode: {}".format(mode))


def external_data_group(name, files, files_devel = [], mode='normal', visibility=None, settings=SETTINGS_DEFAULT,
                        sentinel=SENTINEL_DEFAULT,
                        data = []):
    """ @see external_data """

    if settings.ENABLE_WARN and files_devel and mode == "devel":
        print('WARNING: You are specifying `files_devel` and `mode="devel"`, which is redundant. Try choosing one.')

    kwargs = {'sentinel': sentinel, 'visibility': visibility, 'settings': settings, 'data': data}

    for file in files:
        if file not in files_devel:
            external_data(file, mode, **kwargs)
        else:
            external_data(file, "devel", **kwargs)

    # Consume leftover `files_devel`.
    devel_only = []
    for file in files_devel:
        if file not in files:
            devel_only.append(file)
            external_data(file, "devel", **kwargs)
    if settings.ENABLE_WARN and devel_only:
        print("\nWARNING: The following `files_devel` files are not in `files`:\n" +
              "    {}\n".format("\n  ".join(devel_only)) +
              "  If you remove `files_devel`, then these files will not be part of the target.\n" +
              "  If you are using a `glob`, they may not have a corresponding *{} file\n".format(SHA_SUFFIX))

    all_files = files + devel_only
    native.filegroup(
        name = name,
        srcs = all_files,
    )


def get_original_files(sha_files):
    files = []
    for sha_file in sha_files:
        if not sha_file.endswith(SHA_SUFFIX):
            fail("SHA file does end with '{}': '{}'".format(SHA_SUFFIX, sha_file))
        file = sha_file[:-len(SHA_SUFFIX)]
        files.append(file)
    return files
