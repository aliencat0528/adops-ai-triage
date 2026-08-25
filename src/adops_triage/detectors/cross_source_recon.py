# -*- coding: utf-8 -*-
"""
L0 · 跨來源日對帳偵測器
=======================
每日比對三個來源的轉換數：廣告平台回報 / GA4 / 後台實際訂單。

為什麼門檻是 20%：
  平台與 GA4 的歸因邏輯本來就不同（歸因視窗、跨裝置、last-click vs data-driven），
  小幅差異屬於預期行為，不是故障。把門檻設太低會製造大量誤報，
  反而讓真正的異常被淹沒——這是監控系統最常見的失敗模式。

  LINE LAP 的官方建議即為「與內部系統差異超過 20% 才需調查」，本偵測器沿用此門檻。

這支偵測器攔截的是「歸因與報表」類工單，也是 §02 那兩個 2026 平台事件的第二道防線：
當 changelog 監控沒接住時，對帳會在隔天發現數字對不上。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .base import Detector, Finding

VARIANCE_THRESHOLD_PCT = 20.0
SEVERE_THRESHOLD_PCT = 40.0

# 連續幾天超標才升級——單日差異可能只是資料延遲
CONSECUTIVE_DAYS_TO_ESCALATE = 2


class CrossSourceReconDetector(Detector):
    detector_id = "cross_source_recon"
    schedule = "daily"
    dedup_window_hours = 24

    def __init__(self, probe_cross_source_recon: Callable[..., dict]) -> None:
        super().__init__()
        self._probe = probe_cross_source_recon
        self._streak: dict[tuple[str, str], int] = {}

    def scan(self, *, clients: list[str], target_date: date) -> list[Finding]:
        findings: list[Finding] = []
        for client in clients:
            r = self._probe(client=client, date_from=target_date, date_to=target_date)
            findings.extend(self._evaluate(client, target_date, r))
        return self.emit(findings)

    # ------------------------------------------------------------------
    def _evaluate(self, client: str, d: date, r: dict[str, Any]) -> list[Finding]:
        backend = r.get("backend_orders") or 0
        if backend <= 0:
            return []  # 沒有訂單就沒有比較基準，不告警

        out: list[Finding] = []
        pairs = {
            "platform_vs_backend": (r.get("platform_conversions"), backend, "平台回報 vs 後台訂單"),
            "ga4_vs_backend": (r.get("ga4_conversions"), backend, "GA4 vs 後台訂單"),
        }

        for key, (value, base, label) in pairs.items():
            if value is None:
                continue
            variance = abs(value - base) / base * 100
            streak_key = (client, key)

            if variance < VARIANCE_THRESHOLD_PCT:
                self._streak[streak_key] = 0
                continue

            self._streak[streak_key] = self._streak.get(streak_key, 0) + 1
            if self._streak[streak_key] < CONSECUTIVE_DAYS_TO_ESCALATE:
                continue  # 單日超標先觀察，可能只是資料延遲

            out.append(
                Finding(
                    detector_id=self.detector_id,
                    severity="S1" if variance >= SEVERE_THRESHOLD_PCT else "S2",
                    title=f"{label}差異 {variance:.0f}%（連續 {self._streak[streak_key]} 日）",
                    summary=(
                        f"{client} 在 {d} 的{label}差異達 {variance:.1f}%，"
                        f"已連續 {self._streak[streak_key]} 日超過 {VARIANCE_THRESHOLD_PCT:.0f}% 門檻。"
                        f"請先確認歸因視窗設定是否一致，再檢查追蹤是否有遺失。"
                    ),
                    client=client,
                    asset_id=key,
                    evidence={
                        "date": str(d),
                        "platform_conversions": r.get("platform_conversions"),
                        "ga4_conversions": r.get("ga4_conversions"),
                        "backend_orders": backend,
                        "variance_pct": round(variance, 2),
                        "consecutive_days": self._streak[streak_key],
                        "attribution_windows": r.get("attribution_windows"),
                        "note": "平台與 GA4 歸因邏輯本就不同，門檻 20% 以下屬預期行為",
                    },
                    maps_to_issue_category="歸因與報表",
                    suggested_action_id=None,  # 需人判斷，不自動修復
                )
            )
        return out
