#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI 關卡 3 · 探針唯讀靜態掃描
============================
掃描 probes/ 目錄，禁止出現任何寫入語意的呼叫。

為什麼要這道關卡：
  「探針全部唯讀」是本系統最重要的安全承諾之一。這條原則靠 code review 守不住——
  review 會漏，尤其是 AI 協助開發時。所以把它變成 CI 硬性檢查。

  第二層護欄在 IAM：Terraform 給診斷服務綁定的服務帳號只有 read 角色。
  兩層缺一不可——程式碼自律擋不住模型幻覺，IAM 擋得住。

用法：python tools/check_probes_readonly.py src/adops_triage/probes
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# 寫入語意的函式名／方法名
FORBIDDEN_CALLS = {
    "post",
    "put",
    "patch",
    "delete",
    "write",
    "update",
    "create",
    "insert",
    "upsert",
    "remove",
    "drop",
    "truncate",
    "execute",
    "commit",
    "save",
    "set_",
    "publish",
    "send",
    "upload",
}
# 允許的例外（唯讀語境下的同名函式）
ALLOWLIST = {"write_cache", "save_snapshot_readonly"}

FORBIDDEN_MODULES = {"subprocess", "shutil", "os.remove", "os.rmdir"}


class ProbeVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = None
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        if name and name not in ALLOWLIST:
            low = name.lower()
            if low in FORBIDDEN_CALLS or any(
                low.startswith(f) for f in ("post_", "put_", "delete_")
            ):
                self.violations.append(f"{self.path}:{node.lineno} 呼叫了寫入語意的 `{name}()`")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for a in node.names:
            if a.name in FORBIDDEN_MODULES:
                self.violations.append(f"{self.path}:{node.lineno} 匯入了 `{a.name}`")
        self.generic_visit(node)


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "src/adops_triage/probes")
    if not root.exists():
        print(f"⚠ 找不到 {root}，跳過")
        return 0

    all_violations: list[str] = []
    for py in sorted(root.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        v = ProbeVisitor(py)
        v.visit(tree)
        all_violations.extend(v.violations)

    if all_violations:
        print("✘ 探針唯讀檢查失敗：\n")
        for x in all_violations:
            print(f"   {x}")
        print("\n探針不得有任何寫入行為。修復動作請走 L4，並在 specs/playbook_registry.yaml 註冊。")
        return 1

    print("✔ 探針唯讀檢查通過")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
