# -*- coding: utf-8 -*-
"""
L0 · Feed 健檢偵測器
====================
比對 Feed 欄位值與到達頁的實際內容，在商品被拒登之前先攔下來。

為什麼是這支：
  依 2026 年統計，「價格或庫存與到達頁不符」是 Merchant Center 商品拒登的第一大原因。
  Google 的內容爬蟲會實際抓到達頁，比對 feed 值與頁面上的價格、幣別、庫存狀態，
  以及 schema.org 結構化標記——三者只要不一致就可能整批拒登。

  在本專案的模擬資料中，這支偵測器對應 52 張工單、320.7 小時工程時數。

回傳的 Finding 會建議 playbook 動作 `feed.repush`（低風險、可逆、可自動執行）；
若重推後仍不符，代表是上游 ERP/OMS 問題而非同步延遲，才升級為工單。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import Detector, Finding

# 各欄位的容忍度與嚴重度。價格與庫存最嚴格，因為它們直接觸發拒登。
FIELD_RULES: dict[str, dict[str, Any]] = {
    "price": {"tolerance_pct": 0.0, "severity": "S1", "label": "價格"},
    "availability": {"tolerance_pct": None, "severity": "S1", "label": "庫存狀態"},
    "currency": {"tolerance_pct": None, "severity": "S1", "label": "幣別"},
    "sale_price": {"tolerance_pct": 0.0, "severity": "S2", "label": "特價"},
    "gtin": {"tolerance_pct": None, "severity": "S2", "label": "GTIN"},
    "title": {"tolerance_pct": None, "severity": "S3", "label": "標題"},
    "image_link": {"tolerance_pct": None, "severity": "S3", "label": "主圖"},
}

# 不符比率超過這個門檻才告警，避免單一商品的雜訊
ALERT_THRESHOLD_PCT = 2.0


@dataclass
class Mismatch:
    item_id: str
    field: str
    feed_value: Any
    landing_value: Any


class FeedHealthDetector(Detector):
    detector_id = "feed_health"
    schedule = "hourly"
    dedup_window_hours = 6

    def __init__(self, probe_feed_vs_landing: Callable[..., dict]) -> None:
        """probe_feed_vs_landing 由外部注入（正式接真實探針，測試注入假資料）。

        探針必須是唯讀的，見 specs/probes.yaml。
        """
        super().__init__()
        self._probe = probe_feed_vs_landing

    def scan(self, *, catalogs: list[dict], sample_size: int = 200) -> list[Finding]:
        findings: list[Finding] = []
        for cat in catalogs:
            result = self._probe(catalog_id=cat["catalog_id"], sample_size=sample_size)
            findings.extend(self._evaluate(cat, result, sample_size))
        return self.emit(findings)

    # ------------------------------------------------------------------
    def _evaluate(self, cat: dict, result: dict, sample_size: int) -> list[Finding]:
        mismatches = [Mismatch(**m) for m in result.get("mismatches", [])]
        if not mismatches:
            return []

        by_field: dict[str, list[Mismatch]] = {}
        for m in mismatches:
            by_field.setdefault(m.field, []).append(m)

        out: list[Finding] = []
        for field_name, items in by_field.items():
            rule = FIELD_RULES.get(field_name)
            if rule is None:
                continue
            rate = len(items) / max(sample_size, 1) * 100
            if rate < ALERT_THRESHOLD_PCT:
                continue

            # 價格類欄位再過一次容忍度（避免小數點格式差異誤報）
            if rule["tolerance_pct"] is not None:
                items = [m for m in items if not self._within_tolerance(m, rule["tolerance_pct"])]
                if not items:
                    continue

            out.append(
                Finding(
                    detector_id=self.detector_id,
                    severity=rule["severity"],
                    title=f"{rule['label']}與到達頁不符（{len(items)} 檔商品）",
                    summary=(
                        f"{cat['client']} 的 catalog {cat['catalog_id']} 有 {len(items)} 檔商品的"
                        f"{rule['label']}與到達頁不一致，抽樣不符率 {rate:.1f}%。"
                        f"此為 Merchant Center 商品拒登的主要原因，建議先重推 feed 排除同步延遲。"
                    ),
                    client=cat["client"],
                    asset_id=cat["catalog_id"],
                    evidence={
                        "field": field_name,
                        "mismatch_count": len(items),
                        "sample_size": sample_size,
                        "mismatch_rate_pct": round(rate, 2),
                        "samples": [vars(m) for m in items[:10]],
                        "structured_data_present": result.get("structured_data_present"),
                    },
                    maps_to_issue_category="商品資訊與Feed",
                    suggested_action_id="feed.repush",
                )
            )
        return out

    @staticmethod
    def _within_tolerance(m: Mismatch, tol_pct: float) -> bool:
        try:
            a, b = float(m.feed_value), float(m.landing_value)
        except (TypeError, ValueError):
            return False
        if a == 0:
            return b == 0
        return abs(a - b) / abs(a) * 100 <= tol_pct
