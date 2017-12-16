import os

from external_data_bazel import util, config_helpers, hashes


PROJECT_CONFIG_FILE = ".external_data.yml"
USER_CONFIG_FILE_DEFAULT = os.path.expanduser("~/.config/external_data_bazel/config.yml")
CACHE_DIR_DEFAULT = "~/.cache/external_data_bazel"
USER_CONFIG_DEFAULT = {
    "core": {
        "cache_dir": CACHE_DIR_DEFAULT,
    },
}


class Backend(object):
    """ Downloads or uploads a file from a given storage mechanism given the hash file.
    This also has access to the package (and indirectly, the project) to determine the
    file path relative to the package as well. The project can be used to retrieve the
    (if applicable), etc. """
    def __init__(self, config, project_root, user, can_upload):
        self.can_upload = can_upload

    def has_file(self, hash, project_relpath):
        """ Determines if the storage mechanism has a given SHA.
        @note It is IMPORTANT that the 'hash' be prioritized.
            It is OK if 'project_relpath' is not used, but 'hash' must be a critical part
            of the check!!!"""
        raise NotImplemented()

    def download_file(self, hash, project_relpath, output_path):
        """ Downloads a file from a given hash to a given output path.
        @param project_relpath
            File path relative to project. May be None, depending on
            how this is used (e.g. via CMake/ExternalData). """
        raise RuntimeError("Downloading not supported for this backend")

    def upload_file(self, hash, project_relpath, filepath):
        """ Uploads a file from an output path given a SHA.
        @param project_relpath
            Same as for `download_file`, but must not be None.
        @note This hash should be assumed to be valid. """
        raise RuntimeError("Uploading not supported for this backend")


class Remote(object):
    """ Provides a cache-friendly and hierarchy-friendly access to a given remote. """
    def __init__(self, config, name, project):
        self.config = config
        self.name = name
        self.project = project
        backend_type = self.config['backend']
        self._backend = self.project.load_backend(backend_type, config)
        overlay_name = self.config.get('overlay')
        self.overlay = None
        if overlay_name is not None:
            self.overlay = self.project.get_remote(overlay_name)

    def debug_config(self):
        """For each remote, print its configuration, relative project path, and its overlays. """
        core = {}
        node = core
        remote = self
        while remote:
            config = {remote.name: remote.config}
            node.update(config=config)
            remote = remote.overlay
            if remote:
                parent = node
                node = {}
                parent['overlay'] = node
            else:
                break
        return core

    def has_overlay(self):
        """ Returns whether this remote is overlaying another. """
        return self.overlay is not None

    def has_file(self, hash, project_relpath, check_overlay=True):
        """ Returns whether this remote (or its overlay) has a given SHA. """
        if self._backend.has_file(hash, project_relpath):
            return True
        elif check_overlay and self.has_overlay():
            return self.overlay.has_file(hash, project_relpath)

    def _download_file_direct(self, hash, project_relpath, output_file):
        """ Downloads a file directly and checks the SHA.
        @pre `output_file` should not exist. """
        assert not os.path.exists(output_file)
        try:
            self._backend.download_file(hash, project_relpath, output_file)
            hash.check_file(output_file)
        except util.DownloadError as e:
            if self.has_overlay():
                self.overlay._download_file_direct(hash, project_relpath, output_file)
            else:
                raise e

    def download_file(self, hash, project_relpath, output_file,
                      use_cache = True, symlink = True):
        """ Downloads a file.
        @param use_cache
            Uses `project.user.cache_dir` as a cache. Normally, this is user-specified.
        @param symlink
            If `use_cache` is true, this will place a symlink to the read-only
            cache file at `output_file`.
        @param project_relpath
            @see Backend.download_file
        @returns 'cache' if there was a cachce hit, 'download' otherwise.
        """
        assert os.path.isabs(output_file)

        def download_file_direct(output_file):
            try:
                self._download_file_direct(hash, project_relpath, output_file)
            except util.DownloadError as e:
                sys.stderr.write("ERROR: For remote '{}'".format(self.name))
                raise e

        # Check if we need to download.
        if use_cache:
            cache_path = self.project.get_hash_cache_path(hash, create_dir=True)

            # Helper functions.
            def get_cached(skip_sha_check):
                # Can use cache. Copy to output path.
                if symlink:
                    util.subshell(['ln', '-s', cache_path, output_file])
                else:
                    util.subshell(['cp', cache_path, output_file])
                    util.subshell(['chmod', '+w', output_file])
                # On error, remove cached file, and re-download.
                if not skip_sha_check:
                    if not hash.check_file(output_file, do_throw=False):
                        util.eprint("SHA-512 mismatch. Removing old cached file, re-downloading.")
                        # `os.remove()` will remove read-only files without prompting.
                        os.remove(cache_path)
                        if os.path.islink(output_file):
                            # In this situation, the cache was corrupted (somehow), and Bazel
                            # triggered a recompilation, and we still have a symlink in Bazel-space.
                            # Remove this symlink, so that we do not download into a symlink (which
                            # complicates the logic in `get_download_and_cache`). This also allows
                            # us to "reset" permissions.
                            os.remove(output_file)
                        get_download_and_cache()

            def get_download_and_cache():
                with util.FileWriteLock(cache_path):
                    download_file_direct(cache_path)
                    # Make cache file read-only.
                    util.subshell(['chmod', '-w', cache_path])
                # Use cached file - `get_download()` has already checked the hash.
                get_cached(True)

            # TODO(eric.cousineau): This still isn't atomic, and may encounter a race condition...
            util.wait_file_read_lock(cache_path)
            if os.path.isfile(cache_path):
                get_cached(False)
                return 'cache'
            else:
                get_download_and_cache()
                return 'download'
        else:
            download_file_direct(output_file)
            return 'download'

    def upload_file(self, hash_type, project_relpath, filepath):
        """ Uploads a file (only if it does not already exist in this remote - NOT the backend),
        and updates the corresponding hash file. """
        assert os.path.isabs(filepath)
        hash = hash_type.compute(filepath)
        # TODO(eric.cousineau): Have the project check if this is a valid hash type?
        if not self._backend.can_upload:
            raise RuntimeError("Backend does not support uploading")
        if self._backend.has_file(hash, project_relpath):
            print("File already uploaded")
        else:
            self._backend.upload_file(hash, project_relpath, filepath)
        return hash


