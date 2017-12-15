from external_data_bazel.backends.mock import MockBackend


def _get_core_backends():
    return {
        "mock": MockBackend,
    }


def get_default_backends():
    """ Get all available backends provided via `external_data_bazel`. """
    # TODO: Use `update_unique` to check for duplication?
    backends = _get_core_backends()
    try:
        from external_data_bazel.backends import girder
        backends.update(girder.get_backends())
    except ImportError:
        pass

    return backends
