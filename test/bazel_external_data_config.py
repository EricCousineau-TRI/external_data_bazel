#!/usr/bin/env python
import os

from bazel_external_data import util

class CustomSetup(util.ProjectSetup):
    def get_config(self, filepath):
        sentinel = {'file': '.custom-sentinel'}
        config = util.ProjectSetup.get_config(self, filepath, sentinel=sentinel)

    def get_backends(self):
        backends = util.ProjectSetup.get_backends()
        backends['mock'] = MockBackend


class MockBackend(util.Backend):
    def __init__(self, project, config_node):
        util.Backend.__init__(self, project, config_node)
        self._dir = os.path.join(self.project.root, config_node['dir'])

        # Crawl through files and compute SHAs.
        self._map = {}
        for file in os.path.listfiles(self.dir):
            sha = util.compute_sha(file)
            self._map[sha] = file

    def has_file(self, sha):
        return sha in self._map

    def download_file(self, sha, output_file):
        file = self._map.get(sha)
        if file is None:
            raise util.DownloadError("Unknown sha: {}".format(sha))
        util.subshell(['cp', file, output_file])

    def upload_file(self, filepath):
        sha = util.compute_sha(filepath)
        assert sha not in self._map[sha]
        # Just store the filepath transitively.
        self._map[sha] = filepath


def get_setup():
    return CustomSetup()
