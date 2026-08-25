# TASKS.md — 開發 backlog

> Claude Code 使用方式：讀這份檔案，挑一個 `[ ]` 的任務執行。
> 完成後把 `[ ]` 改成 `[x]`，並在該行後面用 `→` 補一句實作摘要。
> 不確定要做什麼時，從最上面沒打勾的開始。

---

## Phase 0 — 資料底座（先做完這段，後面才有東西可分析）

- [x] T-001 定義 `specs/taxonomy.yaml`：問題八大類、細類、根因、處理方式、AI 分級的列舉值
- [x] T-002 定義 `specs/ticket.schema.json`：50 欄位，含依問題大類動態變更的必填欄位集
- [x] T-003 實作 `generate_dataset.py`：640 筆、12 個月、含 2026 真實平台事件錨點與台灣電商檔期
- [ ] T-004 寫 `tests/test_dataset.py`：驗證欄位邏輯一致性（完整度↓→釐清次數↑、結案單必有結案時間、重複單必有來源單號）
- [ ] T-005 輸出 xlsx 多工作表（主資料／欄位字典／下拉選單／統計摘要）到 `data/raw/`

## Phase 1 — 分析：讓資料自己說話

- [ ] T-101 `analysis/baseline.py`：算出七個 KPI baseline（完整度中位數、釐清次數分布、TTR、工程工時、重工率、復發率、CSAT）
- [ ] T-102 量化「釐清次數 → 處理時數」的關係，跑迴歸並輸出係數與信賴區間
- [ ] T-103 `analysis/ai_opportunity.py`：依 AI 分級 L0–L4 統計工單佔比、對應工時佔比、可回收工時上限
- [ ] T-104 根因 × 客戶交叉分析，找出「反覆出現在同一批客戶」的結構性問題
- [ ] T-105 驗證假說「越急的單資訊完整度越低」，輸出 P0–P3 各級的完整度分布
- [ ] T-106 把分析結果輸出成 `reports/baseline.md` + 圖表 PNG

## Phase 2 — L1 提單助理（入口收斂）

- [ ] T-201 `agents/intake.py`：完整度評分器。輸入自由文字 + 已填欄位，輸出 0–100 分與缺漏欄位清單
- [ ] T-202 動態必填規則：依問題大類切換 required set（讀 `ticket.schema.json`）
- [ ] T-203 自動補件：從 asset_id 反查客戶與關聯活動（mock probe）、從時間比對平台 changelog
- [ ] T-204 追問生成：最多 3 輪，每輪最多 2 題，優先問「缺了會讓診斷無法進行」的欄位
- [ ] T-205 護欄：完整度 <40 阻擋送出；P0 可 override 但標記
- [ ] T-206 回放評測：拿歷史 640 筆重跑，比較「原始完整度」vs「經助理處理後完整度」

## Phase 3 — L2 分診

- [ ] T-301 `agents/triage.py` 規則引擎：關鍵字 × 平台 × 資產類型 → 直接分類
- [ ] T-302 相似單檢索：embedding + cosine similarity，回傳 Top-8 歷史單
- [ ] T-303 LLM fallback：規則未命中時，用 Top-8 做 few-shot 分類
- [ ] T-304 blast radius 計算：關聯活動數 × 日花費 → 影響金額
- [ ] T-305 重複單偵測：similarity > 0.88 且同客戶 7 天內 → 標記合併
- [ ] T-306 評測：對照資料集標註算分類準確率與路由錯誤率

## Phase 4 — L0 主動偵測器（本專案最有價值的一段）

- [ ] T-401 `detectors/base.py`：`Detector` 抽象類別、`Finding` 資料結構、嚴重度判定
- [ ] T-402 `detectors/feed_health.py`：Feed 值 vs 到達頁 schema 逐項比對（價格／庫存／幣別／GTIN）
- [ ] T-403 `detectors/cross_source_recon.py`：平台 vs GA4 vs 後台訂單三方差異率，>20% 告警
- [ ] T-404 偵測器排程與去重（同一 finding 24h 內不重複告警）
- [ ] T-405 回測：把偵測器套在歷史資料上，算「本來會開單但可被攔截」的比例

## Phase 5 — L3–L5 介面與護欄（本專案做到介面即可）

- [ ] T-501 `probes/readonly.py`：七個探針的介面與 mock 實作，加上「唯讀」的執行期斷言
- [ ] T-502 `agents/diagnosis.py`：ReAct 迴圈骨架，輸出 Top-3 根因假設 + 證據 + 信心分數
- [ ] T-503 `agents/remediation.py`：從 `playbook_registry.yaml` 挑動作，拒絕清單外動作
- [ ] T-504 風險閘門：低風險自動、中風險單人核准、高風險 recommendation-only
- [ ] T-505 `agents/verification.py`：重跑原始檢測 + soak 期監控 + 未通過退回

## Phase 6 — 交付

- [ ] T-601 `reports/` 產出完整分析報告
- [ ] T-602 README 補上專案敘事與如何重現
- [ ] T-603 錄一段 3 分鐘 demo（提單助理 → 分診 → 偵測器攔截）

---

## 不做清單（要做請先寫 ADR）

見 `CLAUDE.md` 第 8 節。
