"""回放評測測試：守住三件容易算錯的事。"""

from pathlib import Path

import pandas as pd
import pytest

from adops_triage.agents.intake import IntakeAgent
from adops_triage.analysis.replay import MISSING_TO_FIELD, as_submitted, replay

SCHEMA = Path("specs/ticket.schema.json")


@pytest.fixture
def agent() -> IntakeAgent:
    return IntakeAgent(SCHEMA)


def _row(**kw) -> pd.Series:
    base = {
        "ticket_id": "REQ-T-0001",
        "issue_category": "事件追蹤異常",
        "platform": "Meta(Pixel+CAPI)",
        "affected_asset_id": "pixel_123456789012345",
        "occurred_from": "2026-08-18",
        "environment": "正式站Production",
        "reproducible": "可穩定重現",
        "impacted_campaign_count": 6,
        "attachment_count": 3,
        "client_brand": "熙食嚴選",
        "website_platform": "91APP",
        "severity": "S2-成效顯著受損",
        "metric_before": 3200,
        "metric_after": 0,
        "impacted_spend_daily_ntd": 120000,
        "description": "Purchase 事件從 8/18 起完全沒有進來",
        "missing_fields": "無",
        "clarification_rounds": 3,
        "resolution_hours": 20.0,
        "eng_effort_hours": 8.0,
        "info_completeness_score": 70,
    }
    base.update(kw)
    return pd.Series(base)


def test_缺漏詞會清掉對應欄位() -> None:
    ticket, cleared, unmapped = as_submitted(_row(missing_fields="資產ID、後台截圖"))
    assert set(cleared) == {"affected_asset_id", "attachment_count"}
    assert "affected_asset_id" not in ticket
    assert unmapped == []


def test_對不到欄位的缺漏詞只記錄不動欄位() -> None:
    ticket, cleared, unmapped = as_submitted(_row(missing_fields="錯誤訊息全文、GTM容器版本"))
    assert cleared == []
    assert unmapped == ["錯誤訊息全文", "GTM容器版本"]
    # 這兩個詞在 schema 沒有對應欄位，工單內容不該被動到
    assert ticket["affected_asset_id"] == "pixel_123456789012345"


def test_省下的輪數不會超過原本問的輪數(agent: IntakeAgent) -> None:
    # 原本只問 1 輪，就算助理補回再多欄位也不能宣稱省了 2 輪
    df = pd.DataFrame([_row(missing_fields="受影響活動清單", clarification_rounds=0)])
    out = replay(df, agent, slope_pct=22.2)
    assert out["rounds_saved_mean"] == 0
    assert out["eng_hours_saved"] == 0


def test_係數用觀測值換算工時(agent: IntakeAgent) -> None:
    df = pd.DataFrame([_row(missing_fields="受影響活動清單", clarification_rounds=2)])
    out = replay(df, agent, slope_pct=22.2)
    if out["tickets_helped"]:
        # 省 1 輪 ＝ 回收 (1 − 1/1.222) ≈ 18.2% 的處理時數，再乘該筆的工程/處理時數比
        expected = 20.0 * (1 - 1.222**-1) * (8.0 / 20.0)
        # 輸出四捨五入到小數一位，所以用絕對誤差比
        assert out["eng_hours_saved"] == pytest.approx(expected, abs=0.06)


def test_對照表只收對得到欄位的詞() -> None:
    assert len(MISSING_TO_FIELD) == 6
    assert "錯誤訊息全文" not in MISSING_TO_FIELD
