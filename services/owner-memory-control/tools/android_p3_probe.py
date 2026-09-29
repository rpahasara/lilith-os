#!/usr/bin/env python3
"""ANDROID_P3_PROBE: standalone P3-3A create-only publication probe for Termux.

Record: docs/architecture/slice-15b2b-b1b3e-pr3-android-replica-publication.md.

Run inside Termux, with no arguments:

    python android_p3_probe.py

It writes ONLY inside a fresh temporary directory, created under Termux
private app storage ($TMPDIR, or $PREFIX/tmp), and removes it afterwards. It
refuses shared storage (/sdcard, /storage, /mnt), any path outside the Termux
app sandbox, and any location inside an owner replica. It does not create,
open, or touch a replica, and it has no network access. It prints only the
result lines below, with no paths or device identifiers:

    ANDROID_P3_PROBE
    directory_fsync=PASS|FAIL
    hardlink=PASS|FAIL
    rename_noreplace=PASS|FAIL|UNAVAILABLE
    direct_o_excl=PASS|FAIL
    symlink_detection=PASS|FAIL
    canonical_reread=PASS|FAIL
    cleanup=PASS|FAIL
    admitted_backend=RENAME_NOREPLACE_V1|HARDLINK_PUBLISH_V1|NONE

A PASS proves publication semantics on that filesystem only. It admits
nothing, and it is not P3-3 evidence of independence.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import platform
import stat
import sys
import tempfile

TERMUX_ROOTS = ("/data/data/com.termux/", "/data/user/0/com.termux/")
SHARED_ROOTS = ("/sdcard", "/storage", "/mnt", "/data/media")
PREFIX = ".lilith-p3-android-probe-"
_AT_FDCWD, _RENAME_NOREPLACE = -100, 1
_SYSCALL = {"aarch64": 276, "arm64": 276, "armv7l": 382, "armv8l": 382, "x86_64": 316, "i686": 353}
PAYLOAD = json.dumps({"n": 1, "probe": "LILITH_P3_ANDROID_PROBE"}, sort_keys=True, separators=(",", ":")).encode()


class Unavailable(Exception):
    pass


def _rename_noreplace(src: str, dst: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, "renameat2", None)
    if fn is not None:
        fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        fn.restype = ctypes.c_int
        rc = fn(_AT_FDCWD, os.fsencode(src), _AT_FDCWD, os.fsencode(dst), _RENAME_NOREPLACE)
    else:
        number = _SYSCALL.get(platform.machine().lower())
        if number is None:
            raise Unavailable()
        libc.syscall.restype = ctypes.c_long
        rc = libc.syscall(ctypes.c_long(number), ctypes.c_int(_AT_FDCWD), ctypes.c_char_p(os.fsencode(src)),
                          ctypes.c_int(_AT_FDCWD), ctypes.c_char_p(os.fsencode(dst)), ctypes.c_uint(_RENAME_NOREPLACE))
    if rc == 0:
        return
    code = ctypes.get_errno()
    if code == errno.EEXIST:
        raise FileExistsError(code, os.strerror(code))
    if code in (errno.ENOSYS, errno.EINVAL, errno.EPERM, errno.EACCES, errno.EOPNOTSUPP):
        raise Unavailable()
    raise OSError(code, os.strerror(code))


def _create(path: str, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _read(path: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        return os.read(fd, 1 << 16)
    finally:
        os.close(fd)


def _dir_fsync(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _backend(root: str, name: str, publish) -> str:
    """Publish once, re-read, then prove a second publish at the final name is
    refused by the primitive and the first bytes are untouched."""
    directory = os.path.join(root, name)
    os.mkdir(directory, 0o700)
    final = os.path.join(directory, "000001-probe.json")
    try:
        publish(directory, final, PAYLOAD)
    except Unavailable:
        return "UNAVAILABLE"
    except OSError:
        return "FAIL"
    try:
        if _read(final) != PAYLOAD:
            return "FAIL"
        try:
            publish(directory, final, PAYLOAD + b" ")
            return "FAIL"
        except FileExistsError:
            pass
        return "PASS" if _read(final) == PAYLOAD else "FAIL"
    except (OSError, Unavailable):
        return "FAIL"


def _via_rename(directory: str, final: str, data: bytes) -> None:
    pending = os.path.join(directory, ".pending-" + os.path.basename(final) + "." + os.urandom(4).hex())
    _create(pending, data)
    try:
        _rename_noreplace(pending, final)
    finally:
        if os.path.lexists(pending):
            os.unlink(pending)
    _dir_fsync(directory)


def _via_link(directory: str, final: str, data: bytes) -> None:
    pending = os.path.join(directory, ".pending-" + os.path.basename(final) + "." + os.urandom(4).hex())
    _create(pending, data)
    try:
        os.link(pending, final)
    finally:
        os.unlink(pending)
    _dir_fsync(directory)


def _via_direct(directory: str, final: str, data: bytes) -> None:
    _create(final, data)
    _dir_fsync(directory)


def _base(require_termux: bool) -> str:
    base = os.environ.get("TMPDIR") or os.path.join(os.environ.get("PREFIX", ""), "tmp")
    real = os.path.realpath(base) + "/"
    if any(real.startswith(root.rstrip("/") + "/") for root in SHARED_ROOTS):
        raise SystemExit("ANDROID_P3_PROBE refused: shared storage")
    if require_termux and not any(real.startswith(root) for root in TERMUX_ROOTS):
        raise SystemExit("ANDROID_P3_PROBE refused: not Termux private app storage")
    current = real.rstrip("/") or "/"
    while True:
        if os.path.exists(os.path.join(current, "REPLICA.json")) or os.path.exists(os.path.join(current, "ACCEPTANCE.json")):
            raise SystemExit("ANDROID_P3_PROBE refused: inside an owner replica or acceptance store")
        parent = os.path.dirname(current)
        if parent == current:
            return base
        current = parent


def probe(base: str) -> dict[str, str]:
    result = {"directory_fsync": "FAIL", "hardlink": "FAIL", "rename_noreplace": "UNAVAILABLE",
              "direct_o_excl": "FAIL", "symlink_detection": "FAIL", "canonical_reread": "FAIL", "cleanup": "FAIL"}
    root = tempfile.mkdtemp(prefix=PREFIX, dir=base)
    try:
        try:
            _dir_fsync(root)
            result["directory_fsync"] = "PASS"
        except OSError:
            pass
        a = os.path.join(root, "a.json")
        _create(a, PAYLOAD)
        result["canonical_reread"] = "PASS" if json.loads(_read(a)) == json.loads(PAYLOAD) and \
            json.dumps(json.loads(_read(a)), sort_keys=True, separators=(",", ":")).encode() == PAYLOAD else "FAIL"
        link = os.path.join(root, "s.json")
        try:
            os.symlink(a, link)
            try:
                _read(link)
            except OSError:
                result["symlink_detection"] = "PASS" if stat.S_ISLNK(os.lstat(link).st_mode) else "FAIL"
        except OSError:
            pass
        result["rename_noreplace"] = _backend(root, "rename", _via_rename)
        result["hardlink"] = _backend(root, "link", _via_link)
        result["direct_o_excl"] = _backend(root, "direct", _via_direct)
    finally:
        for current, directories, files in os.walk(root, topdown=False):
            for name in files:
                os.unlink(os.path.join(current, name))
            for name in directories:
                path = os.path.join(current, name)
                os.unlink(path) if os.path.islink(path) else os.rmdir(path)
        os.rmdir(root)
        result["cleanup"] = "FAIL" if os.path.lexists(root) else "PASS"
    common = all(result[k] == "PASS" for k in ("directory_fsync", "symlink_detection", "canonical_reread", "cleanup"))
    admitted = "NONE"
    if common:
        for key, backend in (("rename_noreplace", "RENAME_NOREPLACE_V1"), ("hardlink", "HARDLINK_PUBLISH_V1")):
            if result[key] == "PASS":
                admitted = backend
                break
    result["admitted_backend"] = admitted
    return result


def render(result: dict[str, str]) -> str:
    keys = ("directory_fsync", "hardlink", "rename_noreplace", "direct_o_excl", "symlink_detection",
            "canonical_reread", "cleanup", "admitted_backend")
    return "\n".join(["ANDROID_P3_PROBE"] + [f"{k}={result[k]}" for k in keys]) + "\n"


def main() -> int:
    sys.stdout.write(render(probe(_base(require_termux=True))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
