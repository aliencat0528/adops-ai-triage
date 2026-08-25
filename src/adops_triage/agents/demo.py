"""L1 提單助理 demo — `make demo`

跑兩張工單各一次：一張資訊齊全、一張語焉不詳，印出評分結果與追問。
L2 分診尚未實作（`agents/triage.py` 只有介面），所以本 demo 只涵蓋 L1。
"""
from __future__ import annotations

from pathlib import Path

from adops_triage.agents.intake import IntakeAgent

SCHEMA = Path("specs/ticket.schema.json")

齊全的單 = {
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

語焉不詳的急件 = {
    "ticket_id": "REQ-202608-0002", "submitted_at": "2026-08-20 11:30",
    "org_context": "MarTech SaaS客戶技術支援", "requester_name": "王大明",
    "client_brand": "H客戶-旅遊平台", "issue_category": "事件追蹤異常",
    "title": "數字怪怪的", "description": "客戶說轉換數不太對，很急",
    "platform": "Google(Ads/GA4/GTM)", "severity": "S1-投放中斷/嚴重失真",
    "priority": "P0-立即", "reproducible": "無法重現",
}


def show(agent: IntakeAgent, name: str, ticket: dict) -> None:
    r = agent.score(ticket)
    print(f"\n──────── {name} ────────")
    print(f"完整度       {r.completeness} 分")
    print(f"可否送出     {'可以' if r.can_submit else '擋下'}"
          f"{'（P0 可 override，但會標記）' if r.needs_override else ''}")
    if r.blocking_missing:
        print(f"擋住診斷的   {'、'.join(r.blocking_missing)}")
    if r.flags:
        print(f"標記         {'、'.join(r.flags)}")
    if r.questions:
        print("這一輪要問：")
        for q in r.questions:
            print(f"  → {q}")


def main() -> None:
    agent = IntakeAgent(SCHEMA)
    show(agent, "資訊齊全的單", 齊全的單)
    show(agent, "語焉不詳的 P0 急件", 語焉不詳的急件)
    print("\n（L2 分診尚未實作，見 TASKS.md T-301～T-306）")


if __name__ == "__main__":
    main()
