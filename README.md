# AdOps AI Triage · 廣告支援工程需求單 AI 化

> 用一份刻意設計過的需求單資料，反推出一套人機協作的支援系統架構。
> **所有資料皆為模擬生成，不含任何真實企業或客戶資料。**

---

## 一句話

現有工單系統只記「什麼問題、誰處理、多久解決」，答不出「為什麼花這麼久」。
補上**提單品質**、**根因分類**、**可預防性**三組欄位之後，資料指出兩件事：

1. **釐清次數每增加一次，處理時數增加 22.2%**（完整度與釐清次數相關係數 −0.727）
2. **48.9% 的工單其實可以在發生前被攔截**

因此系統設計為：入口收斂（L1）＋ 知識自助（L2/L3）＋ 主動預防（L0）。

---

## 快速開始

```bash
make setup      # 建虛擬環境並安裝依賴
make data       # 生成 640 筆 × 53 欄需求單 → data/raw/tickets.csv
make xlsx       # 匯出四工作表的 xlsx（給人看）
make analyze    # 跑 baseline 分析 → reports/baseline.json
make test       # 17 個測試
make guardrails # 三道架構護欄檢查
```

或一次跑完：`make all`

---

## 這個 repo 有什麼

| 路徑 | 內容 |
|---|---|
| `CLAUDE.md` | **專案憲法**。Claude Code 進來先讀這份 |
| `TASKS.md` | 開發 backlog，60 個編號任務分六階段 |
| `specs/taxonomy.yaml` | 分類法唯一真實來源（問題類別／根因／處理方式／AI 分級／風險層級） |
| `specs/ticket.schema.json` | 51 欄位工單契約，含**依問題大類動態變更的必填欄位** |
| `specs/playbook_registry.yaml` | 修復動作允許清單，含 risk_tier / 可逆性 / 回滾方式 |
| `specs/probes.yaml` | 七支唯讀探針的介面定義 |
| `src/adops_triage/generate_dataset.py` | 資料生成器（含 2026 真實平台事件錨點） |
| `src/adops_triage/analysis/baseline.py` | KPI 基線與 AI 機會分析 |
| `src/adops_triage/agents/intake.py` | 提單完整度評分器（可執行） |
| `src/adops_triage/detectors/` | Feed 健檢、跨源對帳（可執行） |
| `src/adops_triage/probes/readonly.py` | 七支唯讀探針的 mock 實作 |
| `tools/check_*.py` | 三道 CI 架構護欄 |
| `.github/workflows/` | CI 六道關卡 + 灰度部署 |
| `infra/` | Terraform（IAM 層強制探針唯讀） |

---

## 五條不可違反的原則

1. **Deterministic before generative** — 已知故障先走規則引擎，LLM 只處理模糊案例
2. **探針全部唯讀** — 程式層 CI 掃描 + IAM 層只綁 read 角色，兩層護欄
3. **修復動作只能來自允許清單** — LLM 不得生成 `playbook_registry.yaml` 以外的動作
4. **高風險永遠只建議** — 動預算／出價／刪受眾／改 schema 一律 recommendation-only
5. **寧可 abstain 也不要幻覺** — 無法引用知識庫條目就說「沒把握」

---

## 怎麼在 Claude Code 裡用這些資料

看 `docs/CLAUDE-CODE-USAGE.md`，裡面有：

- 哪些檔案該用、哪些不該用（**不要叫它直接讀 650 KB 的 csv**）
- 六種常見情境的指令範本，可以直接抄
- 三道防止它亂改的護欄
- 一個實際工作循環長什麼樣

## 給 Claude Code 的話

進到這個專案請先讀 `CLAUDE.md`，再讀 `TASKS.md` 挑一個 `[ ]` 的任務。
要推翻 `CLAUDE.md` 第 8 節「不做清單」裡的任何一條，先在 `docs/adr/` 寫一份 ADR。
