# Design

This package is designed to cater towards consuming large data files as tests (and general binaries) in Bazel.

Please see document "Girder Storage for Drake" (not publicly available) for more details on the general requirements.

# Implementation Goals

* Focus on Bazel, and having unittests work with very little work on the user's side (when no authentication is required).
* Keep the CLI interface functionality the same as Bazel's fetching.
    * e.g. Keep the file-based configuration *outside* of Bazel.
* Do not preclude the usage of `git annex` or `git lfs` as a frontend.
    * This means that the system would derive the hash (and the file's path relative to the frontend) from the frontend.
* Do not preclude the usage of `git lfs` (server-side API) as a backend.
* Enable internal *and* external PRs at some point.
    * Try to avoid the need for reference counting.
        * Do not implement a remote-side "prune" functionality. Leave that up to the frontend / backend combination.
            * Try to keep the hash-file frontend as simple as possible.
    * Enable remote overlays for a `"devel"` and `"master"` workflow.
        * This keeps the reference-counting issue at bay, and can allow access to `"master"` to be tightly locked down.
* Keep it easy to consume this package as a Bazel external.
    * Since the Girder backends depend on `girder_client`, keep this as *system* dependency, rather than try to bake it in as a Bazel workspace repository.
    * Bazel does provide [importing `pip` dependencies](https://github.com/bazelbuild/rules_python#importing-pip-dependencies), but it requires a chain of dependent `load` statements, which would make consuming this as an external kind of suck.
        * (There could be something like `external_data_workspace_phase{1,2,3,...}`, but blech.)
        * See [working prototype](https://github.com/EricCousineau-TRI/external_data_bazel/commit/db24e8ff5a21e54ab26f5d6c9da07207467efa10) (but without all downstream Bazel project tests working).
* Consider usage via `CMake/ExternalData`.
    * Project paths may not always be available for files.
    * Useful for `drake-shambhala`-type applications.
