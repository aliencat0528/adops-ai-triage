# -*- coding: utf-8 -*-
"""
廣告支援工程需求單資料生成器
=================================
生成邏輯自洽的模擬需求單，用於反推系統設計。

設計原則
--------
1. 欄位之間有因果關係，不是各自獨立亂數：
   資訊完整度 ↓ → 釐清次數 ↑ → 總處理時數 ×(1+0.38×釐清次數) → CSAT ↓
2. 時間軸上埋入 2026 年真實平台事件（見 specs/taxonomy.yaml#platform_events），
   讓資料有可驗證的骨架，而非純虛構。
3. 台灣電商檔期造成工單量季節性尖峰。

輸出
----
data/raw/tickets.csv   英文欄位名，對應 specs/ticket.schema.json，供程式使用
（xlsx 由 export_xlsx.py 產出，中文欄位名，供人閱讀）

用法
----
python -m adops_triage.generate_dataset --n 640 --seed 20260823
"""

from __future__ import annotations

import argparse
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------- 工具


def stable_int(text: str) -> int:
    """把字串轉成跨 process 穩定的整數。

    不能用內建 `hash()`——CPython 對字串的 hash 每個 process 重新隨機化
    （PYTHONHASHSEED），同一顆 --seed 會產出不同資料，違反「資料生成必須可重現」。
    """
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------- 常數

START = datetime(2025, 8, 1)
END = datetime(2026, 8, 20)

PLATFORM_EVENTS = [
    # (id, 日期, 平台, 主要衝擊的問題細類, 強制根因, 影響天數, 額外工單量)
    (
        "META_VIEW_ATTR_REMOVAL",
        datetime(2026, 1, 12),
        "META",
        [
            "平台回報轉換與後台實際訂單落差",
            "事件量驟降30%以上",
            "歸因視窗設定不一致造成報表對不起來",
        ],
        "POLICY",
        21,
        26,
    ),
    (
        "GA4_CONSENT_SPLIT",
        datetime(2026, 6, 15),
        "GOOGLE",
        [
            "Consent Mode v2／CMP同意訊號設定",
            "再行銷受眾規模歸零或過小",
            "Consent Mode/CMP導致事件下降",
        ],
        "POLICY",
        18,
        22,
    ),
]

TW_PEAKS = [(3, 8), (5, 10), (6, 18), (9, 9), (10, 10), (11, 11), (12, 12), (1, 20)]

ORG_CONTEXTS = [
    ("AGN", "廣告代理商內部RD支援", 0.50),
    ("SAAS", "MarTech SaaS客戶技術支援", 0.30),
    ("INH", "電商品牌in-house團隊", 0.20),
]

REQUESTER_ROLES = {
    "AGN": [
        ("媒體投手", 0.45),
        ("資深投手/組長", 0.18),
        ("AM客戶經理", 0.22),
        ("企劃/Planner", 0.10),
        ("data analyst", 0.05),
    ],
    "SAAS": [
        ("客戶成功經理CSM", 0.34),
        ("Solution Consultant", 0.20),
        ("客戶端行銷窗口", 0.28),
        ("業務BD", 0.10),
        ("客戶端IT窗口", 0.08),
    ],
    "INH": [
        ("電商行銷專員", 0.40),
        ("行銷主管", 0.16),
        ("電商營運PM", 0.24),
        ("站內工程師", 0.12),
        ("data analyst", 0.08),
    ],
}

ASSIGNED_TEAMS = {
    "AGN": [
        ("內部RD/工程組", 0.40),
        ("Data Engineering", 0.22),
        ("MarTech技術顧問", 0.20),
        ("平台原廠窗口", 0.10),
        ("客戶端IT", 0.08),
    ],
    "SAAS": [
        ("Solution Engineering", 0.36),
        ("後端工程Backend", 0.20),
        ("Data Engineering", 0.18),
        ("整合工程Integration", 0.16),
        ("平台原廠窗口", 0.10),
    ],
    "INH": [
        ("站內前端工程", 0.30),
        ("後端工程Backend", 0.24),
        ("Data Engineering", 0.20),
        ("外包/系統商", 0.16),
        ("平台原廠窗口", 0.10),
    ],
}

INDUSTRIES = [
    ("綜合電商", 0.17),
    ("美妝保養", 0.14),
    ("服飾配件", 0.13),
    ("食品生鮮", 0.10),
    ("3C家電", 0.09),
    ("保健食品", 0.09),
    ("旅遊訂房", 0.07),
    ("金融保險", 0.06),
    ("遊戲App", 0.06),
    ("教育課程", 0.05),
    ("家居家具", 0.04),
]

WEBSITE_PLATFORMS = [
    ("91APP", 0.18),
    ("Shopify", 0.16),
    ("SHOPLINE", 0.13),
    ("Cyberbiz", 0.11),
    ("自建站(React/Next.js)", 0.15),
    ("WooCommerce", 0.08),
    ("Magento", 0.05),
    ("自建站(PHP傳統)", 0.09),
    ("App(React Native)", 0.05),
]

CONTRACT_TIERS = [
    ("白金Platinum(4hr SLA)", 0.18),
    ("黃金Gold(8hr SLA)", 0.32),
    ("標準Standard(1營業日)", 0.35),
    ("基礎Basic(3營業日)", 0.15),
]

ENVIRONMENTS = [
    ("正式站Production", 0.74),
    ("測試站Staging", 0.09),
    ("iOS App", 0.07),
    ("Android App", 0.06),
    ("LINE LIFF", 0.04),
]

PLAT = {
    "META": "Meta(Pixel+CAPI)",
    "GOOGLE": "Google(Ads/GA4/GTM)",
    "LINE": "LINE(LAP/LINE Tag)",
    "FEED": "商品Feed/Catalog",
    "TIKTOK": "TikTok Ads",
    "MULTI": "跨平台",
}

RC = {
    "FE": "客戶端網站改版／前端代碼異動",
    "GTM": "GTM容器設定或版本發布錯誤",
    "POLICY": "平台政策／API規格變更",
    "UPSTREAM": "上游資料源異常(ERP/OMS/CDP)",
    "USER": "提單人設定或操作認知錯誤",
    "AUTH": "API憑證／權限失效",
    "BUG": "內部系統程式Bug",
    "THIRD": "第三方服務中斷或延遲",
    "NOISSUE": "非問題(預期行為／認知落差)",
    "DATA": "資料定義／歸因口徑不一致",
    "INFRA": "基礎架構／流量負載問題",
}

