#!/usr/bin/env python
import os

from bazel_external_data.base import ProjectSetup
from bazel_external_data import util

tmp_dir = '/tmp/bazel_external_data'


class CustomProjectSetup(ProjectSetup):
    def __init__(self):
        ProjectSetup.__init__(self)
        # Augment starting directory to `tools/`, since Bazel will start at the root otherwise.
        # Only necessary if the sentinel is not at the Bazel root.
        self.relpath = 'test'
        self.sentinel = {'file': '.custom-sentinel'}

    def load_config(self, guess_filepath):
        root_config, user_config = ProjectSetup.load_config(self, guess_filepath)
        # Override cache directory.
        tmp_cache = os.path.join(tmp_dir, 'test_cache')
        user_config['core']['cache_dir'] = tmp_cache
        # Continue.
        return root_config, user_config


def get_setup():
    return CustomProjectSetup()
