#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI 關卡 4 · Playbook 引用檢查
=============================
程式中引用的每個 action id 必須存在於 specs/playbook_registry.yaml。

擋下什麼：繞過允許清單的修復動作。
Remediation Agent 只能從 registry 挑動作，不得生成新動作——這條規則要靠 CI 強制，
否則 LLM 幻覺出來的 action id 會一路寫進程式碼而沒人發現。

同時檢查：高風險動作不得出現在自動執行路徑（approval 必須是 recommendation_only）。

用法：python tools/check_playbook_refs.py --spec specs/playbook_registry.yaml --src src
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ACTION_PATTERN = re.compile(r'["\']([a-z_]+\.[a-z_]+)["\']')
AUTO_EXEC_HINT = re.compile(r"(auto_execute|execute_now|run_action)\s*\(")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="specs/playbook_registry.yaml")
    ap.add_argument("--src", default="src")
    args = ap.parse_args()

    spec = yaml.safe_load(Path(args.spec).read_text(encoding="utf-8"))
    registry = {a["id"]: a for a in spec["actions"]}
    high_risk = {k for k, v in registry.items() if v.get("risk_tier") == "high"}

    errors: list[str] = []
    for py in sorted(Path(args.src).rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for m in ACTION_PATTERN.finditer(line):
                candidate = m.group(1)
                prefix = candidate.split(".")[0]
                if prefix not in {"feed", "pipeline", "audience", "token", "report",
                                  "gtm", "capi", "consent", "campaign", "schema", "account"}:
                    continue
                if candidate not in registry:
                    errors.append(
                        f"{py}:{lineno} 引用了未註冊的動作 `{candidate}`"
                    )
                elif candidate in high_risk and AUTO_EXEC_HINT.search(line):
                    errors.append(
                        f"{py}:{lineno} 高風險動作 `{candidate}` 出現在自動執行路徑"
                    )

    if errors:
        print("✘ Playbook 引用檢查失敗：\n")
        for e in errors:
            print(f"   {e}")
        print("\n所有修復動作都必須先在 specs/playbook_registry.yaml 註冊，"
              "並標明 risk_tier / reversible / rollback。")
        return 1

    print(f"✔ Playbook 引用檢查通過（registry 共 {len(registry)} 個動作，"
          f"其中 {len(high_risk)} 個為 recommendation-only）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
