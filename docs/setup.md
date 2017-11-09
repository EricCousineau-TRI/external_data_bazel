# Setup

## Prerequisites

For a client, you must have `curl` and a few other dependencies installed.

Please see [`client_prereqs.sh`](../test/backends/girder/docker/client_prereqs.sh) for `apt` packages.

**NOTE**: This is a subset fo 

### Girder

Please ensure that you have `girder_client` available. You may install this via `pip`:

    pip install girder-client

Consider using `virtualenv`:

    dir=/path/to/directory
    virtualenv ${dir}
    source ${dir}/bin/activate
    pip ...

## Configuration

* Inspect the configuration examples in `./config`. The files you will have:
    * `~/.config/external_data_bazel/config.yml` - User configuration (global cache, backend-specific authentication - NOT to be versioned!).
        * Default values will be used if this file does not exist or define them.
    * `${project_root}/.external_data.project.yml` - Project configuration.
    * `${package_root}/.external_data.yml` - Package configuration. You will need one adjacent to the project root.

