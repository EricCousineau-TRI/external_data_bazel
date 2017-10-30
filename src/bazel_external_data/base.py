import os

from bazel_external_data import util, config_helpers

SHA_SUFFIX = '.sha512'

# TODO: Rename `Project` -> `Workspace`

class Backend(object):
    def __init__(self, project, config_node):
        self.project = project

    def has_file(self, sha):
        raise NotImplemented()

    def download_file(self, sha, output_path):
        raise RuntimeError("Downloading not supported for this backend")

    def upload_file(self, sha, filepath):
        raise RuntimeError("Uploading not supported for this backend")


class Remote(object):
    def __init__(self, package, name, config_node):
        self.package = package
        self.config_node = config_node
        self.name = name
        backend_type = config_node['backend']
        self._backend = self.package.load_backend(backend_type, config_node)

        overlay_name = config_node.get('overlay')
        self.overlay = None
        if overlay_name is not None:
            self.overlay = self.package.get_remote(overlay_name)

    def has_overlay(self):
        return self.overlay is not None

    def has_file(self, sha, check_overlay=True):
        if self._backend.has_file(sha):
            return True
        elif checkoverlay and self.has_overlay():
            return self.overlay.has_file(sha)

    def _download_file_direct(self, sha, output_path):
        # TODO: Make this more efficient...
        try:
            self._backend.download_file(sha, output_path)
        except util.DownloadError as e:
            if self.has_overlay():
                self.overlay._download_file_direct(sha, output_path)
            else:
                # Rethrow
                raise e

    def download_file(self, sha, output_file,
                      use_cache = True, symlink_from_cache = True):
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
                    # `os.remove()` will remove read-only files, reguardless.
                    os.remove(cache_path)
                    if os.path.islink(output_file):
                        # In this situation, the cache was corrupted (somehow), and Bazel
                        # triggered a recompilation, and we still have a symlink in Bazel-space.
                        # Remove this symlink, so that we do not download into a symlink (which
                        # complicates the logic in `get_download_and_cache`). This also allows
                        # us to "reset" permissions.
                        os.remove(output_file)
                    get_download_and_cache()

        def get_download(output_file):
            self._download_file_direct(sha, output_file)
            util.check_sha(sha, output_file)

        def get_download_and_cache():
            with util.FileWriteLock(cache_path):
                get_download(cache_path)
                # Make cache file read-only.
                util.subshell(['chmod', '-w', cache_path])
            # Use cached file - `get_download()` has already checked the sha.
            get_cached(skip_sha_check=True)

        # TODO(eric.cousineau): Throw an error if the file already exists?

        # Check if we need to download.
        if use_cache:
            cache_path = self.package.get_sha_cache_path(sha, create_dir=True)
            util.wait_file_read_lock(cache_path)
            if os.path.isfile(cache_path):
                print("Using cached file")
                get_cached()
            else:
                get_download_and_cache()
        else:
            get_download(output_file)


    def upload_file(self, filepath):
        sha = util.compute_sha(filepath)
        if self._backend.has_file(sha, check_overlay=False):
            print("File already uploaded")
        else:
            self._backend.upload_file(sha, filepath)
        return sha


class Package(object):
    def __init__(self, config_node, project, parent):
        self._project = project
        self.parent = parent
        remote_name = config_node['remote']

        self.config_node = config_node  # For debugging.
        self._remotes_config = config_node['remotes']
        self._remotes = {}
        self._remote_is_loading = []

        self.remote = self.get_remote(remote_name)

    def has_remote(self, name):
        return name in self._remotes or name in self._remotes_config

    def load_backend(self, backend_type, config_node):
        return self._project.load_backend(backend_type, config_node)

    def get_remote(self, name):
        if name == '..':
            assert self.parent, "Attempting to access parent remote at root package?"
            return self.parent.remote
        if not self.has_remote(name):
            # Use parent if this package does not contain the desired remote.
            if self.parent:
                self.parent.get_remote(name)
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
            remote_node = self._remotes_config[name]
            # Load remote.
            remote = Remote(self, name, remote_node)
            # Update.
            self._remote_is_loading.remove(name)
            self._remotes[name] = remote
            return remote

    def get_sha_cache_path(self, sha, create_dir=False):
        # TODO(eric.cousineau): Consider enabling multiple tiers of caching (for temporary stuff) according to remotes.
        a = sha[0:2]
        b = sha[2:4]
        out_dir = os.path.join(self._project.core.cache_dir, a, b)
        if create_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        return os.path.join(out_dir, sha)


