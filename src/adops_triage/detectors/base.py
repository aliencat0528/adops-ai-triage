# -*- coding: utf-8 -*-
"""
L0 · 偵測器基底
===============
所有主動偵測器繼承 Detector，實作 scan() 回傳 list[Finding]。

設計約束：
  1. 偵測器只做唯讀觀察，任何修復動作都要交給 L4，且必須來自 playbook_registry.yaml
  2. 每個 Finding 都要能回答「這對應到哪一類工單」——這是回測攔截率的依據
  3. 去重：同一 fingerprint 在 dedup_window_hours 內不重複告警
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

Severity = Literal["S1", "S2", "S3", "S4"]


@dataclass
class Finding:
    detector_id: str
    severity: Severity
    title: str
    summary: str
    client: str
    asset_id: str
    evidence: dict[str, Any]
    maps_to_issue_category: str
    suggested_action_id: str | None = None   # 必須存在於 playbook_registry.yaml
    detected_at: datetime = field(default_factory=datetime.now)

    @property
    def fingerprint(self) -> str:
        raw = f"{self.detector_id}|{self.client}|{self.asset_id}|{self.title}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "detector_id": self.detector_id,
            "severity": self.severity,
            "title": self.title,
            "summary": self.summary,
            "client": self.client,
            "asset_id": self.asset_id,
            "evidence": self.evidence,
            "maps_to_issue_category": self.maps_to_issue_category,
            "suggested_action_id": self.suggested_action_id,
            "detected_at": self.detected_at.isoformat(timespec="seconds"),
        }


class Detector(ABC):
    detector_id: str = "base"
    schedule: str = "hourly"            # hourly / daily / event
    dedup_window_hours: int = 24

    def __init__(self) -> None:
        self._seen: dict[str, datetime] = {}

    @abstractmethod
    def scan(self, **kwargs: Any) -> list[Finding]:
        """執行一次偵測。實作必須是唯讀的。"""

    def emit(self, findings: list[Finding]) -> list[Finding]:
        """去重後才送出，避免同一個問題每小時吵一次。"""
        now = datetime.now()
        out: list[Finding] = []
        for f in findings:
            last = self._seen.get(f.fingerprint)
            if last and now - last < timedelta(hours=self.dedup_window_hours):
                continue
            self._seen[f.fingerprint] = now
            out.append(f)
        return out
