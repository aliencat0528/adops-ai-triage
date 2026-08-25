# -*- coding: utf-8 -*-
"""
Baseline 分析
=============
從模擬需求單算出所有 KPI 基線與 AI 切入機會。
規劃書引用的每一個數字都必須來自這支程式，不得手寫。

用法：PYTHONPATH=src python -m adops_triage.analysis.baseline
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

CSV = Path("data/raw/tickets.csv")
OUT = Path("reports/baseline.json")


# `load()` 為了分析方便加的欄，不屬於工單契約，統計欄位數時要扣掉
DERIVED_COLS = ("csat_num",)


def load() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df["submitted_at"] = pd.to_datetime(df["submitted_at"])
    df["csat_num"] = pd.to_numeric(df["csat"], errors="coerce")
    return df


def q(s: pd.Series) -> dict:
    return {
        "n": int(s.notna().sum()),
        "mean": round(float(s.mean()), 2),
        "p25": round(float(s.quantile(0.25)), 2),
        "median": round(float(s.median()), 2),
        "p75": round(float(s.quantile(0.75)), 2),
        "p90": round(float(s.quantile(0.90)), 2),
    }


def main() -> None:
    df = load()
    closed = df[df["status"] == "已結案"]
    r: dict = {}

    # ---------- 0. 概況
    r["overview"] = {
        "tickets": len(df),
        "columns": len([c for c in df.columns if c not in DERIVED_COLS]),
        "date_from": df["submitted_at"].min().strftime("%Y-%m-%d"),
        "date_to": df["submitted_at"].max().strftime("%Y-%m-%d"),
        "closed_rate_pct": round(len(closed) / len(df) * 100, 1),
        "clients": int(df["client_brand"].nunique()),
        "total_eng_hours": round(float(df["eng_effort_hours"].sum()), 1),
        "total_resolution_hours": round(float(df["resolution_hours"].sum()), 1),
        "impacted_spend_sum_ntd": int(df["impacted_spend_daily_ntd"].sum()),
    }

    # ---------- 1. 提單品質
    r["intake_quality"] = {
        "completeness": q(df["info_completeness_score"]),
        "clarification_rounds": q(df["clarification_rounds"]),
        "clar_zero_pct": round((df["clarification_rounds"] == 0).mean() * 100, 1),
        "clar_ge3_pct": round((df["clarification_rounds"] >= 3).mean() * 100, 1),
        "duplicate_pct": round((df["is_duplicate"] == "是").mean() * 100, 1),
        "attachment_zero_pct": round((df["attachment_count"] == 0).mean() * 100, 1),
    }

    # ---------- 2. 釐清次數 → 處理時數（核心因果鏈）
    grp = (
        df.groupby("clarification_rounds")
        .agg(
            n=("ticket_id", "count"),
            median_hours=("resolution_hours", "median"),
            median_eng=("eng_effort_hours", "median"),
            mean_csat=("csat_num", "mean"),
        )
        .reset_index()
    )
    grp = grp[grp["n"] >= 8]
    r["clarification_cost_curve"] = [
        {
            "rounds": int(x["clarification_rounds"]),
            "n": int(x["n"]),
            "median_hours": round(float(x["median_hours"]), 1),
            "median_eng_hours": round(float(x["median_eng"]), 1),
            "mean_csat": None if pd.isna(x["mean_csat"]) else round(float(x["mean_csat"]), 2),
        }
        for _, x in grp.iterrows()
    ]
    # log-linear 迴歸：log(hours) ~ clarification_rounds
    m = df[df["resolution_hours"] > 0]
    slope, intercept = np.polyfit(m["clarification_rounds"], np.log(m["resolution_hours"]), 1)
    r["clarification_regression"] = {
        "model": "log(resolution_hours) ~ clarification_rounds",
        "slope": round(float(slope), 4),
        "multiplier_per_round_pct": round((float(np.exp(slope)) - 1) * 100, 1),
        "corr_completeness_vs_clar": round(
            float(df["info_completeness_score"].corr(df["clarification_rounds"])), 3
        ),
        "corr_clar_vs_hours": round(
            float(df["clarification_rounds"].corr(df["resolution_hours"])), 3
        ),
    }

    # ---------- 3. 「越急越講不清楚」假說
    r["urgency_vs_quality"] = {
        p: {
            "n": int(g.shape[0]),
            "median_completeness": float(g["info_completeness_score"].median()),
            "median_clar": float(g["clarification_rounds"].median()),
        }
        for p, g in df.groupby("priority")
    }

    # ---------- 4. AI 自動化分級
    lvl = (
        df.groupby("ai_automation_level")
        .agg(
            tickets=("ticket_id", "count"),
            eng_hours=("eng_effort_hours", "sum"),
            median_hours=("resolution_hours", "median"),
        )
        .reset_index()
        .sort_values("ai_automation_level")
    )
    total_eng = df["eng_effort_hours"].sum()
    r["ai_levels"] = [
        {
            "level": x["ai_automation_level"],
            "tickets": int(x["tickets"]),
            "ticket_pct": round(x["tickets"] / len(df) * 100, 1),
            "eng_hours": round(float(x["eng_hours"]), 1),
            "eng_hour_pct": round(float(x["eng_hours"]) / total_eng * 100, 1),
            "median_hours": round(float(x["median_hours"]), 1),
        }
        for _, x in lvl.iterrows()
    ]

    # ---------- 5. 可預防性
    prev = (
        df.groupby("ai_preventable")
        .agg(tickets=("ticket_id", "count"), eng_hours=("eng_effort_hours", "sum"))
        .reset_index()
    )
    r["preventability"] = [
        {
            "level": x["ai_preventable"],
            "tickets": int(x["tickets"]),
            "ticket_pct": round(x["tickets"] / len(df) * 100, 1),
            "eng_hours": round(float(x["eng_hours"]), 1),
        }
        for _, x in prev.iterrows()
    ]

    # ---------- 6. 根因
    rc = (
        df.groupby("root_cause_category")
        .agg(
            tickets=("ticket_id", "count"),
            eng_hours=("eng_effort_hours", "sum"),
            median_hours=("resolution_hours", "median"),
            recurrence_pct=("recurrence_90d", lambda s: (s == "是").mean() * 100),
        )
        .reset_index()
        .sort_values("tickets", ascending=False)
    )
    r["root_causes"] = [
        {
            "root_cause": x["root_cause_category"],
            "tickets": int(x["tickets"]),
            "ticket_pct": round(x["tickets"] / len(df) * 100, 1),
            "eng_hours": round(float(x["eng_hours"]), 1),
            "median_hours": round(float(x["median_hours"]), 1),
            "recurrence_pct": round(float(x["recurrence_pct"]), 1),
        }
        for _, x in rc.iterrows()
    ]

    # ---------- 7. 問題大類
    cat = (
        df.groupby("issue_category")
        .agg(
            tickets=("ticket_id", "count"),
            eng_hours=("eng_effort_hours", "sum"),
            median_hours=("resolution_hours", "median"),
            median_completeness=("info_completeness_score", "median"),
        )
        .reset_index()
        .sort_values("tickets", ascending=False)
    )
    r["issue_categories"] = [
        {
            "category": x["issue_category"],
            "tickets": int(x["tickets"]),
            "ticket_pct": round(x["tickets"] / len(df) * 100, 1),
            "eng_hours": round(float(x["eng_hours"]), 1),
            "median_hours": round(float(x["median_hours"]), 1),
            "median_completeness": int(x["median_completeness"]),
        }
        for _, x in cat.iterrows()
    ]

    # ---------- 8. 處理方式（判斷可自助化的比例）
    res = df["resolution_type"].value_counts()
    r["resolution_types"] = {
        k: {"n": int(v), "pct": round(v / len(df) * 100, 1)} for k, v in res.items()
    }
    edu_none = df["resolution_type"].isin(["教育說明／文件引導", "無需處理(誤報結案)"])
    r["knowledge_solvable"] = {
        "tickets": int(edu_none.sum()),
        "ticket_pct": round(edu_none.mean() * 100, 1),
        "eng_hours": round(float(df.loc[edu_none, "eng_effort_hours"].sum()), 1),
    }

    # ---------- 9. 品質後果
    r["quality_outcomes"] = {
        "reopen_rate_pct": round((closed["reopened_count"] > 0).mean() * 100, 1),
        "recurrence_90d_pct": round((df["recurrence_90d"] == "是").mean() * 100, 1),
        "csat": q(closed["csat_num"]),
        "csat_by_clar": {
            str(int(k)): round(float(v), 2)
            for k, v in closed.groupby("clarification_rounds")["csat_num"].mean().items()
            if closed.groupby("clarification_rounds").size()[k] >= 8
        },
        "first_response_min": q(df["first_response_min"]),
    }

    # ---------- 10. 組織情境切片
    r["by_org_context"] = {
        k: {
            "tickets": int(g.shape[0]),
            "median_completeness": int(g["info_completeness_score"].median()),
            "median_clar": float(g["clarification_rounds"].median()),
            "median_hours": round(float(g["resolution_hours"].median()), 1),
            "mean_csat": round(float(g["csat_num"].mean()), 2),
        }
        for k, g in df.groupby("org_context")
    }

    # ---------- 11. 平台事件衝擊
    ev = df[df["platform_event_id"] != "—"]
    r["platform_events"] = {
        "total_tickets": int(len(ev)),
        "pct_of_all": round(len(ev) / len(df) * 100, 1),
        "by_event": {
            k: {
                "tickets": int(g.shape[0]),
                "median_hours": round(float(g["resolution_hours"].median()), 1),
                "median_completeness": int(g["info_completeness_score"].median()),
                "eng_hours": round(float(g["eng_effort_hours"].sum()), 1),
            }
            for k, g in ev.groupby("platform_event_id")
        },
        "baseline_median_hours": round(
            float(df[df["platform_event_id"] == "—"]["resolution_hours"].median()), 1
        ),
    }

    # ---------- 12. 可回收工時上限（保守估算）
    # L2/L4 視為可完全自動；L3 節省 50% 工時；L1 透過釐清次數歸零節省
    l2 = df["ai_automation_level"].str.startswith("L2")
    l3 = df["ai_automation_level"].str.startswith("L3")
    l4 = df["ai_automation_level"].str.startswith("L4")
    saved_l2 = df.loc[l2, "eng_effort_hours"].sum()
    saved_l4 = df.loc[l4, "eng_effort_hours"].sum()
    saved_l3 = df.loc[l3, "eng_effort_hours"].sum() * 0.5
    # L1：把釐清次數降到 0，依迴歸係數回推
    exp_slope = float(np.exp(slope))
    df["_hours_if_zero_clar"] = df["resolution_hours"] / (exp_slope ** df["clarification_rounds"])
    ratio = (df["_hours_if_zero_clar"] / df["resolution_hours"]).clip(0, 1)
    saved_clar = float((df["eng_effort_hours"] * (1 - ratio)).sum())

    r["recoverable_hours"] = {
        "total_eng_hours": round(float(total_eng), 1),
        "L2_full_auto": round(float(saved_l2), 1),
        "L3_half_auto": round(float(saved_l3), 1),
        "L4_full_auto": round(float(saved_l4), 1),
        "L1_clarification_elimination": round(saved_clar, 1),
        "note": "L1 與 L2/L3/L4 有部分重疊，總計取聯集上限而非相加",
    }
    union_upper = float(saved_l2 + saved_l4 + saved_l3 + saved_clar * 0.6)
    r["recoverable_hours"]["union_upper_bound"] = round(union_upper, 1)
    r["recoverable_hours"]["union_upper_pct"] = round(union_upper / float(total_eng) * 100, 1)

    # ---------- 13. 偵測器可攔截量
    det = (
        df[df["ai_preventable"] == "是"]
        .groupby("detection_signal")
        .agg(tickets=("ticket_id", "count"), eng_hours=("eng_effort_hours", "sum"))
        .reset_index()
    )
    det = det.sort_values("tickets", ascending=False)
    r["detector_coverage"] = [
        {
            "signal": x["detection_signal"],
            "tickets": int(x["tickets"]),
            "ticket_pct": round(x["tickets"] / len(df) * 100, 1),
            "eng_hours": round(float(x["eng_hours"]), 1),
        }
        for _, x in det.iterrows()
    ]

    # ---------- 14. 月度趨勢（給 dashboard 用）
    monthly = (
        df.set_index("submitted_at")
        .resample("MS")
        .agg(
            tickets=("ticket_id", "count"),
            eng_hours=("eng_effort_hours", "sum"),
            median_completeness=("info_completeness_score", "median"),
            median_clar=("clarification_rounds", "median"),
        )
        .reset_index()
    )
    r["monthly"] = [
        {
            "month": x["submitted_at"].strftime("%Y-%m"),
            "tickets": int(x["tickets"]),
            "eng_hours": round(float(x["eng_hours"]), 1),
            "median_completeness": int(x["median_completeness"]),
            "median_clar": float(x["median_clar"]),
        }
        for _, x in monthly.iterrows()
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
