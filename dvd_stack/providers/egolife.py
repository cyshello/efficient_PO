"""EgoLife (Ego-R1) provider.

Ego-R1은 6명(A1~A6)의 1주일(DAY1~DAY7) egocentric 영상 스트림을 30초 단위
청크로 쪼갠 데이터셋이다. 하나의 QA는 단일 mp4가 아니라 "특정 인물의 전체
egocentric 스트림"을 대상으로 하므로, `video_path`는 해당 인물의 영상 루트
**디렉터리**를 가리킨다 (hourvideo/videomme처럼 단일 파일이 아님).
질문 시점(query_time)/근거 시점(target_time)에 해당하는 실제 청크 파일 경로는
`extra`에 함께 담아 소비자가 필요한 구간만 로드할 수 있게 한다.

데이터 레이아웃 (data_root = .../egolife):
    {IDENTITY}/DAY{d}/DAY{d}_{IDENTITY}_{HHMMSSFF}.mp4   # 30초 청크
    transcript/{IDENTITY}/DAY{d}/{IDENTITY}_DAY{d}_{HH}000000.srt
    annotations/Ego-R1-Bench/manual-benchmark/{IDENTITY}.json   # 평가 벤치마크(수동)
    annotations/Ego-R1-Bench/gemini-benchmark/{IDENTITY}.json   # 평가 벤치마크(gemini)
    annotations/Ego-R1-Data/Ego-QA-4.4K/manual-2.9K/{IDENTITY}.json  # 수동 QA 2.9K

split:
    "manual-benchmark" (기본) — Ego-R1-Bench 수동 벤치마크 (150문항, 인물당 25)
    "gemini-benchmark"        — Ego-R1-Bench gemini 벤치마크 (150문항)
    "manual-2.9K"             — Ego-R1-Data 수동 QA (2905문항)  [alias: "manual"]

세 split 모두 4지선다(A~D)이며 정답이 공개돼 있으므로 answer_available=True 고정.
"""

from __future__ import annotations

import glob
import json
import os
import re

from .base import BaseProvider

_IDENTITIES = ["A1_JAKE", "A2_ALICE", "A3_TASHA", "A4_LUCIA", "A5_KATRINA", "A6_SHURE"]

# split 이름 -> annotation 디렉터리 (data_root 기준 상대경로)
_SPLIT_DIRS = {
    "manual-benchmark": os.path.join("annotations", "Ego-R1-Bench", "manual-benchmark"),
    "gemini-benchmark": os.path.join("annotations", "Ego-R1-Bench", "gemini-benchmark"),
    "manual-2.9K": os.path.join(
        "annotations", "Ego-R1-Data", "Ego-QA-4.4K", "manual-2.9K"
    ),
}
# 편의 alias
_SPLIT_ALIASES = {
    "manual": "manual-2.9K",
    "manual-2.9k": "manual-2.9K",
    "bench": "manual-benchmark",
    "gemini": "gemini-benchmark",
}

_CHOICE_KEYS = ["choice_a", "choice_b", "choice_c", "choice_d"]