RES = {
    "CODE": "程式修復(內部)",
    "CONFIG": "設定調整",
    "EDU": "教育說明／文件引導",
    "CLIENT": "請客戶端／系統商修改",
    "VENDOR": "向平台原廠申訴或開case",
    "NONE": "無需處理(誤報結案)",
    "ROUTE": "轉單至其他團隊",
}

DETECTION_SIGNALS = {
    "FE": "Tag 巡檢：每日爬關鍵頁面比對觸發指紋與參數完整度",
    "GTM": "GTM 發布哨兵：容器發布 webhook + 發布後自動回歸測試",
    "POLICY": "Changelog 監控：平台變更公告 × 客戶使用參數比對",
    "UPSTREAM": "Feed 健檢：上游資料新鮮度與筆數落差監控",
    "USER": "設定稽核：變更 log + 上線前檢查表自動驗證",
    "AUTH": "憑證到期預警：Token 到期日與 API 錯誤率監控",
    "BUG": "服務錯誤率告警（事後偵測，不可事前預防）",
    "THIRD": "第三方 status page 與心跳監控",
    "NOISSUE": "口徑差異知識庫比對（提單當下即時解釋）",
    "DATA": "跨源日對帳：平台 vs GA4 vs 後台訂單",
    "INFRA": "排程 SLA 監控與重試佇列告警",
}

