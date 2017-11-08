# Can't name it `external_data_bazel` due to Python package clashes.
# @ref https://github.com/bazelbuild/bazel/issues/3998
workspace(name = "external_data_bazel_pkg")


# <workspace_import package="rules_python">
git_repository(
    name = "io_bazel_rules_python",
    remote = "https://github.com/bazelbuild/rules_python.git",
    commit = "979fca9",
)

# Only needed for PIP support:
load("@io_bazel_rules_python//python:pip.bzl", "pip_repositories", "pip_import")

pip_repositories()
# </workspace_import>  <!-- package="rules_python" -->

pip_import(
    name = "girder_client",
    requirements = "//:requirements.txt",
)

# BLECH
load("@girder_client//:requirements.bzl", girder_client_pip_install="pip_install")
girder_client_pip_install()
