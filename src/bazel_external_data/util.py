from __future__ import absolute_import, print_function
import os
import subprocess
import sys
import json
import time

# TODO(eric.cousineau): If `girder_client` is sufficiently lightweight, we can make this a proper Bazel
# dependency.
# If it's caching mechanism is efficient and robust against Bazel, we should use that as well.

# TODO(eric.cousineau): For testing development files, we could have an `overlay` remote.
# TODO(eric.cousineau): Could this be used for a mirroring / redundancy setup?

cur_dir = os.path.dirname(__file__)

# http://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/
class Bunch(dict):
    def __init__(self, **kw):
        dict.__init__(self, kw)
        self.__dict__ = self

class Config(Bunch):
    def __init__(self, project_root, remote=None, mode='download'):
        Bunch.__init__(self)
        self.project_root = project_root

        self.cache_dir = self._get_conf('core.cache-dir', os.path.expanduser("~/.cache/bazel-girder"))

        self.project_name = self._get_conf('project.name')
        if remote is None:
            self.remote = self._get_conf('project.remote')
        else:
            self.remote = remote

        self.server = self._get_conf('remote.{remote}.server'.format(**self))
        self.folder_id = self._get_conf('remote.{remote}.folder-id'.format(**self))
        self.api_url = "{server}/api/v1".format(**self)

        # TODO(eric.cousineau): Figure out download-only public access, but private push-only access.
        # Most likely can use something like `api-key` for push-only access, and `api-key-download` for
        # non-public access.
        self.api_key = None
        self.token = None

        self._girder_client = None

    def _get_conf(self, key, default=None):
        # TODO(eric.cousineau): 
        user_conf = os.path.expanduser("~/.girder.conf")
        project_conf = os.path.join(self.project_root, 'tools/external_data/girder/girder.repo.conf')
        d = dict(project_conf=project_conf, user_conf=user_conf, key=key)

        value = subshellc("git config -f {project_conf} {key}".format(**d))
        if value is not None:
            return value
        value = subshellc("git config -f {user_conf} {key}".format(**d))
        if value is not None:
            return value
        if default:
            return default
        else:
            raise RuntimeError(
                "Could not resolve config: '{key}' in these files:\n  '{project_conf}'\n  '{user_conf}'".format(**d))

    def authenticate(self):
        assert self.token is None
        self.api_key = self._get_conf('server.{server}.api-key'.format(**self))
        token_raw = subshell("curl -L -s --data key={api_key} {api_url}/api_key/token".format(**self))
        self.token = json.loads(token_raw)["authToken"]["token"]

    def authenticate_if_needed(self):
        if not self.is_authenticated():
            self.authenticate()

    def is_authenticated(self):
        return self.token is not None

    def get_girder_client(self):
        import girder_client
        assert self.is_authenticated()
        if self._girder_client is None:
            self._girder_client = girder_client.GirderClient(apiUrl=self.api_url)
            self._girder_client.authenticate(apiKey=self.api_key)
        return self._girder_client

def is_sha_uploaded(conf, sha):
    """ Returns true if the given SHA exists on the given server. """
    # TODO(eric.cousineau): Is there a quicker way to do this???
    # TODO(eric.cousineau): Check `folder_id` and ensure it lives in the same place?
    # This is necessary if we have users with the same file?
    # What about authentication? Optional authentication / public access?
    url = "{conf.api_url}/file/hashsum/sha512/{sha}/download".format(conf=conf, sha=sha)
    first_line = subshell(
        'curl -s -H "Girder-Token: {conf.token}" --head "{url}" | head -n 1'.format(conf=conf, url=url))
    if first_line == "HTTP/1.1 404 Not Found":
        return False
    elif first_line == "HTTP/1.1 303 See Other":
        return True
    else:
        raise RuntimeError("Unknown response: {}".format(first_line))


def get_sha_cache_path(conf, sha, create_dir=False):
    a = sha[0:2]
    b = sha[2:4]
    out_dir = os.path.join(conf.cache_dir, a, b)
    if create_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    return os.path.join(out_dir, sha)


def find_project_root(start_dir):
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
    sentinel = '.git'
    root_file = find_file_sentinel(start_dir, sentinel, file_type='any')
    if os.path.islink(root_file):
        root_file = os.readlink(root_file)
        assert os.path.isabs(root_file)
        if os.path.islink(root_file):
            raise RuntimeError("Sentinel '{}' should only have one level of an absolute-path symlink.".format(sentinel))
    return os.path.dirname(root_file)


# --- General Utilities ---

def _lock_path(filepath):
    return filepath + ".lock"

def wait_file_read_lock(filepath, timeout=60):
    timeout = 60
    lock = _lock_path(filepath)
    if os.path.isfile(lock):
        now = time.time()
        while os.path.isfile(lock):
            time.sleep(0.1)
            elapsed = time.time() - now
            if elapsed > timeout:
                raise RuntimeError()

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
