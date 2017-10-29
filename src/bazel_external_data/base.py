import os

from bazel_external_data import util, config_helpers

SHA_SUFFIX = '.sha512'

# TODO: Rename `Project` -> `Workspace`
# TODO: Rename `Scope` -> `Package`

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
    def __init__(self, project, name, config_node, scope = None):
        self.project = project
        if scope:
            self.scope = scope
        else:
            self.scope = project.root_scope
        self.name = name
        backend_type = config_node['backend']
        self._backend = self.project.load_backend(backend_type, config_node)

        overlay_name = config_node.get('overlay')
        self._overlay = None
        if overlay_name is not None:
            self._overlay = self.scope.get_remote(overlay_name)

    def has_overlay(self):
        return self._overlay is not None

    def has_parent_overlay(self):
        # We should have not overlays that are descendants of this scope; only ancestors.
        return self.has_overlay() and self._overlay.scope != self.scope

    def has_file(self, sha, check_overlay=True):
        if self._backend.has_file(sha):
            return True
        elif check_overlay and self.has_overlay():
            return self._overlay.has_file(sha)

    def _download_file_direct(self, sha, output_path):
        # TODO: Make this more efficient...
        try:
            self._backend.download_file(sha, output_path)
        except DownloadError as e:
            if self.has_overlay():
                self._overlay.download_file(sha, output_path)
            else:
                # Rethrow
                raise e

    def _get_sha_cache_path(self, sha, create_dir=False):
        # TODO(eric.cousineau): Consider enabling multiple tiers of caching (for temporary stuff) according to remotes.
        a = sha[0:2]
        b = sha[2:4]
        out_dir = os.path.join(self.project.core.cache_dir, a, b)
        if create_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        return os.path.join(out_dir, sha)

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
            cache_path = self._get_sha_cache_path(sha, create_dir=True)
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
        if self._backend.has_file(sha):
            print("File already uploaded")
        else:
            self._backend.upload_file(sha, filepath)
        return sha


class Scope(object):
    def __init__(self, project, config_node, parent):
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

    def get_remote(self, name):
        if name == '..':
            assert self.parent, "Attempting to access parent remote at root scope?"
            return self.parent.remote
        if not self.has_remote(name):
            # Use parent if this scope does not contain the desired remote.
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
            remote = Remote(self._project, name, remote_node, scope=self)
            # Update.
            self._remote_is_loading.remove(name)
            self._remotes[name] = remote
            return remote


class Core(object):
    def __init__(self, config_node):
        self.cache_dir = os.path.expanduser(config_node['cache_dir'])


class Project(object):
    def __init__(self, setup, root_config):
        self.setup = setup
        self.core = Core(root_config['core'])
        self.root_config = root_config

        config_node = root_config['project']
        self.name = config_node['name']
        self.root = config_node['root']
        self._root_alternatives = config_node.get('root_alternatives', [])

        # Register backends.
        self._backends = {}
        self.register_backends(self.setup.get_backends())
        # Create root scope and parse base remotes.
        self._scopes = {}
        self.root_scope = Scope(self, root_config['scope'], None)
        self._scopes['<project config>'] = self.root_scope

    def debug_dump_config(self):
        # Should return copy for const-ness.
        return self.root_config

    def debug_dump_remote(self, remote, dump_all = False):
        scope = remote.scope
        # For each scope, print its respective filepath.
        scope_dump = []
        while scope is not None:
            scope_file = util.find_key(self._scopes, scope)
            scope_dump.append({'config_file': scope_file, 'config': scope.config_node})
            if dump_all or scope.remote.has_parent_overlay():
                scope = scope.parent
            else:
                break
        return scope_dump

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

    def load_scope(self, filepath):
        config_files = self.setup.get_scope_config_files(self, filepath)
        scope = self.root_scope
        for config_file in config_files:
            parent = scope
            scope = self._scopes.get(config_file)
            if scope is None:
                # Parse the scope config file.
                config = config_helpers.parse_config_file(config_file)
                # Load scope.
                scope = Scope(self, config['scope'], parent)
                self._scopes[config_file] = scope
        return scope

    def load_remote(self, filepath):
        """ Load remote for a given file to either fetch or push a file """
        return self.load_scope(filepath).remote

    def load_remote_command_line(self, remote_config, start_dir=None):
        file_name = '<command_line>'
        remote_name = 'command_line'
        assert file_name not in self._scopes
        if start_dir is None:
            parent = self.root_scope
        else:
            parent = self.load_scope(start_dir)
        scope_config = {
            'remote': remote_name,
            'remotes': {
                remote_name: remote_config,
            },
        }
        scope = Scope(self, scope_config, parent)
        self._scopes[file_name] = scope
        return scope.remote

class ProjectSetup(object):
    """ Extend this to change how configuration files are found for a project. """
    def __init__(self):
        self._symlink_root = None
        pass

    def get_config(self, guess_filepath, sentinel={'file': 'WORKSPACE'}, relpath=''):
        start_dir = config_helpers.guess_start_dir(guess_filepath)
        project_root, root_alternatives = config_helpers.find_project_root(start_dir, sentinel, relpath)
        project_config_files = config_helpers.find_project_config_files(project_root, start_dir)
        project_config = config_helpers.parse_and_merge_config_files(project_root, project_config_files)
        if root_alternatives is not None:
            # Cache symlink root, and use this to get relative workspace path if the file is specified in
            # the symlink'd directory (e.g. Bazel runfiles).
            project_config['project']['root_alternatives'] = root_alternatives
        return project_config

    def get_backends(self):
        from bazel_external_data.backends import get_default_backends
        return get_default_backends()

    def get_scope_config_files(self, project, filepath_in):
        filepath = project.get_canonical_path(filepath_in)
        start_dir = config_helpers.guess_start_dir(filepath)
        return config_helpers.find_scope_config_files(project.root, start_dir)


def load_project(filepath):
    # Use custom import to allow modular configuration.
    # See 'test/bazel_external_data_config'
    import bazel_external_data_config as custom
    setup = custom.get_setup()
    config = setup.get_config(filepath)
    project = Project(setup, config)
    return project
