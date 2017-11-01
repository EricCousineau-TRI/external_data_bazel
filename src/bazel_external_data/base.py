import os

from bazel_external_data import util, config_helpers

SHA_SUFFIX = '.sha512'
CONFIG_FILE_DEFAULT = ".bazel_external_data.yml"
USER_CONFIG_FILE_DEFAULT = os.path.expanduser("~/.config/bazel_external_data/config.yml")
CACHE_DIR_DEFAULT = "~/.cache/bazel_external_data"
SENTINEL_DEFAULT = 'WORKSPACE'

class Backend(object):
    """ Downloads or uploads a file from a given storage mechanism given the SHA file.
    This also has access to the project to determine project name, file relative paths
    (if applicable), etc. """
    def __init__(self, config, project):
        self.project = project
        self.config = config

    def has_file(self, sha):
        """ Determines if the storage mechanism has a given SHA. """
        raise NotImplemented()

    def download_file(self, sha, output_path):
        """ Downloads a file from a given SHA to a given output path. """
        raise RuntimeError("Downloading not supported for this backend")

    def upload_file(self, sha, filepath):
        """ Uploads a file from an output path given a SHA.
        @note This SHA should be assumed to be valid. """
        raise RuntimeError("Uploading not supported for this backend")


class Remote(object):
    """ Provides a cache-friendly and hierarchy-friendly access to a given remote. """
    def __init__(self, config, name, package):
        self.package = package
        self.config = config
        self.name = name
        backend_type = config['backend']
        self._backend = self.package.load_backend(backend_type, config)

        overlay_name = config.get('overlay')
        self.overlay = None
        if overlay_name is not None:
            self.overlay = self.package.load_remote(overlay_name)

    def has_overlay(self):
        """ Returns whether this remote is overlaying another. """
        return self.overlay is not None

    def has_file(self, sha, check_overlay=True):
        """ Returns whether this remote (or its overlay) has a given SHA. """
        if self._backend.has_file(sha):
            return True
        elif check_overlay and self.has_overlay():
            return self.overlay.has_file(sha)

    def download_file_direct(self, sha, output_file):
        """ Downloads a file directly and checks the SHA.
        @pre `output_file` should not exist. """
        assert not os.path.exists(output_file)
        try:
            self._backend.download_file(sha, output_file)
            util.check_sha(sha, output_file)
        except util.DownloadError as e:
            if self.has_overlay():
                self.overlay.download_file_direct(sha, output_file)
            else:
                # Rethrow
                raise e

    def download_file(self, sha, output_file,
                      use_cache = True, symlink_from_cache = True):
        """ Downloads a file.
        @param use_cache
            Uses `project.user.cache_dir` as a cache. Normally, this is user-specified.
        @param symlink_from_cache
            If `use_cache` is true, this will place a symlink to the read-only
            cache file at `output_file`.
        @returns 'cache' if there was a cachce hit, 'download' otherwise.
        """

        # Helper functions.
        def get_cached(skip_sha_check=False):
            # Can use cache. Copy to output path.
            if symlink_from_cache:
                util.subshell(['ln', '-s', cache_path, output_file])
            else:
                util.subshell(['cp', cache_path, output_file])
                util.subshell(['chmod', '+w', output_file])
            # On error, remove cached file, and re-download.
            if not skip_sha_check:
                if not util.check_sha(sha, output_file, do_throw=False):
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
                self.download_file_direct(sha, cache_path)
                # Make cache file read-only.
                util.subshell(['chmod', '-w', cache_path])
            # Use cached file - `get_download()` has already checked the sha.
            get_cached(skip_sha_check=True)

        # Check if we need to download.
        if use_cache:
            cache_path = self.package.get_sha_cache_path(sha, create_dir=True)
            util.wait_file_read_lock(cache_path)
            if os.path.isfile(cache_path):
                get_cached()
                return 'cached'
            else:
                get_download_and_cache()
                return 'download'
        else:
            self.download_file_direct(sha, output_file)
            return 'download'

    def upload_file(self, filepath):
        """ Uploads a file (only if it does not already exist in this remote - NOT the backend),
        and updates the corresponding SHA file. """
        sha = util.compute_sha(filepath)
        if self._backend.has_file(sha):
            print("File already uploaded")
        else:
            self._backend.upload_file(sha, filepath)
        return sha


