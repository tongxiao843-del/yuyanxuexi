const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  LevelFormat, PageBreak, BorderStyle
} = require("docx");

// ---------- 工具函数 ----------
function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 280, after: 140 },
    children: [new TextRun({ text, bold: true, font: "Microsoft YaHei", size: 30, color: "1F4E5F" })]
  });
}
function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, bold: true, font: "Microsoft YaHei", size: 26, color: "2E75B6" })]
  });
}
function body(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120, line: 360 },
    alignment: opts.align || AlignmentType.JUSTIFIED,
    children: [new TextRun({ text, font: "Microsoft YaHei", size: 22, ...opts.run })]
  });
}
function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 80, line: 340 },
    children: [new TextRun({ text, font: "Microsoft YaHei", size: 22 })]
  });
}
function stageTitle(text) {
  // 演讲环节小标题，用正文加粗+蓝色强调
  return new Paragraph({
    spacing: { before: 160, after: 80 },
    children: [new TextRun({ text: "【" + text + "】", bold: true, font: "Microsoft YaHei", size: 23, color: "C0504D" })]
  });
}
function guidance(text) {
  // 演讲提示语，灰色斜体，给演讲者看
  return new Paragraph({
    spacing: { after: 80 },
    children: [new TextRun({ text: "（演讲提示：" + text + "）", italics: true, font: "Microsoft YaHei", size: 19, color: "808080" })]
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Microsoft YaHei" },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Microsoft YaHei" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 600, hanging: 300 } } } }] }
    ]
  },
  sections: [{
    properties: {
      page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
    },
    children: [
      // ===== 封面 =====
      new Paragraph({ spacing: { before: 1200, after: 200 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "全龄段多语言学习智能体", bold: true, font: "Microsoft YaHei", size: 44, color: "1F4E5F" })] }),
      new Paragraph({ spacing: { after: 120 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "——面向所有人的 AI 语言教练", font: "Microsoft YaHei", size: 28, color: "2E75B6" })] }),
      new Paragraph({ spacing: { after: 600 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "2026 火山杯 Agent 创新大赛 · 答辩演讲稿", font: "Microsoft YaHei", size: 24, color: "808080" })] }),
      new Paragraph({ spacing: { after: 80 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "拼音 · 英语口语 · 多语种自由切换", font: "Microsoft YaHei", size: 22 })] }),
      new Paragraph({ spacing: { after: 1200 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "演讲时长建议：8—10 分钟", font: "Microsoft YaHei", size: 20, color: "808080" })] }),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 目录式导读 =====
      heading1("演讲稿结构导读"),
      body("为了让各位评委快速抓住重点，本演讲稿按以下顺序展开，建议您配合演示界面的实时操作同步讲解："),
      bullet("开场致辞——用一句话点明我们解决了什么问题"),
      bullet("行业痛点——传统 App 与通用大模型都没解决的事"),
      bullet("产品定位——我们到底做了一个什么智能体"),
      bullet("三大核心能力——全龄段自适应、三板块+多语种、独立记忆"),
      bullet("真实功能演示——现场带评委走一遍学习流程"),
      bullet("技术亮点——为什么它“更会教”而不是“更聪明”"),
      bullet("市场与差异化——为什么当前没有直接竞品"),
      bullet("总结与展望——我们的核心一句话"),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 第一环节：开场 =====
      heading1("一、开场致辞：一个智能体，陪伴每个人的语言学习"),
      guidance("开场语速放慢，面向评委微笑，先抛出共鸣点，再引出产品。"),
      body("各位评委老师，大家好。我想先问大家一个问题：在座的每一位，是不是都曾有过“想学一门语言却坚持不下去”的时刻？"),
      body("孩子刚学拼音，分不清“平舌”和“翘舌”；年轻人练英语口语，对着镜子不敢开口；退休的父母想出国旅游，连“问路”两个字都拼不全。我们身边，几乎每个人都被语言学习卡过——但市面上的产品，要么只服务孩子，要么只教英语，要么换一门语言就得换一个 App。"),
      body("今天我们带来的，是一个能同时服务三岁孩童和七十岁老人、能把拼音、英语口语和多种外语装进同一个智能体的“全龄段 AI 语言教练”。它不只“有问必答”，更“有计划地教”——并且，它记得你上次学到了哪里。"),
      guidance("此处可现场打开智能体首页，展示“选择学习板块”的简洁入口，体现“渐进式展示”设计。"),

      // ===== 第二环节：痛点 =====
      heading1("二、行业痛点：两个都没被解决好的世界"),
      heading2("（1）传统语言学习 App：有体系，但没有“智能”"),
      body("像多邻国、百词斩这类 App，内容很系统，但有三个通病：第一，学完关掉再打开，进度接不上、薄弱点没人管；第二，学拼音、学英语、学日语要下载三个不同的 App，数据互不打通；第三，它们用同一套风格面对所有人——少儿英语不适合老人，商务英语不适合零基础。"),
      heading2("（2）通用大模型：有“智能”，但没有“体系”"),
      body("豆包、ChatGPT 也能陪你练口语，但它们是“有问必答”的聊天工具，不是“有计划地教”的教学系统。零基础用户最需要的是“告诉我该学什么”，而大模型只会问“你想学什么”。更重要的是，每次新对话它都从零开始，根本不记得你上次哪里错了。"),
      guidance("这里可以用一句对比金句收尾：“传统 App 有体系无智能，通用大模型有智能无体系——而我们要做的，是两者之间的那块拼图。”"),
      body("市场正在洗牌：2026 年第一季度，多邻国日活首次下降 7%，它把原因明确归咎于“生成式 AI 辅导工具的竞争”。但通用大模型自己又教不好——这就是我们产品的窗口期。"),

      // ===== 第三环节：产品定位 =====
      heading1("三、产品定位：一个智能体，三大板块"),
      body("我们的智能体，核心定位只有一句话：把“中文拼音、英语口语、多语种自由切换”三大学习板块，整合进同一个 AI 语言教练里。"),
      stageTitle("板块一：中文拼音"),
      body("面向零基础学习者和方言口音矫正需求者。从声母韵母认读，到拼读应用，重点覆盖南方方言最常见的前后鼻音、平翘舌等痛点。"),
      stageTitle("板块二：英语口语"),
      body("以“练会开口”为核心，而不是背单词。从自然拼读入门，到餐厅点餐、机场问路、职场面试等真实场景对话，解决中国人最头疼的“哑巴英语”。"),
      stageTitle("板块三：多语种自由切换"),
      body("支持日语、韩语、法语、西班牙语等多种语言。学完日语基础，可以一键切换到韩语，再切回英语——每个语种的学习进度独立保存，互不干扰。"),

      // ===== 第四环节：三大核心能力 =====
      heading1("四、三大核心能力（我们的差异化）"),
      heading2("能力一：全龄段自适应——一个智能体覆盖所有人"),
      body("这是市面上绝大多数产品做不到的。我们的智能体通过“基础人设层”实时识别用户的年龄和水平，自动调整教学方式："),
      bullet("对 3—12 岁儿童：放慢语速、用趣味比喻、多用鼓励，用提问引导孩子自己发现错误；"),
      bullet("对 13—18 岁青少年：结合中考、高考口语场景，标准语速、游戏化进度；"),
      bullet("对 19—40 岁成人：聚焦职场沟通、面试模拟、学术讨论，信息密度高；"),
      bullet("对 40 岁以上老人：大字体、慢速示范、关键内容重复三遍，操作极简化，主打实用旅游情景；"),
      bullet("对所有年龄段的口音问题用户：自动检测方言类型，启动专项矫正。"),
      guidance("强调一句话：“从孩童到老人，一个智能体陪伴终身学习，用户不用在多个 App 之间来回切换。”"),

      heading2("能力二：三板块 + 多语种自由切换——市场无直接竞品"),
      body("拼音 App、英语口语 App、小语种 App 各自为政。我们把它们整合为一个智能体，并通过“强制分支判断”保证每个板块的教学独立性，又用统一的记忆层管理跨语种学情。这种设计，在当前市场没有直接的竞品。"),
      guidance("可现场演示：说一句“切换到韩语”，展示进度独立保存后再“回到英语口语”能从上次薄弱点继续。"),

      heading2("能力三：独立记忆分区——越用越懂你"),
      body("这是区别于通用大模型最关键的差异。我们为每位用户在拼音、英语口语、各语种分别建立记忆分区。每次学习后，智能体自动提取薄弱知识点存进去；第二天打开时，它会主动说：“昨天你‘th’发音有偏差，我们先复习一下。”"),
      guidance("这是最能打动评委的能力，建议现场展示“跨天记忆复习”的真实对话截图或录屏。金句：“通用大模型记不住你，而我们的智能体记得你。”"),

      // ===== 第五环节：真实功能演示 =====
      heading1("五、真实功能演示：带评委走一遍"),
      guidance("下面三段演示建议现场实操或播放预录视频，每段 40—60 秒，重点体现“真实可用”而非“概念演示”。"),
      stageTitle("演示一：儿童拼音矫正"),
      body("儿童说“我想学拼音”→ 智能体发起语音定级→ 检测出“南方方言、平翘舌混淆”→ 生成 30 天学习计划→ 当天推送前后鼻音专项练习→ 拼读录音后生成“声浪对比图”，直观标出偏差位置。"),
      stageTitle("演示二：成人英语口语场景对话"),
      body("用户说“我想练餐厅点餐英语”→ 智能体扮演服务员用英语对话→ 用户回答后，智能体纠正语法和发音→ 卡壳时用更简单的话引导→ 结束时生成“薄弱点报告”并存入记忆分区。"),
      stageTitle("演示三：跨天记忆复习"),
      body("第二天打开智能体，它主动发起复习，播放昨天的错误录音对比标准发音，引导重新练习，确认改善后再进入新内容。这就是“越用越懂你”的真实体现。"),

      // ===== 第六环节：技术亮点 =====
      heading1("六、技术亮点：为什么我们“更会教”"),
      body("我们不想把它包装成“套壳大模型”。在 LLM 之上，我们叠加了一整套工程化设计，保证它稳定、可控、可信："),
      bullet("知识锚定（Agentic RAG）：所有教学内容必须基于知识库生成，不臆造，杜绝“AI 幻觉”；"),
      bullet("混合校验（SVM + 阈值控制）：用支持向量机做 8 毫秒级快速判断，再交给大模型精细分析，既快又准；"),
      bullet("六层防模板化：动态提示词、语义排斥、多候选生成、内容指纹去重等，保证用户练 100 次也“每次都有新东西”；"),
      bullet("四层护栏系统：从输入验证、输出过滤到行为策略和可观测，层层防御，确保内容安全合规；"),
      bullet("七维度评估：从准确性、安全性到公平性、可解释性，全面衡量教学质量。"),
      guidance("技术部分点到为止，评委不一定全是技术背景，重点说“我们不是在裸用大模型，而是给它套上了教学体系和质量阀门”。"),

      // ===== 第七环节：市场与差异化 =====
      heading1("七、市场与差异化：为什么我们站得住"),
      body("中国有近 5 亿潜在汉语学习者，英语口语应用用户已突破 1.7 亿，72% 的英语学习者最大痛点是“缺乏真实对话环境”。市场足够大，而“全龄段 + 多板块 + 多语种 + 长期记忆”的组合，目前没有任何一款产品同时做到。"),
      body("我们的核心竞争策略，不是在某个单点做到极致，而是在“结构化教学体系”和“AI 对话智能”的交叉地带建立壁垒——同时覆盖所有人群。"),

      // ===== 第八环节：总结 =====
      heading1("八、总结与展望：一句话记住我们"),
      body("最后，我想用一句话总结我们这个智能体："),
      new Paragraph({ spacing: { before: 120, after: 200 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "“当大模型人人可用时，真正有价值的，是把智能与教学体系融合，并让每一个人都能用。”", bold: true, font: "Microsoft YaHei", size: 26, color: "C0504D" })] }),
      body("我们做的不是一个又一个的语言学习 App，而是用 AI 重新定义了“谁来教、教什么、怎么教、教给谁”。"),
      body("从更远的视角看，一个能同时教中文拼音、英语口语和多国语言、且适配所有年龄段的智能体，天然具备跨文化、跨语种的教育能力。未来，它有机会从中国走向全球的学习者。"),
      guidance("结尾停顿两秒，微笑致谢：“以上是我们的全部展示，感谢各位评委，欢迎提问。”"),
      new Paragraph({ spacing: { before: 300 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "—— 演讲完毕，谢谢聆听 ——", bold: true, font: "Microsoft YaHei", size: 24, color: "1F4E5F" })] }),

      new Paragraph({ children: [new PageBreak()] }),

      // ===== 附录：常见提问预案 =====
      heading1("附录：评委可能提问与应答要点"),
      heading2("Q1：你们和普通大模型（如豆包口语陪练）有什么区别？"),
      body("答：豆包是“有问必答”的聊天工具，我们没有结构化学习路径、没有跨会话记忆、没有全龄段适配。我们叠加了三层提示词、独立记忆分区和教学闭环，是“有计划地教”。"),
      heading2("Q2：多语种切换会不会让教学内容变浅？"),
      body("答：不会。我们用强制分支判断，每个语种有独立的知识库和教学流程，进度独立保存；切换只是换了“教练”，底层学情管理是统一的。"),
      heading2("Q3：防模板化的技术真的有用吗？"),
      body("答：我们用了六层防护，包括动态提示词、语义排斥和内容指纹去重。实测可将连续重复率大幅降低，保证用户长期使用的体验不疲劳。"),
      heading2("Q4：开发周期和成本如何？"),
      body("答：基于成熟的智能体平台与工具链，5—7 天即可完成核心流程开发与验证，成本极低、迭代极快，适合快速验证后逐步推向生产。"),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const out = "D:/ai_code/huoshangbei002/docs/火山杯答辩演讲稿.docx";
  fs.writeFileSync(out, buffer);
  console.log("演讲稿已生成：" + out + "，大小：" + buffer.length + " 字节");
});
