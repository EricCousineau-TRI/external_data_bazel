load("@org_drake_bazel_external_data//tools:macros.bzl",
    "external_data_impl",  # Do NOT use externally.
    "external_data_group_impl",  # Do NOT use externally.
    "get_original_files"  # Pass through.
)

TOOL = "//tools:download"
SETTINGS = struct(
    ENABLE_WARN = True,
    VERBOSE = False,
    CHECK_FILE = False,
)

def external_data(*args, **kwargs):
    external_data_impl(
        *args,
        tool = TOOL,
        settings = SETTINGS,
        **kwargs
    )

def external_data_group(*args, **kwargs):
    external_data_group_impl(
        *args,
        tool = TOOL,
        settings = SETTINGS,
        **kwargs
    )