class Package(object):
    """ Provides a hierarchy of remotes for incorporating data from multiple sources. """
    def __init__(self, config, project, parent):
        self._project = project
        self.parent = parent
        remote_name = config['remote']

        self._remotes_config = config['remotes']
        self._remotes = {}
        self._remote_is_loading = []

        self.config = config  # For debugging.

        # Get selected remote for this package.
        self.remote = self.load_remote(remote_name)

    def _has_remote(self, name):
        return name in self._remotes or name in self._remotes_config

    def load_backend(self, backend_type, config):
        """ @see Project.load_backend """
        return self._project.load_backend(backend_type, config)

    def load_remote(self, name):
        """ Load a remote for the given package. 
        If the remote does not exist in the given package, the parent packages will be checked.
        If ".." is specified, then the selected remote for the parent package will be returned. """
        if name == '..':
            assert self.parent, "Attempting to access parent remote at root package?"
            return self.parent.remote
        if not self._has_remote(name):
            # Use parent if this package does not contain the desired remote.
            if self.parent:
                self.parent.load_remote(name)
            else:
                raise RuntimeError("Unknown remote '{}'".format(name))
        # On-demand remote retrieval, with robustness against cycles.
        if name in self._remotes:
            return self._remotes[name]
        else:
            # Check against dependency cycles.
            if name in self._remote_is_loading:
                raise RuntimeError("'remote' cycle detected: {}".format(self._remote_is_loading))
            self._remote_is_loading.append(name)
            remote_config = self._remotes_config[name]
            # Load remote.
            remote = Remote(remote_config, name, self)
            # Update.
            self._remote_is_loading.remove(name)
            self._remotes[name] = remote
            return remote

    def get_sha_cache_path(self, sha, create_dir=False):
        """ Get the cache path for a given SHA file for the given package.
        Presently, this uses `Project.user.cache_dir`. """
        # TODO(eric.cousineau): Consider enabling multiple tiers of caching (for temporary stuff) according to remotes.
        a = sha[0:2]
        b = sha[2:4]
        out_dir = os.path.join(self._project.user.cache_dir, a, b)
        if create_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        return os.path.join(out_dir, sha)


class User(object):
    """ Stores user-level configuration (including backend-specifics, if needed). """
    def __init__(self, config):
        self.config = config
        self.cache_dir = os.path.expanduser(config['core']['cache_dir'])


