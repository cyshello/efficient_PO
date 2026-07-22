"""LVBench provider.

LVBench (zai-org/LVBench): 103개 장편 YouTube 영상(평균 ~1시간, 최대 2h+),
4지선다 MCQ 1,549개. 공식 split 없음 → 단일 "test" split.

데이터 레이아웃 (data_root = .../lvbench_data):
    LVBench/video_info.meta.jsonl   # video당 1줄: {key, type, qa: [...]}
    LVBench/videos/{key}.mp4        # key = YouTube video ID

원본 annotation의 question 필드는 선택지가 본문에 인라인으로 들어 있다:
    "What year ...?\n(A) 1636\n(B) 1366\n(C) 1363\n(D) 1633"
→ 본문/선택지를 분리해 공통 스키마(question + options=["A. ...", ...])로
변환한다. 정답은 전부 공개돼 있으므로 answer_available=True 고정.
자막은 공식 제공되지 않음 → extra["subtitle_path"]=None 고정.
"""

from __future__ import annotations

import json
import os
import re

from .base import BaseProvider

# "(A) text" 스타일 선택지 시작 위치를 찾는다 (줄 시작 기준).
_OPTION_RE = re.compile(r"^\(([A-D])\)\s*(.*)$")


def _split_question(raw: str) -> tuple[str, list[str]]:
    """인라인 선택지가 붙은 question 원문을 (본문, options)로 분리.

    options는 videomme 컨벤션과 동일하게 "A. ..." 형태로 반환한다.
    선택지를 못 찾으면 (원문 그대로, []) 반환 — 호출부에서 검증.
    """
    question_lines: list[str] = []
    options: list[str] = []
    for line in (raw or "").splitlines():
        m = _OPTION_RE.match(line.strip())
        if m:
            options.append(f"{m.group(1)}. {m.group(2).strip()}")
        elif options:
            # 선택지 시작 후의 비선택지 줄은 직전 선택지의 연속줄로 붙인다.
            if line.strip():
                options[-1] += " " + line.strip()
        else:
            question_lines.append(line)
    return "\n".join(question_lines).strip(), options


class LVBenchProvider(BaseProvider):
    name = "lvbench"

    def __init__(self, data_root: str, split: str = "test"):
        if split not in ("test", "all"):
            raise ValueError(
                f"unknown split {split!r} for lvbench; available: ['test']")
        super().__init__(data_root, "test")

        repo = os.path.join(data_root, "LVBench")
        meta_path = os.path.join(repo, "video_info.meta.jsonl")
        self._videos_dir = os.path.join(repo, "videos")

        self._samples: list[dict] = []
        with open(meta_path) as f:
            for line in f:
                if not line.strip():
                    continue
                video = json.loads(line)
                for qa in video.get("qa", []):
                    self._samples.append(self._to_sample(video, qa))

    def _to_sample(self, video: dict, qa: dict) -> dict:
        key = video["key"]
        question, options = _split_question(qa.get("question") or "")
        if len(options) != 4:
            # 선택지 파싱 실패는 조용히 넘기지 않는다 — 원문 보존 + 표시.
            question, options = (qa.get("question") or "").strip(), []
        extra = {
            "videoID": key,                    # 파이프라인 video_id 규칙과 일치
            "video_type": video.get("type"),
            "uid": qa.get("uid"),
            "question_type": qa.get("question_type"),
            "time_reference": qa.get("time_reference"),
            "subtitle_path": None,             # LVBench는 공식 자막 미제공
            "raw_question": qa.get("question"),
        }
        return {
            "dataset": self.name,
            "sample_id": f"{key}_{qa.get('uid')}",
            "video_path": os.path.join(self._videos_dir, f"{key}.mp4"),
            "duration_sec": -1.0,  # meta에 길이 없음 (ffprobe로 산출 가능)
            "split": self.split,
            "task_format": "mcq",
            "question": question,
            "options": options,
            "answer": qa.get("answer"),  # "A"~"D"
            "answer_available": True,
            "extra": extra,
        }

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> dict:
        return self._samples[idx]

    def available_splits(self) -> list[str]:
        return ["test"]