# (大類, 細類, 平台權重, 根因權重, 基準工時, 嚴重度傾向)
ISSUES = [
    (
        "事件追蹤異常",
        "轉換事件完全遺失",
        {"META": 0.34, "GOOGLE": 0.30, "LINE": 0.16, "TIKTOK": 0.10, "MULTI": 0.10},
        {"FE": 0.34, "GTM": 0.24, "AUTH": 0.12, "BUG": 0.10, "POLICY": 0.08, "USER": 0.12},
        9.0,
        "high",
    ),
    (
        "事件追蹤異常",
        "事件量驟降30%以上",
        {"META": 0.32, "GOOGLE": 0.28, "LINE": 0.14, "TIKTOK": 0.10, "MULTI": 0.16},
        {"FE": 0.28, "POLICY": 0.18, "GTM": 0.16, "UPSTREAM": 0.12, "NOISSUE": 0.14, "THIRD": 0.12},
        8.0,
        "high",
    ),
    (
        "事件追蹤異常",
        "事件重複計算(dedup失效)",
        {"META": 0.52, "GOOGLE": 0.22, "LINE": 0.10, "TIKTOK": 0.06, "MULTI": 0.10},
        {"GTM": 0.30, "BUG": 0.24, "FE": 0.22, "USER": 0.14, "DATA": 0.10},
        7.0,
        "mid",
    ),
    (
        "事件追蹤異常",
        "事件參數缺失(value/currency/content_ids)",
        {"META": 0.40, "GOOGLE": 0.30, "LINE": 0.12, "TIKTOK": 0.08, "MULTI": 0.10},
        {"FE": 0.32, "GTM": 0.26, "USER": 0.16, "BUG": 0.14, "UPSTREAM": 0.12},
        5.5,
        "mid",
    ),
    (
        "事件追蹤異常",
        "事件觸發時機錯誤(頁面未完成即觸發)",
        {"META": 0.30, "GOOGLE": 0.36, "LINE": 0.14, "TIKTOK": 0.06, "MULTI": 0.14},
        {"GTM": 0.38, "FE": 0.30, "USER": 0.18, "BUG": 0.14},
        6.0,
        "mid",
    ),
    (
        "事件追蹤異常",
        "App SDK事件未回傳",
        {"META": 0.36, "GOOGLE": 0.26, "LINE": 0.12, "TIKTOK": 0.14, "MULTI": 0.12},
        {"FE": 0.30, "AUTH": 0.16, "POLICY": 0.18, "BUG": 0.22, "THIRD": 0.14},
        12.0,
        "high",
    ),
    (
        "事件追蹤異常",
        "Consent Mode/CMP導致事件下降",
        {"GOOGLE": 0.58, "META": 0.24, "LINE": 0.06, "MULTI": 0.12},
        {"POLICY": 0.30, "GTM": 0.26, "NOISSUE": 0.20, "USER": 0.14, "FE": 0.10},
        6.5,
        "mid",
    ),
    (
        "事件追蹤異常",
        "Server-side事件與Client-side數字對不上",
        {"META": 0.44, "GOOGLE": 0.32, "LINE": 0.08, "MULTI": 0.16},
        {"DATA": 0.30, "BUG": 0.22, "GTM": 0.20, "NOISSUE": 0.16, "UPSTREAM": 0.12},
        10.0,
        "mid",
    ),
    (
        "受眾與媒合",
        "顧客名單媒合率驟降",
        {"META": 0.34, "GOOGLE": 0.24, "LINE": 0.30, "TIKTOK": 0.04, "MULTI": 0.08},
        {
            "UPSTREAM": 0.30,
            "DATA": 0.20,
            "POLICY": 0.16,
            "BUG": 0.14,
            "USER": 0.12,
            "NOISSUE": 0.08,
        },
        11.0,
        "high",
    ),
    (
        "受眾與媒合",
        "EMQ事件比對品質分數下降",
        {"META": 0.78, "TIKTOK": 0.08, "GOOGLE": 0.08, "MULTI": 0.06},
        {"FE": 0.26, "DATA": 0.22, "POLICY": 0.16, "BUG": 0.16, "USER": 0.10, "NOISSUE": 0.10},
        9.5,
        "mid",
    ),
    (
        "受眾與媒合",
        "再行銷受眾規模歸零或過小",
        {"META": 0.36, "GOOGLE": 0.30, "LINE": 0.18, "TIKTOK": 0.08, "MULTI": 0.08},
        {"FE": 0.24, "USER": 0.22, "POLICY": 0.18, "UPSTREAM": 0.16, "NOISSUE": 0.20},
        6.0,
        "mid",
    ),
    (
        "受眾與媒合",
        "CDP自訂受眾同步失敗",
        {"META": 0.32, "GOOGLE": 0.20, "LINE": 0.30, "TIKTOK": 0.06, "MULTI": 0.12},
        {"AUTH": 0.28, "THIRD": 0.20, "BUG": 0.20, "UPSTREAM": 0.18, "INFRA": 0.14},
        8.5,
        "high",
    ),
    (
        "受眾與媒合",
        "跨裝置ID媒合異常(MAID/IDFA)",
        {"LINE": 0.40, "META": 0.28, "GOOGLE": 0.16, "TIKTOK": 0.10, "MULTI": 0.06},
        {"POLICY": 0.30, "DATA": 0.24, "UPSTREAM": 0.18, "NOISSUE": 0.16, "BUG": 0.12},
        10.5,
        "mid",
    ),
    (
        "受眾與媒合",
        "LINE MAID名單上傳失敗或比數異常",
        {"LINE": 0.92, "MULTI": 0.08},
        {"UPSTREAM": 0.26, "AUTH": 0.20, "USER": 0.20, "BUG": 0.18, "POLICY": 0.16},
        7.5,
        "mid",
    ),
    (
        "受眾與媒合",
        "Lookalike/類似受眾無法建立",
        {"META": 0.44, "GOOGLE": 0.26, "LINE": 0.20, "TIKTOK": 0.10},
        {"USER": 0.30, "NOISSUE": 0.24, "POLICY": 0.20, "UPSTREAM": 0.16, "BUG": 0.10},
        4.5,
        "low",
    ),
    (
        "受眾與媒合",
        "Enhanced Conversions雜湊值比對率過低",
        {"GOOGLE": 0.86, "META": 0.10, "MULTI": 0.04},
        {"FE": 0.28, "DATA": 0.24, "GTM": 0.20, "BUG": 0.14, "USER": 0.14},
        9.0,
        "mid",
    ),
    (
        "商品資訊與Feed",
        "商品價格與官網不符",
        {"FEED": 0.62, "META": 0.14, "GOOGLE": 0.16, "TIKTOK": 0.08},
        {"UPSTREAM": 0.40, "THIRD": 0.16, "BUG": 0.14, "USER": 0.14, "DATA": 0.16},
        5.0,
        "high",
    ),
    (
        "商品資訊與Feed",
        "庫存狀態不同步(已售完仍投放)",
        {"FEED": 0.60, "GOOGLE": 0.16, "META": 0.16, "TIKTOK": 0.08},
        {"UPSTREAM": 0.42, "THIRD": 0.18, "BUG": 0.16, "DATA": 0.14, "USER": 0.10},
        5.5,
        "high",
    ),
    (
        "商品資訊與Feed",
        "Feed整批拒登／商品被拒批",
        {"FEED": 0.48, "GOOGLE": 0.24, "META": 0.20, "TIKTOK": 0.08},
        {"POLICY": 0.34, "UPSTREAM": 0.20, "USER": 0.18, "DATA": 0.16, "BUG": 0.12},
        8.0,
        "high",
    ),
    (
        "商品資訊與Feed",
        "GTIN/item_id與Pixel content_ids對不上",
        {"FEED": 0.44, "META": 0.32, "GOOGLE": 0.18, "TIKTOK": 0.06},
        {"DATA": 0.34, "FE": 0.22, "UPSTREAM": 0.18, "BUG": 0.14, "USER": 0.12},
        9.5,
        "high",
    ),
    (
        "商品資訊與Feed",
        "商品圖片/標題規格不符被降級",
        {"FEED": 0.56, "GOOGLE": 0.18, "META": 0.16, "TIKTOK": 0.10},
        {"POLICY": 0.30, "UPSTREAM": 0.24, "USER": 0.22, "DATA": 0.14, "BUG": 0.10},
        4.0,
        "low",
    ),
    (
        "商品資訊與Feed",
        "幣別/運費/稅金欄位設定錯誤",
        {"FEED": 0.66, "GOOGLE": 0.20, "META": 0.10, "TIKTOK": 0.04},
        {"USER": 0.30, "UPSTREAM": 0.24, "DATA": 0.20, "POLICY": 0.14, "BUG": 0.12},
        3.5,
        "low",
    ),
    (
        "商品資訊與Feed",
        "多通路Feed欄位規格差異(Shopee/momo/TikTok)",
        {"FEED": 0.58, "TIKTOK": 0.22, "MULTI": 0.20},
        {"DATA": 0.32, "UPSTREAM": 0.24, "POLICY": 0.20, "BUG": 0.14, "USER": 0.10},
        11.0,
        "mid",
    ),
    (
        "商品資訊與Feed",
        "Feed排程更新失敗或延遲",
        {"FEED": 0.72, "GOOGLE": 0.14, "META": 0.10, "TIKTOK": 0.04},
        {"INFRA": 0.26, "THIRD": 0.22, "UPSTREAM": 0.22, "BUG": 0.18, "AUTH": 0.12},
        6.0,
        "high",
    ),
    (
        "商品資訊與Feed",
        "product set動態商品組合規則錯誤",
        {"FEED": 0.40, "META": 0.38, "GOOGLE": 0.16, "TIKTOK": 0.06},
        {"USER": 0.34, "DATA": 0.24, "NOISSUE": 0.18, "BUG": 0.14, "UPSTREAM": 0.10},
        4.5,
        "low",
    ),
    (
        "歸因與報表",
        "平台數據與GA4落差過大",
        {"GOOGLE": 0.44, "META": 0.32, "MULTI": 0.18, "LINE": 0.06},
        {"DATA": 0.40, "NOISSUE": 0.24, "GTM": 0.14, "FE": 0.12, "BUG": 0.10},
        7.5,
        "mid",
    ),
    (
        "歸因與報表",
        "平台回報轉換與後台實際訂單落差",
        {"META": 0.36, "GOOGLE": 0.28, "MULTI": 0.24, "LINE": 0.12},
        {"DATA": 0.36, "NOISSUE": 0.22, "FE": 0.16, "BUG": 0.14, "UPSTREAM": 0.12},
        8.5,
        "mid",
    ),
    (
        "歸因與報表",
        "歸因視窗設定不一致造成報表對不起來",
        {"META": 0.34, "GOOGLE": 0.32, "MULTI": 0.28, "LINE": 0.06},
        {"DATA": 0.38, "NOISSUE": 0.30, "USER": 0.20, "BUG": 0.12},
        4.0,
        "low",
    ),
    (
        "歸因與報表",
        "UTM參數遺失或被重導覆蓋",
        {"GOOGLE": 0.36, "META": 0.26, "MULTI": 0.24, "LINE": 0.14},
        {"FE": 0.34, "USER": 0.22, "GTM": 0.18, "BUG": 0.14, "THIRD": 0.12},
        5.0,
        "mid",
    ),
    (
        "歸因與報表",
        "報表排程失敗／資料延遲未更新",
        {"MULTI": 0.46, "GOOGLE": 0.24, "META": 0.20, "LINE": 0.10},
        {"INFRA": 0.28, "AUTH": 0.22, "THIRD": 0.20, "BUG": 0.20, "UPSTREAM": 0.10},
        4.5,
        "mid",
    ),
    (
        "歸因與報表",
        "重複訂單／測試訂單造成營收灌水",
        {"MULTI": 0.40, "META": 0.28, "GOOGLE": 0.22, "LINE": 0.10},
        {"BUG": 0.26, "DATA": 0.24, "FE": 0.20, "UPSTREAM": 0.18, "USER": 0.12},
        7.0,
        "high",
    ),
    (
        "歸因與報表",
        "自訂維度／自訂指標未帶入",
        {"GOOGLE": 0.56, "META": 0.20, "MULTI": 0.18, "LINE": 0.06},
        {"GTM": 0.30, "FE": 0.24, "USER": 0.22, "DATA": 0.14, "BUG": 0.10},
        5.0,
        "low",
    ),
    (
        "帳號與權限",
        "資產綁定/BM商業管理平台權限問題",
        {"META": 0.52, "GOOGLE": 0.24, "LINE": 0.16, "TIKTOK": 0.08},
        {"USER": 0.42, "AUTH": 0.28, "POLICY": 0.16, "NOISSUE": 0.14},
        2.5,
        "mid",
    ),
    (
        "帳號與權限",
        "API Token/Refresh Token過期",
        {"MULTI": 0.34, "META": 0.24, "GOOGLE": 0.24, "LINE": 0.18},
        {"AUTH": 0.62, "BUG": 0.16, "POLICY": 0.12, "USER": 0.10},
        3.0,
        "high",
    ),
    (
        "帳號與權限",
        "廣告帳號被停用／付款方式失效",
        {"META": 0.44, "GOOGLE": 0.26, "TIKTOK": 0.16, "LINE": 0.14},
        {"POLICY": 0.44, "USER": 0.26, "AUTH": 0.16, "NOISSUE": 0.14},
        6.5,
        "high",
    ),
    (
        "帳號與權限",
        "網域驗證失效／品牌安全設定",
        {"META": 0.48, "GOOGLE": 0.28, "TIKTOK": 0.12, "LINE": 0.12},
        {"FE": 0.30, "USER": 0.26, "POLICY": 0.24, "AUTH": 0.20},
        4.0,
        "mid",
    ),
    (
        "API與整合",
        "CAPI/Measurement Protocol回傳error code",
        {"META": 0.56, "GOOGLE": 0.24, "TIKTOK": 0.10, "MULTI": 0.10},
        {"BUG": 0.28, "DATA": 0.22, "AUTH": 0.18, "POLICY": 0.18, "FE": 0.14},
        8.0,
        "high",
    ),
    (
        "API與整合",
        "Server-side GTM部署或容器異常",
        {"GOOGLE": 0.62, "META": 0.24, "MULTI": 0.14},
        {"GTM": 0.32, "INFRA": 0.24, "BUG": 0.20, "AUTH": 0.14, "FE": 0.10},
        12.0,
        "high",
    ),
    (
        "API與整合",
        "Webhook未觸發或重送失敗",
        {"MULTI": 0.42, "LINE": 0.24, "META": 0.20, "GOOGLE": 0.14},
        {"BUG": 0.30, "INFRA": 0.22, "THIRD": 0.22, "AUTH": 0.16, "UPSTREAM": 0.10},
        7.5,
        "high",
    ),
    (
        "API與整合",
        "第三方工具串接失敗(CDP/EDM/CRM)",
        {"MULTI": 0.44, "LINE": 0.24, "META": 0.18, "GOOGLE": 0.14},
        {"THIRD": 0.30, "AUTH": 0.24, "BUG": 0.20, "UPSTREAM": 0.16, "DATA": 0.10},
        10.0,
        "mid",
    ),
    (
        "API與整合",
        "API rate limit／配額不足導致中斷",
        {"MULTI": 0.34, "META": 0.26, "GOOGLE": 0.24, "LINE": 0.16},
        {"INFRA": 0.34, "POLICY": 0.24, "BUG": 0.22, "THIRD": 0.20},
        6.0,
        "mid",
    ),
    (
        "素材與投放設定",
        "動態素材參數未帶入(價格/折扣)",
        {"META": 0.42, "FEED": 0.26, "GOOGLE": 0.20, "TIKTOK": 0.12},
        {"UPSTREAM": 0.28, "USER": 0.26, "DATA": 0.20, "BUG": 0.16, "NOISSUE": 0.10},
        5.0,
        "mid",
    ),
    (
        "素材與投放設定",
        "版位不支援素材規格被拒",
        {"META": 0.36, "TIKTOK": 0.24, "GOOGLE": 0.22, "LINE": 0.18},
        {"USER": 0.38, "POLICY": 0.28, "NOISSUE": 0.20, "BUG": 0.14},
        2.5,
        "low",
    ),
    (
        "素材與投放設定",
        "批次出價／預算API設定失敗",
        {"MULTI": 0.34, "META": 0.28, "GOOGLE": 0.24, "LINE": 0.14},
        {"BUG": 0.30, "AUTH": 0.22, "USER": 0.20, "POLICY": 0.16, "INFRA": 0.12},
        6.5,
        "mid",
    ),
    (
        "素材與投放設定",
        "自動化規則未依排程執行",
        {"MULTI": 0.38, "META": 0.30, "GOOGLE": 0.22, "TIKTOK": 0.10},
        {"BUG": 0.32, "INFRA": 0.24, "USER": 0.20, "AUTH": 0.14, "NOISSUE": 0.10},
        5.5,
        "mid",
    ),
    (
        "隱私與政策",
        "Consent Mode v2／CMP同意訊號設定",
        {"GOOGLE": 0.62, "META": 0.22, "MULTI": 0.16},
        {"POLICY": 0.32, "GTM": 0.26, "FE": 0.20, "USER": 0.14, "NOISSUE": 0.08},
        8.0,
        "mid",
    ),
    (
        "隱私與政策",
        "個資／敏感類別受限無法投放",
        {"META": 0.40, "GOOGLE": 0.30, "LINE": 0.16, "TIKTOK": 0.14},
        {"POLICY": 0.48, "USER": 0.24, "NOISSUE": 0.18, "DATA": 0.10},
        5.0,
        "mid",
    ),
    (
        "隱私與政策",
        "iOS ATT／隱私沙盒造成成效衰退",
        {"META": 0.52, "GOOGLE": 0.24, "TIKTOK": 0.14, "MULTI": 0.10},
        {"POLICY": 0.38, "NOISSUE": 0.30, "DATA": 0.18, "BUG": 0.14},
        6.5,
        "mid",
    ),
    (
        "隱私與政策",
        "平台審核政策拒登(廣告文案/到達頁)",
        {"META": 0.38, "GOOGLE": 0.28, "LINE": 0.16, "TIKTOK": 0.18},
        {"POLICY": 0.46, "USER": 0.26, "NOISSUE": 0.16, "FE": 0.12},
        4.0,
        "mid",
    ),
]

