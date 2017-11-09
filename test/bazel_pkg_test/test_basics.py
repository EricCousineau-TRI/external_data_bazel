#!/usr/bin/env python

import os
import unittest

class TestBasics(unittest.TestCase):
    def test_files(self):
        with open('data/direct.bin') as f:
            contents = f.read()
        contents_expected = "Content for 'direct.bin'\n"
        self.assertEquals(contents, contents_expected)


if __name__ == '__main__':
    unittest.main()
