import os
import yaml
import copy

from external_data_bazel import util

# Helpers for configuration finding, specific to (a) general `external_data_bazel` configuration
# and (b) Bazel path obfuscation reversal within `external_data_bazel`.

def guess_start_dir(filepath):
    """ Guess the starting directory for a filepath.
    If it's a file, return the dirname of the file. Otherwise, just pass the directory through. """
    if os.path.isdir(filepath):
        return filepath
    else:
        return os.path.dirname(filepath)


def find_project_root(guess_filepath, sentinel):
    """ Finds the project root, accounting for oddities when in Bazel execroot-land.
    This will attempt to find the file sentinel.
    """
    start_dir = guess_start_dir(guess_filepath)
    root_file = util.find_file_sentinel(start_dir, sentinel['file'], file_type=sentinel.get('type', 'any'))
    # If our root_file is a symlink, then this should be due to a Bazel execroot.
    # Record the original directory as a possible alternative.
    root_alternatives = []
    if os.path.islink(root_file):
        # Assume that the root file is symlink'd because Bazel has linked it in.
        # Read this to get the original path.
        alt_root_file = os.readlink(root_file)
        assert os.path.isabs(alt_root_file)
        if os.path.islink(alt_root_file):
            raise RuntimeError("Sentinel '{}' should only have one level of an absolute-path symlink.".format(sentinel))
        # Ideally, we should be using `root_file` still as the original.
        # However, when testing, Bazel still expects us to declare each file.
        # Since we encounter bugs when attempting to declare all package files, then
        # we will resort to pulling directly from the file system (unfortunately).
        # TODO(eric.cousineau): When using each package file is no longer a bug,
        # remove this swap.
        (alt_root_file, root_file) = (root_file, alt_root_file)
        root_alternatives.append(os.path.dirname(alt_root_file))
    root = os.path.dirname(root_file)
    return (root, root_alternatives)


def find_package_config_files(project_root, start_dir, config_file):
    """ Find all package config files for a given directory in a project.
    This excludes the project-root config. """
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
    # Add project root package.
    test_path = os.path.join(cur_dir, config_file)
    assert os.path.isfile(test_path)
    config_files.insert(0, test_path)
    return config_files


def parse_config_file(config_file, add_filepath = True):
    """ Parse a configuration file.
    @param add_filepath
        Adds `config_file` to the root level for debugging purposes. """
    with open(config_file) as f:
        config = yaml.load(f)
    if add_filepath:
        config['config_file'] = config_file
    return config


def merge_config(base_config, new_config, in_place = False):
    if base_config is None:
        return new_config
    if not in_place:
        base_config = copy.deepcopy(base_config)
    if new_config is None:
        return base_config
    # Merge a configuration file.
    for key, new_value in new_config.iteritems():
        base_value = base_config.get(key)
        if isinstance(base_value, dict):
            assert isinstance(new_value, dict), "New value must be dict: {} - {}".format(key, new_value)
            # Recurse.
            value = merge_config(base_value, new_value, in_place=True)
        else:
            # Overwrite.
            value = new_value
        base_config[key] = value
    return base_config
