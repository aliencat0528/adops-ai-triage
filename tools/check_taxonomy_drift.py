#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI 關卡 2 · Spec 契約驗證（分類法漂移）
======================================
確保程式裡出現的分類值都存在於 specs/taxonomy.yaml。

擋下什麼：有人在程式裡硬寫了一個 taxonomy 沒有的分類字串，
造成資料裡出現「幽靈分類」，讓所有依分類彙總的報表悄悄失準。

規則：generate_dataset.py 與 export_xlsx.py 因需求可持有完整列舉，列為例外；
其餘模組不得硬寫分類字串，一律從 taxonomy.yaml 讀取。

用法：python tools/check_taxonomy_drift.py --spec specs/taxonomy.yaml --src src
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# 這些檔案的中文字串本來就不是分類值：
#   generate_dataset / export_xlsx / baseline —— 產生或呈現資料本身
#   readonly.py —— 探針的 mock 回傳值（假的稽核紀錄、假的變更摘要），不是分類法
#   demo.py —— demo 用的範例工單與客戶名，性質同 mock 資料
EXEMPT = {"generate_dataset.py", "export_xlsx.py", "baseline.py", "readonly.py", "demo.py"}
CJK_STRING = re.compile(r'["\']([^"\']*[一-鿿][^"\']*)["\']')
LABEL_VALUE = re.compile(r'"label"\s*:\s*"[^"]*"')


def collect_known(spec: dict) -> set[str]:
    known: set[str] = set()
    known |= set(spec.get("org_contexts", {}).values())
    known |= set(spec.get("platforms", {}).values())
    for cat, subs in spec.get("issue_taxonomy", {}).items():
        known.add(cat)
        known |= set(subs)
    known |= {v["label"] for v in spec.get("root_causes", {}).values()}
    known |= set(spec.get("resolution_types", {}).values())
    known |= {v["label"] for v in spec.get("ai_automation_levels", {}).values()}
    known |= set(spec.get("severity_levels", {}).values())
    known |= set(spec.get("priority_levels", {}).values())
    # 資料層用的是 `S1-投放中斷/嚴重失真` 這種「代碼-標籤」複合形式，
    # taxonomy 裡存的是拆開的兩半。不補這一段，合法的嚴重度字串會被誤報成漂移。
    for group in ("severity_levels", "priority_levels", "ai_automation_levels"):
        for code, val in spec.get(group, {}).items():
            label = val["label"] if isinstance(val, dict) else val
            known.add(f"{code}-{label}")
    return known


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="specs/taxonomy.yaml")
    ap.add_argument("--src", default="src")
    args = ap.parse_args()

    spec = yaml.safe_load(Path(args.spec).read_text(encoding="utf-8"))
    known = collect_known(spec)

    # 只針對「看起來像分類值」的字串告警：長度 3-24、不含空白與標點
    suspicious: list[str] = []
    for py in sorted(Path(args.src).rglob("*.py")):
        if py.name in EXEMPT:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            for m in CJK_STRING.finditer(line):
                s = m.group(1)
                if not (3 <= len(s) <= 24):
                    continue
                if any(ch in s for ch in " ，。：；？！、（）"):
                    continue
                if s in known:
                    continue
                # 白名單：明顯是提示語或欄位名而非分類值
                if s.endswith(("嗎", "呢", "了", "吧")) or s.startswith(("請", "這", "目前")):
                    continue
                # 白名單：`"label": "庫存狀態"` 這種顯示標籤不是分類值
                if LABEL_VALUE.search(line) and f'"{s}"' in LABEL_VALUE.search(line).group(0):
                    continue
                suspicious.append(f"{py}:{lineno} 可疑的硬寫分類字串 `{s}`")

    if suspicious:
        print("✘ 分類法漂移檢查發現可疑項目：\n")
        for s in suspicious[:40]:
            print(f"   {s}")
        if len(suspicious) > 40:
            print(f"   …另有 {len(suspicious) - 40} 項")
        print(
            "\n分類值請從 specs/taxonomy.yaml 讀取，不要硬寫在程式碼裡。"
            "\n若確認是誤判，將該檔加入本腳本的 EXEMPT 或補充白名單規則。"
        )
        return 1

    print(f"✔ 分類法契約驗證通過（已知分類值 {len(known)} 個）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
