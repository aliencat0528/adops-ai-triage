# -*- coding: utf-8 -*-
"""
L1 · Intake Agent — 提單助理
============================
職責：把投手的口語描述變成結構化工單，缺什麼當場問。

本模組實作「不需要 LLM 的那一半」——完整度評分、缺漏偵測、追問排序、送出護欄。
LLM 只負責從自由文字抽取欄位（`extract_with_llm` 為介面，尚未接模型）。

設計理由（見規劃書 §03）：
    L1 級工單只佔 25.3%，卻吃掉 34.0% 的工程時數。
    釐清次數每增加一次，處理時數增加 22.2%。
    因此把成本擋在入口，比讓診斷變聰明更划算。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path("specs/ticket.schema.json")

# 缺了會讓診斷「無法進行」的欄位，追問時優先問這些
BLOCKING = {"affected_asset_id", "occurred_from", "metric_before", "metric_after"}

# 追問話術：問法要具體到對方能一句話回答，不要問「請提供更多資訊」
QUESTION_TEMPLATES = {
    "affected_asset_id": "這是哪一個資產？{hint}",
    "occurred_from": "大概從哪一天開始不對的？（給個日期就好，不用精確到小時）",
    "metric_before": "異常前的數字大約是多少？",
    "metric_after": "現在的數字是多少？",
    "reproducible": "這個狀況每次都會發生，還是偶爾才出現？",
    "tracking_method": "這個客戶的追蹤是走 Pixel、CAPI，還是雙軌？",
    "environment": "是正式站還是測試站？App 的話是 iOS 還是 Android？",
    "impacted_campaign_count": "大概影響幾檔活動？",
    "attachment_count": "方便附一張後台截圖嗎？有截圖通常可以省掉一輪確認",
    "website_platform": "這個客戶的官網是用哪個平台架的？（91APP／Shopify／自建…）",
    "business_impact": "目前是已經暫停投放，還是還在跑但數字不準？",
    "description": "可以描述一下具體看到什麼現象嗎？",
}

ASSET_HINTS = {
    "Meta(Pixel+CAPI)": "（Pixel ID，在事件管理工具左上角）",
    "Google(Ads/GA4/GTM)": "（GA4 評估 ID，格式像 G-XXXXXXXXXX）",
    "LINE(LAP/LINE Tag)": "（LINE Tag ID）",
    "商品Feed/Catalog": "（Catalog ID）",
    "TikTok Ads": "（TikTok Pixel ID）",
    "跨平台": "（請列出所有受影響的資產 ID）",
}


@dataclass
class IntakeResult:
    completeness: int
    missing: list[str]
    blocking_missing: list[str]
    questions: list[str]
    can_submit: bool
    needs_override: bool
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "info_completeness_score": self.completeness,
            "missing_fields": "、".join(self.missing) if self.missing else "無",
            "questions": self.questions,
            "can_submit": self.can_submit,
            "needs_override": self.needs_override,
            "flags": self.flags,
        }


class IntakeAgent:
    """完整度評分與追問生成。所有規則都來自 ticket.schema.json，不硬寫在這裡。"""

    def __init__(self, schema_path: Path = SCHEMA_PATH) -> None:
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        # 過濾掉 JSON Schema 的 $comment 等註解鍵，只留真正的權重
        self.weights: dict[str, int] = {
            k: v for k, v in self.schema["x-completeness-weights"].items()
            if not k.startswith("$")
        }
        self.guards: dict[str, Any] = {
            k: v for k, v in self.schema["x-submission-guards"].items()
            if not k.startswith("$")
        }

    # ---------------------------------------------------------------- 必填
    def required_fields(self, ticket: dict) -> set[str]:
        """基礎必填 + 依 issue_category / severity 動態追加的必填。"""
        req = set(self.schema.get("required", []))
        for rule in self.schema.get("allOf", []):
            cond = rule.get("if", {}).get("properties", {})
            if self._matches(cond, ticket):
                req |= set(rule.get("then", {}).get("required", []))
        return req

    @staticmethod
    def _matches(cond: dict, ticket: dict) -> bool:
        import re
        for field_name, spec in cond.items():
            val = ticket.get(field_name)
            if val in (None, "", "—"):
                return False
            if "const" in spec and val != spec["const"]:
                return False
            if "pattern" in spec and not re.match(spec["pattern"], str(val)):
                return False
        return True

    # ---------------------------------------------------------------- 評分
    def score(self, ticket: dict) -> IntakeResult:
        filled = {k for k, v in ticket.items() if v not in (None, "", "—", 0, "無")}
        total_w = sum(self.weights.values())
        got_w = sum(w for f, w in self.weights.items() if f in filled)
        completeness = round(got_w / total_w * 100)

        required = self.required_fields(ticket)
        missing = sorted(required - filled, key=lambda f: -self.weights.get(f, 0))
        blocking = [f for f in missing if f in BLOCKING]

        flags: list[str] = []
        if str(ticket.get("priority", "")).startswith("P0") and completeness < 60:
            flags.append(self.guards["p0_override_flag"])
        if ticket.get("reproducible") == self.guards["reproducible_needs_extra_round"]:
            flags.append(self.guards["reproducible_extra_round_flag"])

        min_score = self.guards["min_completeness_to_submit"]
        can_submit = completeness >= min_score and not blocking
        needs_override = (
            not can_submit
            and self.guards["p0_override_allowed"]
            and str(ticket.get("priority", "")).startswith("P0")
        )

        return IntakeResult(
            completeness=completeness,
            missing=missing,
            blocking_missing=blocking,
            questions=self.build_questions(missing, ticket),
            can_submit=can_submit,
            needs_override=needs_override,
            flags=flags,
        )

    # ---------------------------------------------------------------- 追問
    def build_questions(self, missing: list[str], ticket: dict) -> list[str]:
        """一輪最多兩題，先問擋住診斷的欄位。問法要具體到對方能一句話回答。"""
        cap = self.guards["max_questions_per_round"]
        ordered = sorted(missing, key=lambda f: (f not in BLOCKING, -self.weights.get(f, 0)))
        out: list[str] = []
        for f in ordered[:cap]:
            tpl = QUESTION_TEMPLATES.get(f)
            if not tpl:
                continue
            hint = ASSET_HINTS.get(ticket.get("platform", ""), "") if f == "affected_asset_id" else ""
            out.append(tpl.format(hint=hint))
        return out

    # ---------------------------------------------------------------- 自動補件
    def autofill(self, ticket: dict, lookups: dict[str, Any] | None = None) -> dict:
        """能自己查到的絕不問人。

        lookups 由呼叫端注入（正式環境接客戶主檔與 changelog 服務，測試注入假資料）。
        目前支援：
          asset → client_brand / website_platform / campaign_count
          occurred_from + platform → 是否命中已知平台事件
        """
        lookups = lookups or {}
        t = dict(ticket)
        asset = t.get("affected_asset_id")
        if asset and asset in lookups.get("assets", {}):
            for k, v in lookups["assets"][asset].items():
                t.setdefault(k, v)
        events = lookups.get("platform_events", [])
        for ev in events:
            if ev["platform"] == t.get("platform") and ev["date"] <= str(t.get("occurred_from", "")):
                t["_changelog_hit"] = ev["id"]
                break
        return t

    # ---------------------------------------------------------------- LLM 抽取
    def extract_with_llm(self, free_text: str) -> dict:  # pragma: no cover
        """從自由文字抽取結構化欄位。

        實作方向（T-201）：
          - 模型 Haiku，temperature 0
          - 用 ticket.schema.json 當 structured output schema
          - 抽不到的欄位回 null，不要讓模型自己編
          - 抽取結果與 autofill 合併後才進 score()
        """
        raise NotImplementedError("見 TASKS.md T-201")
