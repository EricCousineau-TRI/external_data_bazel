import json
import os

from bazel_external_data import util
from bazel_external_data.base import Backend

# TODO(eric.cousineau): Consider implementing LFS protocol?

def get_default_backends():
    return {
        "mock": MockBackend,
        "url": UrlBackend,
        "url_templates": UrlTemplatesBackend,
        "girder": GirderBackend,
    }


class MockBackend(Backend):
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
                    sha = util.compute_sha(filepath)
                    self._map[sha] = filepath
        crawl(self._dir)
        if os.path.exists(self._upload_dir):
            crawl(self._upload_dir)

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
        if not os.path.isdir(self._upload_dir):
            os.makedirs(self._upload_dir)
        # Copy the file.
        dest = os.path.join(self._upload_dir, sha)
        util.subshell(['cp', filepath, dest])
        # Store the SHA.
        self._map[sha] = dest


def _has_file(self, url):
    first_line = util.subshell('curl -s --head {url} | head -n 1'.format(url=url))
    bad = ["HTTP/1.1 404 Not Found"]
    good = ["HTTP/1.1 200 OK", "HTTP/1.1 303 See Other"]
    if first_line in bad:
        return False
    elif first_line in good:
        return True
    else:
        raise RuntimeError("Unknown code: {}".format(first_line))


def _download_file(self, url, output_file):
    util.curl('-L -o {output_file} {url}'.format(url=url, output_file=output_file))


class UrlBackend(Backend):
    """ For direct URLs. """
    def __init__(self, config, project):
        Backend.__init__(self, config, project)
        self._url = config['url']

    def has_file(self, sha):
        return _has_file(self._url)

    def download_file(self, sha, output_file):
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

    def _format(self, url, sha):
        return url.format(hash=sha, algo='sha512')

    def has_file(self, sha):
        for url in self._urls:
            if _has_file(self._format(url, sha)):
                return True
        return False

    def download_file(self, sha, output_file):
        for url in self._urls:
            try:
                _download_file(self._format(url, sha))
                return
            except util.DownloadError:
                pass
        algo = 'sha512'
        raise util.DownloadError("Could not download {}:{} from:\n{}".format(algo, sha, "\n".join(self._urls)))

# TODO(eric.cousineau): If `girder_client` is sufficiently lightweight, we can make this a proper Bazel
# dependency.
# If it's caching mechanism is efficient and robust against Bazel, we should use that as well.

class GirderBackend(Backend):
    """ Supports Girder servers where authentication may be needed (e.g. for uploading, possibly downloading). """
    def __init__(self, config, project):
        Backend.__init__(self, config, project)
        self._url = config['url']
        self._api_url = "{}/api/v1".format(self._url)
        self._folder_id = config['folder_id']
        # Get (optional) authentication information.
        url_config_node = get_chain(self.project.user.config, ['girder', 'url', self._url])
        self._api_key = get_chain(url_config_node, ['api_key'])
        self._token = None
        self._girder_client = None

    def _authenticate_if_needed(self):
        if self._api_key is not None and self._token is None:
            token_raw = curl(
                "-L -s --data key={api_key} {api_url}/api_key/token".format(api_key=self._api_key, api_url=self._api_url))
            self._token = json.loads(token_raw)["authToken"]["token"]

    def _download_url(self, sha):
        return "{api_url}/file/hashsum/sha512/{sha}/download".format(sha=sha, api_url=self._api_url)

    def _download_args(self, sha):
        url = self._download_url(sha)
        self._authenticate_if_needed()
        if self._token:
            args = '-H "Girder-Token: {token}" "{url}"'.format(token=self._token, url=url)
        else:
            args = url
        return args

    def has_file(self, sha):
        """ Returns true if the given SHA exists on the given server. """
        # TODO(eric.cousineau): Is there a quicker way to do this???
        # TODO(eric.cousineau): Check `folder_id` and ensure it lives in the same place?
        # This is necessary if we have users with the same file?
        # What about authentication? Optional authentication / public access?
        args = self._download_args(sha)
        first_line = util.subshell('curl -s --head {args} | head -n 1'.format(args=args))
        if first_line == "HTTP/1.1 404 Not Found":
            return False
        elif first_line == "HTTP/1.1 303 See Other":
            return True
        else:
            raise RuntimeError("Unknown response: {}".format(first_line))

    def download_file(self, sha, output_file):
        args = self._download_args(sha)
        util.curl("-L --progress-bar -o {output_file} {args}".format(args=args, output_file=output_file))

    def _get_girder_client(self):
        import girder_client
        if self._girder_client is None:
            self._girder_client = girder_client.GirderClient(apiUrl=self._api_url)
            self._girder_client.authenticate(apiKey=self._api_key)
        return self._girder_client

    def upload_file(self, sha, filepath):
        item_name = "%s %s" % (os.path.basename(filepath), datetime.utcnow().isoformat())

        versioned_filepath = os.path.relpath(filepath, self.project.root)
        if versioned_filepath.startswith('..'):
            raise RuntimeError("File to upload, '{}', must be under '{}'".format(filepath, self.project.root))

        print("api_url ............: %s" % self._api_url)
        print("folder_id ..........: %s" % self._folder_id)
        print("filepath ...........: %s" % filepath)
        print("sha512 .............: %s" % sha)
        print("item_name ..........: %s" % item_name)
        print("project_root .......: %s" % self.project.root)
        print("versioned_filepath .: %s" % versioned_filepath)
        # TODO(eric.cousineau): Include `conf.project_name` in the versioning.
        ref = json.dumps({'versionedFilePath': versioned_filepath})
        gc = self._get_girder_client()
        size = os.stat(filepath).st_size
        with open(filepath, 'rb') as fd:
            print("Uploading: {}".format(filepath))
            gc.uploadFile(self._folder_id, fd, name=item_name, size=size, parentType='folder', reference=ref)
