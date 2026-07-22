"""Provider 레지스트리.

    from providers.registry import load_provider
    p = load_provider("hourvideo", split="sample")
    p = load_provider("videomme", split="short")
"""

from __future__ import annotations

import importlib
import os

PROVIDERS = {
    "hourvideo": "providers.hourvideo.HourVideoProvider",
    "videomme": "providers.videomme.VideoMMEProvider",
    "egolife": "providers.egolife.EgoLifeProvider",
    "lvbench": "providers.lvbench.LVBenchProvider",
    # Phase 2에서 여기에 egoschema / longvideobench / mlvu 추가 예정 - 지금은 건드리지 말 것
}

# 데이터셋별 기본 data_root.
# $DATA_ROOT 환경변수가 설정돼 있으면 $DATA_ROOT/<name>_data가 우선한다.
# (현재 물리 배치: HourVideo는 /hub_data2, Video-MME는 /hub_data3 — 2026-07 용량 사정)
DEFAULT_DATA_ROOTS = {
    "hourvideo": "/hub_data2/hourvideo_data",
    "videomme": "/hub_data3/videomme_data",
    # egolife: 원본 영상이 이미 여기 있음. annotations/ 하위에 벤치마크 JSON 배치.
    # (egolife는 <name>_data 규칙이 아니라 egolife/ 루트를 그대로 data_root로 씀)
    "egolife": "/hub_data1/intern/youngseo/egolife",
    # LVBench: 2026-07-19 다운로드 (YouTube 360p 90개 + lmms-lab 미러 복구 13개)
    "lvbench": "/hub_data3/lvbench_data",
}

# 데이터셋별 기본 split (인터페이스 기본값 "test"가 없는 데이터셋 대비)
DEFAULT_SPLITS = {
    "hourvideo": "test",
    "videomme": "short",
    "egolife": "manual-benchmark",
    "lvbench": "test",
}


def _resolve_data_root(name: str) -> str:
    env_root = os.environ.get("DATA_ROOT")
    if env_root:
        candidate = os.path.join(env_root, f"{name}_data")
        if os.path.isdir(candidate):
            return candidate
    return DEFAULT_DATA_ROOTS[name]


def load_provider(name: str, data_root: str | None = None, split: str | None = None):
    """이름만 넣으면 해당 provider 인스턴스 반환.

    data_root 생략 시 $DATA_ROOT/<name>_data (없으면 데이터셋별 기본 경로).
    split 생략 시 데이터셋별 기본 split.
    """
    if name not in PROVIDERS:
        raise KeyError(f"unknown provider {name!r}; available: {list(PROVIDERS)}")
    module_path, cls_name = PROVIDERS[name].rsplit(".", 1)
    cls = getattr(importlib.import_module(module_path), cls_name)
    if data_root is None:
        data_root = _resolve_data_root(name)
    if split is None:
        split = DEFAULT_SPLITS.get(name, "test")
    return cls(data_root=data_root, split=split)
