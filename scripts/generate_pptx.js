// 火山杯参赛答辩 PPT 生成脚本
// 运行: node scripts/generate_pptx.js
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

// ---------- 配色 ----------
const C = {
  primary: "1E3A5F",  // 深蓝
  blue:    "1D4ED8",  // 蓝
  cyan:    "0EA5E9",  // 青
  teal:    "14B8A6",  // 青绿
  amber:   "F59E0B",  // 琥珀
  ink:     "1E293B",  // 深灰文字
  muted:   "64748B",  // 浅灰文字
  bg:      "F8FAFC",  // 背景
  white:   "FFFFFF",
  card:    "FFFFFF",
  light:   "E0F2FE",  // 浅蓝卡片
  line:    "E2E8F0",
};

const FONT = "Microsoft YaHei";

// ---------- 图标 ----------
async function icon(Comp, color = "#FFFFFF", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color, size: String(size) })
  );
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

const makeShadow = () => ({
  type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.12,
});

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
  const PW = 13.33, PH = 7.5;
  pres.author = "全龄段多语言学习智能体团队";
  pres.title = "全龄段多语言学习智能体 · 火山杯参赛答辩";

  // 预生成图标
  const ic = {
    warn:   await icon(fa.FaExclamationTriangle, "#" + C.amber),
    yin:    await icon(fa.FaFont, "#" + C.cyan),
    chat:   await icon(fa.FaCommentDots, "#" + C.blue),
    lang:   await icon(fa.FaLanguage, "#" + C.teal),
    arch:   await icon(fa.FaSitemap, "#" + C.white),
    brain:  await icon(fa.FaBrain, "#" + C.blue),
    shuffle:await icon(fa.FaRandom, "#" + C.teal),
    check:  await icon(fa.FaCheckDouble, "#" + C.cyan),
    shield: await icon(fa.FaShieldAlt, "#" + C.blue),
    chart:  await icon(fa.FaChartBar, "#" + C.primary),
    star:   await icon(fa.FaStar, "#" + C.amber),
    trend:  await icon(fa.FaChartLine, "#" + C.teal),
    play:   await icon(fa.FaPlayCircle, "#" + C.white),
    flag:   await icon(fa.FaFlagCheckered, "#" + C.white),
    user:   await icon(fa.FaUsers, "#" + C.white),
    rocket: await icon(fa.FaRocket, "#" + C.amber),
  };

  // ---------- 通用元素 ----------
  function footer(slide, n) {
    slide.addShape(pres.shapes.LINE, { x: 0.6, y: 7.05, w: PW - 1.2, h: 0, line: { color: C.line, width: 1 } });
    slide.addText("全龄段多语言学习智能体 · 2026 火山杯 Agent 创新大赛", {
      x: 0.6, y: 7.08, w: 9, h: 0.35, fontFace: FONT, fontSize: 9, color: C.muted, align: "left", valign: "middle",
    });
    slide.addText(String(n).padStart(2, "0"), {
      x: PW - 1.2, y: 7.08, w: 0.6, h: 0.35, fontFace: FONT, fontSize: 9, color: C.muted, align: "right", valign: "middle",
    });
  }

  function titleBar(slide, text, sub, iconData) {
    slide.background = { color: C.bg };
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: PW, h: 1.25, fill: { color: C.primary } });
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 1.25, w: PW, h: 0.06, fill: { color: C.cyan } });
    if (iconData) {
      slide.addShape(pres.shapes.OVAL, { x: 0.55, y: 0.28, w: 0.7, h: 0.7, fill: { color: C.cyan } });
      slide.addImage({ data: iconData, x: 0.7, y: 0.43, w: 0.4, h: 0.4 });
    }
    slide.addText(text, {
      x: iconData ? 1.5 : 0.6, y: 0.2, w: PW - 2, h: 0.6, fontFace: FONT, fontSize: 24, bold: true, color: C.white, align: "left", valign: "middle",
    });
    if (sub) slide.addText(sub, {
      x: iconData ? 1.5 : 0.6, y: 0.78, w: PW - 2, h: 0.4, fontFace: FONT, fontSize: 12, color: "BBD8EE", align: "left", valign: "middle",
    });
  }

  function card(slide, x, y, w, h, fill = C.card) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h, fill: { color: fill }, line: { color: C.line, width: 1 }, shadow: makeShadow(),
    });
  }

  // ===================================================================
  // P1 封面
  // ===================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.primary };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: PW, h: 0.18, fill: { color: C.cyan } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: PH - 0.18, w: PW, h: 0.18, fill: { color: C.cyan } });
    // 装饰圆形
    s.addShape(pres.shapes.OVAL, { x: 9.8, y: -1.5, w: 5, h: 5, fill: { color: "24456B" } });
    s.addShape(pres.shapes.OVAL, { x: 10.8, y: 4.2, w: 3.5, h: 3.5, fill: { color: "1B3454" } });
    // 图标
    s.addShape(pres.shapes.OVAL, { x: 0.9, y: 1.5, w: 1.0, h: 1.0, fill: { color: C.cyan } });
    s.addImage({ data: ic.lang, x: 1.12, y: 1.72, w: 0.56, h: 0.56 });
    s.addText("2026 火山杯 Agent 创新大赛 · 参赛作品", {
      x: 0.9, y: 2.75, w: 10, h: 0.4, fontFace: FONT, fontSize: 14, color: C.cyan, align: "left",
    });
    s.addText("全龄段多语言学习智能体", {
      x: 0.85, y: 3.1, w: 11.5, h: 1.1, fontFace: FONT, fontSize: 46, bold: true, color: C.white, align: "left",
    });
    s.addText("更会教，而不只是更聪明 —— 一个覆盖拼音、英语口语与多语种的 AI 语言教练", {
      x: 0.9, y: 4.3, w: 11, h: 0.6, fontFace: FONT, fontSize: 16, color: "CBD5E1", align: "left",
    });
    // 底部标签
    const tags = ["三层提示词架构", "独立记忆分区", "防模板化引擎", "Coze 平台落地"];
    let tx = 0.9;
    tags.forEach((t) => {
      const w = 0.42 + t.length * 0.26;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: tx, y: 5.5, w, h: 0.5, fill: { color: "284E78" }, rectRadius: 0.1 });
      s.addText(t, { x: tx, y: 5.5, w, h: 0.5, fontFace: FONT, fontSize: 11, color: "E2E8F0", align: "center", valign: "middle" });
      tx += w + 0.25;
    });
    s.addText("汇报人：参赛团队　|　基于火山引擎扣子（Coze）平台　|　2026.07", {
      x: 0.9, y: 6.4, w: 11, h: 0.4, fontFace: FONT, fontSize: 12, color: "94A3B8", align: "left",
    });
  }

  // ===================================================================
  // P2 目录
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "目录", "CONTENTS", ic.arch);
    const items = [
      ["01", "行业痛点与机遇", "传统 App 有体系无智能，通用大模型有智能无体系", ic.warn],
      ["02", "产品概述", "三大教学板块 + 全龄段自适应的 AI 语言教练", ic.rocket],
      ["03", "技术架构", "意图 / 知识锚定 / 决策 / 表达 四层架构（Coze 落地）", ic.arch],
      ["04", "核心能力", "记忆分区、防模板化、SVM 校验、四层护栏、七维评估", ic.shield],
      ["05", "平台落地与优势", "Coze 配置映射 · 六大核心优势 · 市场前景", ic.star],
      ["06", "演示与总结", "3 分钟演示故事线 · 总结展望", ic.flag],
    ];
    const colW = 5.7, gap = 0.5, x0 = 0.7, y0 = 1.7, rh = 1.55;
    items.forEach((it, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = x0 + col * (colW + gap), y = y0 + row * (rh + 0.2);
      card(s, x, y, colW, rh);
      s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.1, h: rh, fill: { color: C.cyan } });
      s.addText(it[0], { x: x + 0.25, y: y + 0.2, w: 1.0, h: 1.0, fontFace: FONT, fontSize: 32, bold: true, color: C.light, align: "left", valign: "middle" });
      s.addShape(pres.shapes.OVAL, { x: x + colW - 0.95, y: y + 0.25, w: 0.65, h: 0.65, fill: { color: C.primary } });
      s.addImage({ data: it[3], x: x + colW - 0.82, y: y + 0.38, w: 0.4, h: 0.4 });
      s.addText(it[1], { x: x + 1.35, y: y + 0.22, w: colW - 2.4, h: 0.55, fontFace: FONT, fontSize: 17, bold: true, color: C.ink, align: "left", valign: "middle" });
      s.addText(it[2], { x: x + 1.35, y: y + 0.78, w: colW - 1.6, h: 0.6, fontFace: FONT, fontSize: 11.5, color: C.muted, align: "left", valign: "top" });
    });
    footer(s, 2);
  }

  // ===================================================================
  // P3 痛点与机遇
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "行业痛点与机遇", "为什么是现在？为什么是我们？", ic.warn);
    // 左：痛点
    card(s, 0.7, 1.65, 5.9, 5.1);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 1.65, w: 5.9, h: 0.62, fill: { color: C.amber } });
    s.addText("现有产品的两大断层", { x: 0.9, y: 1.65, w: 5.5, h: 0.62, fontFace: FONT, fontSize: 16, bold: true, color: C.white, valign: "middle" });
    s.addText([
      { text: "传统语言 App：有体系、无智能", options: { bold: true, color: C.ink, breakLine: true, fontSize: 14 } },
      { text: "固定课纲、机械跟读，无法理解“你哪里卡住了”。", options: { color: C.muted, breakLine: true, fontSize: 12, paraSpaceAfter: 8 } },
      { text: "通用大模型：有智能、无体系", options: { bold: true, color: C.ink, breakLine: true, fontSize: 14 } },
      { text: "能对话，却记不住学习进度、不会因材施教、不锚定知识。", options: { color: C.muted, breakLine: true, fontSize: 12, paraSpaceAfter: 8 } },
      { text: "方言 / 银发 / 儿童：普遍缺位", options: { bold: true, color: C.ink, breakLine: true, fontSize: 14 } },
      { text: "平翘舌、前后鼻音矫正、大字慢速引导和趣味化几乎空白。", options: { color: C.muted, fontSize: 12 } },
    ], { x: 0.95, y: 2.45, w: 5.4, h: 4.0, fontFace: FONT, valign: "top", lineSpacingMultiple: 1.05 });

    // 右：机遇
    card(s, 6.85, 1.65, 5.8, 5.1, C.primary);
    s.addText("窗口期已经打开", { x: 7.1, y: 1.85, w: 5.3, h: 0.6, fontFace: FONT, fontSize: 16, bold: true, color: C.white, valign: "middle" });
    const stats = [
      ["153.4 亿元", "2026 中国在线语言学习预计市场规模"],
      ["−7%", "头部产品日活下滑，用户渴望更“会教”的体验"],
      ["0", "真正覆盖全龄段 + 方言矫正的直接竞品"],
    ];
    let yy = 2.55;
    stats.forEach((st) => {
      s.addText(st[0], { x: 7.1, y: yy, w: 2.4, h: 0.7, fontFace: FONT, fontSize: 26, bold: true, color: C.cyan, align: "left", valign: "middle" });
      s.addText(st[1], { x: 9.5, y: yy, w: 3.0, h: 0.7, fontFace: FONT, fontSize: 11.5, color: "CBD5E1", align: "left", valign: "middle" });
      yy += 1.35;
    });
    footer(s, 3);
  }

  // ===================================================================
  // P4 产品概述
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "产品概述", "一个 AI 语言教练，而非又一个聊天机器人", ic.rocket);
    const boards = [
      [ic.yin, C.cyan, "中文拼音", ["零基础声母韵母认读", "平翘舌 / 前后鼻音矫正", "方言口音专项训练"]],
      [ic.chat, C.blue, "英语口语", ["场景对话：餐厅 / 机场 / 职场", "发音实时纠错", "开口说优先于语法讲解"]],
      [ic.lang, C.teal, "多语种", ["日 / 韩 / 法 / 西自由切换", "各语种进度独立保存", "A1–B1 阶梯教材"]],
    ];
    const bw = 3.85, gap = 0.35, x0 = 0.7, y = 1.75, bh = 3.3;
    boards.forEach((b, i) => {
      const x = x0 + i * (bw + gap);
      card(s, x, y, bw, bh);
      s.addShape(pres.shapes.RECTANGLE, { x, y, w: bw, h: 0.95, fill: { color: b[1] } });
      s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.22, w: 0.55, h: 0.55, fill: { color: C.white } });
      s.addImage({ data: b[0], x: x + 0.42, y: y + 0.34, w: 0.32, h: 0.32 });
      s.addText(b[2], { x: x + 1.0, y: y, w: bw - 1.1, h: 0.95, fontFace: FONT, fontSize: 19, bold: true, color: C.white, valign: "middle" });
      s.addText(b[3].map((t, k) => ({ text: t, options: { bullet: { code: "2022" }, color: C.ink, fontSize: 13, breakLine: true, paraSpaceAfter: 6 } })),
        { x: x + 0.35, y: y + 1.1, w: bw - 0.7, h: bh - 1.3, fontFace: FONT, valign: "top" });
    });
    // 底部适配条
    s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 5.35, w: 11.95, h: 1.35, fill: { color: C.light } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 5.35, w: 0.1, h: 1.35, fill: { color: C.primary } });
    s.addText("全龄段自适应：同一套引擎，五类人群差异化对待", {
      x: 0.95, y: 5.45, w: 11.5, h: 0.45, fontFace: FONT, fontSize: 14, bold: true, color: C.primary, valign: "middle",
    });
    s.addText("儿童（降速 + 趣味引导） · 青少年（效率 + 应试衔接） · 成人（场景化速成） · 银发用户（大字 + 慢速重复） · 方言用户（口音专项矫正）", {
      x: 0.95, y: 5.95, w: 11.5, h: 0.65, fontFace: FONT, fontSize: 12, color: C.ink, valign: "top",
    });
    footer(s, 4);
  }

  // ===================================================================
  // P5 技术架构（四层）
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "技术架构：把不确定性封装进确定性流程", "意图 / 知识锚定 / 决策 / 表达 四层 · 落地于 Coze", ic.arch);
    const layers = [
      ["L1 意图识别", "识别年龄 / 基础 / 口音与板块意图，强制分流到三大教学分支", C.cyan],
      ["L2 知识锚定（RAG）", "拼音库 / 英语场景库 / 多语种教材 经向量检索注入，杜绝幻觉", C.blue],
      ["L3 决策引擎", "记忆分区 + 薄弱点复习 + 阈值控制，确定性地决定“下一步教什么”", C.teal],
      ["L4 表达层", "适老化话术 + 防模板化变量池，每次回复自然且因人而异", C.amber],
    ];
    let y = 1.7;
    const lh = 1.15;
    layers.forEach((L, i) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 11.95, h: lh, fill: { color: C.card }, line: { color: C.line, width: 1 }, shadow: makeShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 2.6, h: lh, fill: { color: L[2] } });
      s.addText(L[0], { x: 0.8, y, w: 2.4, h: lh, fontFace: FONT, fontSize: 15, bold: true, color: C.white, align: "left", valign: "middle" });
      s.addText(L[1], { x: 3.5, y, w: 9.0, h: lh, fontFace: FONT, fontSize: 13, color: C.ink, align: "left", valign: "middle" });
      // 箭头
      if (i < layers.length - 1) {
        s.addShape(pres.shapes.OVAL, { x: 6.5, y: y + lh - 0.05, w: 0.4, h: 0.4, fill: { color: C.primary } });
        s.addText("↓", { x: 6.5, y: y + lh - 0.05, w: 0.4, h: 0.4, fontFace: FONT, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
      }
      y += lh + 0.18;
    });
    // 右侧 Coze 映射提示
    s.addText("Coze 落地：人设与回复逻辑 = L1+L4；知识库 = L2；工作流 + 数据库 = L3", {
      x: 0.7, y: 6.55, w: 11.95, h: 0.4, fontFace: FONT, fontSize: 11.5, italic: true, color: C.muted, align: "center",
    });
    footer(s, 5);
  }

  // ===================================================================
  // P6 核心能力（2x2 工程能力）
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "生产级核心能力", "让“会教”稳定、可控、可追溯", ic.shield);
    const caps = [
      [ic.brain, C.blue, "独立记忆分区", "按语种 / 板块存薄弱点，跨天自动复习；区别于通用大模型的关键差异"],
      [ic.shuffle, C.teal, "六层防模板化", "动态提示词 + 语义排斥 + 多候选去重，避免每次对话千篇一律"],
      [ic.check, C.cyan, "SVM 混合校验", "方言分类 / 发音检测 / 质量筛查三模型，8ms 轻量前置过滤"],
      [ic.chart, C.primary, "七维度评估", "准确性 / 效率 / 安全 / 公平 / 可解释 / 锚定 / 合规，量化验收"],
    ];
    const cw = 5.9, ch = 2.45, gx = 0.7, gy = 1.7, gap = 0.35;
    caps.forEach((c, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = gx + col * (cw + gap), y = gy + row * (ch + 0.25);
      card(s, x, y, cw, ch);
      s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: y + 0.35, w: 0.9, h: 0.9, fill: { color: c[1] } });
      s.addImage({ data: c[0], x: x + 0.57, y: y + 0.57, w: 0.46, h: 0.46 });
      s.addText(c[2], { x: x + 1.45, y: y + 0.35, w: cw - 1.7, h: 0.6, fontFace: FONT, fontSize: 17, bold: true, color: C.ink, valign: "middle" });
      s.addText(c[3], { x: x + 1.45, y: y + 1.0, w: cw - 1.7, h: 1.3, fontFace: FONT, fontSize: 12.5, color: C.muted, valign: "top", lineSpacingMultiple: 1.05 });
    });
    footer(s, 6);
  }

  // ===================================================================
  // P7 全龄段自适应
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "全龄段自适应：一套引擎，五类人群", "识别用户画像，差异化教学策略", ic.user);
    const groups = [
      ["儿童", "降速 + 趣味引导 + 游戏化奖励", C.cyan],
      ["青少年", "效率优先 + 应试衔接 + 短平快", C.blue],
      ["成人", "场景化速成 + 碎片时间利用", C.teal],
      ["银发用户", "大字界面 + 慢速重复 + 语音播报", C.amber],
      ["方言用户", "平翘舌 / 前后鼻音专项矫正", C.primary],
    ];
    let y = 1.75;
    const rh = 0.92;
    groups.forEach((g, i) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 11.95, h: rh, fill: { color: C.card }, line: { color: C.line, width: 1 } });
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 2.4, h: rh, fill: { color: g[2] } });
      s.addText(g[0], { x: 0.7, y, w: 2.4, h: rh, fontFace: FONT, fontSize: 16, bold: true, color: C.white, align: "center", valign: "middle" });
      s.addText(g[1], { x: 3.3, y, w: 9.2, h: rh, fontFace: FONT, fontSize: 13.5, color: C.ink, align: "left", valign: "middle" });
      y += rh + 0.12;
    });
    footer(s, 7);
  }

  // ===================================================================
  // P8 记忆分区与复习
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "长期记忆分区与薄弱点复习", "记住“你学到哪、哪里总错、该复习什么”", ic.brain);
    // 左：分区结构
    card(s, 0.7, 1.7, 6.0, 5.0);
    s.addText("记忆分区结构", { x: 0.95, y: 1.85, w: 5.5, h: 0.5, fontFace: FONT, fontSize: 15, bold: true, color: C.primary });
    const parts = [
      ["pinyin", "拼音：声韵掌握度 / 方言错误点"],
      ["english", "英语：场景熟练度 / 发音弱点"],
      ["languages", "多语种：每语种独立进度与薄弱点"],
    ];
    let yy = 2.5;
    parts.forEach((p) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 0.95, y: yy, w: 5.5, h: 0.95, fill: { color: C.light } });
      s.addShape(pres.shapes.RECTANGLE, { x: 0.95, y: yy, w: 0.09, h: 0.95, fill: { color: C.cyan } });
      s.addText(p[0], { x: 1.2, y: yy + 0.1, w: 5.0, h: 0.4, fontFace: FONT, fontSize: 14, bold: true, color: C.blue });
      s.addText(p[1], { x: 1.2, y: yy + 0.48, w: 5.0, h: 0.4, fontFace: FONT, fontSize: 11.5, color: C.muted });
      yy += 1.15;
    });
    // 右：复习闭环
    card(s, 6.95, 1.7, 5.7, 5.0, C.primary);
    s.addText("跨天复习闭环", { x: 7.2, y: 1.85, w: 5.2, h: 0.5, fontFace: FONT, fontSize: 15, bold: true, color: C.white });
    const flow = ["对话中识别薄弱点 → 写入分区", "按遗忘曲线生成次日复习任务", "复习命中率反馈 → 动态调整权重", "长期形成个人专属学习画像"];
    let fy = 2.55;
    flow.forEach((f, i) => {
      s.addShape(pres.shapes.OVAL, { x: 7.2, y: fy, w: 0.5, h: 0.5, fill: { color: C.cyan } });
      s.addText(String(i + 1), { x: 7.2, y: fy, w: 0.5, h: 0.5, fontFace: FONT, fontSize: 14, bold: true, color: C.primary, align: "center", valign: "middle" });
      s.addText(f, { x: 7.85, y: fy - 0.05, w: 4.6, h: 0.6, fontFace: FONT, fontSize: 12.5, color: "E2E8F0", valign: "middle" });
      fy += 1.05;
    });
    footer(s, 8);
  }

  // ===================================================================
  // P9 护栏与质量门
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "四层护栏与阈值控制", "让生产级智能体安全、可控、可观测", ic.shield);
    const guards = [
      ["L1 输入验证", "年龄 / 板块合法性校验，过滤越界请求", C.cyan],
      ["L2 输出过滤", "敏感词 / 不当内容拦截，内容合规", C.blue],
      ["L3 行为策略", "异常分类与恢复（误入 / 权限 / 网络等）", C.teal],
      ["L4 运行时可观测", "日志 + 指标追踪，P95 延迟 < 5s", C.amber],
    ];
    const gw = 2.85, gap = 0.25, x0 = 0.7, y = 1.8, gh = 2.9;
    guards.forEach((g, i) => {
      const x = x0 + i * (gw + gap);
      card(s, x, y, gw, gh);
      s.addShape(pres.shapes.RECTANGLE, { x, y, w: gw, h: 0.7, fill: { color: g[2] } });
      s.addText(g[0], { x: x + 0.1, y, w: gw - 0.2, h: 0.7, fontFace: FONT, fontSize: 13.5, bold: true, color: C.white, align: "center", valign: "middle" });
      s.addText(g[1], { x: x + 0.2, y: y + 0.85, w: gw - 0.4, h: gh - 1.0, fontFace: FONT, fontSize: 12, color: C.ink, valign: "top", lineSpacingMultiple: 1.05 });
    });
    // 阈值条
    s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 5.0, w: 11.95, h: 1.6, fill: { color: C.light } });
    s.addText("六大阈值控制环节", { x: 0.95, y: 5.1, w: 11, h: 0.4, fontFace: FONT, fontSize: 14, bold: true, color: C.primary });
    const ths = ["意图置信度", "发音异常分", "质量评分", "重复度", "RAG 置信度", "安全护栏"];
    let tx = 0.95;
    ths.forEach((t) => {
      const w = 1.75;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: tx, y: 5.6, w, h: 0.7, fill: { color: C.white }, rectRadius: 0.08, line: { color: C.cyan, width: 1 } });
      s.addText(t, { x: tx, y: 5.6, w, h: 0.7, fontFace: FONT, fontSize: 11.5, color: C.ink, align: "center", valign: "middle" });
      tx += w + 0.18;
    });
    footer(s, 9);
  }

  // ===================================================================
  // P10 Coze 平台落地映射
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "基于火山引擎扣子（Coze）落地", "本地生产级设计 → Coze 平台配置", ic.rocket);
    // 表
    const rows = [
      [{ text: "本地生产级组件", options: { bold: true, fill: { color: C.primary }, color: C.white } },
       { text: "Coze 平台等价实现", options: { bold: true, fill: { color: C.primary }, color: C.white } }],
      ["三层提示词 + 分支路由", "Bot「人设与回复逻辑」+ 工作流条件分支"],
      ["Chroma 向量库 / RAG", "Coze 知识库（拼音 / 英语 / 多语种）"],
      ["记忆分区 JSON", "Coze 数据库（数据表：按语种 / 板块）"],
      ["SVM 校验 / 阈值", "工作流代码节点做前置过滤与评分"],
      ["Edge-TTS 语音", "Coze 语音合成插件 / 数字人"],
      ["七维度评估", "评测集 + 运行日志监控面板"],
    ];
    s.addTable(rows, {
      x: 0.7, y: 1.75, w: 11.95, colW: [4.8, 7.15],
      fontFace: FONT, fontSize: 13, color: C.ink,
      border: { pt: 1, color: C.line }, align: "left", valign: "middle",
      rowH: [0.55, 0.62, 0.62, 0.62, 0.62, 0.62, 0.62],
      fill: { color: C.white },
    });
    s.addText("注：Coze 平台已内置知识库、工作流、数据库与语音能力，无需自建 Chroma / SVM 服务即可达到同等教学设计。", {
      x: 0.7, y: 6.5, w: 11.95, h: 0.4, fontFace: FONT, fontSize: 11, italic: true, color: C.muted, align: "center",
    });
    footer(s, 10);
  }

  // ===================================================================
  // P11 六大核心优势 + 竞品对比
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "六大核心优势", "差异化竞争力一览", ic.star);
    // 左：六优势
    const adv = [
      "全龄段覆盖（儿童到银发）", "方言口音专项矫正", "独立记忆分区与复习",
      "防模板化自然交互", "知识锚定防幻觉", "低门槛可演示（Coze 落地）",
    ];
    let ay = 1.8;
    adv.forEach((a) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: ay, w: 6.3, h: 0.72, fill: { color: C.card }, line: { color: C.line, width: 1 } });
      s.addImage({ data: ic.check, x: 0.85, y: ay + 0.18, w: 0.36, h: 0.36 });
      s.addText(a, { x: 1.35, y: ay, w: 5.5, h: 0.72, fontFace: FONT, fontSize: 13, color: C.ink, valign: "middle" });
      ay += 0.82;
    });
    // 右：对比表
    const cmp = [
      [{ text: "维度", options: { bold: true, fill: { color: C.primary }, color: C.white } },
       { text: "本产品", options: { bold: true, fill: { color: C.primary }, color: C.white } },
       { text: "通用大模型", options: { bold: true, fill: { color: C.primary }, color: C.white } }],
      ["记忆学习进度", "✓ 分区持久", "✗ 易失忆"],
      ["方言矫正", "✓ 专项", "△ 不擅长"],
      ["防模板化", "✓ 六层", "✗ 雷同"],
      ["适老化", "✓ 大字慢速", "✗ 无"],
    ];
    s.addTable(cmp, {
      x: 7.2, y: 1.8, w: 5.45, colW: [1.85, 1.85, 1.75],
      fontFace: FONT, fontSize: 12, color: C.ink, border: { pt: 1, color: C.line },
      align: "center", valign: "middle", rowH: [0.5, 0.62, 0.62, 0.62, 0.62], fill: { color: C.white },
    });
    footer(s, 11);
  }

  // ===================================================================
  // P12 市场前景数据
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "市场前景", "需求真实、规模可观、窗口期明确", ic.trend);
    card(s, 0.7, 1.75, 7.0, 5.0);
    s.addText("在线语言学习市场规模（亿元）", { x: 0.95, y: 1.9, w: 6.5, h: 0.5, fontFace: FONT, fontSize: 14, bold: true, color: C.primary });
    s.addChart(pres.charts.BAR, [{
      name: "市场规模", labels: ["2023", "2024", "2025", "2026E"], values: [98, 118, 137, 153.4],
    }], {
      x: 0.85, y: 2.45, w: 6.6, h: 4.1, barDir: "col",
      chartColors: [C.cyan], chartArea: { fill: { color: "FFFFFF" } },
      catAxisLabelColor: C.muted, valAxisLabelColor: C.muted,
      valGridLine: { color: C.line, size: 0.5 }, catGridLine: { style: "none" },
      showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.ink, dataLabelFontFace: FONT,
      showLegend: false, showTitle: false,
    });
    // 右：要点
    const pts = [
      ["需求侧", "终身学习 + 老龄化 + 出海，三重驱动"],
      ["供给侧", "通用大模型不会教，留下专业空白"],
      ["时机", "多邻国日活下滑，用户寻更好体验"],
      ["壁垒", "记忆分区 + 方言矫正 + 防模板化"],
    ];
    let py = 1.9;
    pts.forEach((p) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 7.95, y: py, w: 4.7, h: 1.05, fill: { color: C.card }, line: { color: C.line, width: 1 }, shadow: makeShadow() });
      s.addShape(pres.shapes.RECTANGLE, { x: 7.95, y: py, w: 0.1, h: 1.05, fill: { color: C.teal } });
      s.addText(p[0], { x: 8.2, y: py + 0.12, w: 4.3, h: 0.4, fontFace: FONT, fontSize: 14, bold: true, color: C.teal });
      s.addText(p[1], { x: 8.2, y: py + 0.52, w: 4.3, h: 0.45, fontFace: FONT, fontSize: 12, color: C.ink });
      py += 1.2;
    });
    footer(s, 12);
  }

  // ===================================================================
  // P13 演示规划
  // ===================================================================
  {
    const s = pres.addSlide();
    titleBar(s, "3 分钟演示故事线", "让评委亲眼看见“更会教”", ic.play);
    const steps = [
      ["0:00–0:30", "开场：一句话讲清痛点与定位", "展示全龄段 + 三板块的整体能力"],
      ["0:30–1:10", "拼音板块：平翘舌矫正", "输入“我有平翘舌问题”，展示识别 + 薄弱点写入"],
      ["1:10–1:50", "英语板块：餐厅场景对话", "展示场景卡检索 + 发音纠错 + 开口说引导"],
      ["1:50–2:30", "多语种：切换日语并独立存进度", "展示语种分支 + 记忆分区互不干扰"],
      ["2:30–3:00", "记忆与复习：跨天薄弱点复习", "展示次日复习任务自动生成，呼应“更会教”"],
    ];
    let y = 1.75;
    steps.forEach((st, i) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 11.95, h: 0.92, fill: { color: C.card }, line: { color: C.line, width: 1 } });
      s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y, w: 2.3, h: 0.92, fill: { color: C.primary } });
      s.addText(st[0], { x: 0.7, y, w: 2.3, h: 0.92, fontFace: FONT, fontSize: 13, bold: true, color: C.cyan, align: "center", valign: "middle" });
      s.addText(st[1], { x: 3.2, y: y + 0.08, w: 9.2, h: 0.45, fontFace: FONT, fontSize: 14, bold: true, color: C.ink, valign: "middle" });
      s.addText(st[2], { x: 3.2, y: y + 0.5, w: 9.2, h: 0.38, fontFace: FONT, fontSize: 11.5, color: C.muted, valign: "middle" });
      y += 1.02;
    });
    footer(s, 13);
  }

  // ===================================================================
  // P14 总结
  // ===================================================================
  {
    const s = pres.addSlide();
    s.background = { color: C.primary };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: PW, h: 0.18, fill: { color: C.cyan } });
    s.addShape(pres.shapes.OVAL, { x: -1.2, y: 4.5, w: 4.5, h: 4.5, fill: { color: "24456B" } });
    s.addShape(pres.shapes.OVAL, { x: 11.0, y: -1.0, w: 3.8, h: 3.8, fill: { color: "1B3454" } });
    s.addImage({ data: ic.flag, x: 0.9, y: 0.9, w: 0.7, h: 0.7 });
    s.addText("总结与展望", { x: 1.75, y: 0.85, w: 10, h: 0.8, fontFace: FONT, fontSize: 32, bold: true, color: C.white, valign: "middle" });
    s.addText("把 LLM 的不确定性，封装进确定性的教学设计。", {
      x: 0.95, y: 1.8, w: 11.5, h: 0.6, fontFace: FONT, fontSize: 16, color: C.cyan,
    });
    const sums = [
      "产品：覆盖拼音 / 英语口语 / 多语种的 AI 语言教练，全龄段自适应",
      "技术：四层架构 + 记忆分区 + 防模板化 + SVM 校验 + 四层护栏 + 七维评估",
      "落地：基于火山引擎扣子（Coze）平台，知识库 + 工作流 + 数据库 + 语音一体化",
      "价值：更会教而非更聪明，填补方言矫正与银发学习的市场空白",
    ];
    let yy = 2.7;
    sums.forEach((t) => {
      s.addShape(pres.shapes.RECTANGLE, { x: 0.95, y: yy, w: 11.4, h: 0.72, fill: { color: "284E78" } });
      s.addImage({ data: ic.check, x: 1.15, y: yy + 0.2, w: 0.34, h: 0.34 });
      s.addText(t, { x: 1.65, y: yy, w: 10.5, h: 0.72, fontFace: FONT, fontSize: 13.5, color: "E2E8F0", valign: "middle" });
      yy += 0.88;
    });
    s.addText("感谢评委 · 全龄段多语言学习智能体团队 · 2026 火山杯 Agent 创新大赛", {
      x: 0.95, y: 6.55, w: 11.4, h: 0.4, fontFace: FONT, fontSize: 12, color: "94A3B8", align: "center",
    });
  }

  const out = "docs/火山杯答辩PPT.pptx";
  await pres.writeFile({ fileName: out });
  console.log("PPT 生成完成 ->", out);
})();
