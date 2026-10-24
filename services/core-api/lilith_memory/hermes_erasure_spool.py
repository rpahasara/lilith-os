"""F9-C: the Core API side of the privileged Hermes erasure executor (the Slice 2 ``HermesErasureExecutor``).

``submit`` only queues: it writes the exact Slice 2 request ({v, owner, authorizationRefId, executionNonce}) into the
root-owned spool (group lilith-forget may create files there but not list them), atomically and never overwriting,
under a new name per attempt so a retry after a failed or rebooted attempt queues again. Queued is never COMPLETE.

``read_receipt`` returns the executor's durable receipt only if it is a regular, root-owned, non-writable-by-others
file of bounded size, opened without following links; the adapter (hermes_erasure_owner.verify_receipt) then binds it
to the exact authorization. This module holds no authority and touches nothing but the spool and receipt paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

try:
    from . import hermes_erasure_owner as H
except ImportError:  # deploy-exact flat-directory tests
    import hermes_erasure_owner as H

SPOOL_DIR = Path("/run/hermes-forget/spool")
RECEIPT_DIR = Path("/var/lib/hermes-forget/receipts")
REF_RE = re.compile(r"^erase\.[0-9a-f]{32}$")
MAX_REQUEST_BYTES = 1024
MAX_RECEIPT_BYTES = 64 * 1024


class SpoolHermesErasureExecutor:
    def __init__(self, spool_dir: Path = SPOOL_DIR, receipt_dir: Path = RECEIPT_DIR, *, executor_uid: int = 0):
        self.spool_dir = Path(spool_dir)
        self.receipt_dir = Path(receipt_dir)
        self.executor_uid = executor_uid

    def submit(self, request: Mapping[str, Any]) -> None:
        if not isinstance(request, Mapping) or set(request) != H.REQUEST_FIELDS or request.get("owner") != H.OWNER \
                or not REF_RE.fullmatch(str(request.get("authorizationRefId", ""))):
            raise ValueError("ERASURE_REQUEST_INVALID")
        data = json.dumps(dict(request), sort_keys=True, separators=(",", ":")).encode("ascii")
        if len(data) > MAX_REQUEST_BYTES:
            raise ValueError("ERASURE_REQUEST_INVALID")
        ref_digest = hashlib.sha256(str(request["authorizationRefId"]).encode("ascii")).hexdigest()[:32]
        name = f"{ref_digest}-{uuid.uuid4().hex}.req"
        tmp = self.spool_dir / f".{name}.tmp"                     # not matched by the path unit's *.req glob
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        # The name carries a fresh UUID, so the rename cannot replace another request; a hard link would briefly
        # give the request two links, which the executor (st_nlink == 1) rightly refuses.
        os.rename(tmp, self.spool_dir / name)

    def read_receipt(self, authorization_ref_id: str) -> Optional[Mapping[str, Any]]:
        if not REF_RE.fullmatch(str(authorization_ref_id)):
            raise ValueError("ERASURE_REFERENCE_INVALID")
        path = self.receipt_dir / f"{authorization_ref_id}.receipt.json"
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != self.executor_uid or st.st_mode & 0o022 \
                    or st.st_size > MAX_RECEIPT_BYTES:
                raise PermissionError("ERASURE_RECEIPT_UNTRUSTED")
            data = os.read(fd, MAX_RECEIPT_BYTES + 1)
        finally:
            os.close(fd)
        receipt = json.loads(data.decode("ascii"))
        if not isinstance(receipt, dict):
            raise ValueError("ERASURE_RECEIPT_MALFORMED")
        return receipt
