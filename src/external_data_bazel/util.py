from __future__ import absolute_import, print_function
import os
import subprocess
import sys
import json
import time


def is_child_path(child_path, parent_path, require_abs=True):
    if require_abs:
        assert os.path.isabs(child_path) and os.path.isabs(parent_path)
    if not parent_path.endswith(os.path.sep):
        parent_path += os.path.sep
    return child_path.startswith(parent_path)


def in_bazel_runfiles(cur_dir=None, project=None):
    # Typically, Bazel runfiles is structured something like
    #   ${bazel_cache}/
    # This should catch if the user has called `bazel run ...`, but not if this command is
    # invoked by `bazel build ...` (or rather, that is called as a tool from a Bazel `genrule`).
    if cur_dir is None:
        cur_dir = os.getcwd()
    pieces = cur_dir.split(os.path.sep)
    if len(pieces) > 1:
        if pieces[-2].endswith('.runfiles'):
            # TODO: This may be overly constrained? This can produce false positives. Meh.
            if project is not None:
                return pieces[-1] == project
            else:
                return True
    return False


def merge_unique(core, new):
    # Merge, ensuring there are no shared keys.
    old_keys = set(core.keys())
    new_keys = set(new.keys())
    # Ensure there is no intersection.
    assert new_keys - old_keys == new_keys
    core.update(new)

def find_key(d, value):
    """ Find key by a the first occurrence of a value, or return None. """
    # https://stackoverflow.com/questions/8023306/get-key-by-value-in-dictionary
    if value in d.values():
        return d.keys()[d.values().index(value)]
    else:
        return None

class DownloadError(RuntimeError):
    pass

def get_chain(value, key_chain, default=None):
    for key in key_chain:
        if value is None:
            return default
        value = value.get(key)
    return value


def curl(args):
    try:
        return subshell("curl {}".format(args))
    except subprocess.CalledProcessError as e:
        # Assume any error is just due to downloading.
        raise DownloadError(e)

def _lock_path(filepath):
    return filepath + ".lock"

def wait_file_read_lock(filepath, timeout=60, interval=0.01, warn_at=2):
    lock = _lock_path(filepath)
    warned = False
    if os.path.isfile(lock):
        now = time.time()
        while os.path.isfile(lock):
            time.sleep(interval)
            elapsed = time.time() - now
            if elapsed > timeout:
                raise RuntimeError("Timeout at {}s when attempting to acquire lock: {}".format(timeout, lock))
            elif elapsed > warn_at and not warned:
                eprint("Waiting on lock file for a maximum of {}s:".format(timeout))
                eprint("  '{}'".format(lock))
                eprint("  If this persists, please consider removing this file.")
                warned = True

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

# TODO: Replace this with a more general sentinel with a callback on directory.
# This can be used to check project name as well.
def find_file_sentinel(start_dir, sentinel_file, file_type='file', max_depth=100):
    cur_dir = start_dir
    file_tests = {'any': os.path.exists, 'file': os.path.isfile, 'dir': os.path.isdir}
    file_test = file_tests[file_type]
    assert len(cur_dir) > 0
    for i in xrange(max_depth):
        assert os.path.isdir(cur_dir)
        test_path = os.path.join(cur_dir, sentinel_file)
        if file_test(test_path):
            return test_path
        cur_dir = os.path.dirname(cur_dir)
        if len(cur_dir) == 0:
            break
    raise RuntimeError("Could not find sentinel: {}".format(sentinel_file))


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

class TmpFileName(object):
        def __init__(self):
            pass
        def __enter__(self, *args):
            import tempfile
            self.filepath = tempfile.mkstemp()[1]
        def get_path(self):
            return self.filepath
        def __exit__(self, *args):
            os.unlink(self.filepath)
