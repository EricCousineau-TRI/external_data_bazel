#!/usr/bin/env python
import os

from bazel_external_data.base import ProjectSetup, Backend
from bazel_external_data import config_helpers, util

class CustomProjectSetup(ProjectSetup):
    def __init__(self):
        ProjectSetup.__init__(self)
        # Augment starting directory to `tools/`, since Bazel will start at the root otherwise.
        # Only necessary if the sentinel is not at the Bazel root.
        self.relpath = 'test'
        self.sentinel = {'file': '.custom-sentinel'}

    def load_config(self, guess_filepath):
        project_config, user_config = ProjectSetup.load_config(self, guess_filepath)
        # Override cache directory.
        tmp_cache = os.path.join('/tmp/bazel_external_data/test_cache')
        user_config['core']['cache_dir'] = tmp_cache
        # Continue.
        return project_config, user_config

    def get_backends(self):
        backends = ProjectSetup.get_backends(self)
        backends['mock'] = MockBackend
        return backends


def get_setup():
    return CustomProjectSetup()


class MockBackend(Backend):
    def __init__(self, project, config_node):
        Backend.__init__(self, project, config_node)
        self._dir = os.path.join(self.project.root, config_node['dir'])

        # Crawl through files and compute SHAs.
        self._map = {}
        for file in os.listdir(self._dir):
            filepath = os.path.join(self._dir, file)
            if os.path.isfile(filepath):
                sha = util.compute_sha(filepath)
                self._map[sha] = filepath

    def has_file(self, sha):
        return sha in self._map

    def download_file(self, sha, output_file):
        filepath = self._map.get(sha)
        if filepath is None:
            raise util.DownloadError("Unknown sha: {}".format(sha))
        util.subshell(['cp', filepath, output_file])

    def upload_file(self, sha, filepath):
        sha = util.compute_sha(filepath)
        assert sha not in self._map
        # Just store the filepath temporarily.
        self._map[sha] = filepath
