# This file should be executed by `core.load_project`. Check our files.
# We wish to ensure that these are executed 

import os

tgt_dir = "/tmp/external_data_bazel"
if not os.path.isdir(tgt_dir):
    os.path.makedirs(tgt_dir)
# Signal that we executed this file.
with open(os.path.join(tgt_dir, 'config_was_run'), 'w') as f:
    f.write('1')

assert __file__.endswith('/tools/external_data_config.py')
assert __module__ is None
assert os.path.isdir(__project_root__)
