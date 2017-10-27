#!/usr/bin/env python
import os

from bazel_external_data import util

class CustomSetup(util.ProjectSetup):
    def get_project_config(self, filepath):
        sentinel = {'file': '.custom-sentinel'}
        util.ProjectSetup.get_project_config(self, filepath, sentinel=sentinel)

def get_setup():
    return CustomSetup()
