#!/bin/bash

# Adapted from Drake.

set -eu
set -x

die () {
    echo "$@" 1>&2
    exit 1
}

# Install the APT dependencies.
apt update -y
apt install --no-install-recommends $(tr '\n' ' ' <<EOF

bash-completion
g++
openjdk-8-jdk
zlib1g-dev

git
python-dev
python-yaml
wget
curl
zip

EOF
    )

# TODO(eric.cousineau): Figure out why wget cannot check the security certificate? What package is missing?

# Install Bazel.
wget --no-check-certificate -O /tmp/bazel_0.6.1-linux-x86_64.deb https://github.com/bazelbuild/bazel/releases/download/0.6.1/bazel_0.6.1-linux-x86_64.deb
if echo "5012d064a6e95836db899fec0a2ee2209d2726fae4a79b08c8ceb61049a115cd /tmp/bazel_0.6.1-linux-x86_64.deb" | sha256sum -c -; then
  dpkg -i /tmp/bazel_0.6.1-linux-x86_64.deb
else
  die "The Bazel deb does not have the expected SHA256.  Not installing Bazel."
fi

rm /tmp/bazel_0.6.1-linux-x86_64.deb
