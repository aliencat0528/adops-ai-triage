# 作品集簡報

```bash
node build.js short   # 12 頁，面試 5 分鐘用
node build.js full    # 21 頁，作品集網站用
```

兩個版本共用同一份程式，內容改一次兩份都會更新。

## 字型策略

全部使用 Arial。PowerPoint 與 Google Slides 遇到中文字會自動退回系統的中文字型
（Windows 微軟正黑體 / macOS 蘋方），不會出現豆腐格；
而 Arial 在版面檢查時的字寬是可信的，不會誤判溢位。

**不要改成中文字型名稱**（如「微軟正黑體」），那會讓 macOS 使用者看到替代字型，
反而破壞版面。

## 要改內容

改 `build.js` 裡對應的 slideXxx 函式，重跑即可。
所有數字都應該與 `reports/baseline.json` 一致 —— 改資料就要重跑分析並更新這裡。

## 要改風格

檔案最上方的設計 token 區塊：

```js
const INK = "16202B";   // 主色
const ACC = "B84A16";   // 唯一強調色
const F   = "Arial";    // 字型
```

改這幾個值，整份簡報會一起變。
