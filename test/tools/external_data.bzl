load("//tools:macros.bzl",
    "external_data_impl",
    "external_data_group_impl",
    "get_original_files"
)

CUSTOM_TOOL = "//test/tools:download"

def external_data(*args, **kwargs):
    external_data_impl(
        *args,
        tool = CUSTOM_TOOL,
        **kwargs
    )

def external_data_group(*args, **kwargs):
    external_data_group_impl(
        *args,
        tool = CUSTOM_TOOL,
        **kwargs
    )
