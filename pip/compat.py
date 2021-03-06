"""Stuff that differs in different Python versions and platform
distributions."""
from __future__ import absolute_import, division

import os
import sys
import codecs
import locale
import logging

from pip._vendor.six import text_type

try:
    import ipaddress
except ImportError:
    try:
        from pip._vendor import ipaddress
    except ImportError:
        import ipaddr as ipaddress
        ipaddress.ip_address = ipaddress.IPAddress
        ipaddress.ip_network = ipaddress.IPNetwork


__all__ = [
    "ipaddress", "uses_pycache", "console_to_str", "native_str",
    "get_path_uid", "stdlib_pkgs", "WINDOWS", "samefile",
]


logger = logging.getLogger(__name__)

if sys.version_info >= (3, 4):
    uses_pycache = True
    from importlib.util import cache_from_source
else:
    import imp
    uses_pycache = hasattr(imp, 'cache_from_source')
    if uses_pycache:
        cache_from_source = imp.cache_from_source
    else:
        cache_from_source = None


if sys.version_info >= (3, 5):
    backslashreplace_decode = "backslashreplace"
else:
    # In version 3.4 and older, backslashreplace exists
    # but does not support use for decoding.
    # We implement our own replace handler for this
    # situation, so that we can consistently use
    # backslash replacement for all versions.
    def backslashreplace_decode_fn(err):
        raw_bytes = (err.object[i] for i in range(err.start, err.end))
        if sys.version_info[0] == 2:
            # Python 2 gave us characters - convert to numeric bytes
            raw_bytes = (ord(b) for b in raw_bytes)
        return u"".join(u"\\x%x" % c for c in raw_bytes), err.end
    codecs.register_error(
        "backslashreplace_decode",
        backslashreplace_decode_fn)
    backslashreplace_decode = "backslashreplace_decode"


def console_to_str(data):
    """Return a string, safe for output, of subprocess output.

    We assume the data is in the locale preferred encoding.
    If it won't decode properly, we warn the user but decode as
    best we can.

    We also ensure that the output can be safely written to
    standard output without encoding errors.
    """

    # First, get the encoding we assume. This is the preferred
    # encoding for the locale, unless that is not found, or
    # it is ASCII, in which case assume UTF-8
    encoding = locale.getpreferredencoding()
    if (not encoding) or codecs.lookup(encoding).name == "ascii":
        encoding = "utf-8"

    # Now try to decode the data - if we fail, warn the user and
    # decode with replacement.
    try:
        s = data.decode(encoding)
    except UnicodeDecodeError:
        logger.warning(
            "Subprocess output does not appear to be encoded as %s" %
            encoding)
        s = data.decode(encoding, errors=backslashreplace_decode)

    # Make sure we can print the output, by encoding it to the output
    # encoding with replacement of unencodable characters, and then
    # decoding again.
    # We use stderr's encoding because it's less likely to be
    # redirected and if we don't find an encoding we skip this
    # step (on the assumption that output is wrapped by something
    # that won't fail).
    output_encoding = sys.__stderr__.encoding
    if output_encoding:
        s = s.encode(output_encoding, errors="backslashreplace")
        s = s.decode(output_encoding)

    return s


if sys.version_info >= (3,):
    def native_str(s, replace=False):
        if isinstance(s, bytes):
            return s.decode('utf-8', 'replace' if replace else 'strict')
        return s

else:
    def native_str(s, replace=False):
        # Replace is ignored -- unicode to UTF-8 can't fail
        if isinstance(s, text_type):
            return s.encode('utf-8')
        return s


def get_path_uid(path):
    """
    Return path's uid.

    Does not follow symlinks:
        https://github.com/pypa/pip/pull/935#discussion_r5307003

    Placed this function in compat due to differences on AIX and
    Jython, that should eventually go away.

    :raises OSError: When path is a symlink or can't be read.
    """
    if hasattr(os, 'O_NOFOLLOW'):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        file_uid = os.fstat(fd).st_uid
        os.close(fd)
    else:  # AIX and Jython
        # WARNING: time of check vulnerability, but best we can do w/o NOFOLLOW
        if not os.path.islink(path):
            # older versions of Jython don't have `os.fstat`
            file_uid = os.stat(path).st_uid
        else:
            # raise OSError for parity with os.O_NOFOLLOW above
            raise OSError(
                "%s is a symlink; Will not return uid for symlinks" % path
            )
    return file_uid


def expanduser(path):
    """
    Expand ~ and ~user constructions.

    Includes a workaround for http://bugs.python.org/issue14768
    """
    expanded = os.path.expanduser(path)
    if path.startswith('~/') and expanded.startswith('//'):
        expanded = expanded[1:]
    return expanded


# packages in the stdlib that may have installation metadata, but should not be
# considered 'installed'.  this theoretically could be determined based on
# dist.location (py27:`sysconfig.get_paths()['stdlib']`,
# py26:sysconfig.get_config_vars('LIBDEST')), but fear platform variation may
# make this ineffective, so hard-coding
stdlib_pkgs = {"python", "wsgiref", "argparse"}


# windows detection, covers cpython and ironpython
WINDOWS = (sys.platform.startswith("win") or
           (sys.platform == 'cli' and os.name == 'nt'))


def samefile(file1, file2):
    """Provide an alternative for os.path.samefile on Windows/Python2"""
    if hasattr(os.path, 'samefile'):
        return os.path.samefile(file1, file2)
    else:
        path1 = os.path.normcase(os.path.abspath(file1))
        path2 = os.path.normcase(os.path.abspath(file2))
        return path1 == path2
