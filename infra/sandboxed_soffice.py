#!/usr/bin/env python3
"""Run LibreOffice with no network sockets and bounded process resources."""

from __future__ import annotations

import ctypes
import errno
import os
import resource
import socket
import sys


class ScmpArgCmp(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


def restrict_network() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "Cannot set no_new_privs")

    seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(ScmpArgCmp),
    ]
    seccomp.seccomp_rule_add_array.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]

    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("Cannot create seccomp filter")
    try:
        socket_syscall = seccomp.seccomp_syscall_resolve_name(b"socket")
        if socket_syscall < 0:
            raise RuntimeError("Cannot resolve socket syscall")
        comparison = ScmpArgCmp(0, 1, socket.AF_UNIX, 0)  # SCMP_CMP_NE
        denied = 0x00050000 | errno.EPERM  # SCMP_ACT_ERRNO(EPERM)
        result = seccomp.seccomp_rule_add_array(
            context, denied, socket_syscall, 1, ctypes.byref(comparison)
        )
        if result != 0 or seccomp.seccomp_load(context) != 0:
            raise RuntimeError("Cannot load network restriction")
    finally:
        seccomp.seccomp_release(context)


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    restrict_network()
    if sys.argv[1:] == ["--self-test-network"]:
        try:
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as exc:
            if exc.errno != errno.EPERM:
                raise
        else:
            raise RuntimeError("Network socket was not blocked")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
            pass
        print("Network sockets blocked; Unix sockets allowed")
        return
    os.execv("/usr/bin/soffice", ["soffice", *sys.argv[1:]])


if __name__ == "__main__":
    main()
