import os
from external_data_bazel import util

# TODO(eric.cousineau): `HashType` and `Hash` interfaces are too tightly bound to
# `HashFileFrontend`. Delegate these mechanisms back.
# Specifically, just have `HashType` return its name, and let the `HashFileFrontend`
# figure out how to get the hash / original file.

class HashType(object):
    def __init__(self, name):
        self.name = name

    def compute(self, filepath):
        if not os.path.exists(filepath):
            raise RuntimeError("File does not exist: {}".format(filepath))
        assert os.path.isabs(filepath)
        value = self.do_compute(filepath)
        return self.create(value, filepath)

    def do_compute(self, filepath):
        """ Return a type that can be compared via == (e.g. a string, or tuple (for size + sha)). """
        raise NotImplemented

    def create(self, value, filepath=None):
        return Hash(self, value, filepath=filepath)

    def create_empty(self):
        return Hash(self, None)

    def get_hash_file(self, orig_file):
        """ Get hash file from an original file. """
        raise NotImplemented

    def get_orig_file(self, hash_file):
        """ Get original file from a hash file.
        @return Original path, or None if this file is not related to this hash. """
        raise NotImplemented

    def read_file(self, hash_file):
        """ Return a Hash from a file. """
        orig_file = self.get_orig_file(hash_file)
        assert orig_file is not None
        value = self.do_read_file(hash_file)
        return self.create(value, filepath="hash_file[{}]".format(hash_file))

    def write_file(self, hash_file, hash):
        value = hash.get_value()
        with open(hash_file, 'w') as f:
            f.write(value + "\n")

    def do_read_file(self, hash_file):
        """ Read contents from a file. """
        with open(hash_file) as f:
            value = f.read().strip()
        return value

    def get_value(self, value):
        return value

    def __str__(self):
        return "hash[{}]".format(self.name)


class Hash(object):
    """ Store hash value, type, and possibly the filepath the hash was generated from. """
    def __init__(self, hash_type, value, filepath=None):
        self.hash_type = hash_type
        self.filepath = filepath
        self._value = value

    def compute(self, filepath):
        # Compute hash for a filepath, using the same type as this hash.
        return self.hash_type.compute(filepath)

    def check(self, other_hash, do_throw=True):
        if other_hash.hash_type == self.hash_type and self._value == other_hash._value:
            return True
        else:
            if do_throw:
                raise RuntimeError("Hash mismatch: {} != {}".format(self.full_str(), other_hash.full_str()))

    def check_file(self, filepath, do_throw=True):
        return self.check(self.compute(filepath), do_throw=do_throw)

    def has_value(self):
        return self._value is not None

    def get_value(self):
        return self.hash_type.get_value(self._value)

    def get_algo(self):
        return self.hash_type.name

    def write_hash_file(self):
        assert self.has_value()
        # This *has* to have been computed from a file.
        assert self.filepath is not None
        hash_file = self.hash_type.get_hash_file(self.filepath)
        self.hash_type.write_file(hash_file, self)

    def __str__(self):
        return "{}:{}".format(self.hash_type.name, self._value)

    def __eq__(self, rhs):
        return self.check(rhs, do_throw=False)

    def __hash__(self):
        # Do not permit empty hashes to be used in a dict.
        assert self.has_value()
        params = (self.hash_type, self._value)
        return hash(params)

    def __ne__(self, rhs):
        return not self.__eq__(rhs)

    def full_str(self):
        out = str(self)
        if self.filepath:
            out += " (file: {})".format(self.filepath)
        return out


class Sha512(HashType):
    _SUFFIX = '.sha512'

    def __init__(self):
        HashType.__init__(self, 'sha512')

    def do_compute(self, filepath):
        value = util.subshell(['sha512sum', filepath]).split(' ')[0]
        return value

    def get_hash_file(self, orig_file):
        return orig_file + self._SUFFIX

    def get_orig_file(self, hash_file):
        if not hash_file.endswith(self._SUFFIX):
            return None
        else:
            return hash_file[:-len(self._SUFFIX)]

sha512 = Sha512()

hash_types = [sha512]

if __name__ == "__main__":
    tmp_file = '/tmp/test_hash_file'
    with open(tmp_file, 'w') as f:
        f.write('Example contents\n')
    hash = sha512.compute(tmp_file)

    value_expected = '7f3f25018046549d08c6c9c97808e344aee60071164789a2077a5e34f4a219e45b4f30bc671dc71d2f05d05cec9235a523ebba436254a2b0b3b794f0afd9a7c3'
    hash_expected = sha512.create(value_expected)
    str_expected = 'sha512:{}'.format(value_expected)

    assert hash_expected.check(hash)
    assert hash_expected == hash

    str_actual = str(hash)
    print(str_actual)
    print(hash)
    print(hash.__dict__)
    assert str_actual == str_expected

    try:
        hash_bad = sha512.create('blech')
        hash.check(hash_bad)
        assert False
    except RuntimeError as e:
        print(e)
    assert hash != hash_bad
