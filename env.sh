#!/usr/bin/env bash
# Source this to point the evaluator at its own bundled DVD substrate.
# Data (LVBench videos/frames, split manifest) and models are NOT bundled —
# set the data/cache roots per host.
A="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SR_PROMPT_SENS_ROOT="$A/dvd_stack"                 # dvd_backend/captioning/prompt + vendored dvd/
export SR_CAPTIONING_PARENT="$A/src/surrogate_rollout"    # captioner.py -> `from captioning import ...`
export PYTHONPATH="$A/src${PYTHONPATH:+:$PYTHONPATH}"     # surrogate_rollout.* (until `pip install -e .`)
# Per-host (override): benchmark, data + caches
export SR_BENCHMARK="${SR_BENCHMARK:-lvbench}"
export SR_BENCHMARK_SPLIT="${SR_BENCHMARK_SPLIT:-test}"
# export SR_SPLIT_MANIFEST_PATH=/path/to/split_manifest_lvbench.json
# export SR_CAPTION_CACHE_ROOT=/path/to/caption_cache
