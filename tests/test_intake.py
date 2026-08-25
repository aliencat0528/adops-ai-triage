# -*- coding: utf-8 -*-
"""提單助理評分器測試。"""
from pathlib import Path

import pytest

from adops_triage.agents.intake import IntakeAgent

SCHEMA = Path("specs/ticket.schema.json")


@pytest.fixture
def agent() -> IntakeAgent:
    return IntakeAgent(SCHEMA)


def test_完整工單可以送出(agent: IntakeAgent) -> None:
    t = {
        "ticket_id": "REQ-202608-0001", "submitted_at": "2026-08-20 10:00",
        "org_context": "廣告代理商內部RD支援", "requester_name": "陳怡君",
        "client_brand": "熙食嚴選", "issue_category": "事件追蹤異常",
        "title": "轉換事件遺失", "description": "Purchase 事件從 8/18 起完全沒有進來",
        "platform": "Meta(Pixel+CAPI)", "severity": "S2-成效顯著受損",
        "affected_asset_id": "pixel_123456789012345", "occurred_from": "2026-08-18",
        "tracking_method": "Hybrid (雙軌+dedup)", "reproducible": "可穩定重現",
        "environment": "正式站Production", "metric_before": 3200, "metric_after": 0,
        "impacted_campaign_count": 6, "attachment_count": 3,
        "website_platform": "91APP", "business_impact": "預算誤配／成效失真",
    }
    r = agent.score(t)
    assert r.completeness >= 85
    assert r.can_submit is True
    assert r.blocking_missing == []


def test_語焉不詳的單被擋下並產生追問(agent: IntakeAgent) -> None:
    t = {
        "ticket_id": "REQ-202608-0002", "submitted_at": "2026-08-20 23:40",
        "org_context": "廣告代理商內部RD支援", "requester_name": "李欣穎",
        "client_brand": "熙食嚴選", "issue_category": "事件追蹤異常",
        "title": "數字不對", "description": "客戶說廣告數字不對，很急",
        "platform": "Meta(Pixel+CAPI)", "severity": "S1-投放中斷/嚴重失真",
        "priority": "P0-立即",
    }
    r = agent.score(t)
    assert r.completeness < 40
    assert r.can_submit is False
    assert "affected_asset_id" in r.blocking_missing
    assert r.needs_override is True            # P0 可 override
    assert any("資產" in q for q in r.questions)
    assert len(r.questions) <= 2               # 一輪最多兩題


def test_必填欄位隨問題大類動態變更(agent: IntakeAgent) -> None:
    base = {"ticket_id": "REQ-202608-0003", "submitted_at": "2026-08-20 10:00",
            "org_context": "電商品牌in-house團隊", "requester_name": "張家豪",
            "client_brand": "官網主站", "title": "x", "description": "yyyyyyyyyy",
            "platform": "商品Feed/Catalog", "severity": "S3-局部影響"}

    feed = agent.required_fields({**base, "issue_category": "商品資訊與Feed"})
    audience = agent.required_fields({**base, "issue_category": "受眾與媒合"})

    assert "website_platform" in feed
    assert "metric_before" in audience          # 受眾類要前後值
    assert "metric_before" not in feed          # Feed 類不要


def test_高嚴重度必須量化影響(agent: IntakeAgent) -> None:
    req = agent.required_fields({"issue_category": "API與整合", "severity": "S1-投放中斷/嚴重失真"})
    assert "impacted_spend_daily_ntd" in req
    assert "business_impact" in req
