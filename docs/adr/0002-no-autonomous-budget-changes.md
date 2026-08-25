# ADR-0002 · 高風險動作永遠只建議，不執行

**狀態**：採納 · 2026-08-23

## 背景
技術上可以讓系統自動調整預算、出價、暫停活動。

## 決策
`campaign.adjust_budget`、`campaign.adjust_bid_strategy`、`audience.delete`、
`schema.alter_event_schema`、`account.change_asset_ownership` 一律 `recommendation_only`。

## 理由
判準有三：可逆嗎？誰承擔後果？錯了看得出來嗎？
這五個動作三題全部不及格——不可逆、後果由客戶承擔、且錯誤要等到成效報表出來才看得見。

另有一條非技術理由：支援系統一旦碰投放決策，就越界進入投手的專業範圍，
會同時失去兩邊的信任。守備範圍清楚比功能多更重要。

## 後果
- 系統的「自動化率」上限因此被壓低，這是刻意接受的代價
- 若未來要推翻，必須先證明「錯誤可在 24 小時內被自動偵測並回滾」
