# Testing

Relevant workflow tests are located in `test/`.

To run *all* tests, execute `test/run_tests.sh`.

General tests, under `test/...`:

* `basic_workflows_test.sh` - Tests general workflows (covered in [Workflows](./workflows.md), using `bazel_pkg_advanced_test`.
* `bazel_pkg_test` - An very simple example Bazel package which consumes `bazel_external_data` (via `local_repository`).
    * *WARNING*: The remote is configured for a single file for simplicity. Consider replacing this.
* `bazel_pkg_downstream_test` - A Bazel package that consumes `bazel_pkg_test`, and can access its files that are generated from `external_data`.
* `bazel_pkg_advanced_test` - Extended example, which uses custom configurations for (a) user config, (b) Bazel config (`settings`), and (c) setup conig (`external_data_config.py`).
    * This has Mock storage mechanisms with persistent upload directories (located in `/tmp`.
* `cmake_pkg_test` - An attempt to have `CMake/ExternalData` use `bazel_external_data` - Presently does not work, not sure why...
* `backends` - Backend-specific tests.

## Backends

### Girder

In `test/backends/girder`:
`./run_tests.sh` will configure and spin up Docker containers for (a) a simple Girder test server (with MongoDB set up) and (b) a client to consume data from this server, using the default user configuration and Girder authentication.

This will leverage the current source tree of `bazel_external_data` to run the tests.

If you wish to use this server locally, you may tell the test to run, but to not shutdown (or auto-remove) the container:

    ./test/backends/girder/run_tests.sh [--no-stop] [--no-rm]

To run code within the client (after having run the test), you may run:

    client="<name or id of client container>"
    docker exec -it ${client} bash

This will bring you to a `bash` terminal.

Alternatively, you can just use `localhost:8080` on your host machine, and work with the data there.
