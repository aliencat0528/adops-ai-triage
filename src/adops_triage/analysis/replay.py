"""T-206 回放評測 — 拿 640 筆歷史單重跑提單助理。

量的是**釐清輪數**不是完整度。理由見 `docs/00-規劃書.md` 與 B 路線施工圖：
資料裡的 `info_completeness_score` 是生成器抽出來的潛在變數（generate_dataset.py:986），
不是欄位填寫狀態的函數，與 `IntakeAgent.score()` 算的完整度不同源，兩者相減沒有意義。
釐清輪數則是資料裡的既有欄位，也是 22.2% 成本係數的自變數，口徑一路通到底。

執行：
    python -m adops_triage.analysis.replay              # 全跑，輸出 reports/replay.json
    python -m adops_triage.analysis.replay --calibrate  # 只跑校準閘門，不往下算
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from adops_triage.agents.intake import QUESTION_TEMPLATES, IntakeAgent
from adops_triage.generate_dataset import MISSING_POOL

CSV = Path("data/raw/tickets.csv")
SCHEMA = Path("specs/ticket.schema.json")
OUT = Path("reports/replay.json")

# `missing_fields` 用的詞彙表與 schema 欄位名不是同一套。12 個詞裡只有這 6 個
# 對得到有權重的欄位；其餘 6 個是診斷細節，在本 schema 沒有結構化欄位（只會落在
# description 自由文字裡），因此回放量不到它們——這是本評測的已知天花板。
MISSING_TO_FIELD: dict[str, str] = {
    "資產ID": "affected_asset_id",
    "發生時間區間": "occurred_from",
    "重現步驟": "reproducible",
    "瀏覽器/裝置資訊": "environment",
    "受影響活動清單": "impacted_campaign_count",
    "後台截圖": "attachment_count",
}

UNMAPPED = [
    "對照數據來源",
    "事件名稱",
    "商品ID範例",
    "錯誤訊息全文",
    "GTM容器版本",
    "測試帳號權限",
]

# 詞彙表必須與生成器完全對齊。生成器改了 MISSING_POOL 而這裡沒跟上，
# 回放就會靜靜地少清或多清欄位——所以在 import 時就炸掉，不要等到數字算完才發現。
assert set(MISSING_TO_FIELD) | set(UNMAPPED) == set(MISSING_POOL), (
    "MISSING_TO_FIELD + UNMAPPED 必須剛好涵蓋 generate_dataset.MISSING_POOL，"
    f"目前差異：{set(MISSING_POOL) ^ (set(MISSING_TO_FIELD) | set(UNMAPPED))}"
)

# 工單契約以外的欄位不進助理（它們是結案後才有的事實或分析用欄）
NOT_AT_SUBMISSION = {
    "first_response_min",
    "clarification_rounds",
    "assigned_team",
    "assignee",
    "root_cause_category",
    "root_cause_code",
    "resolution_type",
    "fix_owner",
    "status",
    "resolved_at",
    "resolution_hours",
    "eng_effort_hours",
    "reopened_count",
    "recurrence_90d",
    "csat",
    "ai_automation_level",
    "ai_preventable",
    "detection_signal",
    "kb_article_id",
    "platform_event_id",
    "info_completeness_score",
    "missing_fields",
    "is_duplicate",
    "duplicate_of",
}


def split_missing(cell: Any) -> list[str]:
    if cell is None or str(cell) in ("無", "nan", ""):
        return []
    return [x for x in str(cell).split("、") if x]


def as_submitted(row: pd.Series) -> tuple[dict, list[str], list[str]]:
    """把已結案的歷史列還原成「送出當下」的工單。

    回傳 (工單, 被清掉的欄位, 對不到欄位的缺漏詞)。
    """
    ticket = {k: v for k, v in row.items() if k not in NOT_AT_SUBMISSION and pd.notna(v)}
    cleared: list[str] = []
    unmapped_hit: list[str] = []
    for term in split_missing(row.get("missing_fields")):
        field = MISSING_TO_FIELD.get(term)
        if field is None:
            unmapped_hit.append(term)
            continue
        ticket.pop(field, None)
        cleared.append(field)
    return ticket, cleared, unmapped_hit


def pearson(a: list[float], b: list[float]) -> float:
    return float(pd.Series(a).corr(pd.Series(b)))


def calibrate(df: pd.DataFrame, agent: IntakeAgent) -> dict:
    """校準閘門：重建出來的缺漏狀態，必須與資料自己的品質指標對得上。

    對不上就代表 MISSING_TO_FIELD 對照表錯了，這時候往下算出來的數字都是假的。
    """
    comp_intake: list[float] = []
    comp_dataset: list[float] = []
    n_cleared: list[float] = []
    n_missing: list[float] = []
    n_blocking: list[float] = []
    unmapped_total = 0
    examples: list[dict] = []

    for _, row in df.iterrows():
        ticket, cleared, unmapped_hit = as_submitted(row)
        r = agent.score(ticket)
        comp_intake.append(r.completeness)
        comp_dataset.append(float(row["info_completeness_score"]))
        n_cleared.append(len(cleared))
        n_missing.append(float(len(split_missing(row.get("missing_fields")))))
        n_blocking.append(float(len(r.blocking_missing)))
        unmapped_total += len(unmapped_hit)
        if len(examples) < 3 and cleared:
            examples.append(
                {
                    "ticket_id": row["ticket_id"],
                    "dataset_completeness": int(row["info_completeness_score"]),
                    "dataset_missing": split_missing(row.get("missing_fields")),
                    "cleared_fields": cleared,
                    "unmapped_terms": unmapped_hit,
                    "intake_completeness": r.completeness,
                    "intake_blocking": r.blocking_missing,
                }
            )

    return {
        "n": len(df),
        "corr_intake_vs_dataset_completeness": round(pearson(comp_intake, comp_dataset), 3),
        "corr_cleared_vs_dataset_missing_count": round(pearson(n_cleared, n_missing), 3),
        "corr_blocking_vs_dataset_missing_count": round(pearson(n_blocking, n_missing), 3),
        "intake_completeness": {
            "mean": round(sum(comp_intake) / len(comp_intake), 1),
            "min": min(comp_intake),
            "max": max(comp_intake),
        },
        "dataset_completeness": {
            "mean": round(sum(comp_dataset) / len(comp_dataset), 1),
            "min": int(min(comp_dataset)),
            "max": int(max(comp_dataset)),
        },
        "mapped_terms": len(MISSING_TO_FIELD),
        "unmapped_terms": len(UNMAPPED),
        "unmapped_occurrences": unmapped_total,
        "mapped_occurrences": int(sum(n_cleared)),
        "examples": examples,
    }


def askable(agent: IntakeAgent, ticket: dict) -> list[str]:
    """助理這張單問得出口的缺漏欄位——缺了、而且有追問話術。"""
    r = agent.score(ticket)
    return [f for f in r.missing if f in QUESTION_TEMPLATES]


def build_lookups(df: pd.DataFrame) -> dict:
    """autofill 用的查表。

    **這是完美查表**：資產 ID 直接對回該筆自己的客戶、官網平台與關聯活動數。
    現實中這三個值來自客戶主檔與平台 API，查得到查不到、值準不準都是變數。
    因此本評測算出來的是**上界**，不是預估值。
    """
    assets = {}
    for _, row in df.iterrows():
        aid = row.get("affected_asset_id")
        if pd.notna(aid):
            assets[aid] = {
                "client_brand": row["client_brand"],
                "website_platform": row["website_platform"],
                "impacted_campaign_count": row["impacted_campaign_count"],
            }
    return {"assets": assets, "platform_events": []}


def replay(df: pd.DataFrame, agent: IntakeAgent, slope_pct: float) -> dict:
    """步驟 3–5：autofill → 省下幾輪 → 換算工時。"""
    per_round = agent.guards["max_questions_per_round"]
    lookups = build_lookups(df)
    factor = 1 + slope_pct / 100

    rows = []
    for _, row in df.iterrows():
        ticket, cleared, _ = as_submitted(row)
        before = askable(agent, ticket)
        after = askable(agent, agent.autofill(ticket, lookups))
        filled = [f for f in before if f not in after]

        rounds_before = math.ceil(len(before) / per_round)
        rounds_after = math.ceil(len(after) / per_round)
        actual = int(row["clarification_rounds"])
        # 上限：不能省得比這張單原本問的還多
        saved = max(0, min(rounds_before - rounds_after, actual))

        res_hr = float(row["resolution_hours"])
        eng_hr = float(row["eng_effort_hours"])
        saved_res = res_hr * (1 - factor ** (-saved)) if saved else 0.0
        saved_eng = saved_res * (eng_hr / res_hr) if res_hr else 0.0

        rows.append(
            {
                "cleared": len(cleared),
                "filled": filled,
                "rounds_before": rounds_before,
                "rounds_after": rounds_after,
                "actual_rounds": actual,
                "saved_rounds": saved,
                "saved_eng_hours": saved_eng,
            }
        )

    helped = [r for r in rows if r["saved_rounds"] > 0]
    total_saved_eng = sum(r["saved_eng_hours"] for r in rows)
    actual_mean = sum(r["actual_rounds"] for r in rows) / len(rows)
    saved_mean = sum(r["saved_rounds"] for r in rows) / len(rows)

    return {
        "coefficient_pct_per_round": slope_pct,
        "coefficient_source": "reports/baseline.json · clarification_regression（觀測值，非生成器參數）",
        "tickets": len(rows),
        "tickets_helped": len(helped),
        "tickets_helped_pct": round(len(helped) / len(rows) * 100, 1),
        "rounds_mean_before": round(actual_mean, 2),
        "rounds_mean_after": round(actual_mean - saved_mean, 2),
        "rounds_saved_mean": round(saved_mean, 3),
        "rounds_saved_pct": round(saved_mean / actual_mean * 100, 1) if actual_mean else 0.0,
        "eng_hours_saved": round(total_saved_eng, 1),
        "eng_hours_total": 3285.7,
        "eng_hours_saved_pct": round(total_saved_eng / 3285.7 * 100, 2),
        "vs_baseline_l1_upper_bound": {
            "baseline_l1_hours": 1262.5,
            "captured_pct": round(total_saved_eng / 1262.5 * 100, 1),
        },
        "boundaries": [
            "上界不是預估：autofill 用完美查表（資產 ID 直接對回該筆自己的值），"
            "現實中查不查得到、值準不準都是變數",
            "假設追問一定得到正確回答——真實情況會有答錯與再追問",
            "只還原得了一半的缺漏：missing_fields 的 12 個詞只有 6 個對得到 schema 欄位，"
            "另外 6 個是診斷細節，本 schema 沒有結構化欄位可清",
            "重建後的完整度平均 87.5、資料自己的平均 55.8——兩者相關（r=+0.63）但不同尺，"
            "所以只比輪數不比完整度，也不宣稱助理把完整度拉高了多少",
            "這是模擬資料。本評測證明的是管線正確與係數用對，不是商業價值",
        ],
        "fields_autofilled": {
            f: sum(1 for r in rows if f in r["filled"])
            for f in sorted({f for r in rows for f in r["filled"]})
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="只跑校準閘門")
    args = ap.parse_args()

    df = pd.read_csv(CSV)
    agent = IntakeAgent(SCHEMA)
    cal = calibrate(df, agent)

    print("▸ 校準閘門")
    print(f"  重建完整度 vs 資料完整度     r = {cal['corr_intake_vs_dataset_completeness']:+.3f}")
    print(f"  清掉欄位數 vs 資料缺漏項數   r = {cal['corr_cleared_vs_dataset_missing_count']:+.3f}")
    print(
        f"  擋診斷欄位數 vs 資料缺漏項數 r = {cal['corr_blocking_vs_dataset_missing_count']:+.3f}"
    )
    print(
        f"  對得上的缺漏詞 {cal['mapped_occurrences']} 次 / 對不上 {cal['unmapped_occurrences']} 次"
    )
    print(
        f"  重建完整度 平均 {cal['intake_completeness']['mean']}"
        f"（{cal['intake_completeness']['min']}–{cal['intake_completeness']['max']}）"
    )
    print(
        f"  資料完整度 平均 {cal['dataset_completeness']['mean']}"
        f"（{cal['dataset_completeness']['min']}–{cal['dataset_completeness']['max']}）"
    )

    if args.calibrate:
        print(json.dumps(cal["examples"], ensure_ascii=False, indent=2))
        return

    baseline = json.loads(Path("reports/baseline.json").read_text(encoding="utf-8"))
    slope_pct = baseline["clarification_regression"]["multiplier_per_round_pct"]
    res = replay(df, agent, slope_pct)

    print("\n▸ 回放結果")
    print(
        f"  幫得上忙的單           {res['tickets_helped']} / {res['tickets']}"
        f"（{res['tickets_helped_pct']}%）"
    )
    print(
        f"  平均釐清輪數           {res['rounds_mean_before']} → {res['rounds_mean_after']}"
        f"（−{res['rounds_saved_pct']}%）"
    )
    print(
        f"  回收工程工時           {res['eng_hours_saved']} hr"
        f"（佔總工時 {res['eng_hours_saved_pct']}%）"
    )
    print(
        f"  佔 baseline L1 上界     {res['vs_baseline_l1_upper_bound']['captured_pct']}%"
        f"（上界 {res['vs_baseline_l1_upper_bound']['baseline_l1_hours']} hr）"
    )
    print(f"  補回的欄位             {res['fields_autofilled']}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps({"calibration": cal, "replay": res}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✔ {OUT}")


if __name__ == "__main__":
    main()