class User(object):
    """Stores user-level configuration (including backend-specifics, if needed). """
    def __init__(self, config):
        self.config = config
        self.cache_dir = os.path.expanduser(config['core']['cache_dir'])


def get_hash_cache_path(cache_dir, hash, create_dir=True):
    """ Get the cache path for a given hash file. """
    hash_algo = hash.get_algo()
    hash_value = hash.get_value()
    out_dir = os.path.join(
        cache_dir, hash_algo, hash_value[0:2], hash_value[2:4])
    if create_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    return os.path.join(out_dir, hash_value)


class Project(object):
    """Specifies a project's structure, remotes, and determines the mapping
    between files and their remotes (for download / uploading). """
    def __init__(self, config, user, backends):
        self.config = config
        self.user = user
        self._backends = backends
        # Load project-specific settings.
        self.name = self.config['project']
        self.root = self.config['root']
        self._root_alternatives = self.config.get('root_alternatives', [])
        # Load frontend.
        self.frontend = HashFileFrontend(self)
        # Remotes.
        self._remote_selected = self.config['remote']
        self._remotes = {}
        self._remote_is_loading = []

    def load_backend(self, backend_type, config):
        backend_cls = self._backends[backend_type]
        return backend_cls(config, self.root, self.user)

    def get_remote(self, name):
        remote = self._remotes.get(name)
        if remote:
            return remote
        # Check against dependency cycles.
        if name in self._remote_is_loading:
            raise RuntimeError("'remote' cycle detected: {}".format(self._remote_is_loading))
        self._remote_is_loading.append(name)
        # Load remote.
        remote_config = self.config['remotes'][name]
        remote = Remote(remote_config, name, self)
        # Update.
        self._remote_is_loading.remove(name)
        self._remotes[name] = remote
        return remote

    def get_selected_remote(self):
        return self.get_remote(self._remote_selected)

    def get_relpath(self, filepath):
        """ Get filepah relative to project root, using alternative roots if viable.
        @note This should be used for reading operations only! """
        assert os.path.isabs(filepath)
        root_paths = [self.root] + self._root_alternatives
        # WARNING: This will not handle a nest root!
        # (e.g. if an alternative is a child or parent of another path)
        for root in root_paths:
            if util.is_child_path(filepath, root):
                return os.path.relpath(filepath, root)
        raise RuntimeError("Path is not a child of given project")

    def get_canonical_path(self, relpath):
        """ Get filepath as an absolute path, ensuring that it is with respect to the canonical project root.
        @ note This should be reading operations only! """
        assert not os.path.isabs(relpath)
        return os.path.join(self.root, relpath)

    def get_hash_cache_path(self, hash, create_dir=False):
        return get_hash_cache_path(self.user.cache_dir, hash, create_dir)


