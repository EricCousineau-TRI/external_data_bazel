from __future__ import absolute_import, print_function
import os
import subprocess
import sys
import json
import time
import yaml

# TODO: Rename `Project` -> `Workspace`
# TODO: Rename `Scope` -> `Package`

# TODO(eric.cousineau): If `girder_client` is sufficiently lightweight, we can make this a proper Bazel
# dependency.
# If it's caching mechanism is efficient and robust against Bazel, we should use that as well.

# TODO(eric.cousineau): For testing development files, we could have an `overlay` remote.
# TODO(eric.cousineau): Could this be used for a mirroring / redundancy setup?

cur_dir = os.path.dirname(__file__)
SHA_SUFFIX = '.sha512'

# TODO(eric.cousineau): Make a hashing setup, that defines a key for the algorithm, a suffix,
# and a computation / check method.

def compute_sha(filepath):
    sha = subshell(['sha512sum', filepath]).split(' ')[0]
    return sha

def check_sha(sha_expected, filepath, do_throw=True):
    sha = compute_sha(filepath)
    if sha != sha_expected:
        if do_throw:
            raise RuntimeError("SHA-512 mismatch: {} != {} for {}".format(sha, sha_expected, filepath))
        else:
            return False
    else:
        return True

def get_backends():
    return {
        "girder": GirderBackend,
        "direct": DirectBackend,
    }

# TODO: Cache fake Bazel root, and use this to get relative workspace path.

class ProjectSetup(object):
    def __init__(self):
        pass

    def get_config(self, filepath, sentinel={'file': 'WORKSPACE'}):
        # NOTE: This may not work if Bazel places the file in a symlink'd directory...
        start_dir = guess_start_dir(filepath)
        # ^ Alternative: Guess project_root and do symlink interface,
        # then try to guess start_dir.
        project_root = find_project_root(start_dir, sentinel)
        project_config_files = find_project_config_files(project_root, start_dir)
        project_config = parse_and_merge_config_files(project_root, project_config_files)
        return project_config

    def get_backends(self):
        return get_backends()

    def get_scope_config_files(self, project_root, filepath):
        start_dir = guess_start_dir(filepath)
        return find_scope_config_files(project_root, start_dir)


def load_project(filepath):
    # Use custom import to allow modular configuration.
    # See 'test/bazel_external_data_config'
    import bazel_external_data_config as custom
    setup = custom.get_setup()
    config = setup.get_config(filepath)
    project = Project(setup, config)
    return project


class Core(object):
    def __init__(self, config_node):
        self.cache_dir = os.path.expanduser(config_node['cache_dir'])

def _merge_unique(base, new):
    # Merge, ensuring there are no shared keys.
    old_keys = set(base.keys())
    new_keys = set(new.keys())
    # Ensure there is no intersection.
    assert new_keys - old_keys == new_keys
    base.update(new)

# Compatibility shim.
util = sys.modules[__name__]


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

def find_key(d, value):
    # https://stackoverflow.com/questions/8023306/get-key-by-value-in-dictionary
    if value in d.values():
        return d.keys()[d.values().index(value)]
    else:
        return None

class Project(object):
    def __init__(self, setup, root_config):
        self.setup = setup
        self.core = Core(root_config['core'])
        self.root_config = root_config

        config_node = root_config['project']
        self.name = config_node['name']
        self.root = config_node['root']

        # Register backends.
        self._backends = {}
        self.register_backends(self.setup.get_backends())
        # Create root scope and parse base remotes.
        self._scopes = {}
        self.root_scope = Scope(self, root_config['scope'], None)
        self._scopes['<project config>'] = self.root_scope

    def debug_dump_config(self, f = None):
        # TODO: What about a given Scope node?
        return yaml.dump(self.root_config, f, default_flow_style=False)

    def debug_dump_remote(self, remote, f = None, dump_all = False):
        scope = remote.scope
        # For each scope, print its respective filepath.
        scope_dump = []
        while scope is not None:
            scope_file = find_key(self._scopes, scope)
            scope_dump.append({'filepath': scope_file, 'value': scope.config_node})
            if dump_all or scope.remote.has_parent_overlay():
                scope = scope.parent
            else:
                break
        return yaml.dump({'scopes': scope_dump}, f, default_flow_style=False)

    def register_backends(self, backends):
        _merge_unique(self._backends, backends)

    def load_backend(self, backend_type, config_node):
        backend_cls = self._backends[backend_type]
        return backend_cls(self, config_node)

    def load_scope(self, filepath):
        config_files = self.setup.get_scope_config_files(self.root, filepath)
        scope = self.root_scope
        for config_file in config_files:
            parent = scope
            scope = self._scopes.get(config_file)
            if scope is None:
                # Parse the scope config file.
                config = _parse_config_file(config_file)
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
        scope = util.Scope(self, scope_config, parent)
        self._scopes[file_name] = scope
        return scope.remote


