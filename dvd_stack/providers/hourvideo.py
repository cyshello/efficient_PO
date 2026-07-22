"""HourVideo provider.

데이터 레이아웃 (data_root = .../hourvideo_data):
    HourVideo/v1.0_release/json/samples_v1.0.json          # 2 videos, 정답 포함
    HourVideo/v1.0_release/json/dev_v1.0_annotations.json  # 50 videos, 정답 포함 (2025-03 별도 공개)
    HourVideo/v1.0_release/json/test_v1.0.json             # 500 videos, 정답 미포함
    videos/v2/video_540ss/{video_uid}.mp4

각 video의 benchmark_dataset 리스트를 QA 단위(mcq)로 평탄화한다.
dev는 정답 포함 annotation 파일(dev_v1.0_annotations.json)을 사용 → sample/dev는
answer_available=True, test만 False. (공식 권장 평가 시작점이 dev set: 50 videos,
1,182 QA, 39.3h. 정답 없는 dev_v1.0.json은 사용하지 않음.)
"""

from __future__ import annotations

import json
import os

from .base import BaseProvider

# split 이름 -> (json 파일명, 정답 공개 여부)
_SPLIT_FILES = {
    "sample": ("samples_v1.0.json", True),
    # dev 정답은 dev_v1.0_annotations.json에 correct_answer_label로 들어있음
    "dev": ("dev_v1.0_annotations.json", True),
    "test": ("test_v1.0.json", False),
}
# 편의 alias
_SPLIT_ALIASES = {"samples": "sample"}

_ANSWER_KEYS = ["answer_1", "answer_2", "answer_3", "answer_4", "answer_5"]


class HourVideoProvider(BaseProvider):
    name = "hourvideo"

    def __init__(self, data_root: str, split: str = "test"):
        split = _SPLIT_ALIASES.get(split, split)
        if split not in _SPLIT_FILES:
            raise ValueError(
                f"unknown split {split!r} for hourvideo; available: {list(_SPLIT_FILES)}"
            )
        super().__init__(data_root, split)

        fname, self._answer_available = _SPLIT_FILES[split]
        json_path = os.path.join(
            data_root, "HourVideo", "v1.0_release", "json", fname
        )
        with open(json_path) as f:
            per_video = json.load(f)

        self._video_dir = os.path.join(data_root, "videos", "v2", "video_540ss")
        self._samples: list[dict] = []
        for video_uid, entry in per_video.items():
            meta = entry.get("video_metadata", {})
            for qa in entry.get("benchmark_dataset", []):
                self._samples.append(self._to_sample(video_uid, meta, qa))

    def _to_sample(self, video_uid: str, meta: dict, qa: dict) -> dict:
        options = [qa.get(k) for k in _ANSWER_KEYS if qa.get(k) is not None]
        answer = qa.get("correct_answer_label") if self._answer_available else None
        extra = {
            "video_uid": video_uid,
            "task": qa.get("task"),
            "relevant_timestamps": qa.get("relevant_timestamps"),
            "mcq_test": qa.get("mcq_test"),
            **{f"video_{k}": v for k, v in meta.items()},
        }
        return {
            "dataset": self.name,
            "sample_id": qa["qid"],
            "video_path": os.path.join(self._video_dir, f"{video_uid}.mp4"),
            "duration_sec": float(meta.get("duration_in_seconds", -1.0)),
            "split": self.split,
            "task_format": "mcq",
            "question": qa.get("question"),
            "options": options,
            "answer": answer,
            "answer_available": self._answer_available,
            "extra": extra,
        }

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> dict:
        return self._samples[idx]

    def available_splits(self) -> list[str]:
        return list(_SPLIT_FILES)