class Project(object):
    """ Specifies a project's structure, caches packages (and remotes), and determines the mapping
    between files and their packages / remotes (for download / uploading). """
    def __init__(self, config, user, setup):
        self.config = config
        self.user = user
        self.setup = setup

        # Register backends.
        self._backends = self.setup.get_backends()

        # Load project-specific settings.
        self.name = self.config['name']
        self.root = self.config['root']
        self._root_alternatives = self.config.get('root_alternatives', [])

        # Set up for root package.
        self._packages = {}
        self.root_package = None

    def init_root_package(self, package_config):
        """ Initializes the root package for a project.
        Must be called close to the project being initialized. """
        assert self.root_package is None
        self.root_package = Package(package_config, self, None)
        config_file_rel = self.config.get('config_file', '<project>')
        self._packages[config_file_rel] = self.root_package

    def debug_dump_user_config(self):
        """ Returns the user settings configuration. """
        return self.user.config

    def debug_dump_config(self):
        """ Returns the project configuration. """
        return self.config

    def _get_remote_config_file(self, remote):
        package_file = util.find_key(self._packages, remote.package)
        assert package_file is not None
        return package_file

    def debug_dump_remote_config(self, remote):
        """ For each remote, print its configuration, relative project path, and its overlays. """
        base = {}
        node = base
        while remote:
            config_file = self._get_remote_config_file(remote)
            config = {remote.name: remote.config}
            node.update(config_file=config_file, config=config)
            remote = remote.overlay
            if remote:
                parent = node
                node = {}
                parent['overlay'] = node
            else:
                break
        return base

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

    def get_canonical_path(self, filepath):
        """ Get filepath as an absolute path, ensuring that it is with respect to the canonical project root.
        @ note This should be reading operations only! """
        relpath = self.get_relpath(filepath)
        return os.path.join(self.root, relpath)

    def load_backend(self, backend_type, config):
        """ Load the backend of a given type. """
        backend_cls = self._backends[backend_type]
        return backend_cls(config, self)

    def _load_package(self, filepath):
        """ Load the package for the given filepath. """
        config_files = self.setup.get_package_config_files(self, filepath)
        package = self.root_package
        for config_file in config_files:
            config_file_rel = self.get_relpath(config_file)
            parent = package
            package = self._packages.get(config_file_rel)
            if package is None:
                # Parse the package config file.
                config = config_helpers.parse_config_file(config_file)
                # Load package.
                package = Package(config['package'], self, parent)
                self._packages[config_file_rel] = package
        return package

    def load_remote(self, filepath):
        """ Load remote for a given file to either fetch or push a file """
        return self._load_package(filepath).remote

    def load_remote_command_line(self, remote_config, start_dir=None):
        """ Load a remote from the command-line (e.g. specifying a URL). """
        # TODO(eric.cousineau): As an alternative, consider keeping file-specific items
        # also in the configuration, akin to `.gitattributes` (possibly supporting fnmatch / globs).
        # For now, that's redundant w.r.t. Bazel's abilities.
        file_name = '<command_line>'
        remote_name = 'command_line'
        assert file_name not in self._packages
        if start_dir is None:
            parent = self.root_package
        else:
            parent = self._load_package(start_dir)
        package_config = {
            'remote': remote_name,
            'remotes': {
                remote_name: remote_config,
            },
        }
        package = Package(package_config, self, parent)
        self._packages[file_name] = package
        return package.remote


class ProjectSetup(object):
    """ Specifies how configuration is loaded for a project. """
    def __init__(self):
        self.config_file_name = CONFIG_FILE_DEFAULT
        self.sentinel = {'file': SENTINEL_DEFAULT}
        self.relpath = ''

    def load_config(self, guess_filepath):
        """ Load the project and user configuration from a given filepath.
        @param guess_filepath Initial guess at a filepath.
        @return root_config (dict), user_config (dict)
        """
        # Start guessing where the project lives.
        project_root, root_alternatives = config_helpers.find_project_root_bazel(guess_filepath, self.sentinel, self.relpath)
        # Load configuration.
        project_config_file = os.path.join(project_root, os.path.join(project_root, self.config_file_name))
        root_config = config_helpers.parse_config_file(project_config_file)
        # Inject project information.
        root_config['project']['root'] = project_root
        root_config['project']['config_file'] = self.config_file_name  # Relative path.
        if root_alternatives is not None:
            # Cache symlink root, and use this to get relative workspace path if the file is specified in
            # the symlink'd directory (e.g. Bazel runfiles).
            root_config['project']['root_alternatives'] = root_alternatives
        # Can augment `user_config` with project-specific settings, if needed.
        user_config_default = {
            "core": {
                "cache_dir": CACHE_DIR_DEFAULT,
            },
        }
        user_config = config_helpers.parse_config_file(USER_CONFIG_FILE_DEFAULT, user_config_default)
        return root_config, user_config

    def get_backends(self):
        """ Get backends specific to be used in this project setup. """
        from bazel_external_data.backends import get_default_backends
        return get_default_backends()

    def get_package_config_files(self, project, filepath_in):
        """ Get all package's config files for a given filepath.
        This permits specifying a hierarchy of packages. """
        filepath = project.get_canonical_path(filepath_in)
        start_dir = config_helpers.guess_start_dir(filepath)
        return config_helpers.find_package_config_files(project.root, start_dir, self.config_file_name)


def load_project(guess_filepath):
    """ Load a project given the injected `bazel_external_data_config` module.
    @param guess_filepath
        Filepath where to start guessing where the project root is.
    @return A `Project` instance.
    @see test/bazel_external_data_config
    """
    import bazel_external_data_config as custom
    setup = custom.get_setup()
    root_config, user_config = setup.load_config(guess_filepath)
    user = User(user_config)
    project = Project(root_config['project'], user, setup)
    project.init_root_package(root_config['package'])
    return project
