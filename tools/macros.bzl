SETTINGS_DEFAULT = dict(
    # Warn if in development mode (e.g. if files will be lost when pushing).
    enable_warn = True,
    # Verbosity: Will dump configuration, including user information (e.g. API keys!).
    verbose = False,
    # Check file: Rather than just relying on the cache, this will check that the file
    # actually exists in the given remote. This is an integrity check.
    check_file = False,
    # Extra data. Generally, this is just the sentinel data (so we can detect the project
    # root). However, any custom configuration modules can be included here as well.
    # WARNING: The sentinel MUST be placed next to the workspace root. Logic for non-workspace
    # root files is too complex (and useless).
    extra_data = ["//:external_data_sentinel"],
    # Extra arguments to `cli`. Namely for `--user_config` for mock testing, but can
    # be changed.
    extra_args = "",
)


SHA_SUFFIX = ".sha512"
PACKAGE_CONFIG_FILE = ".external_data.yml"


def external_data(file, mode='normal', url=None, visibility=None,
                  settings=SETTINGS_DEFAULT):
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
    settings:
        Settings for the given repository (or even individual target).
        @see SETTINGS_DEFAULT.
    """
    # Overlay.
    # TODO: Check for invalid settings?
    settings = SETTINGS_DEFAULT + settings

    if mode == 'devel':
        # TODO(eric.cousineau): It'd be nice if there is a way to (a) check if there is
        # a `*.sha512` file, and if so, (b) check the hash of the input file.
        if settings['enable_warn']:
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
        tool = "@external_data_bazel_pkg//:cli"

        # Binary:
        cmd = "$(location {}) ".format(tool)
        # Argument: Verbosity.
        if settings['verbose']:
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
        extra_args = settings['extra_args']
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
            cmd += "--symlink "
        # Argument: SHA file or SHA.
        cmd += "$(location {}) ".format(sha_file)
        # Argument: Output file.
        cmd += "--output $@ "
        if settings['check_file']:
            cmd += "--check_file=extra "

        if settings['verbose']:
            print("\nexternal_data(file = '{}', mode = '{}'):".format(file, mode) +
                  "\n  cmd: {}".format(cmd))

        extra_data = settings['extra_data']

        # package_config_files = _find_package_config_files(sha_file)
        # NOTE: This above can include glob-visibile sub-package config files.
        # HOWEVER, this would not include parent files, so we would have to either
        # (a) explicitly declare those files or (b) keep the odd root_alternatives setup.
        # (b) is simpler, and does not matter since dirtiness should be due to hash
        # changing, not the remote changing.
        # Example: In package "x", sha_file = "a/test.bin.sha512" *could* find
        # ["//x:.config_file", "//x/a:.config_file"].
        # However, it would NOT find ["//:.config_file"].

        native.genrule(
            name = name,
            srcs = [sha_file] + extra_data,
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


def external_data_group(name, files, files_devel = [], mode='normal', visibility=None,
                        settings=SETTINGS_DEFAULT):
    """ @see external_data """

    # Overlay.
    settings = SETTINGS_DEFAULT + settings

    if settings['enable_warn'] and files_devel and mode == "devel":
        print('WARNING: You are specifying `files_devel` and `mode="devel"`, which is redundant. Try choosing one.')

    kwargs = {'visibility': visibility, 'settings': settings}

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
    if settings['enable_warn'] and devel_only:
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


def _find_package_config_files(filepath):
    # TODO(eric.cousineau): This may get expensive... Is there a way to specify this more simply???
    # Or even more consistently???
    sep = '/'
    pieces = filepath.split(sep)
    test_files = []
    for i in range(len(pieces)):
        test_file = sep.join(pieces[0:i] + [PACKAGE_CONFIG_FILE])
        test_files.append(test_file)
    files = native.glob(test_files)
    return files
