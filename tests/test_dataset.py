# -*- coding: utf-8 -*-
"""資料一致性測試：驗證欄位之間的因果鏈確實成立。"""
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return pd.read_csv("data/raw/tickets.csv")


def test_筆數與欄數(df: pd.DataFrame) -> None:
    assert len(df) == 640
    assert len(df.columns) >= 50


def test_完整度與釐清次數負相關(df: pd.DataFrame) -> None:
    corr = df["info_completeness_score"].corr(df["clarification_rounds"])
    assert corr < -0.6, f"相關係數 {corr:.3f} 太弱，因果鏈沒有被還原出來"


def test_釐清次數越多處理時數越長(df: pd.DataFrame) -> None:
    med = df.groupby("clarification_rounds")["resolution_hours"].median()
    med = med[df.groupby("clarification_rounds").size() >= 20]
    assert med.is_monotonic_increasing, "釐清成本曲線不是單調遞增"


def test_結案單必有結案時間(df: pd.DataFrame) -> None:
    closed = df[df["status"] == "已結案"]
    assert (closed["resolved_at"] != "—").all()


def test_未結案單不應有滿意度(df: pd.DataFrame) -> None:
    open_t = df[df["status"] != "已結案"]
    assert (open_t["csat"] == "—").all()


def test_重複單必有來源單號(df: pd.DataFrame) -> None:
    dup = df[df["is_duplicate"] == "是"]
    assert (dup["duplicate_of"] != "—").all()


def test_平台事件工單處理時數高於基準(df: pd.DataFrame) -> None:
    ev = df[df["platform_event_id"] != "—"]
    base = df[df["platform_event_id"] == "—"]
    assert ev["resolution_hours"].median() > base["resolution_hours"].median() * 1.4


def test_不可預防的根因沒有偵測訊號(df: pd.DataFrame) -> None:
    no_prev = df[df["ai_preventable"] == "否"]
    assert (no_prev["detection_signal"] == "—").all()
