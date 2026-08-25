/**
 * AdOps AI Triage — 作品集簡報生成器
 *
 * 輸出兩個版本：
 *   node build.js short  → 12 頁，面試 5 分鐘用
 *   node build.js full   → 21 頁，放作品集網站讓人自己翻
 *
 * 字型策略：全部使用 Arial。
 *   PowerPoint 與 Google Slides 遇到中文字會自動退回系統的中文字型
 *   （Windows 微軟正黑體 / macOS 蘋方），不會出現豆腐格；
 *   而 Arial 在版面檢查時的字寬是可信的，不會誤判溢位。
 */
const pptxgen = require("pptxgenjs");

// ---------------------------------------------------------------- 設計 token
const INK = "16202B";   // 主色，深墨藍灰
const INK_2 = "24313F";
const PAPER = "FFFFFF";
const MIST = "EFF2F5";  // 淺底
const RULE = "D3DBE3";
const MUTED = "5C6B7A";
const ACC = "B84A16";   // 銹橘，全案唯一強調色
const ACC_SOFT = "F6E4DA";
const OK = "2C6E52";
const CRIT = "A93A2E";
const F = "Arial";
const M = "Courier New";

const W = 13.333;
const H = 7.5;
const L = 0.62;          // 左邊界
const R = W - 0.62;      // 右邊界
const CW = R - L;        // 內容寬

let PAGE = 0;
let TOTAL = 0;

// ---------------------------------------------------------------- 版面元件

function pageMark(s, dark) {
  PAGE += 1;
  s.addText(
    [
      { text: String(PAGE).padStart(2, "0"), options: { bold: true } },
      { text: ` / ${String(TOTAL).padStart(2, "0")}`, options: { color: dark ? "6E7F91" : MUTED } },
    ],
    { x: R - 1.2, y: H - 0.62, w: 1.2, h: 0.3, fontFace: M, fontSize: 10,
      color: dark ? "9FB0C0" : MUTED, align: "right", margin: 0 }
  );
}

/** 深色頁：封面、章節、結尾 */
function darkSlide(pres, opts) {
  const s = pres.addSlide();
  s.background = { color: INK };
  if (opts.kicker) {
    s.addText(opts.kicker, {
      x: L, y: opts.kickerY || 1.5, w: CW, h: 0.32, fontFace: M, fontSize: 12,
      color: ACC, bold: true, charSpacing: 2, margin: 0,
    });
  }
  return s;
}

/** 淺色內容頁 */
function contentSlide(pres, chip, title, kicker) {
  const s = pres.addSlide();
  s.background = { color: PAPER };

  // 分類 chip —— 全案重複的視覺母題，呼應「儀表板狀態標籤」
  if (chip) {
    const cw = 0.22 + chip.length * 0.115;
    s.addShape(pres.ShapeType.roundRect, {
      x: L, y: 0.5, w: cw, h: 0.3, fill: { color: ACC_SOFT }, rectRadius: 0.05, line: { color: ACC_SOFT },
    });
    s.addText(chip, {
      x: L, y: 0.5, w: cw, h: 0.3, fontFace: M, fontSize: 10, bold: true,
      color: ACC, align: "center", valign: "middle", margin: 0,
    });
  }
  s.addText(title, {
    x: L, y: 0.92, w: CW, h: 0.62, fontFace: F, fontSize: 30, bold: true,
    color: INK, margin: 0, valign: "middle",
  });
  if (kicker) {
    s.addText(kicker, {
      x: L, y: 1.56, w: CW, h: 0.34, fontFace: F, fontSize: 15,
      color: MUTED, margin: 0, valign: "middle",
    });
  }
  return s;
}

/** 大數字磚 */
function statTile(pres, s, x, y, w, value, label, opts) {
  const o = opts || {};
  const h = o.h || 1.42;
  s.addShape(pres.ShapeType.rect, {
    x, y, w, h, fill: { color: o.fill || MIST }, line: { color: o.fill || MIST },
  });
  s.addText(value, {
    x: x + 0.22, y: y + 0.14, w: w - 0.44, h: 0.66, fontFace: F, fontSize: o.vs || 34,
    bold: true, color: o.color || INK, margin: 0, valign: "middle",
  });
  s.addText(label, {
    x: x + 0.22, y: y + 0.8, w: w - 0.44, h: h - 0.94, fontFace: F, fontSize: 11.5,
    color: o.labelColor || MUTED, margin: 0, valign: "top",
  });
}

/** 內容卡 */
function card(pres, s, x, y, w, h, head, lines, opts) {
  const o = opts || {};
  s.addShape(pres.ShapeType.rect, {
    x, y, w, h, fill: { color: o.fill || MIST }, line: { color: o.line || (o.fill || MIST) },
  });
  if (o.tag) {
    s.addText(o.tag, {
      x: x + 0.24, y: y + 0.2, w: w - 0.48, h: 0.24, fontFace: M, fontSize: 9.5,
      bold: true, color: o.tagColor || ACC, charSpacing: 1, margin: 0,
    });
  }
  s.addText(head, {
    x: x + 0.24, y: y + (o.tag ? 0.46 : 0.22), w: w - 0.48, h: 0.4,
    fontFace: F, fontSize: o.hs || 16, bold: true, color: o.headColor || INK, margin: 0, valign: "middle",
  });
  const body = lines.map((t, i) => ({
    text: t,
    options: { bullet: o.bullet === false ? false : { code: "2022" }, breakLine: i < lines.length - 1 },
  }));
  s.addText(body, {
    x: x + 0.24, y: y + (o.tag ? 0.92 : 0.68), w: w - 0.48, h: h - (o.tag ? 1.12 : 0.88),
    fontFace: F, fontSize: o.bs || 12.5, color: o.bodyColor || INK_2, margin: 0,
    paraSpaceAfter: 5, valign: "top",
  });
}

/** 條列，非卡片 */
function bullets(s, x, y, w, h, lines, opts) {
  const o = opts || {};
  s.addText(
    lines.map((t, i) => ({
      text: t,
      options: { bullet: { code: "2022" }, breakLine: i < lines.length - 1 },
    })),
    { x, y, w, h, fontFace: F, fontSize: o.fs || 14, color: o.color || INK_2,
      margin: 0, paraSpaceAfter: 8, valign: "top" }
  );
}

/** 分隔線 */
function rule(pres, s, x, y, w, color) {
  s.addShape(pres.ShapeType.rect, { x, y, w, h: 0.014, fill: { color: color || RULE }, line: { color: color || RULE } });
}

// ---------------------------------------------------------------- 各頁

function slideCover(pres) {
  const s = darkSlide(pres, {});
  s.addText("SOLUTION DESIGN · 模擬資料專案", {
    x: L, y: 1.62, w: CW, h: 0.32, fontFace: M, fontSize: 12, color: ACC,
    bold: true, charSpacing: 2, margin: 0,
  });
  s.addText("AdOps AI Triage", {
    x: L, y: 2.15, w: CW, h: 1.0, fontFace: F, fontSize: 54, bold: true,
    color: PAPER, margin: 0, valign: "middle",
  });
  s.addText("廣告支援工程需求單的 AI 化設計", {
    x: L, y: 3.18, w: CW, h: 0.55, fontFace: F, fontSize: 24,
    color: "AFC0D0", margin: 0, valign: "middle",
  });
  s.addText("先找出成本結構，再決定該蓋什麼系統", {
    x: L, y: 3.86, w: 8.2, h: 0.4, fontFace: F, fontSize: 15,
    color: "7E90A2", margin: 0, valign: "middle", italic: true,
  });
  rule(pres, s, L, 4.62, CW, "35485C");
  const facts = [
    ["640 筆 × 54 欄", "需求單資料集"],
    ["12.5 個月", "2025-08 ~ 2026-08"],
    ["4 大平台", "Meta · Google · LINE · Feed"],
    ["3 種組織情境", "代理商 · SaaS · 品牌"],
  ];
  facts.forEach((f, i) => {
    const x = L + i * (CW / 4);
    s.addText(f[0], { x, y: 4.86, w: CW / 4 - 0.2, h: 0.36, fontFace: F, fontSize: 17,
      bold: true, color: PAPER, margin: 0, valign: "middle" });
    s.addText(f[1], { x, y: 5.22, w: CW / 4 - 0.2, h: 0.3, fontFace: F, fontSize: 11,
      color: "7E90A2", margin: 0, valign: "middle" });
  });
  s.addText("資料為模擬生成，不含任何真實企業或客戶資料", {
    x: L, y: H - 0.94, w: 8, h: 0.3, fontFace: F, fontSize: 10.5, color: "6E7F91", margin: 0,
  });
  pageMark(s, true);
  s.addNotes("開場一句話：這個專案的起點不是「我想做 AI」，而是「我看不見什麼」。所有資料皆為模擬生成，面試時務必主動說明。");
  return s;
}