class EgoLifeProvider(BaseProvider):
    """Ego-R1 / EgoLife MCQ provider (Ego-R1-Bench + manual-2.9K)."""

    name = "egolife"

    def __init__(self, data_root: str, split: str = "manual-benchmark"):
        split = _SPLIT_ALIASES.get(split, split)
        if split not in _SPLIT_DIRS:
            raise ValueError(
                f"unknown split {split!r} for egolife; available: {list(_SPLIT_DIRS)}"
            )
        super().__init__(data_root, split)

        self._ann_dir = os.path.join(data_root, _SPLIT_DIRS[split])
        # 인물별 DAY 디렉터리 청크 목록 캐시: (identity, date) -> [(start_int, path), ...]
        self._chunk_cache: dict[tuple[str, str], list[tuple[int, str]]] = {}

        self._samples: list[dict] = []
        for identity in _IDENTITIES:
            json_path = os.path.join(self._ann_dir, f"{identity}.json")
            if not os.path.exists(json_path):
                continue
            with open(json_path) as f:
                items = json.load(f)
            for qa in items:
                self._samples.append(self._to_sample(identity, qa))

    # ---- 청크 경로 해석 --------------------------------------------------
    def _list_chunks(self, identity: str, date: str) -> list[tuple[int, str]]:
        date = date.upper()  # 원본에 "day6"처럼 소문자가 섞여 있음 → 디렉터리는 DAY6
        key = (identity, date)
        if key not in self._chunk_cache:
            day_dir = os.path.join(self.data_root, identity, date)
            pat = re.compile(rf"{re.escape(date)}_{re.escape(identity)}_(\d{{8}})\.mp4$")
            found: list[tuple[int, str]] = []
            for path in glob.glob(os.path.join(day_dir, "*.mp4")):
                m = pat.match(os.path.basename(path))
                if m:
                    found.append((int(m.group(1)), path))
            found.sort()
            self._chunk_cache[key] = found
        return self._chunk_cache[key]

    @staticmethod
    def _parse_time(time_field: dict) -> int | None:
        """time_field에서 시작 시각(HHMMSSFF)을 int로 뽑아낸다.

        원본 annotation에는 몇몇 비정상 포맷이 섞여 있어 방어적으로 처리한다:
        - 범위 "start-end"                → 시작값
        - 다중 concat "……DAY1_……"        → 첫 8자리
        - 9자리 이상 (오타)               → 앞 8자리로 절단
        - "time" 없이 "time_list": [...]  → 첫 원소
        파싱 불가하면 None.
        """
        time = time_field.get("time")
        if time is None:
            tl = time_field.get("time_list")
            if isinstance(tl, list) and tl:
                time = tl[0]
        if time is None:
            return None
        m = re.match(r"\d+", str(time))  # 선두 숫자 런
        if not m:
            return None
        digits = m.group(0)[:8]  # HHMMSSFF 8자리 초과분(concat/오타) 절단
        return int(digits)

    def _resolve_chunk(self, identity: str, time_field: dict | None) -> str | None:
        """query_time/target_time({date, time})가 속한 30초 청크 mp4 경로 반환.

        시작 시각 <= t 인 청크 중 가장 늦게 시작하는 것을 고른다.
        해당 DAY 청크가 없거나 시각 파싱이 불가하면 None.
        """
        if not time_field:
            return None
        date = time_field.get("date")
        if not date:
            return None
        t = self._parse_time(time_field)
        if t is None:
            return None
        chunks = self._list_chunks(identity, date)
        if not chunks:
            return None
        pick = chunks[0][1]
        for start, path in chunks:
            if start <= t:
                pick = path
            else:
                break
        return pick

    # ---- 샘플 변환 -------------------------------------------------------
    def _to_sample(self, identity: str, qa: dict) -> dict:
        options = [qa.get(k) for k in _CHOICE_KEYS]
        query_time = qa.get("query_time")
        target_time = qa.get("target_time")
        query_chunk = self._resolve_chunk(identity, query_time)
        target_chunk = self._resolve_chunk(identity, target_time)

        extra = {
            "identity": identity,
            "question_type": qa.get("type"),
            "question_type_chinese": qa.get("type_chinese"),
            "query_time": query_time,
            "target_time": target_time,
            "query_video_path": query_chunk,
            "target_video_path": target_chunk,
            "need_audio": qa.get("need_audio"),
            "need_name": qa.get("need_name"),
            "last_time": qa.get("last_time"),
            "keywords": qa.get("keywords"),
            "trigger": qa.get("trigger"),
            "reason": qa.get("reason"),
            "transcript_dir": os.path.join(self.data_root, "transcript", identity),
            "raw": qa,  # 원본 필드 전체 보관 (중국어 필드 등 포함)
        }
        return {
            "dataset": self.name,
            # ID는 인물 파일 내에서만 유일 → identity로 네임스페이스 부여
            "sample_id": f"{identity}_{qa.get('ID')}",
            # egolife의 "영상"은 인물의 egocentric 스트림 전체 디렉터리
            "video_path": os.path.join(self.data_root, identity),
            "duration_sec": -1.0,  # 스트림 총 길이는 청크 합산 필요 → 미제공
            "split": self.split,
            "task_format": "mcq",
            "question": qa.get("question"),
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
        return list(_SPLIT_DIRS)
