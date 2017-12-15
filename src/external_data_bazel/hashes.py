import os
from external_data_bazel import util


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
        return self._value

    def get_algo(self):
        return self.hash_type.name

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
    def __init__(self):
        HashType.__init__(self, 'sha512')

    def do_compute(self, filepath):
        value = util.subshell(['sha512sum', filepath]).split(' ')[0]
        return value


sha512 = Sha512()

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