class HashFileFrontend(object):
    """ Frontend to determine file information based on neighboring hash file. """
    def __init__(self, project):
        self.project = project
        self._hash_type = hashes.sha512
        self._suffix = ".sha512"

    def _get_orig_file(self, hash_file):
        if not hash_file.endswith(self._suffix):
            return None
        else:
            return hash_file[:-len(self._suffix)]

    def _infer_hash_type(self, input_file):
        # Infer hash type from filepath *ONLY*, not the file system.
        orig_file = self._get_orig_file(input_file)
        if orig_file is None:
            return (self._hash_type, input_file)
        else:
            return (self._hash_type, orig_file)

    def is_hash_file(self, input_file):
        assert os.path.isabs(input_file)
        return self._get_orig_file(input_file) is not None

    def get_hash_file(self, input_file):
        assert not self.is_hash_file(input_file)
        return input_file + self._suffix

    def get_file_info(self, input_file, must_have_hash=True):
        assert os.path.isabs(input_file)
        hash_type, orig_filepath = self._infer_hash_type(input_file)
        default_output_file = orig_filepath
        hash_file = self.get_hash_file(orig_filepath)
        if not os.path.isfile(hash_file):
            if must_have_hash:
                raise RuntimeError("ERROR: Hash file not found: {}".format(hash_file))
            else:
                hash = hash_type.create_empty()
        else:
            # Load the hash.
            with open(hash_file, 'r') as f:
                hash = hash_type.create(f.read().strip(), filepath=orig_filepath)
        project_relpath = self.project.get_relpath(orig_filepath)
        remote = self.project.get_selected_remote()
        return FileInfo(hash, remote, project_relpath, default_output_file, orig_filepath)

    def update_file_info(self, info, hash):
        """Writes hashsum, updating hash filepath if needed. """
        assert hash.hash_type == self._hash_type
        hash_file = self.get_hash_file(info.orig_filepath)
        if hash.filepath is not None:
            assert hash.filepath == info.orig_filepath, "{} != {}".format(hash.filepath, info.orig_filepath)
        else:
            hash.filepath = info.orig_filepath
        with open(hash_file, 'w') as f:
            f.write(hash.get_value())


class FileInfo(object):
    """ Specifies general information for a given file. """
    def __init__(self, hash, remote, project_relpath, default_output_file, orig_filepath):
        # This is the *project* hash, NOT the has of the present file.
        # If None, then that means the file is not yet part of the project.
        self.hash = hash
        self.remote = remote
        self.project_relpath = project_relpath
        self.default_output_file = default_output_file
        self.orig_filepath = orig_filepath


def _load_project_config(guess_filepath, project_name=None):
    # Load the project user configuration from a filepath to guess to find the project root.
    # Start guessing where the project lives.
    sentinel = PROJECT_CONFIG_FILE
    project_root, root_alternatives = config_helpers.find_project_root(guess_filepath, sentinel, project_name)
    # Load configuration.
    project_config_file = os.path.join(project_root, os.path.join(project_root, PROJECT_CONFIG_FILE))
    project_config = config_helpers.parse_config_file(project_config_file)
    # Inject project information.
    project_config['root'] = project_root
    # Cache symlink root, and use this to get relative workspace path if the file is specified in
    # the symlink'd directory (e.g. Bazel runfiles).
    project_config['root_alternatives'] = root_alternatives
    return project_config


def load_project(guess_filepath, project_name = None, user_config_file = None):
    """ Load a project given the injected `bazel_external_data_config` module.
    @param guess_filepath
        Filepath where to start guessing where the project root is.
    @param user_config_file
        Overload for user configuration.
    @param project_name
        Constrain finding the project root to project files with the provided project name.
        (For working with nested projects.)
    @return A `Project` instance.
    @see test/bazel_external_data_config
    """
    if user_config_file is None:
        user_config_file = USER_CONFIG_FILE_DEFAULT
    if os.path.exists(user_config_file):
        user_config = config_helpers.parse_config_file(user_config_file)
    else:
        user_config = {}
    user_config = config_helpers.merge_config(USER_CONFIG_DEFAULT, user_config)
    user = User(user_config)
    project_config = _load_project_config(guess_filepath, project_name)
    # We must place this import here given that `Backend` is defined in this module.
    from external_data_bazel import backends
    project = Project(project_config, user, backends.get_default_backends())
    return project
