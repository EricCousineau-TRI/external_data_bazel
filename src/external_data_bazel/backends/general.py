import json
import os

from external_data_bazel import util
from external_data_bazel.core import Backend


def _check_hash(url, hash_expected):
    # TODO(eric.cousineau): It'd be nice to cache the downloaded file, if it's ever
    # useful.
    tmp_file = util.TmpFileName()
    with tmp_file:
        tmp_path = tmp_file.get_path()
        util.subshell('curl -s -o {} {}'.format(tmp_path, url))
        hash = util.compute_hash(tmp_path)
        good = (hash_expected == hash)
    if not good:
        util.eprint("WARNING: SHA-512 mismatch for url: {}".format(url))
        util.eprint("  expected:\n    {}".format(hash_expected))
        util.eprint("  url:\n    {}".format(hash))
    return good

def _has_file(url, hash, trusted=False):
    if not trusted:
        # Download the full file, and check the hash.
        return _check_hash(url, hash)
    else:
        # Just check header.
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


def _parse_trusted(config):
    check = config.get('check', 'untrusted')
    if check == 'trusted':
        return True
    elif check == 'untrusted':
        return False
    else:
        raise RuntimeError('Unknown check type: {}'.format(check))

class UrlBackend(Backend):
    """ For direct URLs. """
    def __init__(self, config, package):
        Backend.__init__(self, config, package, can_upload=False)
        self._url = config['url']
        self._trusted = _parse_trusted(config)

    def has_file(self, hash, project_relpath):
        return _has_file(self._url, hash, self._trusted)

    def download_file(self, hash, project_relpath, output_file):
        # Ignore the SHA. Just download. Everything else will validate.
        _download_file(self._url, output_file)


class UrlTemplatesBackend(Backend):
    """ For formatted or direct URL downloads.
    This supports CMake/ExternalData-like URL templates, but using Python formatting '{algo}' and '{hash}'
    rather than '%(algo)' and '%(hash)'.
    """
    def __init__(self, config, package):
        Backend.__init__(self, config, package, can_upload=False)
        self._urls = config['url_templates']
        self._trusted = _parse_trusted(config)

    def _format(self, url, hash):
        return url.format(hash=hash.get_value(), algo=hash.get_algo())

    def has_file(self, hash, project_relpath):
        for url in self._urls:
            if _has_file(self._format(url, hash), hash, self._trusted):
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
