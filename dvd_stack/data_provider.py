"""Dataset provider — component 1.

The provider package is bundled next to this file (`dvd_stack/providers/`), so
a host that has only this repo can run the benchmarks. It is a verbatim copy of
longVideoPO/providers — sync it there, do not fork it here. Those modules use
relative imports, so the parent dir is put on sys.path and the package is
imported by name.

Set SR_PROVIDERS_PARENT to a directory containing a `providers/` package to
override the bundled copy (e.g. /home/intern/youngseo/longVideoPO on the host
where longVideoPO is checked out).

Common sample schema (see providers/base.py):
    dataset, sample_id, video_path, duration_sec, split, task_format,
    question, options, answer, answer_available, extra
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_OVERRIDE = os.environ.get("SR_PROVIDERS_PARENT")
if _OVERRIDE:
    # insert-0: an explicit override must beat the bundled copy, which sits in
    # this same directory (already on sys.path via SR_PROMPT_SENS_ROOT).
    if _OVERRIDE not in sys.path:
        sys.path.insert(0, _OVERRIDE)
elif _HERE not in sys.path:
    # Append (not insert-0) so this project's own modules — e.g. captioner.py —
    # keep priority over same-named packages elsewhere on the path.
    sys.path.append(_HERE)

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
