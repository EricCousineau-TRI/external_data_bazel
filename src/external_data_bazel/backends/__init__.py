from external_data_bazel.backends.mock import MockBackend
from external_data_bazel.backends import girder


def get_default_backends():
    """ Get all available backends provided via `external_data_bazel`. """
    backends = {
        "mock": MockBackend,
    }
    backends.update(girder.get_backends())
    return backends
