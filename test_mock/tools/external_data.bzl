load("@org_drake_bazel_external_data//tools:macros.bzl",
    _external_data="external_data",
    _external_data_group="external_data_group",
    "get_original_files"
)

SETTINGS = dict(
    verbose = False,
    extra_args = "--user_config $(location //tools:external_data.user.yml)",
    extra_data = ['//tools:external_data.user.yml'],
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
