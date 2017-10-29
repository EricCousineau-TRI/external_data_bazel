import os
import yaml

from bazel_external_data import util

CONFIG_FILE = ".bazel_external_data.yml"
USER_CONFIG = os.path.expanduser("~/.config/bazel_external_data/config.yml")

# Helpers for configuration finding, specific to (a) general `bazel_external_data` configuration
# and (b) Bazel path obfuscation reversal within `bazel_external_data`.

def guess_start_dir_bazel(guess_filepath, rel_path):
    # rel_path - Path of project root relative to Bazel workspace.
    if os.path.isdir(guess_filepath):
        guess_start_dir = guess_filepath
    else:
        guess_start_dir = os.path.dirname(guess_filepath)
    test_dir = os.path.join(guess_start_dir, rel_path)
    if os.path.isdir(test_dir):
        return test_dir
    else:
        return guess_start_dir

def is_bazel_cache_dir(filepath):
    # WARNING: This won't apply if the user changes it...
    return '/.cache/bazel/' in filepath

def guess_start_dir(filepath):
    if os.path.isdir(filepath):
        return filepath
    else:
        return os.path.dirname(filepath)

def find_project_root(start_dir, sentinel, relpath):
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
    root_file = util.find_file_sentinel(start_dir, sentinel['file'], file_type=sentinel.get('type', 'any'))
    root_alternatives = []
    if os.path.islink(root_file):
        old_root_dir = os.path.dirname(root_file)
        root_alternatives.append(old_root_dir)
        root_file = os.readlink(root_file)
        assert os.path.isabs(root_file)
        if os.path.islink(root_file):
            raise RuntimeError("Sentinel '{}' should only have one level of an absolute-path symlink.".format(sentinel))
    elif relpath and is_bazel_cache_dir(root_file):
        # Check up according to the relative path.
        old_root_dir = os.path.dirname(root_file)
        pieces = relpath.split('/')
        up_dir_rel = '/'.join(['..'] * len(pieces))
        execroot_dir = os.path.join(old_root_dir, up_dir_rel)
        # Change to potential bazel cache dir, and if the top-level piece is a symlink, assume that we should use that.
        if os.path.isdir(os.path.join(execroot_dir, 'bazel-out')):
            # We're in Bazel execroot. Normalize.
            first_dir = os.path.normpath(os.path.join(execroot_dir, pieces[0]))
            if os.path.islink(first_dir):
                extra = pieces[1:] + [sentinel['file']]
                root_file = os.path.join(os.readlink(first_dir), *extra)
                assert os.path.exists(root_file)
                root_alternatives.append(old_root_dir)
    root = os.path.dirname(root_file)
    return (root, root_alternatives)

def find_package_config_files(project_root, start_dir, config_file = CONFIG_FILE):
    assert os.path.isabs(start_dir)
    assert os.path.isabs(project_root)
    assert util.is_child_path(start_dir, project_root)
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


def parse_config_file(config_file):
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
        new_config = parse_config_file(config_file)
        # TODO(eric.cousineau): Add checks that we have desired keys, e.g. only one project name, etc.
        _merge_config(config, new_config)
    return config
