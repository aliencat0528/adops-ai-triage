# -*- coding: utf-8 -*-
"""
L3 · 唯讀探針
=============
七支探針的介面與 mock 實作，介面定義見 specs/probes.yaml。

鐵則：本模組任何函式都不得有寫入行為。
  - CI 會靜態掃描本目錄（tools/check_probes_readonly.py）
  - Terraform 綁定的服務帳號只有 read 角色，寫入會被平台回 403
  兩層護欄缺一不可。

正式實作時把 mock 換成真實 API 呼叫，介面簽章不變，診斷 Agent 不需修改。
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any

READ_ONLY = True   # 供執行期斷言使用


def _stable_seed(*parts: str) -> int:
    """mock 資料的隨機種子。

    不用內建 `hash()`——它對字串每個 process 重新隨機化，會讓同一支探針
    在不同 process 回傳不同 mock 值，測試與 demo 都不可重現。
    """
    joined = "|".join(parts)
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8], 16)


def _assert_readonly() -> None:
    if not READ_ONLY:
        raise RuntimeError("探針被設定為非唯讀，這違反架構約束")


# ------------------------------------------------------------------ 探針

def probe_pixel_events(asset_id: str, date_from: date, date_to: date) -> dict[str, Any]:
    """事件量趨勢、參數覆蓋率、觸發頁面分布。"""
    _assert_readonly()
    rng = random.Random(_stable_seed(asset_id, str(date_from)))
    days = (date_to - date_from).days + 1
    base = rng.randint(800, 12000)
    return {
        "daily_event_counts": [
            {"date": str(date_from + timedelta(days=i)),
             "Purchase": int(base * rng.uniform(0.7, 1.2)),
             "ViewContent": int(base * rng.uniform(4, 9))}
            for i in range(days)
        ],
        "param_coverage": {"value": 0.98, "currency": 0.98,
                           "content_ids": rng.uniform(0.4, 1.0), "event_id": rng.uniform(0.6, 1.0)},
        "trigger_pages": {"/checkout/success": 0.86, "/cart": 0.09, "其他": 0.05},
        "week_over_week_delta_pct": round(rng.uniform(-45, 12), 1),
    }


def probe_emq(pixel_id: str) -> dict[str, Any]:
    """EMQ 分數與識別參數覆蓋率。

    參數影響權重（高→低）：fbc / em > ph / fbp > fn·ln / zp / external_id > 地理·IP·UA。
    補上電話號碼通常是單一改動中最大的分數提升。
    """
    _assert_readonly()
    rng = random.Random(_stable_seed(pixel_id))
    cov = {"em": rng.uniform(.7, 1.0), "ph": rng.uniform(.0, .8), "fbp": rng.uniform(.5, 1.0),
           "fbc": rng.uniform(.2, .9), "external_id": rng.uniform(.0, .7),
           "fn": rng.uniform(.2, .9), "ln": rng.uniform(.2, .9), "zp": rng.uniform(.0, .6)}
    score = 3 + 3 * cov["em"] + 1.6 * cov["ph"] + 1.2 * cov["fbc"] + 0.8 * cov["fbp"]
    return {
        "emq_score": round(min(10, score), 1),
        "param_coverage": {k: round(v, 3) for k, v in cov.items()},
        "dedup_warnings": [] if cov["fbp"] > .7 else ["部分事件的 event_id 在 Pixel 與 CAPI 不一致"],
        "hash_format_errors": [],
    }


def probe_feed_vs_landing(catalog_id: str, sample_size: int = 200) -> dict[str, Any]:
    """Feed 值與到達頁逐項比對。價格與庫存不符是商品拒登第一大原因。"""
    _assert_readonly()
    rng = random.Random(_stable_seed(catalog_id))
    n_bad = rng.randint(0, max(1, sample_size // 8))
    mismatches = []
    for i in range(n_bad):
        f = rng.choice(["price", "availability", "price", "currency", "gtin"])
        feed_v, land_v = (rng.choice([1280, 990, 2490]), rng.choice([1180, 890, 2290])) \
            if f in ("price",) else (rng.choice(["in stock", "TWD", "471..."]),
                                     rng.choice(["out of stock", "USD", "472..."]))
        mismatches.append({"item_id": f"SKU-{rng.randint(10000, 99999)}",
                           "field": f, "feed_value": feed_v, "landing_value": land_v})
    return {
        "mismatches": mismatches,
        "mismatch_rate_by_field": {},
        "structured_data_present": rng.random() > .25,
        "disapproval_reasons": {"price_mismatch": n_bad // 2} if n_bad else {},
    }


def probe_gtm_versions(container_id: str, lookback_days: int = 30) -> dict[str, Any]:
    _assert_readonly()
    rng = random.Random(_stable_seed(container_id))
    return {
        "versions": [{"version": 40 + i, "published_at": str(date.today() - timedelta(days=d)),
                      "publisher": rng.choice(["客戶端IT", "我方顧問"]), "summary": "調整觸發器條件"}
                     for i, d in enumerate(sorted(rng.sample(range(lookback_days), 3)))],
        "diff_vs_last_stable": ["新增 Purchase 觸發器", "移除舊版 Pixel 標籤"],
        "trigger_changes": 2,
    }


def probe_cross_source_recon(client: str, date_from: date, date_to: date) -> dict[str, Any]:
    """平台 / GA4 / 後台訂單三方對帳。差異率 >20% 才視為異常。"""
    _assert_readonly()
    rng = random.Random(_stable_seed(client, str(date_from)))
    backend = rng.randint(40, 900)
    return {
        "platform_conversions": int(backend * rng.uniform(0.6, 1.5)),
        "ga4_conversions": int(backend * rng.uniform(0.7, 1.2)),
        "backend_orders": backend,
        "variance_pct": None,
        "attribution_windows": {"platform": "7d_click", "ga4": "data-driven"},
    }


def probe_token_status(account_id: str) -> dict[str, Any]:
    """憑證到期日與 API 錯誤率。到期前 14 天即應預警。"""
    _assert_readonly()
    rng = random.Random(_stable_seed(account_id))
    return {
        "tokens": [{"type": "access_token", "expires_in_days": rng.randint(-2, 90),
                    "scopes": ["ads_read", "catalog_management"]}],
        "api_error_rate_24h": round(rng.uniform(0, .12), 4),
        "recent_error_codes": {"190": rng.randint(0, 8), "429": rng.randint(0, 20)},
    }


def probe_platform_changelog(date_from: date, date_to: date,
                             features_used: list[str]) -> dict[str, Any]:
    """平台變更公告 × 客戶實際使用參數的交集。專門對付靜默失敗。"""
    _assert_readonly()
    known = [
        {"date": "2026-01-12", "platform": "META",
         "change": "Ads Insights API 移除 7d_view / 28d_view 歸因視窗",
         "deprecated": ["7d_view", "28d_view"], "silent": True},
        {"date": "2026-06-15", "platform": "GOOGLE",
         "change": "Google Signals 不再控管 GA4→Ads 資料流，ad_storage 成為唯一閘門",
         "deprecated": ["google_signals_gate"], "silent": True},
    ]
    hits = [c for c in known
            if str(date_from) <= c["date"] <= str(date_to)
            and set(c["deprecated"]) & set(features_used)]
    return {
        "changes": known,
        "impacted_features": sorted({f for c in hits for f in c["deprecated"]}),
        "silent_failure_risk": any(c["silent"] for c in hits),
    }


PROBE_REGISTRY = {
    "probe_pixel_events": probe_pixel_events,
    "probe_emq": probe_emq,
    "probe_feed_vs_landing": probe_feed_vs_landing,
    "probe_gtm_versions": probe_gtm_versions,
    "probe_cross_source_recon": probe_cross_source_recon,
    "probe_token_status": probe_token_status,
    "probe_platform_changelog": probe_platform_changelog,
}
