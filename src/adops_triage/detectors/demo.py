"""L0 主動偵測器 demo — `make detect`

用 `probes/readonly.py` 的 mock 探針各跑一次兩個偵測器，印出 Finding。
跨源對帳刻意跑兩天：第一天只計數不告警，第二天才告警——這是為了避免
單日波動製造誤報，看得到這個行為才算看懂這支偵測器。
"""
from __future__ import annotations

from datetime import date, timedelta

from adops_triage.detectors.cross_source_recon import CrossSourceReconDetector
from adops_triage.detectors.feed_health import FeedHealthDetector
from adops_triage.probes.readonly import probe_cross_source_recon, probe_feed_vs_landing


def show(findings: list) -> None:
    if not findings:
        print("  （無告警）")
        return
    for f in findings:
        print(f"  [{f.severity}] {f.title}")
        print(f"        客戶 {f.client} · 資產 {f.asset_id}")
        print(f"        {f.summary}")
        print(f"        對應問題大類：{f.maps_to_issue_category}")
        print(f"        建議動作：{f.suggested_action_id or '（無，僅告警）'}")
        print(f"        指紋：{f.fingerprint}")


def main() -> None:
    print("──────── Feed 健檢 ────────")
    feed = FeedHealthDetector(probe_feed_vs_landing)
    # 這兩個 ID 的 mock 值會超過門檻——mock 已改為穩定種子，所以每次跑結果一樣
    catalogs = [{"catalog_id": "cat_10000", "client": "熙食嚴選"}]
    show(feed.scan(catalogs=catalogs))
    print("  同一輪再掃一次（24 小時去重）：")
    show(feed.scan(catalogs=catalogs))

    print("\n──────── 跨源對帳 ────────")
    recon = CrossSourceReconDetector(probe_cross_source_recon)
    day1 = date(2026, 8, 24)
    print(f"  {day1}（第一天，只計數）：")
    show(recon.scan(clients=["熙食嚴選"], target_date=day1))
    day2 = day1 + timedelta(days=1)
    print(f"  {day2}（連續第二天超標才告警）：")
    show(recon.scan(clients=["熙食嚴選"], target_date=day2))


if __name__ == "__main__":
    main()
