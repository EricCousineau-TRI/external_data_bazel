#!/usr/bin/env python
import os

from bazel_external_data import util

class CustomSetup(util.ProjectSetup):
    def get_config(self, filepath):
        sentinel = {'file': '.custom-sentinel'}
        return util.ProjectSetup.get_config(self, filepath, sentinel=sentinel)

def get_setup():
    return CustomSetup()
