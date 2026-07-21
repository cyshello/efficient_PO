"""Dataset provider — component 1.

Reuses the provider package at /home/intern/youngseo/longVideoPO/providers
as-is (no copy). Those modules use relative imports, so the parent dir is put
on sys.path and the package is imported by name.

Common sample schema (see longVideoPO/providers/base.py):
    dataset, sample_id, video_path, duration_sec, split, task_format,
    question, options, answer, answer_available, extra
"""

from __future__ import annotations

import os
import sys

# Append (not insert-0) so this project's own modules — e.g. captioner.py —
# win over same-named packages that live under longVideoPO/.
_PROVIDERS_PARENT = "/home/intern/youngseo/longVideoPO"
if _PROVIDERS_PARENT not in sys.path:
    sys.path.append(_PROVIDERS_PARENT)

from providers.registry import load_provider  # noqa: E402
from providers.base import BaseProvider  # noqa: E402

__all__ = ["load_provider", "BaseProvider", "get_provider"]


def get_provider(name: str, split: str | None = None, data_root: str | None = None):
    """Thin alias over providers.registry.load_provider.

    name: "videomme" | "egolife" | "hourvideo"
    """
    return load_provider(name, data_root=data_root, split=split)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect a dataset provider")
    parser.add_argument("name", nargs="?", default="videomme")
    parser.add_argument("--split", default="long")
    args = parser.parse_args()

    p = get_provider(args.name, split=args.split)
    print(repr(p))
    s = p[0]
    print("first sample:")
    for k, v in s.items():
        if k == "extra":
            continue
        print(f"  {k}: {v}")
    print(f"  video exists: {os.path.exists(s['video_path'])}")
