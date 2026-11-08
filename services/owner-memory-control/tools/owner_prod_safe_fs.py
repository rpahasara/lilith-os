"""Verified, descriptor-relative removal for the OWNER_PROD inert installer (H-1, H-2). SOURCE ONLY.

Record: docs/architecture/canonical-memory-prod-integration-plan.md §13. Shared by `owner_prod_inert_install` (stage 1)
and `owner_prod_inert_stages` (stages 2-5); nothing here runs on its own.

- **H-1 (what is verified).** Every installer-managed path is described by a `Meta`: its kind, permission bits,
  owner and group, and its integrity value (file SHA-256, link target, "" for a directory). The install journals the
  `Meta` it observed right after creating each item; a return refuses before removing anything unless every item
  still has exactly that `Meta`.
- **H-2 (how it is removed).** Paths are never resolved by name from the root. Every lookup opens the parent chain
  one component at a time with `O_DIRECTORY | O_NOFOLLOW` relative to the previous descriptor, so no symlink anywhere
  in the path is followed. Verification records each entry's inode `identity`. Immediately before an entry is
  removed it is `lstat`-ed again through its parent descriptor and must have that identity, otherwise
  `CHANGED_DURING_RETURN`. Removal is `unlinkat` / `unlinkat(AT_REMOVEDIR)` on that parent: a link is removed, never
  followed, and a directory is only ever removed when empty. Nothing is ever deleted recursively.
- **Lock.** Install and return in both tools hold one exclusive, non-blocking `flock` on the state directory's
  `lock` file; a second process is refused (`LOCKED_BY_ANOTHER_PROCESS`), it never waits.

A residual window remains between the final `fstatat` and the `unlinkat` (POSIX has no compare-and-unlink). The
lock and the owner's maintenance window (no other process writes these paths; no installer-managed unit is loaded
or started) cover it. Every refusal leaves the journal naming exactly what was removed; a partly returned stage is
never resumed automatically.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

O_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
O_FILE = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NOATIME", 0) | getattr(os, "O_CLOEXEC", 0)
KINDS = ("file", "dir", "link")


class Stop(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise Stop(reason)


def _parts(relative: str) -> list[str]:
    parts = [p for p in relative.split("/") if p]
    need(bool(parts) and all(p not in (".", "..") for p in parts), "PATH_INVALID:" + relative)
    return parts


def open_dir(root: Path, relative: str) -> int:
    """A descriptor for root/relative, opened one component at a time, never following a link (an empty relative
    path is the root itself)."""
    fd = os.open(root, O_DIR)
    try:
        for part in [p for p in relative.split("/") if p]:
            need(part not in (".", ".."), "PATH_INVALID:" + relative)
            try:
                child = os.open(part, O_DIR, dir_fd=fd)
            except OSError as exc:                       # ELOOP (a link), ENOTDIR, ENOENT: never followed or guessed
                raise Stop("PATH_NOT_A_REAL_DIRECTORY:" + relative) from exc
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def split(relative: str) -> tuple[str, str]:
    parts = _parts(relative)
    return "/".join(parts[:-1]), parts[-1]


@dataclass(frozen=True)
class Meta:
    """H-1: what an installer-managed entry must still be. `mode` is the permission bits (0 for a link)."""
    kind: str
    mode: int
    uid: int
    gid: int
    integrity: str          # file SHA-256 | link target | "" for a directory

    def as_list(self) -> list:
        return [self.kind, self.mode, self.uid, self.gid, self.integrity]

    @staticmethod
    def from_journal(value: object, where: str) -> "Meta":
        need(isinstance(value, list) and len(value) == 5 and value[0] in KINDS
             and all(isinstance(v, int) and not isinstance(v, bool) for v in value[1:4])
             and isinstance(value[4], str), "JOURNAL_INCOMPLETE:" + where)
        return Meta(*value)


def identity(st: os.stat_result, kind: str) -> tuple:
    """H-2: the inode facts that must not change between verification and removal. A directory's own timestamps
    change whenever a verified child is removed, so for a directory only its inode, type, mode and owner count (and
    `rmdir` refuses a non-empty one); for a file or link every field counts."""
    base = (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid)
    return base if kind == "dir" else base + (st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink)


def _kind(st: os.stat_result) -> str:
    if stat.S_ISLNK(st.st_mode):
        return "link"
    if stat.S_ISDIR(st.st_mode):
        return "dir"
    if stat.S_ISREG(st.st_mode):
        return "file"
    return "special"


def _file_sha(parent_fd: int, name: str, st: os.stat_result, where: str) -> str:
    fd = os.open(name, O_FILE, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        need(stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino) == (st.st_dev, st.st_ino),
             "CHANGED_DURING_VERIFY:" + where)
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1 << 20):
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(fd)


def observe_at(parent_fd: int, name: str, where: str) -> tuple[Meta, tuple]:
    """The Meta and identity of one entry, through its parent descriptor; links are read, never followed."""
    try:
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise Stop("ITEM_MISSING:" + where) from exc
    kind = _kind(st)
    need(kind in KINDS, "ENTRY_TYPE:" + where)
    if kind == "file":
        integrity = _file_sha(parent_fd, name, st, where)
    elif kind == "link":
        integrity = os.readlink(name, dir_fd=parent_fd)
    else:
        integrity = ""
    meta = Meta(kind, 0 if kind == "link" else stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid, integrity)
    return meta, identity(st, kind)


def observe(root: Path, relative: str) -> tuple[Meta, tuple]:
    parent, name = split(relative)
    fd = open_dir(root, parent)
    try:
        return observe_at(fd, name, relative)
    finally:
        os.close(fd)


def list_dir(root: Path, relative: str) -> list[str]:
    fd = open_dir(root, relative)
    try:
        return sorted(os.listdir(fd))
    finally:
        os.close(fd)


def walk(root: Path, relative: str) -> dict[str, tuple[Meta, tuple]]:
    """Every entry under root/relative ("." = the directory itself), each observed through its parent descriptor;
    links recorded, never followed; any special file is a STOP."""
    parent, name = split(relative)
    pfd = open_dir(root, parent)
    try:
        top = observe_at(pfd, name, relative)
    finally:
        os.close(pfd)
    need(top[0].kind == "dir", "ITEM_CHANGED:" + relative)
    out = {".": top}
    pending = [""]
    while pending:
        rel = pending.pop()
        dfd = open_dir(root, f"{relative}/{rel}" if rel else relative)
        try:
            for entry in sorted(os.listdir(dfd)):
                child = f"{rel}/{entry}" if rel else entry
                meta, ident = observe_at(dfd, entry, f"{relative}/{child}")
                out[child] = (meta, ident)
                if meta.kind == "dir":
                    pending.append(child)
        finally:
            os.close(dfd)
    return dict(sorted(out.items()))


def remove_verified(root: Path, relative: str, verified: tuple, kind: str) -> None:
    """Remove one entry only if it is still exactly the verified inode: through its parent descriptor, never
    following a link, a directory only when empty."""
    parent, name = split(relative)
    fd = open_dir(root, parent)
    try:
        try:
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise Stop("CHANGED_DURING_RETURN:" + relative) from exc
        need(_kind(st) == kind and identity(st, kind) == verified, "CHANGED_DURING_RETURN:" + relative)
        try:
            if kind == "dir":
                os.rmdir(name, dir_fd=fd)                 # fails on a non-empty directory: nothing unverified goes
            else:
                os.unlink(name, dir_fd=fd)                # a link is removed itself, its target never touched
        except OSError as exc:
            raise Stop("REMOVE_REFUSED:" + relative) from exc
    finally:
        os.close(fd)


class HostLock:
    """One exclusive, non-blocking flock on <state>/lock, shared by install and return of every stage."""

    def __init__(self, root: Path, state_relative: str):
        self.root, self.state, self.fd = root, state_relative, -1

    def __enter__(self) -> "HostLock":
        sfd = open_dir(self.root, self.state)
        try:
            self.fd = os.open("lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0), 0o600,
                              dir_fd=sfd)
        finally:
            os.close(sfd)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self.fd)
            self.fd = -1
            raise Stop("LOCKED_BY_ANOTHER_PROCESS") from exc
        return self

    def __exit__(self, *_exc) -> None:
        if self.fd >= 0:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = -1
