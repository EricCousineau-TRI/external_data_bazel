import os

from external_data_bazel import util
from external_data_bazel.core import Backend

class MockBackend(Backend):
    """ A mock backend for testing. """
    def __init__(self, config, project):
        Backend.__init__(self, config, project)
        self._dir = os.path.join(self.project.root, config['dir'])
        # TODO(eric.cousineau): Enable ${PWD} for testing?
        self._upload_dir = os.path.join(self.project.root, config['upload_dir'])

        # Crawl through files and compute SHAs.
        self._map = {}
        def crawl(cur_dir):
            for file in os.listdir(cur_dir):
                filepath = os.path.join(cur_dir, file)
                if os.path.isfile(filepath):
                    hash = util.compute_hash(filepath)
                    self._map[hash] = filepath
        crawl(self._dir)
        if os.path.exists(self._upload_dir):
            crawl(self._upload_dir)

    def has_file(self, hash, project_relpath):
        return hash in self._map

    def download_file(self, hash, project_relpath, output_file):
        filepath = self._map.get(hash)
        if filepath is None:
            raise util.DownloadError("Unknown hash: {}".format(hash))
        util.subshell(['cp', filepath, output_file])

    def upload_file(self, hash, project_relpath, filepath):
        hash = util.compute_hash(filepath)
        assert hash not in self._map
        if not os.path.isdir(self._upload_dir):
            os.makedirs(self._upload_dir)
        # Copy the file.
        dest = os.path.join(self._upload_dir, hash)
        util.subshell(['cp', filepath, dest])
        # Store the SHA.
        self._map[hash] = dest
