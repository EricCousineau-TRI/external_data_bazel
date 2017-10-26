#!/usr/bin/env python
import os

def get_configuration():
    config = {
        # Sentinel to determine the project root relative to a file's path.
        "root_sentinel": {
            "name": ".custom-sentinel",
            "file_type": "any",
        },
        # Configuration file path relative to the project root.
        "config_path": ".bazel_external_data",
        # Specify "None" if you wish to use the user's cachedir.
        "cache_dir": "/tmp/bazel_external_data_cache",
    }
    return config