TITLE_TPL = {
    "事件追蹤異常": [
        "{brand}的{plat}{sub}，麻煩協助檢查",
        "【急】{brand} {sub}（{plat}）",
        "{brand} {sub}，投放已受影響",
        "{plat} {sub} - {brand}",
    ],
    "受眾與媒合": [
        "{brand} {sub}，無法正常放大預算",
        "{plat} {sub}，請協助排查 - {brand}",
        "【{brand}】{sub}",
    ],
    "商品資訊與Feed": [
        "{brand} {sub}，客戶已反映",
        "{sub}（{brand}／{plat}）",
        "【客訴風險】{brand} {sub}",
    ],
    "歸因與報表": [
        "{brand} {sub}，客戶對數要用",
        "{sub} - {brand} 月報卡住",
        "{brand}／{plat} {sub}",
    ],
    "帳號與權限": ["{brand} {sub}，需盡快處理", "{sub}（{brand}）"],
    "API與整合": ["{brand} {sub}，串接中斷", "【技術】{brand} {sub}"],
    "素材與投放設定": ["{brand} {sub}，上檔前需解決", "{sub} - {brand} {plat}"],
    "隱私與政策": ["{brand} {sub}，影響投放", "{sub}（{brand}）需要說明給客戶"],
}

DESC_OPEN = [
    "投手回報：",
    "客戶今天早上反映：",
    "上檔檢查時發現：",
    "AM 轉來的問題：",
    "例行對數時發現：",
    "客戶信件中提到：",
    "自己在後台看到：",
    "監控警示後確認：",
]
DESC_TAIL_COMPLETE = [
    "已附上後台截圖與事件除錯工具畫面，資產 ID 如上欄位，影響區間自 {d1} 起。",
    "附件包含 GTM 版本紀錄、平台後台匯出 CSV、以及對照的 GA4 報表，可直接比對。",
    "已提供受影響活動清單、事件名稱、以及變更前後的數字，異常起始 {d1}。",
    "已用無痕模式重現並錄影，同時附上 network request 的 payload。",
]
DESC_TAIL_INCOMPLETE = [
    "麻煩幫忙看一下，謝謝！",
    "客戶很急，請盡快回覆。",
    "不確定是哪邊的問題，先開單。",
    "細節我再補，先請 RD 幫忙看。",
    "上面就是客戶說的，沒有其他資訊了。",
]

