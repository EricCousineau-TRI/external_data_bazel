# We will inject additional settings here.
load("@external_data_bazel_pkg//tools:macros.bzl",
    _external_data="external_data",
    _external_data_group="external_data_group",
    _add_external_data_tests="add_external_data_tests",
    "get_original_files"
)

SETTINGS = dict(
    cli_data = [
        "//:external_data_sentinel",
        "//tools:external_data.user.yml",
        "//tools:external_data_config.py",
    ],
    cli_extra_args = ["--user_config=$(location //tools:external_data.user.yml)"],
)

def external_data(*args, **kwargs):
    _external_data(
        *args,
        settings = SETTINGS,
        **kwargs
    )

def external_data_group(*args, **kwargs):
    _external_data_group(
        *args,
        settings = SETTINGS,
        **kwargs
    )

def add_external_data_tests(*args, **kwargs):
    _add_external_data_tests(
        *args,
        settings = SETTINGS,
        **kwargs
    )
