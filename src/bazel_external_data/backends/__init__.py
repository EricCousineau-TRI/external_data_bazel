from bazel_external_data.backends.mock import MockBackend
from bazel_external_data.backends import girder


def get_default_backends():
    """ Get all available backends provided via `bazel_external_data`. """
    backends = {
        "mock": MockBackend,
    }
    backends.update(girder.get_backends())
    return backends
