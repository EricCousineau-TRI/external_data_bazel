#!/usr/bin/env python
import os

from bazel_external_data import util

_sentinel = {'file': '.custom-sentinel'}

def get_config(filepath):
    start_dir = util.guess_start_dir(filepath)
    project_root = util.find_project_root(start_dir, _sentinel)
    # ^ Alternative: Guess project_root and do symlink interface,
    # then try to guess start_dir.
    config_files = util.find_config_files(project_root, start_dir)
    config = util.parse_and_merge_config_files(project_root, config_files)
    return config

def get_additional_backends():
    pass
