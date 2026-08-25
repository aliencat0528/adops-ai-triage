# 這些資料要怎麼在 Claude Code 裡用

> 一句話：**資料不用手動搬**。csv 與 xlsx 是給人看與作品集交付用的；
> 開發時資料由 `make data` 現場生成（固定種子，每次結果一樣）。

---

## 1. 檔案各自的用途，不要搞混

| 檔案 | 給誰 | 在 Claude Code 裡要不要用 |
|---|---|---|
| `廣告支援需求單.xlsx` | 人看、作品集交付 | ❌ 不用。它是 `export_xlsx.py` 的產物 |
| `廣告支援需求單.csv` | 丟 BI 工具、給別人跑 | ❌ 不用。開發時用 `data/raw/tickets.csv` |
| `data/raw/tickets.csv` | 程式 | ✅ 由 `make data` 生成，**不要進 git** |
| `reports/baseline.json` | 分析結果 | ✅ 由 `make analyze` 生成，是所有數字的唯一來源 |
| 規劃書 / 圖解 artifact | 設計依據 | ✅ 意見不合時，貼對應章節給它 |
| `deck/*.pptx` | 面試簡報 | ⚠️ 改內容改 `deck/build.js`，別直接改 pptx |

**第一次進專案先跑這個**，資料、xlsx、分析、護欄、測試一次到位：

```bash
make all
```

---

## 2. 大檔案：絕對不要叫它直接讀 csv

640 筆 × 54 欄約 650 KB。叫 Claude Code `Read` 整份 csv 會吃掉大量 context，
之後它就開始忘記前面講過的事。

**❌ 錯誤**

> 幫我讀 data/raw/tickets.csv，分析哪些根因最花工時

**✅ 正確**

> 寫一支 pandas 腳本分析 data/raw/tickets.csv：依 root_cause_category 分組，
> 算工單數、工程工時總和、中位處理時數，依工時排序後印出前五名。
> 只印結果，不要把原始資料印出來。

差別在於：讓它**寫程式去讀**，你和它都只看結果。這個習慣在資料變大後差距會更明顯。

同樣道理，`reports/baseline.json` 只有幾 KB，可以直接讀，那是刻意設計的——
分析腳本已經把 640 筆壓縮成一份摘要。

---

## 3. 常用指令：照情境抄

### 接續開發

```
讀 CLAUDE.md 和 TASKS.md，告訴我目前進度，然後從第一個未打勾的任務開始。
動工前先說明這個任務對應核心論證的哪一步。
```

或直接用內建指令：`/next-task`

### 問資料問題

```
跑 make analyze，然後告訴我：釐清次數與工程工時的關係，在三種組織情境下
有沒有差異？如果有，差在哪裡。用 pandas 算，只給我結論和支撐的數字。
```

### 改欄位設計（最容易出錯的操作）

```
我想在需求單加一個「客戶端配合度」欄位，1-5 分。請同步修改：
1. specs/ticket.schema.json 的欄位定義
2. src/adops_triage/generate_dataset.py 的生成邏輯
3. src/adops_triage/export_xlsx.py 的 FIELDS 欄位字典
改完重跑 make all，測試要全過。
注意 dataset-repro 測試的 hash 會變，記得更新 tests/fixtures/dataset.sha256。
```

**為什麼要講這麼細**：欄位散落在三個檔案，只改一個會靜默不一致。
把三個檔案列出來，它就不會漏。

### 實作某個 agent

```
實作 TASKS.md 的 T-201 提單完整度評分器。
實作前先讀 specs/ticket.schema.json 的 x-completeness-weights，
不要自己定權重。完成後跑 make test 和 make guardrails。
```

### Debug

```
make test 失敗了，錯誤如下：

[貼完整錯誤訊息]

請先判斷是生成器邏輯被改壞，還是測試本身該調整。
不要為了讓測試過就放寬門檻——test_完整度與釐清次數負相關 那條是刻意設計來
守護核心論證的，如果它失敗，代表資料生成邏輯出問題了。
```

### 新增偵測器

`/new-detector`，然後說要做哪一個。指令裡已經寫好八個步驟（含門檻設定理由、
測試涵蓋範圍、Terraform 排程註冊），它會照做。

### 改簡報

```
把精簡版簡報的第 6 頁改成強調「L1 佔 25.3% 工單卻吃 34% 工時」這件事，
其他頁不要動。改 deck/build.js 的 slideFinding2，改完跑 node build.js short，
然後用 soffice 轉 PDF 讓我確認版面。
```

---

## 4. 讓它不要亂改的三道護欄

### 護欄一：不做清單

`CLAUDE.md` 第 8 節列了八項本專案不做的事。如果它提議做其中一項，回它：

```
這在 CLAUDE.md 第 8 節的不做清單裡。如果你認為該推翻，先寫一份 ADR
放到 docs/adr/ 說明為什麼，我看過再決定。
```

### 護欄二：架構檢查

```bash
make guardrails
```

三道靜態檢查：探針唯讀掃描、playbook 引用檢查、分類法漂移檢查。
**每次它改完程式都叫它跑一次**，尤其是動到 `probes/` 或 `agents/` 的時候。

### 護欄三：設計依據

如果它提出跟規劃書衝突的做法，把對應章節貼給它。譬如它想讓 AI 自動調整預算：

```
規劃書 §05 有寫：高風險動作（動預算、出價、刪受眾、改 schema）永遠只建議
不執行，判準是「不可逆 + 後果由客戶承擔 + 錯了要等報表才看得出來」。
請照這個設計走。
```

---

## 5. Context 管理

- **長對話變鈍**時打 `/compact`，它會壓縮前面的內容但保留重點
- **開新對話**時第一句永遠是「讀 CLAUDE.md 和 TASKS.md」，兩份檔案加起來
  約 300 行，讀完它就有完整脈絡
- **不要**在一個對話裡同時做「改資料生成」和「寫簡報」——分兩個對話，
  各自的 context 才乾淨

---

## 6. 三個 artifact 怎麼配合

| Artifact | 什麼時候貼給 Claude Code |
|---|---|
| 規劃書 | 它的做法跟設計衝突時，貼對應章節 |
| 架構圖 | 要它實作某一層時，說明那一層在整體中的位置 |
| 白話版 | 通常用不到，那是給人看的 |

Artifact 是**設計的真實來源**，`specs/` 是**程式的真實來源**。
兩者衝突時以 specs 為準，然後回頭更新 artifact——
因為程式跑得起來，文件不會。

---

## 7. 一個實際的工作循環長怎樣

```bash
$ cd adops-ai-triage && code .
$ claude
```

```
你：讀 CLAUDE.md 和 TASKS.md，告訴我進度

它：目前 Phase 0 完成（T-001~003），T-004 測試已寫但 TASKS.md 沒打勾…
    建議從 T-101 baseline 分析開始，但那支已經實作了。
    要不要從 T-201 提單評分器開始？

你：好，做 T-201。先跟我確認你打算怎麼算完整度分數

它：我會讀 specs/ticket.schema.json 的 x-completeness-weights…

你：對，開始吧

（它寫程式）

你：跑 make test 和 make guardrails

它：17 passed，三道護欄通過

你：把 TASKS.md 的 T-201 打勾，補一句實作摘要
```

重點是**中間那句「先跟我確認你打算怎麼做」**。讓它先講方法再動手，
比事後 review 省事很多。
