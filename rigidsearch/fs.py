import os
import errno
import hashlib

from rigidsearch.utils import chop_tail


def filename_to_path(filename, base):
    base = base.rstrip('/')
    if filename.startswith(base + '/'):
        filename = filename[len(base) + 1:]
    filename, chopped = chop_tail(filename, '/index.html')
    if not chopped:
        filename, _ = chop_tail(filename, '.html')
    return filename.decode('utf-8', 'replace')


def find_all_documents(base, ignore=None):
    """Finds all HTML documents on the path and returns them as a dictionary
    as a mapping of path to source filename.
    """
    rv = {}

    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [x for x in dirnames if x[:1] != '.']
        for filename in filenames:
            if filename.endswith('.html'):
                full_filename = os.path.join(dirpath, filename)
                path = filename_to_path(full_filename, base)
                if not ignore or path not in ignore:
                    rv[path] = full_filename

    return rv


def get_file_checksum(filename):
    try:
        with open(filename, 'rb') as f:
            h = hashlib.sha1()
            while 1:
                chunk = f.read(16384)
                if not chunk:
                    break
                h.update(chunk)
            return h.hexdigest()
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        return '0' * 40


def file_changed(filename, reference_checksum):
    checksum = get_file_checksum(filename)
    return checksum != reference_checksum
