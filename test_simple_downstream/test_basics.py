#!/usr/bin/env python

import os

with open('external/test_simple/data/direct.bin') as f:
    contents = f.read()
contents_expected = "Content for 'direct.bin'\n"
assert contents == contents_expected

print("Expected contents")
