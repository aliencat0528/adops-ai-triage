# -*- coding: utf-8 -*-
"""偵測器測試：驗證門檻邏輯與去重，避免製造誤報。"""

from datetime import date

from adops_triage.detectors.cross_source_recon import CrossSourceReconDetector
from adops_triage.detectors.feed_health import FeedHealthDetector


def test_feed健檢低於門檻不告警() -> None:
    def probe(catalog_id: str, sample_size: int = 200) -> dict:
        return {
            "mismatches": [
                {"item_id": "SKU-1", "field": "price", "feed_value": 100, "landing_value": 90}
            ],
            "structured_data_present": True,
        }

    d = FeedHealthDetector(probe)
    out = d.scan(catalogs=[{"catalog_id": "cat_1", "client": "A"}], sample_size=200)
    assert out == []  # 1/200 = 0.5% < 2% 門檻


def test_feed健檢超過門檻會建議重推() -> None:
    def probe(catalog_id: str, sample_size: int = 200) -> dict:
        return {
            "mismatches": [
                {"item_id": f"SKU-{i}", "field": "price", "feed_value": 1280, "landing_value": 1180}
                for i in range(20)
            ],
            "structured_data_present": True,
        }

    d = FeedHealthDetector(probe)
    out = d.scan(catalogs=[{"catalog_id": "cat_1", "client": "A"}], sample_size=200)
    assert len(out) == 1
    assert out[0].severity == "S1"
    assert out[0].suggested_action_id == "feed.repush"
    assert out[0].maps_to_issue_category == "商品資訊與Feed"


def test_feed健檢會去重() -> None:
    def probe(catalog_id: str, sample_size: int = 200) -> dict:
        return {
            "mismatches": [
                {
                    "item_id": f"SKU-{i}",
                    "field": "availability",
                    "feed_value": "in stock",
                    "landing_value": "out of stock",
                }
                for i in range(20)
            ],
            "structured_data_present": True,
        }

    d = FeedHealthDetector(probe)
    cats = [{"catalog_id": "cat_1", "client": "A"}]
    assert len(d.scan(catalogs=cats)) == 1
    assert d.scan(catalogs=cats) == []  # 6 小時內同一 finding 不重複告警


def test_對帳單日超標先觀察不立即告警() -> None:
    def probe(client: str, date_from: date, date_to: date) -> dict:
        return {
            "platform_conversions": 200,
            "ga4_conversions": 100,
            "backend_orders": 100,
            "attribution_windows": {},
        }

    d = CrossSourceReconDetector(probe)
    assert d.scan(clients=["A"], target_date=date(2026, 8, 1)) == []  # 第一天只計數
    out = d.scan(clients=["A"], target_date=date(2026, 8, 2))  # 第二天才告警
    assert len(out) == 1
    assert out[0].severity == "S1"  # 100% 差異 >= 40%


def test_對帳門檻內不告警() -> None:
    def probe(client: str, date_from: date, date_to: date) -> dict:
        return {
            "platform_conversions": 115,
            "ga4_conversions": 108,
            "backend_orders": 100,
            "attribution_windows": {},
        }

    d = CrossSourceReconDetector(probe)
    d.scan(clients=["A"], target_date=date(2026, 8, 1))
    assert d.scan(clients=["A"], target_date=date(2026, 8, 2)) == []  # 15% < 20% 門檻