class Core(object):
    def __init__(self, config_node):
        self.cache_dir = os.path.expanduser(config_node['cache_dir'])


class Project(object):
    def __init__(self, config_node, user_config, setup):
        self.config_node = config_node
        self.user_config = user_config
        self.setup = setup

        self.core = Core(user_config['core'])

        sub_config = config_node['project']
        self.name = sub_config['name']
        self.root = sub_config['root']
        self._root_alternatives = sub_config.get('root_alternatives', [])

        # Register backends.
        self._backends = {}
        self.register_backends(self.setup.get_backends())

        # Create root package (parsing remotes).
        self._packages = {}
        self.root_package = Package(self.config_node['package'], self, None)
        self._packages[sub_config['config_file']] = self.root_package

    def debug_dump_config(self):
        # Should return copy for const-ness.
        return self.config_node

    def _get_remote_config_file(self, remote):
        package_file = util.find_key(self._packages, remote.package)
        assert package_file is not None
        if package_file.startswith('<'):
            return package_file
        else:
            return self.get_relpath(package_file)

    def debug_dump_remote(self, remote):
        # For each remote, print its respective filepath.
        base = {}
        node = base
        while remote:
            print(remote)
            config_file = self._get_remote_config_file(remote)
            config = {remote.name: remote.config_node}
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
        # Get filepath relative to project root, using alternatives.
        assert os.path.isabs(filepath)
        root_paths = [self.root] + self._root_alternatives
        # WARNING: This will not handle a nest root!
        # (e.g. if an alternative is a child or parent of another path)
        for root in root_paths:
            if util.is_child_path(filepath, root):
                return os.path.relpath(filepath, root)
        raise RuntimeError("Path is not a child of given project")

    def get_canonical_path(self, filepath):
        """ Get filepath as an absolute path, ensuring that it is with respect to the canonical project root """
        relpath = self.get_relpath(filepath)
        return os.path.join(self.root, relpath)

    def register_backends(self, backends):
        util.merge_unique(self._backends, backends)

    def load_backend(self, backend_type, config_node):
        backend_cls = self._backends[backend_type]
        return backend_cls(self, config_node)

    def load_package(self, filepath):
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
        return self.load_package(filepath).remote

    def load_remote_command_line(self, remote_config, start_dir=None):
        file_name = '<command_line>'
        remote_name = 'command_line'
        assert file_name not in self._packages
        if start_dir is None:
            parent = self.root_package
        else:
            parent = self.load_package(start_dir)
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
    """ Extend this to change how configuration files are found for a project. """
    def __init__(self):
        self.config_file_name = config_helpers.CONFIG_FILE_DEFAULT
        self.sentinel = sentinel={'file': 'WORKSPACE'}
        self.relpath = ''

    def load_config(self, guess_filepath):
        # Start guessing where the project lives.
        project_root, root_alternatives = config_helpers.find_project_root_bazel(guess_filepath, self.sentinel, self.relpath)
        # Load configuration.
        project_config_file = os.path.join(project_root, os.path.join(project_root, self.config_file_name))
        project_config = config_helpers.parse_config_file(project_config_file)
        # Inject project information.
        project_config['project']['root'] = project_root
        project_config['project']['config_file'] = self.config_file_name  # Relative path.
        if root_alternatives is not None:
            # Cache symlink root, and use this to get relative workspace path if the file is specified in
            # the symlink'd directory (e.g. Bazel runfiles).
            project_config['project']['root_alternatives'] = root_alternatives
        # Can augment `user_config` with project-specific settings, if needed.
        user_config = config_helpers.parse_user_config()
        return project_config, user_config

    def get_backends(self):
        from bazel_external_data.backends import get_default_backends
        return get_default_backends()

    def get_package_config_files(self, project, filepath_in):
        filepath = project.get_canonical_path(filepath_in)
        start_dir = config_helpers.guess_start_dir(filepath)
        return config_helpers.find_package_config_files(project.root, start_dir, self.config_file_name)


def load_project(guess_filepath):
    # Use custom import to allow modular configuration.
    # See 'test/bazel_external_data_config'
    import bazel_external_data_config as custom
    setup = custom.get_setup()
    project_config, user_config = setup.load_config(guess_filepath)
    return Project(project_config, user_config, setup)