class DownloadError(RuntimeError):
    pass

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
                if not check_sha(sha, output_file, do_throw=False):
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
            check_sha(sha, output_file)

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
        sha = compute_sha(filepath)
        if self._backend.has_file(sha):
            print("File already uploaded")
        else:
            self._backend.upload_file(sha, filepath)
        return sha




class Backend(object):
    def __init__(self, project, config_node):
        self.project = project

    def has_file(self, sha):
        raise NotImplemented()

    def download_file(self, sha, output_path):
        raise RuntimeError("Downloading not supported for this backend")

    def upload_file(self, sha, filepath):
        raise RuntimeError("Uploading not supported for this backend")


def get_chain(value, key_chain, default=None):
    for key in key_chain:
        if value is None:
            return default
        value = value.get(key)
    return value


def reduce_url(url_full):
    begin = '['
    end = '] '
    if url_full.startswith(begin):
        # Scan until we find '] '
        fin = url_full.index(end)
        url = url_full[fin + len(end):]
    else:
        url = url_full
    return url


def curl(args):
    try:
        return subshell("curl {}".format(args))
    except subprocess.CalledProcessError as e:
        # Assume any error is just due to downloading.
        raise DownloadError(e)


class GirderBackend(Backend):
    def __init__(self, project, config_node):
        Backend.__init__(self, project, config_node)

        url_full = config_node['url']
        self._url = reduce_url(url_full)
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
        first_line = subshell('curl -s --head {args} | head -n 1'.format(args=args))
        if first_line == "HTTP/1.1 404 Not Found":
            return False
        elif first_line == "HTTP/1.1 303 See Other":
            return True
        else:
            raise RuntimeError("Unknown response: {}".format(first_line))

    def download_file(self, sha, output_file):
        args = self._download_args(sha)
        curl("-L --progress-bar -o {output_file} {args}".format(args=args, output_file=output_file))

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
        curl('-L -o {output_file} {url}'.format(url=self._url, output_file=output_file))

guess_at_end = True

if not guess_at_end:

    def guess_start_dir(filepath):
        if os.path.islink(filepath):
            # If this is a link to *.sha512, assume we're in Bazel land, and attempt to resolve the link.
            filepath = os.readlink(filepath)
            assert os.path.isabs(filepath)
        if os.path.isdir(filepath):
            start_dir = filepath
        else:
            start_dir = os.path.dirname(filepath)
        return start_dir

    def find_project_root(start_dir, sentinel):
        root_file = find_file_sentinel(start_dir, sentinel['file'], file_type=sentinel.get('type', 'any'))
        return os.path.dirname(root_file)

else:

    def guess_start_dir(filepath):
        if os.path.isdir(filepath):
            return filepath
        else:
            return os.path.dirname(filepath)

    def find_project_root(start_dir, sentinel):
        # Ideally, it'd be nice to just use `git rev-parse --show-top-level`.
        # However, because Bazel does symlink magic that is not easily parseable,
        # we should not rely on something like `symlink -f ${file}`, because
        # if a directory is symlink'd, then we will go to the wrong directory.
        # Instead, we should just do one `readlink` on the sentinel, and expect
        # that it is not a link.
        # Alternatives:
        #  (1) Custom `.project-root` sentinel. Fine, but useful for accurate versioning,
        # which is the entire point of `.project-root`.
        #  (2) `.git` - What we really want, just need to make sure Git sees this.
        root_file = find_file_sentinel(start_dir, sentinel['file'], file_type=sentinel.get('type', 'any'))
        if os.path.islink(root_file):
            root_file = os.readlink(root_file)
            assert os.path.isabs(root_file)
            if os.path.islink(root_file):
                raise RuntimeError("Sentinel '{}' should only have one level of an absolute-path symlink.".format(sentinel))
        return os.path.dirname(root_file)

CONFIG_FILE = ".bazel_external_data.yml"
USER_CONFIG = os.path.expanduser("~/.config/bazel_external_data/config.yml")

