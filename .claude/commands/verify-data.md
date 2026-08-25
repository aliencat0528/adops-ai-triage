---
description: 驗證資料一致性與規劃書引用數字
---
1. 執行 `make data` 重新生成資料，確認 hash 與 `tests/fixtures/dataset.sha256` 一致
2. 執行 `make analyze`，讀 `reports/baseline.json`
3. 執行 `make test`，特別注意 `tests/test_dataset.py` 的因果鏈驗證
4. 檢查是否有任何文件引用了 `reports/baseline.json` 裡沒有的數字——
   規劃書的每個數字都必須來自分析腳本，不得手寫
