import json
import os

from bazel_external_data.base import Backend

# TODO(eric.cousineau): If `girder_client` is sufficiently lightweight, we can make this a proper Bazel
# dependency.
# If it's caching mechanism is efficient and robust against Bazel, we should use that as well.

def _reduce_url(url_full):
    begin = '['
    end = '] '
    if url_full.startswith(begin):
        # Scan until we find '] '
        fin = url_full.index(end)
        url = url_full[fin + len(end):]
    else:
        url = url_full
    return url

class GirderBackend(Backend):
    def __init__(self, project, config_node):
        Backend.__init__(self, project, config_node)

        url_full = config_node['url']
        self._url = _reduce_url(url_full)
        self._api_url = "{}/api/v1".format(self._url)
        self._folder_id = config_node['folder_id']
        # Get (optional) authentication information.
        url_config_node = get_chain(self.project.root_config, ['girder', 'url', url_full])
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


# For direct file downloads.
# Example: download --remote="{backend: direct, url: '...'}"
class DirectBackend(Backend):
    def __init__(self, project, config_node):
        Backend.__init__(self, project)
        self._url = config_node['url']

    def download_file(self, sha, output_file):
        # Ignore the SHA. Just download. Everything else will validate.
        util.curl('-L -o {output_file} {url}'.format(url=self._url, output_file=output_file))


def get_default_backends():
    return {
        "girder": GirderBackend,
        "direct": DirectBackend,
    }
