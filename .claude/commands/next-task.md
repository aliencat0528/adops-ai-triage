---
description: 從 TASKS.md 挑下一個任務並開始執行
---
讀 `TASKS.md`，找出第一個未打勾（`[ ]`）且沒有被阻擋的任務。

執行前先確認：
1. 這個任務對應 `CLAUDE.md` 第 2 節核心論證的哪一步？如果都不是，跳過並說明原因。
2. 需要用到的列舉值是否都在 `specs/taxonomy.yaml`？不要硬寫中文字串常數。
3. 若要新增修復動作，先在 `specs/playbook_registry.yaml` 註冊。
4. 若要新增探針，確認它是唯讀的，並在 `specs/probes.yaml` 定義介面。

完成後：
- 執行 `make test` 與 `make guardrails`，兩者都要通過
- 把 `TASKS.md` 該行改成 `[x]`，並在行尾用 `→` 補一句實作摘要