MISSING_POOL = [
    "資產ID",
    "發生時間區間",
    "受影響活動清單",
    "後台截圖",
    "重現步驟",
    "瀏覽器/裝置資訊",
    "對照數據來源",
    "事件名稱",
    "商品ID範例",
    "錯誤訊息全文",
    "GTM容器版本",
    "測試帳號權限",
]

BRANDS = {
    "AGN": [
        "熙食嚴選",
        "PureGlow保養",
        "MoveWell運動",
        "小森家居",
        "TechNow3C",
        "紅日茶業",
        "Bellaire女裝",
        "NutriPlus保健",
        "旅時旅行社",
        "晨光文教",
        "海嶼生鮮",
        "SoftLab美妝",
        "KidoPlay玩具",
        "安心保經",
        "極光戶外",
    ],
    "SAAS": [
        "A客戶-momo館",
        "B客戶-連鎖藥妝",
        "C客戶-運動品牌",
        "D客戶-銀行信用卡",
        "E客戶-遊戲發行",
        "F客戶-訂閱制生鮮",
        "G客戶-家電品牌",
        "H客戶-旅遊平台",
        "I客戶-保健通路",
        "J客戶-時尚電商",
    ],
    "INH": [
        "官網主站",
        "官網-會員專區",
        "App商城",
        "LINE商城",
        "海外站(HK)",
        "海外站(SG)",
        "品牌旗艦館",
        "門市O2O",
    ],
}

NAMES = [
    "陳怡君",
    "林柏翰",
    "黃于庭",
    "張家豪",
    "李欣穎",
    "吳承翰",
    "劉品妤",
    "蔡孟修",
    "鄭雅文",
    "許志偉",
    "謝宜蓁",
    "曾冠廷",
    "洪詩涵",
    "邱建良",
    "簡佩宜",
    "廖俊安",
    "潘思妤",
    "楊皓宇",
    "呂佳穎",
    "賴柏毅",
    "江宛柔",
    "范植軒",
    "石郁婷",
    "汪明哲",
]

ENG_NAMES = [
    "Kevin Lu",
    "Ariel Wu",
    "Ted Chen",
    "Mina Kao",
    "Jason Hsu",
    "Fiona Lin",
    "Ryan Peng",
    "Cindy Ho",
    "Marcus Yeh",
    "Eva Tsai",
    "Leo Chang",
    "Nina Su",
]

