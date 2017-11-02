#!/bin/bash

# Follow `WORKFLOWS.md`
pwd
cd test_workflow
ls -l
ln -s .. bazel_external_data
mkdir test_mock
cp -r test_mock_orig/* test_mock/
cd test_mock

bazel run //:test_basics

# 1. Create file for development.

# 2. etc.
