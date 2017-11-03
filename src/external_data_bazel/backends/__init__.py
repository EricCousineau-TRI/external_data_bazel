from external_data_bazel.backends.general import UrlBackend, UrlTemplatesBackend
from external_data_bazel.backends.mock import MockBackend

# Do not import specific backends automagically.

# TODO(eric.cousineau): Consider implementing Git LFS protocol as a backend for pure
# Hash files (for migration, if needed).

# TODO(eric.cousineau): Given that Backend supports a `project_relpath`, consider adding
# git-lfs or git-annex clients as potential backends.

def _get_core_backends():
    return {
        "mock": MockBackend,
        "url": UrlBackend,
        "url_templates": UrlTemplatesBackend,
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
