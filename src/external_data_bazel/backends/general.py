import json
import os

from external_data_bazel import util
from external_data_bazel.core import Backend

def _has_file(url):
    first_line = util.subshell('curl -s --head {url} | head -n 1'.format(url=url))
    bad = ["HTTP/1.1 404 Not Found"]
    good = ["HTTP/1.1 200 OK", "HTTP/1.1 303 See Other"]
    if first_line in bad:
        return False
    elif first_line in good:
        return True
    else:
        raise RuntimeError("Unknown code: {}".format(first_line))


def _download_file(url, output_file):
    util.curl('-L -o {output_file} {url}'.format(url=url, output_file=output_file))


class UrlBackend(Backend):
    """ For direct URLs. """
    def __init__(self, config, project):
        Backend.__init__(self, config, project)
        self._url = config['url']

    def has_file(self, hash, project_relpath):
        return _has_file(self._url)

    def download_file(self, hash, project_relpath, output_file):
        # Ignore the SHA. Just download. Everything else will validate.
        _download_file(self._url, output_file)


class UrlTemplatesBackend(Backend):
    """ For formatted or direct URL downloads.
    This supports CMake/ExternalData-like URL templates, but using Python formatting '{algo}' and '{hash}'
    rather than '%(algo)' and '%(hash)'.
    """
    def __init__(self, config, project):
        Backend.__init__(self, config, project)
        self._urls = config['url_templates']

    def _format(self, url, hash):
        return url.format(hash=hash, algo='sha512')

    def has_file(self, hash, project_relpath):
        for url in self._urls:
            if _has_file(self._format(url, hash)):
                return True
        return False

    def download_file(self, hash, project_relpath, output_file):
        for url in self._urls:
            try:
                _download_file(self._format(url, hash))
                return
            except util.DownloadError:
                pass
        algo = 'sha512'
        raise util.DownloadError("Could not download {}:{} from:\n{}".format(algo, hash, "\n".join(self._urls)))
