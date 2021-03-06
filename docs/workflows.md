# Workflows

## Setup Project

To enable `external_data_bazel` in a Project:

1. Add the project configuration (see [Setup](./setup.md)) to the project, and the root package configuration.
2. Add `external_data_bazel` in your `WORKSPACE`.

    As an example:

        http_archive(
            name = "external_data_bazel_pkg",
            url = "https://github.com/EricCousineau-TRI/external_data_bazel/archive/ce71398ac319cf4dedcf3eed3ae5c2c25e4eb1b4.zip",
            sha256 = "9f3ade94ee039f99074809da920d55fe7202e01e4861e9e76f0a5e0c7db39eb0",
            strip_prefix = "external_data_bazel-ce71398ac319cf4dedcf3eed3ae5c2c25e4eb1b4",
        )


2. Expose the sentinel so that the CLI script can track things correctly when being run from within Bazel.

    As an example, in `${workspace}/BUILD`:

        filegroup(
            name = "external_data_sentinel",
            srcs = [':.external_data.project.yml'],
            visibility=["//:__subpackages__"],
        )

    Ensure that this sentinel is visible as `//:external_data_sentinel`.

3. Under `${workspace}/tools`:

    1. Add `BUILD` (to enable it as a package).

    2. Add `external_data.bzl`:

            # Pass through.
            load("@external_data_bazel_pkg//tools:macros.bzl",
                "external_data",
                "external_data_group",
                "get_original_files",
            )

    3. Add the CLI proxy script, `external_data` (and make it executable):

            #!/bin/bash
            set -e -u
            # Proxy to use Bazel binary, but with access to PWD.
            workspace_dir=$(cd $(dirname $0)/.. && pwd)
            bin_dir=${workspace_dir}/bazel-bin/external/external_data_bazel_pkg
            bin=${bin_dir}/cli
            # Build the binary if it does not exist.
            if [[ ! -f ${bin} ]]; then
                bazel build @external_data_bazel_pkg//:cli
            fi
            # Execute.
            ${bin} "$@"


## Start Drafting a Large File

Say you're in `:/data`, and want to author `dragon.obj` to be used in a Bazel
test.

1. In your package's `BUILD` file, ensure that you have loaded the appropriate macros:

        load("//tools:external_data.bzl",
            "external_data",
            "external_data_group",
            "get_original_files",
        )

1. Add a Bazel target for this file indicating that it's external data and that you're in the process of developing the file. In `:/data/BUILD`:

        external_data(
            file = "dragon.obj",
            mode = "devel",  # Delete once you've uploaded.
        )

    NOTE: Under the hood, this simply uses `exports_files(...)` in "devel" mode
    to make the file a proper target, using the same name. This is useful for later points in time, when you want to edit a file that has already been versioned.

2. Write a test, e.g. `://test:inspect_dragon`, that consumes this file:

        sh_test(
            name = "inspect_dragon",
            ...,
            args = ["data/dragon.obj"],
            data = ["//data:dragon.obj"],
            tags = ["external_data"],  # Specify so that we can discriminate.
        )

    Run the test to ensure it works as expected.


## Upload the File for Deployment

1. Run the `upload` script given the absolute path of the desired file:

        cd data
        touch dragon.obj
        ../tools/external_data upload ./dragon.obj

    If the file does not already exist on the desired server, this will upload the file. This will also update `dragon.obj.sha512` to reflect that the server-side information.

    NOTE: You may upload multiple files via the CLI interface.

2. Update `:/data/BUILD` to indicate that you're now using the uploaded version (this tells Bazel to expect `dragon.obj.sha512`):

        external_data(
            file = "dragon.obj",
        )

3. To test if Bazel can download this file, execute this in `:/data`:

        bazel build :dragon.obj

    This should have downloaded, cached, and exposed this file in Bazel's workspace.
    Now run `://test:inspect_dragon` (which should use Bazel's cached version) and ensure this works.

4. Now commit the `*.sha512` file in Git.


## Edit the File Later

Let's say you've removed `dragon.obj` from `:/data`, but a month later you wish to revise it. To update the file:

1. Delete and then download the corresponding hash file:

        cd data
        rm -f dragon.obj
        ../tools/external_data download ./dragon.obj.sha512

    **NOTE**: You may also run `../tools/external_data download ./dragon.obj`. It will recognize the intended object.

2. Change `:/data/BUILD` back to development mode:

        external_data(
            file = "dragon.obj",
            mode = "devel",  # Add this line back in.
        )

3. Make the appropriate changes.

4. Follow the steps in "Upload the File for Deployment".

## Use `*.sha512` groups in `BUILD`

For groups of large data files, you could specify individual Bazel `external_data` targets, or explicitly list the files in  `external_data_group`.

However, if you have a large set of `*.${ext}.sha512` files, it may be easier to use the workspace's directory structure to glob these files. (You cannot reliably use `*.${ext}` without the suffix because these files would not exist normally.)

As an example in `:/data`:

    external_data_group(
        name = "meshes",
        files = get_original_files(
            glob(['**/*.obj.sha512'])
        ),
    )

You may now use `:meshes` in tests to get all of these files.

If you wish to expose all of these files within the Bazel build sandbox, you may execute:

    bazel build :meshes

NOTE: This interface will cache the files under the cache directory specified in your user configuration, and thus you will not need to re-download these files.


## Edit Files in a `*.sha512` group

You may also use `mode = "devel"` in `external_data_group` if you wish to edit *all* of the files. If you do want this, you *must* have all of the files available in your workspace. (See "Download a Set of Files".)

If you want to edit a certain file in a group, you may use
`external_data_group(..., files_devel = ...)`. As an example:

    external_data_group(
        name = "meshes_nondevel",
        files = get_original_files(
            glob(['**/*.obj.sha512'])
        ),
        files_devel = ['robot/to_edit.obj'],
    )

**NOTE**: You can extend this to use an `*.obj` files in the workspace to assume that they are to be consumed directly:

    external_data_group(
        name = "meshes_nondevel",
        files = get_original_files(
            glob(['**/*.obj.sha512'])
        ),
        files_devel = glob(['**/*.obj']),
    )

This means that Bazel will automatically switch to using your local file, rather than use its own internal version. *Please use caution* when updating your branches.

## Download a Set of Files

If you wish to download *all* files of a given extension at the specified revision under a certain directory, you may use `find`. For example:

    find . -name '*.obj.sha512' | ./tools/external_data:download

For each `${file}.sha512` that is found, the file will be downloaded to `${file}`.

NOTE: This will fail if one of the outputs already exists; you must specify `--force` to enable overwriting.

As above, these files are cached.


## Download One File to a Specific Location

This is used in Bazel via `macros.bzl`:

    ./tools/external_data download ${file}.sha512 --output ${file}


## Download Files and Expose as Symlinks (No Copy)

If you just need easy read-only access to files (and don't want to deal with Bazel's paths), you can use `--symlink`:

    ./tools/external_data download --symlink *.sha512


## Integrity Checks

Note that just downloading the files may not check if the file is still available on the remote.
If you wish to ensure that other users can reproduce your results, consider `check`'ing your files:

    find . -name '*.sha512' | xargs ./tools/external_data check

This will ensure that the correct file is stored on the remote, regardless of what is stored in the cache.

You may run these tests in Bazel:

    bazel test --test_tag_filters=external_data_check_test ...

This will check all external data tests in the current package and its subpackages.

*   Warning: All `external_data` tests are marked as `external`, thus the Bazel test results won't be cached, and the test (potentially downloading and checking a file) will *always* be run. Consider excluding this from tests that are normally run.
