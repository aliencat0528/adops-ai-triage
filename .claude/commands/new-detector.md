---
description: 新增一個主動偵測器
---
建立新偵測器時依序完成：

1. 在 `specs/probes.yaml` 確認所需探針已定義；若無則新增（必須唯讀）
2. 在 `src/adops_triage/detectors/` 建立模組，繼承 `base.Detector`
3. 實作 `scan()` 回傳 `list[Finding]`，並在最後呼叫 `self.emit()` 做去重
4. **設定門檻時要說明理由**——門檻太低會製造誤報，淹沒真正的異常
5. 若建議修復動作，`suggested_action_id` 必須存在於 `specs/playbook_registry.yaml`
6. 在 `tests/test_detectors.py` 加測試，至少涵蓋：門檻內不告警、超過門檻告警、去重有效
7. 在 `infra/main.tf` 的 `google_cloud_scheduler_job.detectors` 加排程
8. 回測：把偵測器套在 `data/raw/tickets.csv` 上，算「本來會開單但可被攔截」的比例
