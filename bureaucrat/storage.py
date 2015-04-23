"""Storage manages documents which constitute the engine's state."""

from __future__ import absolute_import

import logging
import os
import os.path
import fcntl

from bureaucrat.configs import Configs

LOG = logging.getLogger(__name__)
LOCK_FILE = '/tmp/bureaucrat-schedule.lock'

class StorageError(Exception):
    """Storage error."""

def lock_storage(func):
    """Decorator to lock storage."""

    def new_func(*args, **kwargs):
        """Wrapper function."""
        with open(LOCK_FILE, 'w') as fhdl:
            fcntl.lockf(fhdl, fcntl.LOCK_EX)
            result = func(*args, **kwargs)
            fcntl.lockf(fhdl, fcntl.LOCK_UN)
            return result
    return new_func

class Storage(object):
    """Singletone class representing file storage."""

    _instance = None
    _is_instantiated = False

    @classmethod
    def instance(cls):
        """Return storage instance."""

        cls._is_instantiated = True
        if cls._instance is None:
            instance = Storage()
            cls._instance = instance

        return cls._instance

    def __init__(self):
        """Initialize the instance."""

        if self._instance is not None or not self._is_instantiated:
            raise StorageError("Storage.instance() should be " + \
                               "used to get an instance")

        self._bucket_cache = []
        self.storage_dir = Configs.instance().storage_dir

        if not os.path.isdir(self.storage_dir):
            os.makedirs(self.storage_dir)

    def save(self, bucket, key, doc):
        """Save document in storage."""

        bucket_path = os.path.join(self.storage_dir, bucket)
        if not bucket in self._bucket_cache:
            if not os.path.exists(bucket_path):
                os.makedirs(bucket_path)
            self._bucket_cache.append(bucket)

        with open(os.path.join(bucket_path, key), 'w') as fhdl:
            fhdl.write(doc)

    def load(self, bucket, key):
        """Load document from storage."""

        bucket_path = os.path.join(self.storage_dir, bucket)
        doc_path = os.path.join(bucket_path, key)
        with open(doc_path) as fhdl:
            return fhdl.read()

    def delete(self, bucket, key):
        """Delete document from storage."""

        bucket_path = os.path.join(self.storage_dir, bucket)
        doc_path = os.path.join(bucket_path, key)
        os.unlink(doc_path)

    def keys(self, bucket):
        """Return list of keys in the bucket."""

        bucket_path = os.path.join(self.storage_dir, bucket)
        if os.path.isdir(bucket_path):
            return os.listdir(bucket_path)
        else:
            return []

    def exists(self, bucket, key):
        """Retrun true if key exists in bucket."""

        bucket_path = os.path.join(self.storage_dir, bucket)
        doc_path = os.path.join(bucket_path, key)
        return os.path.exists(doc_path)
