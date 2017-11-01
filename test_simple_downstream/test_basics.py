#!/usr/bin/env python

import os
import unittest

class TestBasics(unittest.TestCase):
    def test_files(self):
        with open('external/test_simple/data/direct.bin') as f:
            contents = f.read()
        contents_expected = "Content for 'direct.bin'\n"
        assert contents == contents_expected


if __name__ == '__main__':
    unittest.main()
