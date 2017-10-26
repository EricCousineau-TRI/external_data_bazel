#!/usr/bin/env python

def get_repo_configuration():
    config = {
        "workspace": {
            # Sentinel to determine the project root relative to a file's path.
            "root_sentinel": {
                "name": ".custom-sentinel",
                "file_type": "any",
            },
            # Configuration file path relative to the project root.
            "config_path": ".bazel_external_data",
        },
    }
    return config
