#!/usr/bin/env python
import os

from bazel_external_data.base import ProjectSetup
from bazel_external_data import util

class CustomProjectSetup(ProjectSetup):
    def __init__(self):
        ProjectSetup.__init__(self)
        # Augment starting directory to `tools/`, since Bazel will start at the root otherwise.
        # Only necessary if the sentinel is not at the Bazel root.
        self.relpath = 'test'
        self.sentinel = {'file': '.custom-sentinel'}

def get_setup():
    return CustomProjectSetup()
