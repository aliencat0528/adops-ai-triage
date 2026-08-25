> 繼承根目錄共用規則（Claude Code 已自動載入，勿重複讀取 ../CLAUDE.md）

# CLAUDE.md — 專案憲法

> 這份檔案是 Claude Code 進入本專案時的第一份上下文。
> 修改設計決策時，請一併更新這份檔案與 `docs/adr/`。

---

## 1. 這個專案是什麼

**專案名**：AdOps AI Triage — 廣告支援工程需求單 AI 化系統

**一句話**：用一份「刻意設計過的廣告技術需求單資料」反推出一套人機協作的支援系統架構，
並實作其中可驗證的部分（資料生成、提單品質評分、自動分診、兩個主動偵測器）。

**這是作品集專案，不是產品**：
- 所有資料皆為**模擬資料**，由 `src/adops_triage/generate_dataset.py` 生成，禁止宣稱為真實企業資料。
- 不串接任何真實廣告平台 API。所有探針（probe）為 mock 實作，介面依 `specs/probes.yaml`。
- 目標讀者：MarTech / Data / Solution Engineer 職缺面試官。

---

## 2. 核心論證（所有程式都在服務這條論證）

```
現有工單系統只記「什麼問題、誰處理、多久解決」
  → 答不出「為什麼花這麼久」
  → 所以補三組欄位：提單品質 / 根因分類 / 可預防性
  → 資料證明：釐清次數是最大成本放大器，且大量工單根本不該存在
  → 因此系統設計為：入口收斂(L1) + 知識自助(L2/L3) + 主動預防(L0)
```

**寫任何程式前先問**：這段程式是在支撐上面哪一步？如果都不是，就不該寫。

---

## 3. 分層架構（七層）

| 層 | 名稱 | 職責 | 本專案實作程度 |
|---|---|---|---|
| L0 | 感知層 Detection | 六個主動偵測器，在開單前攔截 | **實作 2 個原型** |
| L1 | 受理層 Intake | 對話式提單、完整度評分、自動補件 | **實作評分器** |
| L2 | 分診層 Triage | 分類／嚴重度／路由／重複單合併 | **實作規則+相似檢索** |
| L3 | 診斷層 Diagnosis | 呼叫唯讀探針、產出根因假設 | 介面 + mock |
| L4 | 處置層 Execution | 受控執行（允許清單、速率限制、audit log） | 介面 + 風險閘門 |
| L5 | 驗證層 Verification | 重跑檢測、soak 期監控、未通過退回 | 介面 |
| L6 | 學習層 Learning | 結案回寫知識庫、根因聚類、月報 | 分析腳本 |

**不可違反的設計原則**：

1. **Deterministic before generative** — 已知故障先走版本控管的規則引擎，LLM 只處理規則接不住的模糊案例。任何新功能都先問「這能不能用規則做完」。
2. **探針全部唯讀** — `src/adops_triage/probes/` 底下任何函式不得有寫入行為。程式碼審查時這是紅線。
3. **修復動作只能來自允許清單** — LLM 不得生成 `specs/playbook_registry.yaml` 以外的動作。
4. **高風險動作永遠只建議、不執行** — 動預算／出價／刪除受眾／改 schema，一律 recommendation-only。
5. **寧可 abstain 也不要幻覺** — 檢索回覆無法引用到具體知識庫條目時必須回「無把握」並轉人工。

---

## 4. 六個 Agent 與模型路由

| # | Agent | 模組 | 模型 | 為什麼是這個模型 |
|---|---|---|---|---|
| 1 | Intake 提單助理 | `agents/intake.py` | Haiku | 高頻、結構化抽取，不需推理深度 |
| 2 | Triage 分診 | `agents/triage.py` | Haiku + 規則 | 分類任務，可用歷史單 few-shot |
| 3 | Retrieval 檢索回覆 | `agents/retrieval.py` | Sonnet | 需判斷「我到底知不知道」 |
| 4 | Diagnosis 診斷 | `agents/diagnosis.py` | **Opus** | 全案唯一需跨源推理的環節 |
| 5 | Remediation 修復規劃 | `agents/remediation.py` | Sonnet | 受限選擇題，不需最強模型 |
| 6 | Verification 驗證回寫 | `agents/verification.py` | Sonnet | 結構化比對 + 摘要 |

成本原則：**只有 Agent 4 值得用 Opus**。若發現其他 agent 需要升級模型，先檢查是不是 prompt 或 schema 設計有問題。

---

## 5. 目錄結構

```
specs/          設計契約。改這裡等於改架構，需同步更新 docs/
  taxonomy.yaml            問題分類、根因、處理方式的列舉值（單一真實來源）
  ticket.schema.json       工單 JSON Schema，含依大類動態變更的必填欄位
  playbook_registry.yaml   修復動作允許清單 + 風險層級 + 回滾方式
  probes.yaml              七個唯讀探針的介面定義

src/adops_triage/
  generate_dataset.py      資料生成器（含 2026 真實平台事件錨點）
  agents/                  六個 agent
  detectors/               主動偵測器
  probes/readonly.py       探針介面與 mock 實作
  analysis/                baseline 與 AI 機會分析

docs/           設計文件。docs/adr/ 放架構決策紀錄
data/raw/       生成的資料（不進 git）
tests/          測試
TASKS.md        開發 backlog — 不知道要做什麼就看這裡
```

---

## 6. 開發慣例

- **Python 3.11+**，格式化用 `ruff format`，檢查用 `ruff check`。
- **列舉值一律從 `specs/taxonomy.yaml` 讀取**，不要在 Python 裡硬寫中文字串常數。
- **資料生成必須可重現**：任何隨機性都要吃 `--seed`，預設 `20260823`。
- **新增偵測器**：繼承 `detectors/base.py` 的 `Detector`，實作 `scan()` 回傳 `list[Finding]`，並在 `specs/probes.yaml` 註冊所需探針。
- **新增修復動作**：先在 `specs/playbook_registry.yaml` 註冊（含 risk_tier 與 rollback），才允許在程式中引用。
- **測試**：`make test`。偵測器與評分器必須有測試，agent 的 LLM 呼叫用 mock。
- **命名用 snake_case（PEP 8）**——這是與根規則 `camelCase` 唯一的風格差異。
  縮排 4 spaces、double quotes、commit 前 lint 必過，均與根規則一致。

---

## 7. 常用指令

```bash
make setup        # 建虛擬環境並安裝依賴
make data         # 生成 640 筆需求單 → data/raw/
make analyze      # 跑 baseline 與 AI 機會分析，輸出到 reports/
make demo         # 跑提單評分 + 分診 demo
make detect       # 跑兩個偵測器原型
make test         # 跑測試
make lint         # ruff check + format
```

---

## 8. 明確不做清單（防範 scope creep）

以下項目**本專案不做**。若要做，先寫一份 ADR 說明為什麼推翻這個決定：

- ❌ 全自動修復。高風險動作永遠只建議。
- ❌ 廣告成效優化建議（那是投手的專業，不是支援系統的守備範圍）。
- ❌ 即時串流架構。日批 + 事件觸發足夠。
- ❌ 自建向量資料庫。用託管方案或本地 FAISS。
- ❌ 多語系。先繁體中文單一市場。
- ❌ 真實客戶資料。全案使用模擬資料。
- ❌ 前端介面。本專案交付分析、規劃與可跑的後端原型，不做 UI。

---

## 9. 目前進度

見 `TASKS.md`。開始工作前先讀該檔並挑一個 `[ ]` 的任務；完成後改成 `[x]` 並在該行後面補一句實作摘要。
