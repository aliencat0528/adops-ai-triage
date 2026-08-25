# 環境設定

## 1. 解壓縮並開啟

```bash
unzip adops-ai-triage.zip
cd adops-ai-triage
code .                    # 開 VS Code
```

Windows 沒有 unzip 的話，用檔案總管右鍵「解壓縮全部」即可，
然後 VS Code → File → Open Folder → 選這個資料夾。

## 2. 建環境

**macOS / Linux / WSL：**
```bash
make setup
source .venv/bin/activate
make all                  # 生成資料 + xlsx + 分析 + 護欄 + 測試
```

**Windows（沒有 make）：**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

$env:PYTHONPATH="src"
python -m adops_triage.generate_dataset
python -m adops_triage.export_xlsx
python -m adops_triage.analysis.baseline
python -m pytest tests -q
python tools\check_probes_readonly.py src\adops_triage\probes
python tools\check_playbook_refs.py --spec specs\playbook_registry.yaml --src src
python tools\check_taxonomy_drift.py --spec specs\taxonomy.yaml --src src
```

跑完應該看到：
```
✔ 640 筆 × 54 欄 → data/raw/tickets.csv
✔ data/raw/廣告支援需求單.xlsx（4 個工作表，640 筆）
17 passed
✔ 探針唯讀檢查通過
✔ Playbook 引用檢查通過（registry 共 14 個動作，其中 5 個為 recommendation-only）
✔ 分類法契約驗證通過
```

## 順序沒有規定 —— 先開 Claude Code 也可以

上面把「建環境」寫在前面，那是偏好，不是技術上的依賴。兩者可以交換，而且多數情況
**先開 Claude Code 反而更好**：

| 你的情況 | 建議順序 | 理由 |
|---|---|---|
| 想先確認這包東西是好的 | 先 `make all`，再 `claude` | 出錯時你知道是骨架的問題，不是 AI 動過什麼 |
| 想直接開始做事 | 先 `claude`，叫它幫你跑 | 它會自己執行、看懂錯誤訊息、直接修 |
| Windows、沒裝 make | 先 `claude` | 直接說「我在 Windows 沒有 make」，它會給你對應指令 |
| 環境有問題（Python 版本、套件衝突） | 先 `claude` | 它讀得到完整錯誤訊息，比你自己 Google 快 |

唯一真正的先後關係是：**`make data` 要先跑過，`make analyze` 和 `make test` 才有資料可用**。
這個依賴已經寫進 Makefile（`analyze: data`），所以你直接跑 `make analyze` 它會自動先生成資料。

## 3. 啟動 Claude Code

若還沒安裝：
```bash
npm install -g @anthropic-ai/claude-code
```

在 VS Code 的內建終端機（``Ctrl+` `` 或 ``Cmd+` ``）輸入：
```bash
claude
```

第一句話建議這樣說：

> 讀 CLAUDE.md 和 TASKS.md，告訴我目前進度，然後從第一個未打勾的任務開始。
> 動工前先說明這個任務對應核心論證的哪一步。

## 4. 三個自訂指令

`.claude/commands/` 裡已經備好，在 Claude Code 裡直接打：

| 指令 | 用途 |
|---|---|
| `/next-task` | 從 TASKS.md 挑下一個任務，並自動檢查四項前置條件 |
| `/verify-data` | 驗證資料一致性與規劃書引用數字 |
| `/new-detector` | 新增偵測器的完整八步流程 |

## 5. 建議的前三步

1. **先確認環境跑得起來**（上面第 2 步），不要急著寫新程式
2. **打開 `reports/baseline.json` 看一遍**，理解資料在說什麼
3. **從 T-004 開始**（TASKS.md 第一個未打勾的任務）

## 常見問題

**`ModuleNotFoundError: No module named 'adops_triage'`**
→ 忘了設 `PYTHONPATH=src`。Makefile 已經內建，手動跑要自己加。

**`make: command not found`（Windows）**
→ 用上面的 PowerShell 指令，或裝 WSL / Git Bash。

**測試 `test_釐清次數越多處理時數越長` 失敗**
→ 代表資料生成邏輯被改動，因果鏈沒還原出來。這個測試是刻意設計來守護核心論證的，
　　不要為了讓它過而放寬門檻，要回頭檢查生成器改了什麼。
