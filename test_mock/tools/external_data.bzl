load("@org_drake_bazel_external_data//tools:macros.bzl",
    _external_data="external_data",
    _external_data_group="external_data_group",
    "get_original_files"
)

SETTINGS = struct(
    ENABLE_WARN = True,
    VERBOSE = False,
    DEBUG_CONFIG = False,
    CHECK_FILE = False,
    EXTRA_ARGS = "--user_config=$(location //tools:external_data.user.yml)",
)

KWARGS = {
    "settings": SETTINGS,
    "data": ['//tools:external_data.user.yml'],
}

def external_data(*args, **kwargs):
    kwargs_ext = kwargs + KWARGS
    _external_data(
        *args,
        **kwargs_ext
    )

def external_data_group(*args, **kwargs):
    kwargs_ext = kwargs + KWARGS
    _external_data_group(
        *args,
        **kwargs_ext
    )