METRIC_MAP = {
    "事件追蹤異常": ("每日事件量", 500, 40000),
    "受眾與媒合": ("名單媒合率(%)", 20, 92),
    "商品資訊與Feed": ("有效商品數", 300, 25000),
    "歸因與報表": ("平台回報轉換數", 30, 3500),
    "帳號與權限": ("可投放帳號數", 1, 12),
    "API與整合": ("API成功率(%)", 55, 99),
    "素材與投放設定": ("正常上檔素材數", 4, 180),
    "隱私與政策": ("可歸因轉換佔比(%)", 35, 88),
}

ROLE_QUALITY = {
    "站內工程師": 26,
    "客戶端IT窗口": 22,
    "data analyst": 20,
    "Solution Consultant": 16,
    "資深投手/組長": 10,
    "媒體投手": 0,
    "電商營運PM": 2,
    "客戶成功經理CSM": -4,
    "AM客戶經理": -8,
    "企劃/Planner": -10,
    "客戶端行銷窗口": -14,
    "業務BD": -18,
    "電商行銷專員": -2,
    "行銷主管": -6,
}

RES_BY_RC = {
    "FE": {"CLIENT": 0.44, "CODE": 0.24, "CONFIG": 0.18, "EDU": 0.10, "ROUTE": 0.04},
    "GTM": {"CONFIG": 0.52, "EDU": 0.18, "CODE": 0.16, "CLIENT": 0.12, "ROUTE": 0.02},
    "POLICY": {"EDU": 0.34, "CONFIG": 0.24, "VENDOR": 0.26, "CODE": 0.10, "NONE": 0.06},
    "UPSTREAM": {"CODE": 0.34, "CLIENT": 0.26, "CONFIG": 0.22, "ROUTE": 0.10, "EDU": 0.08},
    "USER": {"EDU": 0.52, "CONFIG": 0.36, "NONE": 0.10, "ROUTE": 0.02},
    "AUTH": {"CONFIG": 0.58, "CODE": 0.20, "CLIENT": 0.14, "EDU": 0.08},
    "BUG": {"CODE": 0.76, "CONFIG": 0.14, "ROUTE": 0.06, "EDU": 0.04},
    "THIRD": {"VENDOR": 0.34, "CONFIG": 0.22, "CODE": 0.20, "EDU": 0.14, "NONE": 0.10},
    "NOISSUE": {"EDU": 0.62, "NONE": 0.34, "CONFIG": 0.04},
    "DATA": {"EDU": 0.44, "CONFIG": 0.22, "CODE": 0.20, "NONE": 0.10, "ROUTE": 0.04},
    "INFRA": {"CODE": 0.42, "CONFIG": 0.30, "VENDOR": 0.14, "ROUTE": 0.08, "EDU": 0.06},
}

FIX_OWNER = {
    "CODE": "內部工程團隊",
    "CONFIG": "內部工程團隊",
    "EDU": "內部支援窗口",
    "CLIENT": "客戶端／系統商",
    "VENDOR": "平台原廠",
    "NONE": "無",
    "ROUTE": "其他團隊",
}

SLA_HOURS = {
    "白金Platinum(4hr SLA)": 4,
    "黃金Gold(8hr SLA)": 8,
    "標準Standard(1營業日)": 24,
    "基礎Basic(3營業日)": 72,
    "內部標準(1營業日)": 24,
    "內部急件(4hr)": 4,
}

SEV_MAP = {
    "high": [
        ("S1-投放中斷/嚴重失真", 0.30),
        ("S2-成效顯著受損", 0.42),
        ("S3-局部影響", 0.22),
        ("S4-無立即影響", 0.06),
    ],
    "mid": [
        ("S1-投放中斷/嚴重失真", 0.12),
        ("S2-成效顯著受損", 0.34),
        ("S3-局部影響", 0.40),
        ("S4-無立即影響", 0.14),
    ],
    "low": [
        ("S1-投放中斷/嚴重失真", 0.04),
        ("S2-成效顯著受損", 0.18),
        ("S3-局部影響", 0.46),
        ("S4-無立即影響", 0.32),
    ],
}


# ---------------------------------------------------------------- 工具


def pick(weighted, rng):
    if isinstance(weighted, dict):
        keys, ws = list(weighted.keys()), list(weighted.values())
    else:
        keys = [k[0] for k in weighted]
        ws = [k[-1] for k in weighted]
    return rng.choices(keys, weights=ws, k=1)[0]


def peak_boost(d: datetime) -> float:
    for pm, pd_ in TW_PEAKS:
        try:
            anchor = datetime(d.year, pm, pd_)
        except ValueError:
            continue
        if abs((d - anchor).days) <= 7:
            return 1.0
    return 0.0


def gen_dates(n: int, rng) -> list[datetime]:
    days = (END - START).days
    out: list[datetime] = []
    guard = 0
    while len(out) < n and guard < n * 200:
        guard += 1
        d = START + timedelta(days=rng.randint(0, days))
        w = 1.0 + 1.6 * peak_boost(d)
        if d.weekday() >= 5:
            w *= 0.28
        if rng.random() < w / 2.6:
            hh = rng.choices(
                range(8, 23), weights=[2, 5, 9, 11, 10, 7, 9, 11, 10, 8, 6, 4, 3, 2, 1], k=1
            )[0]
            out.append(d.replace(hour=hh, minute=rng.randint(0, 59)))
    return sorted(out)


def gen_event_dates(rng) -> list[tuple[datetime, str]]:
    """為 2026 真實平台事件生成額外工單的日期，衝擊呈指數衰減。"""
    out = []
    for ev_id, ev_date, _plat, _subs, _rc, span, extra in PLATFORM_EVENTS:
        for _ in range(extra):
            offset = int(abs(rng.gauss(0, span / 2.2)))
            offset = min(offset, span)
            d = ev_date + timedelta(days=offset)
            d = d.replace(
                hour=rng.choices(
                    range(8, 22), weights=[3, 7, 11, 12, 10, 7, 9, 11, 9, 7, 5, 4, 3, 2], k=1
                )[0],
                minute=rng.randint(0, 59),
            )
            out.append((d, ev_id))
    return out


# ---------------------------------------------------------------- 主流程


