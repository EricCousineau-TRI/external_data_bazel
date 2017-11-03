import json
import os

from external_data_bazel import util
from external_data_bazel.core import Backend

# TODO(eric.cousineau): If `girder_client` is sufficiently lightweight, we can make this a proper Bazel
# dependency.
# If it's caching mechanism is efficient and robust against Bazel, we should use that as well.

# TODO(eric.cousineau): Split this into a common base backend.
# @ref https://github.com/girder/girder/issues/2446
# For the above link, if it turns into a separate plugin on Girder server-side,
# still keep the original backend for hashsum.
# Ensure this plugin still uses the same configuration.

# TODO(eric.cousineau): Consider permitting padding a URL with a prefix, e.g. "[devel] " or "[master] ",
# to allow specific configuruation to be specified.
# Possibly permit still leveraging the original URL authentication?

class GirderHashsumBackend(Backend):
    """ Supports Girder servers where authentication may be needed (e.g. for uploading, possibly downloading). """
    def __init__(self, config, project):
        Backend.__init__(self, config, project)
        self.can_upload = True
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

    def _download_url(self, hash):
        return "{api_url}/file/hashsum/sha512/{hash}/download".format(hash=hash, api_url=self._api_url)

    def _download_args(self, hash):
        url = self._download_url(hash)
        self._authenticate_if_needed()
        if self._token:
            args = '-H "Girder-Token: {token}" "{url}"'.format(token=self._token, url=url)
        else:
            args = url
        return args

    def has_file(self, hash, project_relpath):
        """ Returns true if the given hash exists on the given server. """
        # TODO(eric.cousineau): Is there a quicker way to do this???
        # TODO(eric.cousineau): Check `folder_id` and ensure it lives in the same place?
        # This is necessary if we have users with the same file?
        # What about authentication? Optional authentication / public access?
        args = self._download_args(hash)
        first_line = util.subshell('curl -s --head {args} | head -n 1'.format(args=args))
        if first_line == "HTTP/1.1 404 Not Found":
            return False
        elif first_line == "HTTP/1.1 303 See Other":
            return True
        else:
            raise RuntimeError("Unknown response: {}".format(first_line))

    def download_file(self, hash, project_relpath, output_file):
        args = self._download_args(hash)
        util.curl("-L --progress-bar -o {output_file} {args}".format(args=args, output_file=output_file))

    def _get_girder_client(self):
        # @note We import girder_client here, as only uploading requires it at present.
        # If `girder_client` can be imported via Bazel with minimal pain, then we can bubble
        # this up to the top-level.
        import girder_client
        if self._girder_client is None:
            self._girder_client = girder_client.GirderClient(apiUrl=self._api_url)
            self._girder_client.authenticate(apiKey=self._api_key)
        return self._girder_client

    def upload_file(self, hash, project_relpath, filepath):
        item_name = "%s %s" % (os.path.basename(filepath), datetime.utcnow().isoformat())

        print("api_url ............: %s" % self._api_url)
        print("folder_id ..........: %s" % self._folder_id)
        print("filepath ...........: %s" % filepath)
        print("sha512 .............: %s" % hash)
        print("item_name ..........: %s" % item_name)
        print("project_root .......: %s" % self.project.root)
        print("project_relpath .: %s" % project_relpath)
        # TODO(eric.cousineau): Include `project.name` in the versioning!
        # TODO(eric.cousineau): Add the visualization key for the Girder `vtk.js` stuff.
        ref = json.dumps({'versionedFilePath': project_relpath})
        gc = self._get_girder_client()
        size = os.stat(filepath).st_size
        with open(filepath, 'rb') as fd:
            print("Uploading: {}".format(filepath))
            gc.uploadFile(self._folder_id, fd, name=item_name, size=size, parentType='folder', reference=ref)


def get_backends():
    return {
        "girder_hashum": GirderHashsumBackend,
    }