def _is_child_path(child_path, parent_path):
    rel_path = os.path.relpath(child_path, parent_path)
    return not rel_path.startswith('..' + os.path.sep)

def find_scope_config_files(project_root, start_dir, config_file = CONFIG_FILE):
    assert _is_child_path(start_dir, project_root)
    config_files = []
    cur_dir = start_dir
    while cur_dir != project_root:
        test_path = os.path.join(cur_dir, config_file)
        if os.path.isfile(test_path):
            config_files.insert(0, test_path)
        cur_dir = os.path.dirname(cur_dir)
    return config_files


def find_project_config_files(project_root, start_dir,
                              config_file = CONFIG_FILE,
                              optional_extras = [USER_CONFIG]):
    config_paths = []
    for extra in optional_extras:
        if os.path.isfile(extra):
            config_paths.append(extra)
    # At project root, we *must* have a config file.
    project_config_path = os.path.join(project_root, config_file)
    assert os.path.isfile(project_config_path), "Must specify project config"
    config_paths.append(project_config_path)
    return config_paths


def _parse_config_file(config_file):
    with open(config_file) as f:
        config = yaml.load(f)
    return config


def _merge_config(base_config, new_config):
    for key, new_value in new_config.iteritems():
        base_value = base_config.get(key)
        if isinstance(base_value, dict):
            assert isinstance(new_value, dict), "New value must be dict: {} - {}".format(key, new_value)
            # Recurse.
            value = _merge_config(base_value, new_value)
        else:
            # Overwrite.
            value = new_value
        base_config[key] = value
    return base_config


def parse_and_merge_config_files(project_root, config_files):
    # Define base-level configuration (for defaults and debugging).
    config = {
        "core": {
            "cache_dir": "~/.cache/bazel_external_data",
        },
        "project": {
            "root": project_root,
            "config_files": config_files,
        },
    }
    # Parse all config files.
    for config_file in config_files:
        new_config = _parse_config_file(config_file)
        # TODO(eric.cousineau): Add checks that we have desired keys, e.g. only one project name, etc.
        _merge_config(config, new_config)
    return config


# --- General Utilities ---

def _lock_path(filepath):
    return filepath + ".lock"

def wait_file_read_lock(filepath, timeout=60, interval=0.01):
    lock = _lock_path(filepath)
    if os.path.isfile(lock):
        now = time.time()
        while os.path.isfile(lock):
            time.sleep(interval)
            elapsed = time.time() - now
            if elapsed > timeout:
                raise RuntimeError("Timeout at {}s when attempting to acquire lock: {}".format(timeout, lock))

class FileWriteLock(object):
    def __init__(self, filepath):
        self.lock = _lock_path(filepath)
    def __enter__(self):
        if os.path.isfile(self.lock):
            raise RuntimeError("Lock already acquired? {}".format(self.lock))
        # Touch the file.
        with open(self.lock, 'w') as f:
            pass
    def __exit__(self, *args):
        assert os.path.isfile(self.lock)
        os.remove(self.lock)

def find_file_sentinel(start_dir, sentinel_file, file_type='file', max_depth=6):
    cur_dir = start_dir
    if file_type == 'file':
        file_test = os.path.isfile
    elif file_type == 'dir':
        file_test = os.path.isdir
    elif file_type == 'any':
        file_test = os.path.exists
    else:
        raise RuntimeError("Internal error: Invalid file_type {}".format(file_type))
    assert len(cur_dir) > 0
    for i in xrange(max_depth):
        assert os.path.isdir(cur_dir)
        test_path = os.path.join(cur_dir, sentinel_file)
        if file_test(test_path):
            return test_path
        cur_dir = os.path.dirname(cur_dir)
        if len(cur_dir) == 0:
            break
    raise RuntimeError("Could not find project root")


def subshell(cmd, strip=True):
    output = subprocess.check_output(cmd, shell=isinstance(cmd, str))
    if strip:
        return output.strip()
    else:
        return output

def subshellc(cmd, strip=True):
    try:
        return subshell(cmd, strip)
    except subprocess.CalledProcessError as e:
        return None


def runc(cmd, input):
    PIPE = subprocess.PIPE
    p = subprocess.Popen(cmd, shell=isinstance(cmd, str), stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate(input)
    return (p.returncode, output, err)

def run(cmd, input):
    out = run(cmd, input)
    if out[0] != 0:
        raise subprocess.CalledProcessError(p.returncode, cmd, err)

def eprint(*args):
    print(*args, file=sys.stderr)
