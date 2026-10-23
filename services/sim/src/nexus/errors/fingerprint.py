"""Error fingerprint (ERROR-PIPELINE EP-8): which captures count as the same error.

16 hex chars of SHA-256 over the component, the exception type (module.qualname) and the
innermost `FRAME_COUNT` frames inside the `nexus` package as `file:function`. Line numbers are left
out so an unrelated edit in the same file does not split an issue. A capture with no in-package
frame hashes component and type only.
"""

import hashlib
from collections.abc import Mapping, Sequence

FRAME_COUNT = 5


def fingerprint(component: str, exc_type: str, frames: Sequence[Mapping[str, object]]) -> str:
    """`frames` are the sample's frames, outermost first (`file` is already a short path)."""
    inside = [f"{f['file']}:{f['function']}" for f in frames if str(f["file"]).startswith("nexus/")]
    material = "\n".join([component, exc_type, *inside[-FRAME_COUNT:]])
    return hashlib.sha256(material.encode()).hexdigest()[:16]
