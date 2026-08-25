# Prepare — adops-ai-triage 決策記錄

> **版本**：AT-002 · 2026-08-25
> 記錄規則繼承根 `prepare.md`，此處只寫差異。編號前綴 `AT-`。
> 完整規劃書（15 章，含架構圖與資料圖表）：
> https://claude.ai/code/artifact/54e98b0d-f386-412e-a503-45e038ddca39
> 實跑體檢報告（架構 vs 規劃落差、階段、待辦）：
> https://claude.ai/code/artifact/daa19581-5483-475d-a367-f573b1213099

---

## 決策日誌（新的在上）

### AT-002 · 2026-08-25 · v1.0 先推再修
- **決策**（用戶拍板）：帶著已知缺陷推 v1.0 公開 repo，缺陷另開 `fix/` 分支處理
- **棄選**：先修 FIX-1～5 再推（代價：延後約半天）。取捨點是**先有 remote 才有 PR 流程**——
  polyrepo 下沒有 remote 就只能一直在本地 commit，缺陷修完也無處開 PR
- **已知代價**：CI 兩道關卡會紅——關卡 5 資料再現性（`hash()` 未吃 seed）、
  關卡 1 lint（未釘住 ruff 規則集，ruff 0.16 預設新增 UP／DTZ／RUF 等規則後 34 處不合、
  16 檔待 reformat）。後者是版本漂移不是程式錯，修法是補 `pyproject.toml` 定版規則集
- **落地**：`gh repo create aliencat0528/adops-ai-triage --public`，
  `ALLOW_PUSH_MAIN=1` 首推 main ＝ v1.0 初始化

### AT-001 · 2026-08-25 · 以獨立公開 repo 納管（← D-002）
- **落地細節**：本專案原為外部 zip 匯入、完全未版控。補三件才進 git——
  `CLAUDE.md` 首行繼承聲明、`.claude/settings.json`（hooks 轉接）、本檔
- **公開**：作品集用途，招募端要看得到（對照 scorm-notion-clipper／tab-secretary／
  hackathon-radar 走私有，理由是那三個含個人資料或未完成度過高）
- **不套 README 模板基線**：現有 README 的敘事結構優於模板，照根規範應提案改模板而非改差它。
  待討論，暫不動

---

## 待討論

1. **後續路線 A 或 B 未定**——A＝補完 L2／L3–L5 四支 agent（要接 LLM，成本最大）；
   B＝深化敘事（T-206 回放評測 → T-405 回測 → 報告與 demo）。決定的是接下來三四個 PR 的內容
2. **README 是否提案改根模板**（見 AT-001 第三點）
