# TASKS.md — 開發 backlog

> Claude Code 使用方式：讀這份檔案，挑一個 `[ ]` 的任務執行。
> 完成後把 `[ ]` 改成 `[x]`，並在該行後面用 `→` 補一句實作摘要。
> 不確定要做什麼時，從最上面沒打勾的開始。
>
> **2026-08-25 校準過一次**：此前勾選狀態嚴重落後（只勾 3 項，實際完成 16 項），
> 導致 `/next-task` 會挑到早就做完的任務。動工前若發現某項已經有程式，先回來補勾。

---

## Phase 0 — 資料底座（先做完這段，後面才有東西可分析）

- [x] T-001 定義 `specs/taxonomy.yaml`：問題八大類、細類、根因、處理方式、AI 分級的列舉值
- [x] T-002 定義 `specs/ticket.schema.json`：50 欄位，含依問題大類動態變更的必填欄位集
- [x] T-003 實作 `generate_dataset.py`：640 筆、12 個月、含 2026 真實平台事件錨點與台灣電商檔期
- [x] T-004 寫 `tests/test_dataset.py`：驗證欄位邏輯一致性（完整度↓→釐清次數↑、結案單必有結案時間、重複單必有來源單號） → `tests/test_dataset.py` 8 個測試，含完整度↔釐清次數負相關、結案時間、重複單來源單號、平台事件工時
- [x] T-005 輸出 xlsx 多工作表（主資料／欄位字典／下拉選單／統計摘要）到 `data/raw/` → `export_xlsx.py`，四工作表（主檔／欄位字典／下拉選單／統計摘要）

## Phase 1 — 分析：讓資料自己說話

- [x] T-101 `analysis/baseline.py`：算出七個 KPI baseline（完整度中位數、釐清次數分布、TTR、工程工時、重工率、復發率、CSAT） → `analysis/baseline.py`，七組 KPI 全數輸出到 `reports/baseline.json`
- [x] T-102 量化「釐清次數 → 處理時數」的關係，跑迴歸並輸出係數與信賴區間 → log 線性迴歸 slope 0.2002 ＝ 每輪 +22.2%；完整度相關 −0.727（`clarification_regression`）
- [ ] T-103 `analysis/ai_opportunity.py`：依 AI 分級 L0–L4 統計工單佔比、對應工時佔比、可回收工時上限 → 部分：`ai_levels` 與 `recoverable_hours` 已在 `baseline.py` 產出，尚未拆成獨立模組
- [x] T-104 根因 × 客戶交叉分析，找出「反覆出現在同一批客戶」的結構性問題 → `by_org_context` 與 `root_causes` 交叉，見 `reports/baseline.json`
- [x] T-105 驗證假說「越急的單資訊完整度越低」，輸出 P0–P3 各級的完整度分布 → `urgency_vs_quality`：P0 中位完整度 50 最低，但 P1 59＞P2 57，假說只部分成立
- [ ] T-106 把分析結果輸出成 `reports/baseline.md` + 圖表 PNG

## Phase 2 — L1 提單助理（入口收斂）

- [x] T-201 `agents/intake.py`：完整度評分器。輸入自由文字 + 已填欄位，輸出 0–100 分與缺漏欄位清單 → 評分器可跑（`IntakeAgent.score`），LLM 抽取仍是介面（`extract_with_llm`）
- [x] T-202 動態必填規則：依問題大類切換 required set（讀 `ticket.schema.json`） → 讀 `ticket.schema.json` 的 `allOf` 動態切換必填集，不硬寫
- [x] T-203 自動補件：從 asset_id 反查客戶與關聯活動（mock probe）、從時間比對平台 changelog → `IntakeAgent.autofill`，lookups 由呼叫端注入；尚無測試覆蓋
- [ ] T-204 追問生成：最多 3 輪，每輪最多 2 題，優先問「缺了會讓診斷無法進行」的欄位 → 部分：每輪最多 2 題已實作；`max_clarification_rounds` 三輪迴圈尚未接
- [x] T-205 護欄：完整度 <40 阻擋送出；P0 可 override 但標記 → 完整度 <40 擋下、P0 可 override 但標記，門檻讀 `x-submission-guards`
- [ ] T-206 回放評測：拿歷史 640 筆重跑，比較「原始完整度」vs「經助理處理後完整度」

## Phase 3 — L2 分診

- [ ] T-301 `agents/triage.py` 規則引擎：關鍵字 × 平台 × 資產類型 → 直接分類
- [ ] T-302 相似單檢索：embedding + cosine similarity，回傳 Top-8 歷史單
- [ ] T-303 LLM fallback：規則未命中時，用 Top-8 做 few-shot 分類
- [ ] T-304 blast radius 計算：關聯活動數 × 日花費 → 影響金額
- [ ] T-305 重複單偵測：similarity > 0.88 且同客戶 7 天內 → 標記合併
- [ ] T-306 評測：對照資料集標註算分類準確率與路由錯誤率

## Phase 4 — L0 主動偵測器（本專案最有價值的一段）

- [x] T-401 `detectors/base.py`：`Detector` 抽象類別、`Finding` 資料結構、嚴重度判定 → `Detector` 抽象類別＋`Finding`＋24 小時去重（`emit`）
- [x] T-402 `detectors/feed_health.py`：Feed 值 vs 到達頁 schema 逐項比對（價格／庫存／幣別／GTIN） → 價格／庫存／幣別／特價／GTIN 五欄逐項比對，容忍度分級
- [x] T-403 `detectors/cross_source_recon.py`：平台 vs GA4 vs 後台訂單三方差異率，>20% 告警 → 三方差異率，連續兩日超標才告警（單日只計數，避免誤報）
- [x] T-404 偵測器排程與去重（同一 finding 24h 內不重複告警） → `dedup_window_hours = 24`，同 fingerprint 靜默；`make detect` 可看到行為
- [ ] T-405 回測：把偵測器套在歷史資料上，算「本來會開單但可被攔截」的比例

## Phase 5 — L3–L5 介面與護欄（本專案做到介面即可）

- [x] T-501 `probes/readonly.py`：七個探針的介面與 mock 實作，加上「唯讀」的執行期斷言 → 七支探針＋`_assert_readonly()` 執行期斷言，CI 另有靜態掃描
- [ ] T-502 `agents/diagnosis.py`：ReAct 迴圈骨架，輸出 Top-3 根因假設 + 證據 + 信心分數
- [ ] T-503 `agents/remediation.py`：從 `playbook_registry.yaml` 挑動作，拒絕清單外動作
- [ ] T-504 風險閘門：低風險自動、中風險單人核准、高風險 recommendation-only
- [ ] T-505 `agents/verification.py`：重跑原始檢測 + soak 期監控 + 未通過退回

## Phase 6 — 交付

- [ ] T-601 `reports/` 產出完整分析報告 → 部分：`reports/baseline.json` 已產出，缺 md 報告
- [x] T-602 README 補上專案敘事與如何重現 → README 已含敘事、快速開始與重現方式
- [ ] T-603 錄一段 3 分鐘 demo（提單助理 → 分診 → 偵測器攔截）

---

## 不做清單（要做請先寫 ADR）

見 `CLAUDE.md` 第 8 節。
