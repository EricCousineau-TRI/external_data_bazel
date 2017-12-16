from datetime import datetime
import json
import os
import re
import yaml

from external_data_bazel import util
from external_data_bazel.core import Backend


def action(api_url, endpoint_in, query = None, token = None, args = [], method = "GET"):
    """ Lightweight REST call """
    extra_args = []
    if token:
        extra_args += ["--header", "Girder-Token: {}".format(token)]
    if method != "GET":
        # https://serverfault.com/a/315852/443276
        extra_args += ["-d", ""]
    endpoint = format_qs(endpoint_in, query)
    response_full = util.subshell([
        "curl", "-X", method, "-s",
            "--write-out", "\n%{http_code}",
            "--header", "Accept: application/json"] + args + extra_args +
        ["{}{}".format(api_url, endpoint)])
    lines = response_full.splitlines()
    response = "\n".join(lines[0:-1])
    code = int(lines[-1])
    if code >= 400:
        raise RuntimeError("Bad response for: {}\n  {}".format(endpoint, response))
    return json.loads(response)


def format_qs(url, query):
    from urllib import urlencode
    if query:
        jq = {}
        for key, value in query.iteritems():
            if isinstance(value, str):
                jq[key] = value
            else:
                jq[key] = json.dumps(value)
        return url + "?" + urlencode(jq)
    else:
        return url


class GirderHashsumBackend(Backend):
    """ Supports Girder servers where authentication may be needed (e.g. for uploading, possibly downloading). """
    def __init__(self, config, project_root, user):
        # Until there is a Girder plugin that can discriminate based on folder_id,
        # have configuration disable uploading on "master".
        # @ref https://github.com/girder/girder/issues/2446
        disable_upload = config.get('disable_upload', False)
        Backend.__init__(self, config, project_root, user, can_upload=not disable_upload)
        self._url = config['url']
        self._api_url = "{}/api/v1".format(self._url)
        self._folder_path = config['folder_path']
        # Get (optional) authentication information.
        url_config_node = util.get_chain(user.config, ['girder', 'url', self._url])
        self._api_key = util.get_chain(url_config_node, ['api_key'])
        self._token = None
        self._girder_client = None
        # Cache configuration.
        self._config_cache_file = os.path.join(user.cache_dir, 'config', 'girder.yml')

    def _action(self, *args, **kwargs):
        return action(self._api_url, *args, token=self._token, **kwargs)

    def _read_config_cache(self):
        if os.path.isfile(self._config_cache_file):
            with open(self._config_cache_file) as f:
                return yaml.load(f)
        else:
            return {}

    def _write_config_cache(self, config_cache):
        tgt_dir = os.path.dirname(self._config_cache_file)
        if not os.path.isdir(tgt_dir):
            os.makedirs(tgt_dir)
        with open(self._config_cache_file, 'w') as f:
            yaml.dump(config_cache, f, default_flow_style=False)

    def _get_folder_id(self):
        config_cache = self._read_config_cache()
        key_chain = ['url', self._url, 'folder_ids', self._folder_path]
        folder_id = util.get_chain(config_cache, key_chain)
        # TODO(eric.cousineau): If folder is invalid, discard it.
        # Do this in `has_file`?
        if folder_id is None:
            self._authenticate_if_needed()
            response = self._action('/resource/lookup', query = {"path": self._folder_path})
            assert response["_modelType"] == "folder"
            folder_id = str(response["_id"])
            util.set_chain(config_cache, key_chain, folder_id)
            self._write_config_cache(config_cache)
        return folder_id

    def _authenticate_if_needed(self):
        if self._api_key is not None and self._token is None:
            response = self._action("/api_key/token", method = "POST", query = {"key": self._api_key})
            self._token = response["authToken"]["token"]

    def _download_url(self, hash):
        return "{api_url}/file/hashsum/{algo}/{hash}/download".format(algo=hash.get_algo(), hash=hash.get_value(), api_url=self._api_url)

    def _download_args(self, hash):
        url = self._download_url(hash)
        self._authenticate_if_needed()
        if self._token:
            args = '-H "Girder-Token: {token}" "{url}"'.format(token=self._token, url=url)
        else:
            args = url
        return args

    def _is_part_of_folder(self, hash):
        # Get files for the given hashsum.
        files = self._action("/file/hashsum/{algo}/{hash}".format(algo=hash.get_algo(), hash=hash.get_value()))
        for file in files:
            id = file["_id"]
            # Get path.
            path = self._action("/resource/{id}/path".format(id=id), query = {"type": "file"})
            if path.startswith(self._folder_path + "/"):
                return True
        return False

    def has_file(self, hash, project_relpath):
        """ Returns true if the given hash exists on the given server. """
        # TODO(eric.cousineau): Is there a quicker way to do this???
        # TODO(eric.cousineau): Check `folder_id` and ensure it lives in the same place?
        # This is necessary if we have users with the same file?
        # What about authentication? Optional authentication / public access?
        return self._is_part_of_folder(hash)

    def download_file(self, hash, project_relpath, output_file):
        if not self.has_file(hash, project_relpath):
            raise util.DownloadError("File not available in Girder folder '{}': {} (hash: {})".format(self._folder_path, project_relpath, hash))
        # Unfortunately, not having authentication does not yield user-friendly errors.
        # Should fix this later.
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
        folder_id = self._get_folder_id()

        print("api_url ............: %s" % self._api_url)
        print("folder_path ..........: %s" % self._folder_path)
        print("folder_id ..........: %s" % folder_id)
        print("filepath ...........: %s" % filepath)
        print("hash ...............: %s" % hash)
        print("item_name ..........: %s" % item_name)
        print("project_relpath .: %s" % project_relpath)
        # TODO(eric.cousineau): Include `project.name` in the versioning!
        # TODO(eric.cousineau): Add the visualization key for the Girder `vtk.js` stuff.
        ref = json.dumps({'versionedFilePath': project_relpath})
        gc = self._get_girder_client()
        size = os.stat(filepath).st_size
        with open(filepath, 'rb') as fd:
            print("Uploading: {}".format(filepath))
            gc.uploadFile(folder_id, fd, name=item_name, size=size, parentType='folder', reference=ref)


def get_backends():
    return {
        "girder_hashsum": GirderHashsumBackend,
    }
