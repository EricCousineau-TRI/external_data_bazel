# WARNING

This is a prototype, and the API / documentation has not yet stablized.
Additionally, the present commits will be rebased, so Git history will not be
connected.

Please do not use this yet.

# About

This is a Bazel-centric implementation for incorporating external data into the workspace (not to be versioned in Git, etc.) for testing and running binaries.
This design is based on Kitware's [CMake/ExternalData](https://blog.kitware.com/cmake-externaldata-using-large-files-with-distributed-version-control/) module, with the implementation based on [this demo repository](https://github.com/jcfr/bazel-large-files-with-girder).

Please see the [Design](docs/DESIGN.md) documentation for more information about the design goals.

# How do I use this?

Please see the [Workflows](docs/WORKFLOWS.md) documentation.