function slideConflict(pres) {
  const s = contentSlide(pres, "問題", "我看到的矛盾", "兩邊都覺得自己在等對方");
  card(pres, s, L, 2.25, 5.85, 2.5, "投手說",
    ["RD 都不理我，一個追蹤問題拖三天", "客戶一直問，我沒東西可以回", "每次都要重新解釋一遍背景"],
    { tag: "MEDIA BUYER", bs: 13.5 });
  card(pres, s, L + 6.25, 2.25, 5.85, 2.5, "RD 說",
    ["單子寫得我看不懂，光問清楚就三輪", "說「數字不對」，但沒說哪個帳號、哪個指標", "查完發現不是我方問題"],
    { tag: "ENGINEER", bs: 13.5 });
  s.addShape(pres.ShapeType.rect, { x: L, y: 5.12, w: CW, h: 1.28, fill: { color: INK }, line: { color: INK } });
  s.addText("這種爭論永遠停在感覺層次，因為沒有人握有數字。", {
    x: L + 0.32, y: 5.3, w: CW - 0.64, h: 0.42, fontFace: F, fontSize: 17, bold: true,
    color: PAPER, margin: 0, valign: "middle" });
  s.addText("所以我的第一個問題不是「怎麼解決」，而是「為什麼沒有人能證明誰對」。", {
    x: L + 0.32, y: 5.76, w: CW - 0.64, h: 0.42, fontFace: F, fontSize: 15,
    color: "AFC0D0", margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("這一頁的作用是建立同理，讓聽的人想起自己團隊也有一樣的爭執。不要急著講解法。");
  return s;
}

function slideBlindspot(pres) {
  const s = contentSlide(pres, "問題", "現有工單系統的盲點", "它答得出「多久」，答不出「為什麼」");
  statTile(pres, s, L, 2.34, 3.9, "10.3 小時", "工單中位處理時間\n這是現有系統唯一能給的答案", { vs: 34, h: 2.05 });
  s.addText("？", { x: L + 4.4, y: 2.34, w: 1.1, h: 2.05, fontFace: F, fontSize: 72,
    bold: true, color: ACC, align: "center", valign: "middle", margin: 0 });
  bullets(s, L + 5.8, 2.5, CW - 5.8, 1.9, [
    "這 10.3 小時裡，有多少在真正除錯？",
    "有多少在等對方回訊息？",
    "有多少花在查錯方向？",
  ], { fs: 16.5 });
  rule(pres, s, L, 4.86, CW);
  s.addText("一般工單系統只記三件事", {
    x: L, y: 5.14, w: CW, h: 0.34, fontFace: F, fontSize: 14, bold: true, color: MUTED, margin: 0 });
  const three = ["什麼問題", "誰處理", "多久解決"];
  three.forEach((t, i) => {
    const x = L + i * 2.95;
    s.addShape(pres.ShapeType.rect, { x, y: 5.6, w: 2.65, h: 0.72, fill: { color: MIST }, line: { color: MIST } });
    s.addText(t, { x, y: 5.6, w: 2.65, h: 0.72, fontFace: F, fontSize: 16, bold: true,
      color: INK, align: "center", valign: "middle", margin: 0 });
  });
  s.addText("欄位結構讓「為什麼」這個問題無法被回答 —— 這才是真正的問題。", {
    x: L + 9.15, y: 5.6, w: CW - 9.15, h: 0.72, fontFace: F, fontSize: 13.5, bold: true,
    color: ACC, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("重點：不是工具不好，是欄位設計決定了哪些問題能被回答。這是資料工程的核心觀點。");
  return s;
}

function slideThreeGroups(pres) {
  const s = contentSlide(pres, "資料設計", "所以我補了三組欄位", "設計資料的動機：讓看不見的成本變得可測量");
  const cw2 = (CW - 0.5) / 3;
  card(pres, s, L, 2.28, cw2, 2.35, "提單品質",
    ["完整度分數 0–100", "缺漏欄位清單", "來回釐清次數"],
    { tag: "GROUP F", bs: 13 });
  card(pres, s, L + cw2 + 0.25, 2.28, cw2, 2.35, "根因分類",
    ["根因大類 11 種", "修復責任方", "90 天復發標記"],
    { tag: "GROUP G", bs: 13 });
  card(pres, s, L + (cw2 + 0.25) * 2, 2.28, cw2, 2.35, "可預防性",
    ["AI 自動化分級 L0–L4", "可否主動偵測", "建議偵測訊號"],
    { tag: "GROUP H", bs: 13 });
  const qa = [
    ["時間到底花在哪？", "→ 提單助理（把成本擋在入口）"],
    ["問題出在誰身上？", "→ 主動偵測器（Shift-Left）"],
    ["哪些不該變成工單？", "→ 知識檢索與回寫迴圈"],
  ];
  s.addText("每組欄位回答一個問題，每個答案直接對應一個系統設計決策", {
    x: L, y: 4.86, w: CW, h: 0.32, fontFace: F, fontSize: 13.5, bold: true, color: MUTED, margin: 0 });
  qa.forEach((q, i) => {
    const y = 5.26 + i * 0.44;
    s.addText(q[0], { x: L, y, w: 4.2, h: 0.38, fontFace: F, fontSize: 14, bold: true,
      color: INK, margin: 0, valign: "middle" });
    s.addText(q[1], { x: L + 4.3, y, w: CW - 4.3, h: 0.38, fontFace: F, fontSize: 14,
      color: ACC, margin: 0, valign: "middle" });
  });
  pageMark(s, false);
  s.addNotes("順序很重要：不是先想做 AI，是先讓成本結構可見，再讓資料指出該蓋什麼。這是整份簡報的論證核心。");
  return s;
}

function slideFinding1(pres) {
  const s = contentSlide(pres, "發現 01", "釐清次數是成本放大器", "每多問一次，代價 22.2%");
  s.addChart(
    pres.ChartType.bar,
    [{ name: "中位處理時數", labels: ["0 次", "1 次", "2 次", "3 次", "4 次", "5 次"],
       values: [6.4, 7.9, 11.4, 12.4, 17.1, 19.1] }],
    { x: L, y: 2.22, w: 7.5, h: 3.55,
      barDir: "col", chartColors: [ACC], barGapWidthPct: 55,
      showTitle: false, showLegend: false,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
      dataLabelColor: INK, dataLabelFontFace: F, dataLabelFormatCode: '0.0"h"',
      catAxisLabelColor: MUTED, catAxisLabelFontSize: 11, catAxisLabelFontFace: F,
      catGridLine: { style: "none" },
      valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, valAxisLabelFontFace: F,
      valGridLine: { color: RULE, size: 0.5 },
      valAxisMinVal: 0, valAxisMaxVal: 22, valAxisMajorUnit: 5,
      catAxisTitle: "來回釐清次數", showCatAxisTitle: true,
      catAxisTitleColor: MUTED, catAxisTitleFontSize: 11, catAxisTitleFontFace: F,
    }
  );
  const st = [
    ["+22.2%", "每多一次釐清\n處理時數增加"],
    ["-0.727", "完整度與釐清次數\n相關係數"],
    ["9.4%", "只有這麼多工單\n一次到位"],
  ];
  st.forEach((t, i) => {
    statTile(pres, s, L + 7.9, 2.22 + i * 1.22, CW - 7.9, t[0], t[1],
      { vs: 26, h: 1.06, color: i === 0 ? ACC : INK });
  });
  s.addText("滿意度同步下滑：釐清 0 次 4.39 分 → 釐清 5 次 3.10 分。每一次「請問你說的是哪個帳號」，同時在燒工程時數和客戶耐心。", {
    x: L, y: 5.95, w: CW, h: 0.5, fontFace: F, fontSize: 13, color: INK_2, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("這是全簡報最重要的一張圖。對數迴歸係數 0.2002，換算每次釐清 +22.2%。相關係數 -0.727 是全資料集最強的關聯。");
  return s;
}

function slideFinding2(pres) {
  const s = contentSlide(pres, "發現 02", "最貴的不是難題，是講不清楚的題", "違反直覺的一筆數字");
  s.addChart(
    pres.ChartType.bar,
    [
      { name: "佔工單量", labels: ["L0 人工", "L1 分診補件", "L2 自助回覆", "L3 自動診斷", "L4 自動修復"],
        values: [19.8, 25.3, 19.2, 28.3, 7.3] },
      { name: "佔工程時數", labels: ["L0 人工", "L1 分診補件", "L2 自助回覆", "L3 自動診斷", "L4 自動修復"],
        values: [22.4, 34.0, 7.0, 27.3, 9.3] },
    ],
    { x: L, y: 2.22, w: 7.8, h: 3.5,
      barDir: "col", chartColors: [MUTED, ACC], barGapWidthPct: 45,
      showTitle: false, showLegend: true, legendPos: "t", legendColor: MUTED,
      legendFontSize: 11, legendFontFace: F,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9.5,
      dataLabelColor: INK, dataLabelFontFace: F, dataLabelFormatCode: '0.0"%"',
      catAxisLabelColor: MUTED, catAxisLabelFontSize: 10.5, catAxisLabelFontFace: F,
      catGridLine: { style: "none" },
      valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, valAxisLabelFontFace: F,
      valGridLine: { color: RULE, size: 0.5 },
      valAxisMinVal: 0, valAxisMaxVal: 40, valAxisMajorUnit: 10,
    }
  );
  card(pres, s, L + 8.2, 2.22, CW - 8.2, 1.65, "L1 只佔 25.3% 的量",
    ["卻吃掉 34.0% 的工程時數", "是所有分級中最高"], { tag: "反直覺", bs: 12.5, hs: 15 });
  card(pres, s, L + 8.2, 4.05, CW - 8.2, 1.67, "中位 15.4 小時",
    ["比真正需要人工深度介入", "的 L0（12.1 小時）還久"], { tag: "更反直覺", bs: 12.5, hs: 15 });
  s.addShape(pres.ShapeType.rect, { x: L, y: 5.95, w: CW, h: 0.72, fill: { color: INK }, line: { color: INK } });
  s.addText("如果只能做一件事，做提單助理，不做診斷 Agent —— 診斷再聰明，也救不了一張「客戶說數字不對，很急」的單。", {
    x: L + 0.32, y: 5.95, w: CW - 0.64, h: 0.72, fontFace: F, fontSize: 15, bold: true,
    color: PAPER, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("這一頁是「資料反推系統設計」最有說服力的證據：直覺會告訴你先做診斷，資料說先做入口。");
  return s;
}

function slideFinding3(pres) {
  const s = contentSlide(pres, "發現 03", "近半數工單可以在發生前攔截", "48.9% 標註為可預防");
  const rows = [
    ["Changelog 監控", "平台變更公告 × 客戶使用參數", "101 單", "810 小時"],
    ["Feed 健檢", "Feed 值 vs 到達頁逐項比對", "52 單", "321 小時"],
    ["Tag 巡檢", "每日爬頁比對觸發指紋", "47 單", "253 小時"],
    ["憑證到期預警", "Token 到期日與 API 錯誤率", "35 單", "192 小時"],
    ["GTM 發布哨兵", "容器發布後自動回歸測試", "30 單", "151 小時"],
  ];
  s.addTable(
    [[
      { text: "偵測器", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "訊號來源", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "可攔截", options: { bold: true, color: MUTED, fontSize: 11, align: "right" } },
      { text: "對應工時", options: { bold: true, color: MUTED, fontSize: 11, align: "right" } },
    ]].concat(rows.map((r, i) => [
      { text: r[0], options: { bold: true, color: INK, fontSize: 12.5 } },
      { text: r[1], options: { color: INK_2, fontSize: 12 } },
      { text: r[2], options: { color: INK, fontSize: 12.5, align: "right", fontFace: M } },
      { text: r[3], options: { color: i === 0 ? ACC : INK, bold: i === 0, fontSize: 12.5, align: "right", fontFace: M } },
    ])),
    { x: L, y: 2.3, w: 8.5, colW: [2.1, 3.7, 1.2, 1.5],
      rowH: 0.46, fontFace: F, border: { type: "solid", color: RULE, pt: 0.5 },
      fill: { color: PAPER }, valign: "middle", margin: [4, 8, 4, 8] }
  );
  statTile(pres, s, L + 8.9, 2.3, CW - 8.9, "48.9%", "工單標註為可預防\n另有 15.9% 部分可預防", { vs: 40, h: 1.6, color: ACC, fill: ACC_SOFT });
  card(pres, s, L + 8.9, 4.06, CW - 8.9, 1.5, "共同點",
    ["問題發生時系統知道", "只是沒有人在看"], { bs: 12.5, hs: 15 });
  s.addText("Changelog 監控單獨一項就對應 810 小時 —— 因為它攔截的正是「API 不報錯但回空值」的靜默失敗。", {
    x: L, y: 5.9, w: CW, h: 0.44, fontFace: F, fontSize: 13, color: INK_2, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("2026-01-12 Meta 移除 7d_view/28d_view，API 回空值不報錯，轉換數掉 15-40%，很多團隊查了兩天才發現。這就是靜默失敗。");
  return s;
}

function slideFourTypes(pres) {
  const s = contentSlide(pres, "設計原則", "AI 介入的四種型態", "「取代人做的事」和「讓事情不發生」是兩件事");
  const cw2 = (CW - 0.4) / 2;
  const ch = 1.55;
  card(pres, s, L, 2.28, cw2, ch, "替代型　Substitution",
    ["同一條流程，人做的動作換 AI 做", "流程形狀不變，單位成本下降"], { tag: "形狀不變", bs: 12.5, hs: 15 });
  card(pres, s, L + cw2 + 0.4, 2.28, cw2, ch, "預防型　Prevention",
    ["改變流程本身，讓工單不產生", "工單總量下降"],
    { tag: "形狀改變", bs: 12.5, hs: 15, fill: ACC_SOFT, tagColor: ACC });
  card(pres, s, L, 2.28 + ch + 0.28, cw2, ch, "增強型　Augmentation",
    ["人仍在流程中，但 AI 給更好的輸入", "決策品質與速度提升"], { tag: "形狀不變", bs: 12.5, hs: 15 });
  card(pres, s, L + cw2 + 0.4, 2.28 + ch + 0.28, cw2, ch, "複利型　Compounding",
    ["系統從每次結案學習", "前三型的覆蓋率隨時間上升"],
    { tag: "自我改變", bs: 12.5, hs: 15, fill: ACC_SOFT, tagColor: ACC });
  s.addShape(pres.ShapeType.rect, { x: L, y: 5.98, w: CW, h: 0.74, fill: { color: INK }, line: { color: INK } });
  s.addText("權重刻意不平均：預防型（48.9% 可預防）與替代型的入口（34.0% 工時）是主戰場。若資源只夠做兩型，做這兩型。", {
    x: L + 0.32, y: 5.98, w: CW - 0.64, h: 0.74, fontFace: F, fontSize: 14.5, bold: true,
    color: PAPER, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("面試常見追問：那增強型和複利型不重要嗎？答：複利型不直接產生效益，但它決定前三型三年後還有沒有效。");
  return s;
}

function slideArch(pres) {
  const s = darkSlide(pres, {});
  s.addText("系統架構", {
    x: L, y: 0.55, w: CW, h: 0.5, fontFace: F, fontSize: 28, bold: true, color: PAPER, margin: 0, valign: "middle" });
  s.addText("七層，以及一條把整套系統分成兩半的紅線", {
    x: L, y: 1.08, w: CW, h: 0.34, fontFace: F, fontSize: 14, color: "8FA2B4", margin: 0, valign: "middle" });

  const layers = [
    ["L0", "感知層", "六個主動偵測器 · 在開單之前攔截", false],
    ["L1", "受理層", "提單助理 · 完整度評分 · 自動補件", false],
    ["L2", "分診層", "規則優先 · 相似單檢索 · 影響面計算", false],
    ["L3", "診斷層", "七支唯讀探針 · Top-3 根因假設", false],
    ["L4", "處置層", "受控執行 · 允許清單 · 三級風險閘門", true],
    ["L5", "驗證層", "重跑原始檢測 · soak 期 · 未過退回", true],
    ["L6", "學習層", "知識回寫 · 根因聚類 · 提案新偵測器", true],
  ];
  const top = 1.66;
  const rh = 0.48;
  const gap = 0.10;
  const split = 0.60;          // L3 與 L4 之間留給紅線的空間
  layers.forEach((ly, i) => {
    const y = top + i * (rh + gap) + (i >= 4 ? split : 0);
    s.addShape(pres.ShapeType.rect, {
      x: L, y, w: 9.4, h: rh,
      fill: { color: ly[3] ? "31241C" : INK_2 }, line: { color: ly[3] ? "5A3A25" : "31414F" },
    });
    s.addText(ly[0], { x: L + 0.22, y, w: 0.6, h: rh, fontFace: M, fontSize: 13, bold: true,
      color: ACC, margin: 0, valign: "middle" });
    s.addText(ly[1], { x: L + 0.88, y, w: 1.5, h: rh, fontFace: F, fontSize: 14, bold: true,
      color: PAPER, margin: 0, valign: "middle" });
    s.addText(ly[2], { x: L + 2.5, y, w: 6.7, h: rh, fontFace: F, fontSize: 12,
      color: "9FB0C0", margin: 0, valign: "middle" });
  });
  // 唯讀 / 寫入 紅線 —— 放在 L3 底部與 L4 頂部之間的空隙裡
  const l3Bottom = top + 3 * (rh + gap) + rh;
  s.addText("以上唯讀，錯了最多是誤報　　以下會寫入，每個動作都必須來自允許清單", {
    x: L, y: l3Bottom + 0.08, w: 9.4, h: 0.24, fontFace: F, fontSize: 10.5, bold: true,
    color: ACC, margin: 0, align: "center", valign: "middle" });
  s.addShape(pres.ShapeType.rect, {
    x: L, y: l3Bottom + 0.4, w: 9.4, h: 0.02, fill: { color: ACC }, line: { color: ACC } });

  const right = L + 9.85;
  const rw = CW - 9.85;
  s.addText("六個 Agent · 模型路由", { x: right, y: top - 0.06, w: rw, h: 0.32, fontFace: F,
    fontSize: 13, bold: true, color: PAPER, margin: 0 });
  const agents = [
    ["提單助理", "Haiku"], ["分診", "Haiku + 規則"], ["檢索回覆", "Sonnet"],
    ["診斷", "Opus"], ["修復規劃", "Sonnet"], ["驗證回寫", "Sonnet"],
  ];
  agents.forEach((a, i) => {
    const y = top + 0.44 + i * 0.42;
    s.addText(a[0], { x: right, y, w: rw * 0.52, h: 0.36, fontFace: F, fontSize: 12,
      color: "C9D6E2", margin: 0, valign: "middle" });
    s.addText(a[1], { x: right + rw * 0.52, y, w: rw * 0.48, h: 0.36, fontFace: M, fontSize: 10.5,
      color: a[1] === "Opus" ? ACC : "7E90A2", bold: a[1] === "Opus", margin: 0, valign: "middle", align: "right" });
  });
  s.addText("全案只有診斷 Agent 值得用最強模型。其他若需升級，先檢查是不是 prompt 或 schema 設計有問題。", {
    x: right, y: top + 3.15, w: rw, h: 0.9, fontFace: F, fontSize: 11.5, color: "7E90A2",
    margin: 0, valign: "top" });
  s.addText("L6 學到的規則回饋成 L0 的新偵測器 —— 這條迴圈是系統越用越省的原因。", {
    x: L, y: 6.44, w: 9.4, h: 0.34, fontFace: F, fontSize: 12, color: ACC, margin: 0, valign: "middle" });
  pageMark(s, true);
  s.addNotes("紅線是這頁的重點。L0-L3 唯讀所以可以放心讓 AI 全權；L4 以下會寫入，所以要允許清單加風險分級。");
  return s;
}

function slideBoundary(pres) {
  const s = contentSlide(pres, "人機邊界", "畫線，然後反駁自己", "三道判準，以及三個把自己的判準拆開來檢查的問題");
  const jud = ["可逆嗎？", "誰承擔後果？", "錯了看得出來嗎？"];
  jud.forEach((t, i) => {
    const x = L + i * 2.55;
    s.addShape(pres.ShapeType.rect, { x, y: 2.24, w: 2.3, h: 0.56, fill: { color: INK }, line: { color: INK } });
    s.addText(t, { x, y: 2.24, w: 2.3, h: 0.56, fontFace: F, fontSize: 14, bold: true,
      color: PAPER, align: "center", valign: "middle", margin: 0 });
  });
  s.addText("三題有任何一題不及格 → 人決策", {
    x: L + 7.9, y: 2.24, w: CW - 7.9, h: 0.56, fontFace: F, fontSize: 13.5, bold: true,
    color: ACC, margin: 0, valign: "middle" });

  const cw3 = (CW - 0.5) / 3;
  card(pres, s, L, 3.1, cw3, 2.35, "把「做不到」偽裝成「不該做」？",
    ["中風險只要單人核准，理由是可逆", "但回退期間的資料缺口不可逆", "→ 延長 soak 期並顯示缺口量"],
    { tag: "檢驗一", bs: 12, hs: 14 });
  card(pres, s, L + cw3 + 0.25, 3.1, cw3, 2.35, "人是在決策還是按核准鍵？",
    ["核准通過率長期 >95% 等於橡皮圖章", "護欄是假的，只是轉嫁責任", "→ 把通過率列為監控指標"],
    { tag: "檢驗二", bs: 12, hs: 14, fill: ACC_SOFT });
  card(pres, s, L + (cw3 + 0.25) * 2, 3.1, cw3, 2.35, "失敗時誰知道、多久知道？",
    ["AI 擋錯單、分錯類都是靜默失敗", "沒人發現比做錯更危險", "→ 影子佇列每日人工掃描"],
    { tag: "檢驗三", bs: 12, hs: 14 });

  s.addShape(pres.ShapeType.rect, { x: L, y: 5.72, w: CW, h: 0.78, fill: { color: INK }, line: { color: INK } });
  s.addText("高風險動作 —— 動預算、改出價、刪除受眾、變更 schema —— 永遠只建議，不執行。", {
    x: L + 0.32, y: 5.72, w: CW - 0.64, h: 0.78, fontFace: F, fontSize: 15.5, bold: true,
    color: PAPER, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("檢驗一和檢驗二實際上導出了架構修正，不是事後補的說法。面試時可以強調：我對自己的設計做了反駁。");
  return s;
}

function slideCounter(pres) {
  const s = contentSlide(pres, "誠實度", "兩個推翻我自己假設的發現", "如果資料只用來證實既有想法，就不需要蒐集資料");
  const cw2 = (CW - 0.4) / 2;
  card(pres, s, L, 2.28, cw2, 2.7, "「越急越講不清楚」只部分成立",
    ["P0 急件完整度 50，四級中最低",
     "但 P3 排程單也只有 52，P1 反而最高（59）",
     "低完整度有兩種成因：急件來不及寫、低優先級懶得寫",
     "→ 護欄必須分開設計，不能一套打天下"],
    { tag: "反例 A", bs: 12.5, hs: 15 });
  card(pres, s, L + cw2 + 0.4, 2.28, cw2, 2.7, "重複工單根本不是問題",
    ["重複單率僅 1.1%",
     "原本假設的「重複提問浪費」不成立",
     "→ 重複單偵測在架構中降級為次要功能",
     "→ 資源全部集中在釐清成本"],
    { tag: "反例 B", bs: 12.5, hs: 15 });
  rule(pres, s, L, 5.3, CW);
  s.addText("同樣的誠實：拒絕業界常見的效益灌水算法", {
    x: L, y: 5.5, w: CW, h: 0.34, fontFace: F, fontSize: 14, bold: true, color: INK, margin: 0, valign: "middle" });
  bullets(s, L, 5.88, CW, 0.9, [
    "多數廠商把 deflection（客戶放棄詢問）計入 resolution（問題真的被解決），本專案明確區分兩者",
    "不引用任何外部「AI 解決率」基準，只用自己資料算出的上限，並標明是理論天花板",
  ], { fs: 12.5 });
  pageMark(s, false);
  s.addNotes("這頁通常最能引出好問題。準備好回答：那你怎麼知道自己沒有在挑對自己有利的數字？答：因為兩個反例都寫進去了。");
  return s;
}

function slideDeliver(pres) {
  const s = darkSlide(pres, {});
  s.addText("交付與亮點", {
    x: L, y: 0.62, w: CW, h: 0.6, fontFace: F, fontSize: 32, bold: true, color: PAPER, margin: 0, valign: "middle" });
  s.addText("規劃不是終點，是開發的起點", {
    x: L, y: 1.24, w: CW, h: 0.34, fontFace: F, fontSize: 15, color: "8FA2B4", margin: 0, valign: "middle" });

  const tiles = [
    ["1,743 小時", "可回收工程時數上限\n佔總工時 53.0%"],
    ["17 個測試", "含因果鏈驗證\n資料還原不出關聯就 CI 紅燈"],
    ["3 道 CI 護欄", "探針唯讀掃描 · 允許清單檢查\n分類法漂移檢查"],
    ["60 個任務", "六階段編號 backlog\n解壓縮就能接著開發"],
  ];
  tiles.forEach((t, i) => {
    const x = L + i * ((CW + 0.3) / 4);
    const w = (CW + 0.3) / 4 - 0.3;
    s.addShape(pres.ShapeType.rect, { x, y: 2.0, w, h: 1.6, fill: { color: INK_2 }, line: { color: "31414F" } });
    s.addText(t[0], { x: x + 0.2, y: 2.16, w: w - 0.4, h: 0.5, fontFace: F, fontSize: 22,
      bold: true, color: i === 0 ? ACC : PAPER, margin: 0, valign: "middle" });
    s.addText(t[1], { x: x + 0.2, y: 2.7, w: w - 0.4, h: 0.8, fontFace: F, fontSize: 11,
      color: "8FA2B4", margin: 0, valign: "top" });
  });

  s.addText("這個專案想證明的三件事", {
    x: L, y: 3.92, w: CW, h: 0.34, fontFace: F, fontSize: 14, bold: true, color: ACC, margin: 0, valign: "middle" });
  const pts = [
    ["從資料反推系統，不是從技術反推需求", "「L1 只佔 25.3% 工單卻吃掉 34% 工時」直接決定了投資順序"],
    ["安全設計是架構的一部分，不是附加條款", "唯讀邊界、允許清單、風險閘門，每條都對應一個具體失敗模式"],
    ["規劃書與程式共用同一份 spec", "分類法與動作清單抽成 YAML，文件與實作不會不同步"],
  ];
  pts.forEach((p, i) => {
    const y = 4.34 + i * 0.72;
    s.addText(String(i + 1).padStart(2, "0"), { x: L, y, w: 0.5, h: 0.62, fontFace: M, fontSize: 13,
      bold: true, color: ACC, margin: 0, valign: "middle" });
    s.addText(p[0], { x: L + 0.6, y: y + 0.02, w: 6.3, h: 0.3, fontFace: F, fontSize: 14,
      bold: true, color: PAPER, margin: 0, valign: "middle" });
    s.addText(p[1], { x: L + 0.6, y: y + 0.32, w: CW - 0.6, h: 0.28, fontFace: F, fontSize: 11.5,
      color: "8FA2B4", margin: 0, valign: "middle" });
  });
  s.addText("資料為模擬生成，不含任何真實企業或客戶資料", {
    x: L, y: H - 0.94, w: 8, h: 0.3, fontFace: F, fontSize: 10.5, color: "6E7F91", margin: 0 });
  pageMark(s, true);
  s.addNotes("收尾一句：這份規劃附帶一包可以直接開工的專案骨架，解壓縮、開 VS Code 就能接著做。");
  return s;
}

// ---------------------------------------------------------------- 完整版加頁

function slideDataDesign(pres) {
  const s = contentSlide(pres, "資料設計", "50 欄位，八個群組", "每個欄位都是為了回答一個特定問題而存在");
  const rows = [
    ["A 工單識別", "5", "工單編號 · 提單時間 · 組織情境 · 提單人角色", "三種公司型態可切片比較"],
    ["B 客戶脈絡", "4", "客戶品牌 · 產業別 · SLA 等級 · 建站平台", "建站平台直接決定根因分布"],
    ["C 問題描述", "6", "大類 · 細類 · 標題 · 自由文字 · 平台 · 資產 ID", "分診模型的輸入與評測基準"],
    ["D 技術上下文", "4", "追蹤方式 · 環境 · 可重現性 · 發生起始", "決定要跑哪一支診斷探針"],
    ["E 影響量化", "9", "嚴重度 · 優先級 · 日花費 · 指標前後值", "讓「省下多少錢」可被算出來"],
    ["F 提單品質", "7", "完整度分數 · 缺漏欄位 · 釐清次數 · 重複單", "全案最關鍵，成本放大器在這"],
    ["G 處理與根因", "13", "根因 · 處理方式 · 時數 · 重啟 · 復發 · CSAT", "判斷哪些能被預防的依據"],
    ["H AI 標註", "4", "AI 分級 L0–L4 · 可否預防 · 偵測訊號", "規劃層標註，餵給機會分析"],
  ];
  s.addTable(
    [[
      { text: "群組", options: { bold: true, color: MUTED, fontSize: 10.5 } },
      { text: "欄", options: { bold: true, color: MUTED, fontSize: 10.5, align: "center" } },
      { text: "代表欄位", options: { bold: true, color: MUTED, fontSize: 10.5 } },
      { text: "設計理由", options: { bold: true, color: MUTED, fontSize: 10.5 } },
    ]].concat(rows.map((r) => {
      const hot = r[0].startsWith("F");
      return [
        { text: r[0], options: { bold: true, color: hot ? ACC : INK, fontSize: 11.5 } },
        { text: r[1], options: { color: INK, fontSize: 11.5, align: "center", fontFace: M } },
        { text: r[2], options: { color: INK_2, fontSize: 11 } },
        { text: r[3], options: { color: hot ? ACC : MUTED, bold: hot, fontSize: 11 } },
      ];
    })),
    { x: L, y: 2.24, w: CW, colW: [1.75, 0.6, 5.15, 4.6],
      rowH: 0.44, fontFace: F, border: { type: "solid", color: RULE, pt: 0.5 },
      fill: { color: PAPER }, valign: "middle", margin: [3, 8, 3, 8] }
  );
  s.addText("核心因果鏈：資訊完整度 ↓ → 釐清次數 ↑ → 處理時數 ×(1 + 0.38 × 釐清次數) → 滿意度 ↓", {
    x: L, y: 6.24, w: CW, h: 0.42, fontFace: F, fontSize: 13, bold: true, color: INK, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("這條鏈是刻意寫進生成器的，後面的分析實際上是在驗證這條鏈能不能被資料本身還原出來。");
  return s;
}

function slideAnchors(pres) {
  const s = contentSlide(pres, "資料設計", "錨定在 2026 年真實平台事件上", "與其全部虛構，不如讓資料有可驗證的骨架");
  const items = [
    ["2026-01-12", "Meta 移除 7d_view / 28d_view 歸因視窗",
     "API 回空值而非報錯，第三方工具收到空白卻無告警",
     "26 張工單 · 中位處理 17.1 小時 · 完整度僅 45"],
    ["2026-06-15", "Google Signals 不再控管 GA4 → Ads 資料流",
     "ad_storage 成為唯一閘門，雙向故障：受眾歸零或超收",
     "22 張工單 · 中位處理 29.4 小時 · 完整度僅 47"],
    ["全年 · 檔期放大", "Merchant Center 價格庫存與到達頁不符",
     "爬蟲比對 feed 值與到達頁，2026 年第一大拒登原因",
     "Feed 類工單最大宗 · 根因指向上游 ERP / OMS"],
  ];
  items.forEach((it, i) => {
    const y = 2.24 + i * 1.28;
    s.addShape(pres.ShapeType.rect, { x: L, y, w: CW, h: 1.12, fill: { color: MIST }, line: { color: MIST } });
    s.addText(it[0], { x: L + 0.24, y: y + 0.14, w: 2.1, h: 0.32, fontFace: M, fontSize: 11.5,
      bold: true, color: ACC, margin: 0, valign: "middle" });
    s.addText(it[1], { x: L + 2.5, y: y + 0.12, w: CW - 2.8, h: 0.36, fontFace: F, fontSize: 14.5,
      bold: true, color: INK, margin: 0, valign: "middle" });
    s.addText(it[2], { x: L + 2.5, y: y + 0.5, w: CW - 2.8, h: 0.28, fontFace: F, fontSize: 12,
      color: INK_2, margin: 0, valign: "middle" });
    s.addText(it[3], { x: L + 2.5, y: y + 0.78, w: CW - 2.8, h: 0.28, fontFace: F, fontSize: 11.5,
      color: MUTED, margin: 0, valign: "middle" });
  });
  s.addShape(pres.ShapeType.rect, { x: L, y: 6.16, w: CW, h: 0.72, fill: { color: INK }, line: { color: INK } });
  s.addText("這些工單的完整度只有 45–47（全體中位 56），處理時數卻是基準的 1.7–2.9 倍 —— 靜默失敗的典型特徵。", {
    x: L + 0.32, y: 6.16, w: CW - 0.64, h: 0.72, fontFace: F, fontSize: 14, bold: true,
    color: PAPER, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("面試時可以說：這三個尖峰不是我編的，是 2026 年真實發生的平台變更，而偵測層第一條規則就是為了接住它們。");
  return s;
}

function slideSubstitution(pres) {
  const s = contentSlide(pres, "替代型", "AI 直接接手的人為動作", "同一條流程，把人做的動作換成 AI 做");
  const rows = [
    ["手動填寫工單、被追問補資料", "Intake Agent 結構化抽取 + 動態必填", "L1", "釐清 2.27 次／單"],
    ["判斷這單屬於哪類、該給誰", "規則引擎 + few-shot 分類與路由", "L2", "轉單率 3.3%"],
    ["翻文件回答重複問題", "Retrieval Agent 附引用回覆", "L3", "教育說明 26.9%"],
    ["登入各平台後台截圖比對", "七支唯讀探針自動取數", "L3", "缺附件工單 27.0%"],
    ["手動重推 feed、重試 API、續期 token", "L4 低風險自動修復", "L4", "L4 級工單 7.3%"],
    ["手動爬客戶網站抓商品、產 feed", "商品資料管線（見下一頁）", "P", "Feed 類工單最大宗"],
  ];
  s.addTable(
    [[
      { text: "原本人在做什麼", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "換成什麼", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "層", options: { bold: true, color: MUTED, fontSize: 11, align: "center" } },
      { text: "資料佐證", options: { bold: true, color: MUTED, fontSize: 11 } },
    ]].concat(rows.map((r, i) => {
      const hot = i === rows.length - 1;
      return [
        { text: r[0], options: { color: INK, fontSize: 12, bold: hot } },
        { text: r[1], options: { color: hot ? ACC : INK_2, fontSize: 12, bold: hot } },
        { text: r[2], options: { color: MUTED, fontSize: 11, align: "center", fontFace: M } },
        { text: r[3], options: { color: MUTED, fontSize: 11 } },
      ];
    })),
    { x: L, y: 2.3, w: CW, colW: [4.0, 4.3, 0.7, 3.1],
      rowH: 0.5, fontFace: F, border: { type: "solid", color: RULE, pt: 0.5 },
      fill: { color: PAPER }, valign: "middle", margin: [4, 8, 4, 8] }
  );
  s.addText("最後一列是我過往實際做過的類型：把人為爬資料與產 feed 自動化。它不是這套系統的附屬功能，而是另一條完整產線。", {
    x: L, y: 6.1, w: CW, h: 0.5, fontFace: F, fontSize: 13, color: INK_2, margin: 0, valign: "middle" });
  pageMark(s, false);
  return s;
}

function slidePipeline(pres) {
  const s = contentSlide(pres, "商品資料管線", "把人為爬資料與產 feed 自動化", "這條產線的 AI 化屬於典型的替代型");
  const steps = ["爬取", "抽取", "正規化", "品質檢核", "Feed 產製", "多平台適配"];
  const sw = (CW - 5 * 0.18) / 6;
  steps.forEach((t, i) => {
    const x = L + i * (sw + 0.18);
    s.addShape(pres.ShapeType.rect, { x, y: 2.3, w: sw, h: 0.6, fill: { color: INK }, line: { color: INK } });
    s.addText(t, { x, y: 2.3, w: sw, h: 0.6, fontFace: F, fontSize: 13.5, bold: true,
      color: PAPER, align: "center", valign: "middle", margin: 0 });
    if (i < 5) {
      s.addText("→", { x: x + sw, y: 2.3, w: 0.18, h: 0.6, fontFace: F, fontSize: 12,
        color: MUTED, align: "center", valign: "middle", margin: 0 });
    }
  });
  const ai = [
    ["站點結構自動判讀", "免逐站寫規則"],
    ["JSON-LD 優先，LLM 後備", "selector 失效自動重新定位"],
    ["品類對映各平台分類樹", "品牌正規化 · 同商品合併"],
    ["價格異常偵測", "政策風險預判，拒登前先攔"],
    ["標題描述改寫符合規格", "差異更新，只推變動商品"],
    ["各平台欄位規格自動對映", "拒登原因回讀自動修正"],
  ];
  ai.forEach((a, i) => {
    const x = L + i * (sw + 0.18);
    s.addText(a[0], { x, y: 3.02, w: sw, h: 0.6, fontFace: F, fontSize: 10.5,
      color: ACC, margin: 0, valign: "top" });
    s.addText(a[1], { x, y: 3.58, w: sw, h: 0.6, fontFace: F, fontSize: 10.5,
      color: MUTED, margin: 0, valign: "top" });
  });
  s.addText("AI 介入點", { x: L, y: 2.98, w: CW, h: 0.001, fontFace: M, fontSize: 1, color: PAPER, margin: 0 });

  card(pres, s, L, 4.36, CW / 2 - 0.2, 1.86, "最有價值的不是生成文案",
    ["是抽取層的自我修復",
     "傳統爬蟲靠人維護 selector，客戶網站一改版就整批失效",
     "改成 JSON-LD 優先加 LLM 後備，改版從故障變成一次人審"],
    { tag: "關鍵洞察", bs: 11.5, hs: 14, fill: ACC_SOFT });
  card(pres, s, L + CW / 2 + 0.2, 4.36, CW / 2 - 0.2, 1.86, "三個人工閘門",
    ["新 selector 上線前人審",
     "價格異常超過門檻停推",
     "文案改寫首次上線抽審"],
    { tag: "人在哪裡", bs: 11.5, hs: 14 });
  s.addText("與工單系統的銜接：品質檢核結果直接成為 Feed 健檢偵測器的訊號源，不必等客戶投訴。兩套系統共用「商品資料的真實狀態」這個底座。", {
    x: L, y: 6.42, w: CW, h: 0.5, fontFace: F, fontSize: 12.5, color: INK_2, margin: 0, valign: "middle" });
  pageMark(s, false);
  s.addNotes("這頁對應我過往的實務經驗，圖為依通用形態繪製的推測版，實際專案細節可再校正。");
  return s;
}

function slideDataflow(pres) {
  const s = contentSlide(pres, "資料流", "三條性質完全不同的流", "把它們混在一條管線裡，是這類系統最常見的架構錯誤");
  const rows = [
    ["工單流", "需求單本體 · 狀態變更 · 釐清對話 · 稽核 log", "事件驅動", "秒級", "使用者當下卡住，立即可見"],
    ["遙測流", "平台指標快照 · Tag 巡檢 · Feed 比對 · EMQ", "批次（時／日）", "分鐘～小時", "偵測延遲，問題晚被發現"],
    ["知識流", "結案摘要 · 根因 · 平台文件 · 向量索引", "結案觸發 + 日重建", "日級", "答案過時，但不會出錯"],
  ];
  s.addTable(
    [[
      { text: "資料流", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "內容", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "頻率", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "延遲要求", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "失敗後果", options: { bold: true, color: MUTED, fontSize: 11 } },
    ]].concat(rows.map((r) => [
      { text: r[0], options: { bold: true, color: INK, fontSize: 13 } },
      { text: r[1], options: { color: INK_2, fontSize: 11.5 } },
      { text: r[2], options: { color: INK_2, fontSize: 11.5 } },
      { text: r[3], options: { color: ACC, bold: true, fontSize: 11.5 } },
      { text: r[4], options: { color: MUTED, fontSize: 11.5 } },
    ])),
    { x: L, y: 2.26, w: CW, colW: [1.4, 4.2, 2.0, 1.8, 2.7],
      rowH: 0.62, fontFace: F, border: { type: "solid", color: RULE, pt: 0.5 },
      fill: { color: PAPER }, valign: "middle", margin: [5, 8, 5, 8] }
  );
  const flow = ["來源", "擷取", "原始落地", "服務層", "消費端"];
  flow.forEach((t, i) => {
    const x = L + i * 2.45;
    s.addShape(pres.ShapeType.rect, { x, y: 4.72, w: 2.15, h: 0.56, fill: { color: MIST }, line: { color: RULE } });
    s.addText(t, { x, y: 4.72, w: 2.15, h: 0.56, fontFace: F, fontSize: 13, bold: true,
      color: INK, align: "center", valign: "middle", margin: 0 });
    if (i < 4) s.addText("→", { x: x + 2.15, y: 4.72, w: 0.3, h: 0.56, fontFace: F, fontSize: 13,
      color: MUTED, align: "center", valign: "middle", margin: 0 });
  });
  s.addText("個資遮蔽閘門在服務層與消費端之間：任何資料進入 LLM 之前，email、電話、雜湊識別碼都必須先被遮蔽。", {
    x: L, y: 5.46, w: CW, h: 0.38, fontFace: F, fontSize: 12.5, bold: true, color: ACC, margin: 0, valign: "middle" });
  bullets(s, L, 5.94, CW, 0.9, [
    "批次與事件的分界原則：人在等的走事件驅動，機器在看的走批次",
    "刻意不做串流 —— 中位處理 10.3 小時的尺度下，把偵測延遲從一小時壓到一分鐘對北極星指標沒有可測量的影響",
  ], { fs: 12 });
  pageMark(s, false);
  return s;
}

function slideDashboard(pres) {
  const s = contentSlide(pres, "Dashboard", "它是人機協作的介面，不是報表", "而且必須在第一個 AI 功能上線之前就存在");
  const cw3 = (CW - 0.5) / 3;
  card(pres, s, L, 2.26, cw3, 2.0, "戰情層　Now",
    ["現在有什麼需要我處理？", "待核准動作佇列 · 偵測器告警", "soak 期監控中 · 影子佇列"],
    { tag: "值班工程師", bs: 12, hs: 15 });
  card(pres, s, L + cw3 + 0.25, 2.26, cw3, 2.0, "診斷層　Why",
    ["這筆 AI 判斷可信嗎？", "探針原始輸出不做二次加工", "Top-3 根因假設 + 信心分數"],
    { tag: "處理工程師", bs: 12, hs: 15 });
  card(pres, s, L + (cw3 + 0.25) * 2, 2.26, cw3, 2.0, "治理層　Trend",
    ["這套系統有沒有變好？", "KPI 趨勢 · 核准通過率", "abstain 率 · 誤執行計數"],
    { tag: "團隊主管", bs: 12, hs: 15, fill: ACC_SOFT });

  const phases = [
    ["P0 觀測", "Baseline 儀表板，沒有任何 AI 功能", "沒有基線，之後所有改善都無法證明"],
    ["P1 收斂入口", "加上提單品質即時面板", "AI 擋錯單沒人發現，變成靜默失敗"],
    ["P2 知識與診斷", "加上 AI 決策審視台", "無法判斷 AI 的建議該不該信"],
    ["P3 預防與修復", "加上偵測器戰情牆與核准佇列", "受控自動化失去「受控」"],
  ];
  s.addText("放在哪個階段", { x: L, y: 4.44, w: 3, h: 0.32, fontFace: F, fontSize: 14,
    bold: true, color: INK, margin: 0, valign: "middle" });
  s.addText("這時候不做會怎樣", { x: L + 7.6, y: 4.44, w: 4.5, h: 0.32, fontFace: F, fontSize: 14,
    bold: true, color: MUTED, margin: 0, valign: "middle" });
  phases.forEach((p, i) => {
    const y = 4.82 + i * 0.46;
    s.addText(p[0], { x: L, y, w: 1.9, h: 0.4, fontFace: F, fontSize: 12.5, bold: true,
      color: i === 0 ? ACC : INK, margin: 0, valign: "middle" });
    s.addText(p[1], { x: L + 1.95, y, w: 5.6, h: 0.4, fontFace: F, fontSize: 12,
      color: INK_2, margin: 0, valign: "middle" });
    s.addText(p[2], { x: L + 7.6, y, w: CW - 7.6, h: 0.4, fontFace: F, fontSize: 12,
      color: MUTED, margin: 0, valign: "middle" });
  });
  s.addText("治理層可以直接吃分析腳本產出的 JSON —— 這代表本專案現在就能做出治理層的可運作版本。", {
    x: L, y: 6.72, w: CW, h: 0.36, fontFace: F, fontSize: 12.5, bold: true, color: ACC, margin: 0, valign: "middle" });
  pageMark(s, false);
  return s;
}

function slideCICD(pres) {
  const s = contentSlide(pres, "工程交付", "AI 系統的 CI 要多守兩件事", "模型行為會漂移，而且錯誤是機率性的");
  const gates = [
    ["1", "lint / type / unit test", "一般程式錯誤"],
    ["2", "Spec 契約驗證", "硬寫字串造成的分類漂移"],
    ["3", "探針唯讀靜態掃描", "探針悄悄變成有寫入能力"],
    ["4", "Playbook 引用檢查", "繞過允許清單的修復動作"],
    ["5", "資料再現性 hash", "生成器被改動導致結論失效"],
    ["6", "Prompt 黃金集回歸", "模型行為漂移"],
  ];
  gates.forEach((g, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = L + col * (CW / 2 + 0.2);
    const y = 2.26 + row * 0.72;
    const w = CW / 2 - 0.2;
    const special = ["3", "4", "6"].includes(g[0]);
    s.addShape(pres.ShapeType.rect, { x, y, w, h: 0.62,
      fill: { color: special ? ACC_SOFT : MIST }, line: { color: special ? ACC_SOFT : MIST } });
    s.addText(g[0], { x: x + 0.18, y, w: 0.34, h: 0.62, fontFace: M, fontSize: 12.5,
      bold: true, color: special ? ACC : MUTED, margin: 0, valign: "middle" });
    s.addText(g[1], { x: x + 0.58, y, w: 2.9, h: 0.62, fontFace: F, fontSize: 12.5,
      bold: true, color: INK, margin: 0, valign: "middle" });
    s.addText(g[2], { x: x + 3.5, y, w: w - 3.7, h: 0.62, fontFace: F, fontSize: 11.5,
      color: MUTED, margin: 0, valign: "middle" });
  });
  s.addText("橘色三道在一般後端專案不存在，卻是這套架構的安全承諾能不能兌現的實際執行機制。", {
    x: L, y: 4.48, w: CW, h: 0.36, fontFace: F, fontSize: 12.5, color: ACC, bold: true, margin: 0, valign: "middle" });
  rule(pres, s, L, 4.94, CW);
  card(pres, s, L, 5.14, CW / 2 - 0.2, 1.6, "Terraform 管的不只是機器",
    ["「探針只能唯讀」在程式層是 code review 紅線",
     "在 IAM 層則是物理限制：服務帳號只綁 read 角色",
     "就算 LLM 幻覺出寫入呼叫，平台直接回 403"],
    { tag: "兩層護欄", bs: 11.5, hs: 14, fill: ACC_SOFT });
  card(pres, s, L + CW / 2 + 0.2, 5.14, CW / 2 - 0.2, 1.6, "灰度與自動回滾",
    ["staging 影子模式：跑但不生效，累積 48 小時才上 prod",
     "回滾觸發：準確率跌破基線 5%、誤執行 > 0、成本超支 30%",
     "誤執行計數必須永遠是 0，非 0 即自動降級"],
    { bs: 11.5, hs: 14 });
  pageMark(s, false);
  return s;
}

function slideRoadmap(pres) {
  const s = contentSlide(pres, "導入路線", "四階段，每階段都有退出條件", "達不到就不進下一階段");
  const rows = [
    ["P0 觀測", "4 週", "只收單、只標註、不介入。建立 baseline", "完整度與釐清次數有 4 週穩定基線"],
    ["P1 收斂入口", "6 週", "上線提單助理與分診。人仍全權處理內容", "完整度中位 +15 分、釐清次數中位 ≤ 1"],
    ["P2 知識與診斷", "8 週", "知識庫回覆 + 診斷探針 + 決策審視台", "覆蓋率達標、誤判率 < 5%、reopen 不上升"],
    ["P3 預防與修復", "12 週", "六偵測器全開 + 低風險自動修復", "復發率下降、高風險誤執行 = 0"],
  ];
  s.addTable(
    [[
      { text: "階段", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "週期", options: { bold: true, color: MUTED, fontSize: 11, align: "center" } },
      { text: "做什麼", options: { bold: true, color: MUTED, fontSize: 11 } },
      { text: "退出條件", options: { bold: true, color: MUTED, fontSize: 11 } },
    ]].concat(rows.map((r) => [
      { text: r[0], options: { bold: true, color: INK, fontSize: 12.5 } },
      { text: r[1], options: { color: INK_2, fontSize: 12, align: "center", fontFace: M } },
      { text: r[2], options: { color: INK_2, fontSize: 11.5 } },
      { text: r[3], options: { color: ACC, fontSize: 11.5 } },
    ])),
    { x: L, y: 2.26, w: CW, colW: [2.0, 0.9, 4.6, 4.6],
      rowH: 0.62, fontFace: F, border: { type: "solid", color: RULE, pt: 0.5 },
      fill: { color: PAPER }, valign: "middle", margin: [5, 8, 5, 8] }
  );
  s.addText("明確不做清單", { x: L, y: 5.12, w: CW, h: 0.34, fontFace: F, fontSize: 15,
    bold: true, color: INK, margin: 0, valign: "middle" });
  const nos = [
    "不做全自動修復，高風險永遠只建議",
    "不做廣告成效優化建議，那是投手的專業",
    "不做即時串流，日批加事件觸發足夠",
    "不自建向量資料庫",
    "不做多語系，先繁中單一市場",
    "不碰真實客戶資料",
  ];
  nos.forEach((t, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    s.addText([{ text: "✕  ", options: { color: CRIT, bold: true } }, { text: t, options: {} }], {
      x: L + col * (CW / 2 + 0.2), y: 5.52 + row * 0.4, w: CW / 2 - 0.2, h: 0.36,
      fontFace: F, fontSize: 12.5, color: INK_2, margin: 0, valign: "middle",
    });
  });
  s.addText("寫下不做什麼，比寫下要做什麼更能保護專案。要推翻任何一條，都必須先寫一份架構決策紀錄。", {
    x: L, y: 6.78, w: CW, h: 0.34, fontFace: F, fontSize: 12, color: MUTED, margin: 0, valign: "middle", italic: true });
  pageMark(s, false);
  return s;
}

function slideKPI(pres) {
  const s = contentSlide(pres, "成效衡量", "KPI 樹與可回收工時", "所有基線都由分析腳本從資料算出，沒有一個是手寫的");
  const kpis = [
    ["北極星", "每張工單的工程實際投入工時", "5.13 h / 單"],
    ["前段", "資訊完整度 ↑ → 釐清次數 ↓", "56 分 / 2.27 次"],
    ["中段", "AI 自動結案率 ↑ → 首次回應 ↓", "— / 296 分鐘"],
    ["後段", "重啟次數 ↓ → 滿意度 ↑", "13.4% / 3.81"],
    ["預防", "90 天復發率 ↓ → 工單總量 ↓", "8.6% / 640 單"],
  ];
  kpis.forEach((k, i) => {
    const y = 2.26 + i * 0.6;
    const hot = i === 0;
    s.addShape(pres.ShapeType.rect, { x: L, y, w: 7.6, h: 0.52,
      fill: { color: hot ? INK : MIST }, line: { color: hot ? INK : MIST } });
    s.addText(k[0], { x: L + 0.22, y, w: 1.3, h: 0.52, fontFace: F, fontSize: 12,
      bold: true, color: hot ? ACC : MUTED, margin: 0, valign: "middle" });
    s.addText(k[1], { x: L + 1.6, y, w: 4.0, h: 0.52, fontFace: F, fontSize: 12.5,
      color: hot ? PAPER : INK, bold: hot, margin: 0, valign: "middle" });
    s.addText(k[2], { x: L + 5.7, y, w: 1.7, h: 0.52, fontFace: M, fontSize: 11,
      color: hot ? "AFC0D0" : MUTED, margin: 0, valign: "middle", align: "right" });
  });
  const rec = [
    ["L1 釐清成本消除", "1,262.5 h"],
    ["L3 診斷加速（50%）", "448.6 h"],
    ["L4 自動修復", "305.9 h"],
    ["L2 知識自助", "231.0 h"],
  ];
  s.addText("可回收工時的保守估算", { x: L + 8.0, y: 2.26, w: CW - 8.0, h: 0.34,
    fontFace: F, fontSize: 13, bold: true, color: INK, margin: 0, valign: "middle" });
  rec.forEach((r, i) => {
    const y = 2.66 + i * 0.42;
    s.addText(r[0], { x: L + 8.0, y, w: 2.5, h: 0.38, fontFace: F, fontSize: 12,
      color: INK_2, margin: 0, valign: "middle" });
    s.addText(r[1], { x: L + 10.5, y, w: CW - 10.5, h: 0.38, fontFace: M, fontSize: 12,
      color: INK, margin: 0, valign: "middle", align: "right" });
  });
  statTile(pres, s, L + 8.0, 4.5, CW - 8.0, "53.0%", "聯集上限 1,743 小時\n已扣除重疊，非直接相加",
    { vs: 32, h: 1.3, color: ACC, fill: ACC_SOFT });
  s.addShape(pres.ShapeType.rect, { x: L, y: 6.06, w: CW, h: 0.82, fill: { color: INK }, line: { color: INK } });
  s.addText("為什麼說是「上限」而不是「預期」：這是理論天花板。AI 有誤判率、人有適應期，實際落地必然低於此值。刻意不給「預期節省 X%」，因為那需要導入後的數據才算得出來。", {
    x: L + 0.32, y: 6.06, w: CW - 0.64, h: 0.82, fontFace: F, fontSize: 13, bold: true,
    color: PAPER, margin: 0, valign: "middle" });
  pageMark(s, false);
  return s;
}

// ---------------------------------------------------------------- 組裝

function build(mode) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.author = "Angel";
  pres.company = "aliencatuniverse.tw";
  pres.title = "AdOps AI Triage";
  pres.subject = "廣告支援工程需求單的 AI 化設計";

  PAGE = 0;
  const short = [
    slideCover, slideConflict, slideBlindspot, slideThreeGroups,
    slideFinding1, slideFinding2, slideFinding3, slideFourTypes,
    slideArch, slideBoundary, slideCounter, slideDeliver,
  ];
  const full = [
    slideCover, slideConflict, slideBlindspot, slideThreeGroups,
    slideDataDesign, slideAnchors,
    slideFinding1, slideFinding2, slideFinding3,
    slideFourTypes, slideSubstitution, slidePipeline,
    slideArch, slideDataflow, slideBoundary,
    slideDashboard, slideCICD, slideRoadmap, slideKPI,
    slideCounter, slideDeliver,
  ];
  const seq = mode === "full" ? full : short;
  TOTAL = seq.length;
  seq.forEach((fn) => fn(pres));

  const out = mode === "full"
    ? "AdOps-AI-Triage-完整版.pptx"
    : "AdOps-AI-Triage-精簡版.pptx";
  return pres.writeFile({ fileName: out }).then(() => {
    console.log(`✔ ${out}（${TOTAL} 頁）`);
  });
}

const mode = process.argv[2] || "short";
build(mode).catch((e) => { console.error(e); process.exit(1); });