def build(n: int = 640, seed: int = 20260823) -> pd.DataFrame:
    rng = random.Random(seed)

    org_name_of = {o[0]: o[1] for o in ORG_CONTEXTS}
    event_lookup = {e[0]: e for e in PLATFORM_EVENTS}

    base_dates = [(d, None) for d in gen_dates(n - sum(e[6] for e in PLATFORM_EVENTS), rng)]
    all_dates = sorted(base_dates + gen_event_dates(rng), key=lambda x: x[0])

    recurrence_memory: dict[tuple, datetime] = {}
    dup_memory: dict[tuple, str] = {}
    rows = []

    for i, (sub_dt, ev_id) in enumerate(all_dates, start=1):
        # ---- 若屬平台事件，強制指定問題細類與根因
        if ev_id:
            _id, _dt, ev_plat, ev_subs, ev_rc, _span, _extra = event_lookup[ev_id]
            target_sub = rng.choice(ev_subs)
            cat, subcat, plat_w, rc_w, base_hr, sev_tend = next(
                x for x in ISSUES if x[1] == target_sub
            )
            plat_key = ev_plat
            rc_key = ev_rc
        else:
            cat, subcat, plat_w, rc_w, base_hr, sev_tend = rng.choice(ISSUES)
            plat_key = pick(plat_w, rng)
            rc_key = pick(rc_w, rng)

        org = pick(ORG_CONTEXTS, rng)
        platform = PLAT[plat_key]
        client = rng.choice(BRANDS[org])
        industry = pick(INDUSTRIES, rng)
        role = pick(REQUESTER_ROLES[org], rng)
        team = pick(ASSIGNED_TEAMS[org], rng)
        tier = (
            pick(CONTRACT_TIERS, rng)
            if org != "INH"
            else pick([("內部標準(1營業日)", 0.70), ("內部急件(4hr)", 0.30)], rng)
        )

        # ---- 嚴重度與優先級
        severity = pick(SEV_MAP[sev_tend], rng)
        sev_rank = int(severity[1])
        pri_shift = -1 if ("白金" in tier or "急件" in tier) else (1 if "基礎" in tier else 0)
        pri_rank = min(3, max(0, sev_rank - 1 + pri_shift))
        priority = ["P0-立即", "P1-當日", "P2-本週", "P3-排程"][pri_rank]

        # ---- 影響量化
        lo, hi = {"AGN": (8000, 180000), "SAAS": (20000, 450000), "INH": (5000, 120000)}[org]
        spend = int(rng.triangular(lo, hi, lo * 2.2))
        if sev_rank <= 2:
            spend = int(spend * rng.uniform(1.1, 1.9))
        camp_cnt = max(1, int(rng.triangular(1, 26, 4)))

        mname, mlo, mhi = METRIC_MAP[cat]
        m_before = round(rng.uniform(mlo, mhi), 1)
        drop = rng.uniform(0.12, 0.95) if sev_rank <= 2 else rng.uniform(0.03, 0.45)
        m_after = round(m_before * (1 - drop), 1)
        delta_pct = round((m_after - m_before) / m_before * 100, 1)

        # ---- 提單品質（核心因果鏈起點）
        comp = int(max(8, min(100, rng.gauss(58 + ROLE_QUALITY.get(role, 0), 17))))
        if pri_rank == 0:
            comp = int(min(100, comp * rng.uniform(0.78, 1.0)))  # 越急越講不清楚
        if ev_id:
            comp = int(max(8, comp * rng.uniform(0.72, 0.92)))  # 靜默失敗時人更難描述

        n_missing = (
            0
            if comp >= 85
            else (1 if comp >= 70 else (2 if comp >= 52 else (3 if comp >= 35 else 4)))
        )
        missing = "、".join(rng.sample(MISSING_POOL, n_missing)) if n_missing else "無"
        attach = max(0, int(round((comp - 30) / 22 + rng.gauss(0, 0.7))))

        clar = max(0, int(round((100 - comp) / 21 + rng.gauss(0, 0.75))))
        reproducible = pick(
            [("可穩定重現", 0.46), ("偶發/間歇", 0.32), ("無法重現", 0.12), ("未測試", 0.10)], rng
        )
        if reproducible == "無法重現":
            clar += 1

        root_cause = RC[rc_key]
        res_key = pick(RES_BY_RC[rc_key], rng)
        resolution = RES[res_key]

        # ---- 時間（釐清次數是主要放大器）
        sla_hr = SLA_HOURS[tier]
        frt = max(4, int(rng.gauss(sla_hr * 60 * 0.42, sla_hr * 60 * 0.26)))
        if pri_rank == 0:
            frt = int(frt * 0.45)
        if sub_dt.hour >= 19:
            frt += rng.randint(120, 640)

        hr = base_hr * {0: 1.05, 1: 1.0, 2: 0.88, 3: 0.72}[pri_rank]
        hr *= 1 + 0.38 * clar
        hr *= rng.uniform(0.55, 1.75)
        if res_key == "VENDOR":
            hr *= rng.uniform(1.6, 3.4)
        if res_key in ("EDU", "NONE"):
            hr *= rng.uniform(0.28, 0.6)
        if org == "SAAS":
            hr *= 1.12
        if ev_id:
            hr *= rng.uniform(1.3, 2.4)  # 靜默失敗，查錯方向浪費時間
        resolution_hours = round(max(0.3, hr), 1)
        eng_hours = round(resolution_hours * rng.uniform(0.18, 0.55), 1)

        status = pick(
            [
                ("已結案", 0.84),
                ("處理中", 0.07),
                ("待客戶回覆", 0.05),
                ("待平台原廠回覆", 0.03),
                ("已擱置", 0.01),
            ],
            rng,
        )
        if (END - sub_dt).days < 12 and rng.random() < 0.55:
            status = pick([("處理中", 0.5), ("待客戶回覆", 0.3), ("已結案", 0.2)], rng)

        resolved_at = ""
        if status == "已結案":
            resolved_at = (
                sub_dt + timedelta(hours=resolution_hours * rng.uniform(1.4, 3.6))
            ).strftime("%Y-%m-%d %H:%M")

        reopened = 0
        if status == "已結案":
            p = 0.06 + 0.03 * clar + (0.08 if rc_key in ("BUG", "UPSTREAM") else 0)
            if rng.random() < p:
                reopened = 2 if rng.random() < 0.22 else 1

        key = (client, subcat)
        prev = recurrence_memory.get(key)
        recurrence = "是" if prev and (sub_dt - prev).days <= 90 else "否"
        recurrence_memory[key] = sub_dt

        wkey = (client, subcat, sub_dt.isocalendar()[1], sub_dt.year)
        dup_of = dup_memory.get(wkey, "")
        ticket_id = f"REQ-{sub_dt.strftime('%Y%m')}-{i:04d}"
        if not dup_of:
            dup_memory[wkey] = ticket_id

        csat = None
        if status == "已結案":
            base_csat = 4.5 - 0.22 * clar - 0.5 * reopened - (0.4 if resolution_hours > 24 else 0)
            csat = round(min(5, max(1, rng.gauss(base_csat, 0.55))), 1)

        # ---- AI 自動化分級
        if res_key in ("EDU", "NONE") and clar <= 2:
            ai_level = "L2-AI自助回覆"
        elif rc_key in ("USER", "NOISSUE", "DATA") and res_key in ("CONFIG", "EDU"):
            ai_level = "L3-AI自動診斷"
        elif rc_key in ("AUTH", "UPSTREAM", "INFRA") and res_key == "CONFIG":
            ai_level = "L4-AI自動修復"
        elif rc_key in ("FE", "GTM", "POLICY") and res_key in ("CONFIG", "CLIENT"):
            ai_level = "L3-AI自動診斷"
        elif comp < 55:
            ai_level = "L1-AI分診與補件"
        else:
            ai_level = "L0-需人工深度介入"

        preventable_rc = rc_key in ("FE", "GTM", "UPSTREAM", "AUTH", "POLICY", "INFRA", "THIRD")
        ai_preventable = (
            "是"
            if (preventable_rc and rng.random() < 0.82)
            else ("部分" if rng.random() < 0.3 else "否")
        )
        detection = DETECTION_SIGNALS[rc_key] if ai_preventable in ("是", "部分") else "—"

        # ---- 文字
        brand_short = client.split("-")[-1]
        title = rng.choice(TITLE_TPL[cat]).format(
            brand=brand_short, plat=platform.split("(")[0], sub=subcat
        )
        occurred_from = sub_dt - timedelta(days=rng.randint(0, 6))
        tail = rng.choice(DESC_TAIL_COMPLETE if comp >= 68 else DESC_TAIL_INCOMPLETE)
        desc = (
            f"{rng.choice(DESC_OPEN)}{brand_short} 的 {platform} 出現「{subcat}」。"
            f"{mname} 從 {m_before} 掉到 {m_after}（{delta_pct}%），"
            f"影響 {camp_cnt} 檔活動、日花費約 NT${spend:,}。"
            f"{tail.format(d1=occurred_from.strftime('%m/%d'))}"
        )

        asset_id = {
            "META": f"pixel_{rng.randint(10**14, 10**15 - 1)}",
            "GOOGLE": "G-" + "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", k=10)),
            "LINE": f"linetag_{rng.randint(10**8, 10**9 - 1)}",
            "FEED": f"catalog_{rng.randint(10**12, 10**13 - 1)}",
            "TIKTOK": "ttpixel_"
            + "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=12)),
            "MULTI": "多資產(詳見附件)",
        }[plat_key]

        rows.append(
            {
                "ticket_id": ticket_id,
                "submitted_at": sub_dt.strftime("%Y-%m-%d %H:%M"),
                "org_context": org_name_of[org],
                "requester_name": rng.choice(NAMES),
                "requester_role": role,
                "client_brand": client,
                "industry": industry,
                "sla_tier": tier,
                "website_platform": pick(WEBSITE_PLATFORMS, rng),
                "issue_category": cat,
                "issue_subcategory": subcat,
                "title": title,
                "description": desc,
                "platform": platform,
                "affected_asset_id": asset_id,
                "tracking_method": pick(
                    {
                        "Client-side (JS/Pixel)": 0.30,
                        "Server-side (CAPI/MP)": 0.22,
                        "Hybrid (雙軌+dedup)": 0.20,
                        "Feed/Catalog 排程": 0.16,
                        "API 直連": 0.08,
                        "SDK (App)": 0.04,
                    },
                    rng,
                ),
                "environment": pick(ENVIRONMENTS, rng),
                "reproducible": reproducible,
                "occurred_from": occurred_from.strftime("%Y-%m-%d"),
                "severity": severity,
                "priority": priority,
                "impacted_spend_daily_ntd": spend,
                "impacted_campaign_count": camp_cnt,
                "metric_name": mname,
                "metric_before": m_before,
                "metric_after": m_after,
                "delta_pct": delta_pct,
                "business_impact": pick(
                    {
                        "預算誤配／成效失真": 0.28,
                        "無法優化決策": 0.22,
                        "被迫暫停投放": 0.16,
                        "客戶客訴／信任受損": 0.14,
                        "報表無法交付": 0.12,
                        "合規風險": 0.08,
                    },
                    rng,
                ),
                "attachment_count": attach,
                "info_completeness_score": comp,
                "missing_fields": missing,
                "first_response_min": frt,
                "clarification_rounds": clar,
                "is_duplicate": "是" if dup_of else "否",
                "duplicate_of": dup_of or "—",
                "assigned_team": team,
                "assignee": rng.choice(ENG_NAMES),
                "root_cause_category": root_cause,
                "root_cause_code": rc_key,
                "resolution_type": resolution,
                "fix_owner": FIX_OWNER[res_key],
                "status": status,
                "resolved_at": resolved_at or "—",
                "resolution_hours": resolution_hours,
                "eng_effort_hours": eng_hours,
                "reopened_count": reopened,
                "recurrence_90d": recurrence,
                "csat": csat if csat is not None else "—",
                "ai_automation_level": ai_level,
                "ai_preventable": ai_preventable,
                "detection_signal": detection,
                "kb_article_id": f"KB-{stable_int(subcat) % 900 + 100}",
                "platform_event_id": ev_id or "—",
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=640)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--out", type=str, default="data/raw/tickets.csv")
    args = ap.parse_args()

    df = build(args.n, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"✔ {len(df)} 筆 × {len(df.columns)} 欄 → {out}")


if __name__ == "__main__":
    main()
