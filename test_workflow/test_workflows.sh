#!/bin/bash

# Follow `WORKFLOWS.md`
pwd
cd test_workflow
ls -l
cd test_mock

bazel run //:test_basics

# 1. Create file for development.

# 2. etc.
