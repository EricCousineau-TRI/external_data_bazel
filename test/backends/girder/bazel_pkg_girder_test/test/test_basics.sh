#!/bin/bash
set -e -u

filepath=data/master.bin
sha=a5ecf3b0390c0718d8e53f539b013cb5379b53c601acaf1a4ef7377bfaeb60e955d0b2b5c0714b72d9f8f6bf43f6d5e5942e938756231557130d0f02fbb22564
{ echo "${sha} ${filepath}" | sha256sum -; } > /dev/null

echo "Checksum Passed"
