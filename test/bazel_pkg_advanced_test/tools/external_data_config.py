# This file should be executed by `core.load_project`. Check our files.
# We wish to ensure that these are executed 

import os

tmp_dir = "/tmp/external_data_bazel"
if not os.path.isdir(tmp_dir):
    os.makedirs(tmp_dir)
# Signal that we executed this file.
with open(os.path.join(tmp_dir, 'config_was_run'), 'w') as f:
    f.write('1')

assert __file__.endswith('/tools/external_data_config.py')
assert __module__ is None
assert os.path.isdir(__project_root__)
