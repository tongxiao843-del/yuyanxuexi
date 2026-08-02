# 全龄段多语言学习智能体 — 火山杯 Coze 平台移植指南

> **文档用途**：这是给 AI IDE（Trae）的迁移开发需求文档。
> 把本地生产级代码（`agent/`、`config.py`，基于 Ollama+Chroma+SVM）的"设计意图"
> 翻译成 **火山引擎扣子 Coze 平台** 上可配置、可发布的形态。
> 本地栈用来快速验证逻辑与提示词；最终参赛作品必须运行在 Coze 平台。

---

## 0. 赛事硬约束（来自官方海报）

| 项 | 要求 |
|---|---|
| 主办平台 | 火山引擎 / 扣子 Coze（豆包大模型 doubao 为主） |
| 评审权重 | 创新性 20% · 技术实现 30% · 实用价值 30% · 用户体验 20% |
| 提交物 | 作品视频(3-5min) + 介绍材料 + 演示 PPT |
| 差异化定位 | "更会教，而非更聪明"——把教学体系 + 适老化/全龄段作为核心卖点 |

**关键结论**：GitHub 高星 skills/rules 不是评审重点；重点是把三层提示词、分支路由、
记忆分区、护栏/评估这些**设计**在 Coze 上落地。

---

## 1. 架构映射（本地栈 → Coze 等价组件）

| 本地组件 | Coze 等价实现 | 备注 |
|---|---|---|
| Ollama qwen3:1.7b | 豆包大模型（doubao）节点 | Coze 默认，免本地 GPU |
| 三层提示词 | Bot「人设与回复逻辑」 | 见 §3 完整模板 |
| 分支路由 `route()` | 意图识别 / 工作流条件分支 | 见 §4 |
| Chroma 向量库 RAG | Coze **知识库** | 见 §6 上传清单 |
| 记忆分区 `Memory` | Coze **数据库（数据表）** | 见 §7 schema |
| SVM 校验 | 代码节点调用外部 API / 简化规则 | 竞赛演示可弱化，见 §8 |
| 四层护栏 | 内容安全 + 工作流校验节点 | 见 §8 |
| 防模板化变量池 | 提示词变量 + 工作流随机选择 | 见 §9 |
| Edge-TTS 语音 | Coze 语音合成插件 / 播报节点 | 可选 |
| Streamlit 演示 | Coze 网页/API 发布 + 作品视频 | 最终形态 |

---

## 2. Coze Bot 元信息（直接填写）

- **Bot 名称**：全龄段 AI 语言教练
- **简介**：面向儿童/青少年/成人/老人/方言用户的多语言学习智能体，覆盖拼音、英语口语、日韩法西，具备长期记忆与薄弱点复习。
- **图标/开场白**：调用 `data/prompts/prompt_vars.json` 中的 `openings` 字段随机轮换。

---

## 3. 三层系统提示词（直接粘贴到「人设与回复逻辑」）

> 将下方模板整体复制进 Coze Bot 的「人设与回复逻辑」。其中 `{变量}` 由 Coze 变量/工作流注入。

```
你是「全龄段 AI 语言教练」，面向所有年龄段与基础水平的学习者，用中文讲解。
当前用户群体识别为：{group}。{group_style}
你禁止中途打断用户；具备自主规划、学情记录、动态复习能力。
{accent_note}

【教学分支】
{board_flow}

【知识锚定】请严格基于下方检索到的教学内容生成，不得臆造：
{knowledge}

{low_conf_note}

【记忆复习】
{review_note}

每次学习后，总结 1-2 个该用户的薄弱点，以独立一行 JSON 打印：
__WEAK__:<薄弱点描述>

【本轮表达风格】开场白：{opening}；语气角色：{tone}；教学策略：{strategy}。
（每轮轮换，避免模板化）
```

### 3.1 人群风格映射（`GROUP_STYLE`）

| group | group_style |
|---|---|
| 儿童 | 用极慢语速、简单短句、趣味化比喻和图片式描述，多用鼓励；采用苏格拉底式提问引导其自己发现错误。 |
| 青少年 | 结合校内考试（中考/高考口语）场景，游戏化进度感，标准语速。 |
| 成人 | 标准语速、高密度信息，聚焦职场/学术/实用场景。 |
| 老人 | 大字体提示、慢速示范、关键内容重复三遍，操作极简，实用旅游情景为主。 |
| 通用 | 标准语速，平衡趣味与效率。 |

### 3.2 三个教学分支流程（`BOARD_FLOW`）

- **拼音(pinyin)**：定级→声母韵母认读→书写→拼读→日常应用；若检测到方言口音问题，启动平翘舌/前后鼻音/n-l/f-h 专项矫正（参考知识库 dialect_errors）。术语规范：平舌音=舌尖前音(z/c/s)，翘舌音=舌尖后音(zh/ch/sh/r)，禁止自创术语。
- **英语(english)**：场景定级→场景化对话→发音矫正→口音改善→次日复习；以"真实对话环境"为核心，低压力高频练习。
- **多语种(multilingual)**：选语种→基础入门→日常会话→可随时切换其他语种（各语种进度独立保存）。

---

## 4. 分支路由规则（Coze 意图识别 / 工作流条件分支）

| 触发关键词（命中即路由） | 目标板块 board | 语种 lang |
|---|---|---|
| 拼音、声母、韵母、平翘舌、前后鼻音、nl、fh、拼读、汉语拼音、拼音打字 | pinyin | — |
| 日语/日文、韩语/韩文、法语/法文、西班牙语/西文（含 ja/ko/fr/es） | multilingual | ja/ko/fr/es |
| 英语、口语、english、speak、发音、口音、对话练习、练英语 | english | — |
| 以上都不命中 | english（兜底，置信度低，需追问） | — |

**Coze 落地**：在「人设」里写好分支描述，用工作流 `意图识别` 节点或 `选择器` 节点实现；
兜底分支向用户追问"您是想练习拼音、英语口语，还是其他语言？"

---

## 5. 全龄段自适应规则

**年龄识别关键词 → group**：
- 儿童：儿童、小孩、孩子、小朋友、幼儿、小学、3岁、5岁、一年级
- 青少年：初中、高中、中考、高考、初高中、student、teen
- 成人：成人、职场、工作、面试、出差、留学
- 老人：老人、退休、老年、年纪大、长辈、爸妈、父母、爷爷奶奶
- 默认：通用

**口音需求标记**（`has_accent_need`）：用户含"口音/平翘舌/前后鼻音/方言/n l/f h/发音不准" → 人设追加"该用户有口音矫正需求，请主动检测口音类型并启动专项矫正流程"。

---

## 6. 知识库上传清单（对应 `data/` 语料）

| 本地文件 | Coze 知识库名称 | 内容 | 切片建议 |
|---|---|---|---|
| `data/pinyin/pinyin_kb.json` | 拼音知识库 | 23声母/复韵母/5类方言错误对照 | 每条声母/韵母/错误对照独立切片 |
| `data/english/scenarios.json` | 英语口语场景库 | 8 场景卡（每卡7轮对话+关键句+易错点） | 每个场景作为一个文档 |
| `data/languages/multilingual.json` | 多语种教材库 | 日/韩/法/西 A1 教材（问候/数字/短语/语法） | 每个语种作为一个文档 |
| `data/prompts/prompt_vars.json` | （不入库） | 防模板化变量池 | 转为 Coze 提示词变量，见 §9 |

> 上传格式：把 JSON 转成 Markdown/文本段落后上传即可，Coze 知识库会自动向量化（等价于本地 Chroma + all-MiniLM）。

---

## 7. 记忆数据库 Schema（Coze 数据表）

对应本地 `Memory` 结构。在 Coze「数据库」中建一张用户表：

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | string | 主键 |
| pinyin_progress | json | [{item, at}] 进度 |
| pinyin_weak | json | [薄弱点字符串] |
| english_progress | json | 同上 |
| english_weak | json | 同上 |
| languages | json | {lang_ja:{progress,weak,last}, ...} 各语种独立 |
| openings_used | json | [已用开场白] 防重复 |
| created | string | 创建日期 |
| last_seen | string | 最近活跃日期 |

**复习逻辑**：每次对话前读取 `weak` 字段末尾 3 条 → 注入人设"记忆复习"段；
对话后提取 `__WEAK__:` 标记 → 追加写入 `weak` 字段。

---

## 8. 阈值控制与护栏规则（Coze 工作流可实现）

### 8.1 六环节阈值（`THRESHOLDS`，竞赛演示可简化为提示词约束）

1. 意图置信度：>0.5 放行；0.2–0.5 二次确认；<0.2 追问用户
2. 发音错误检测：异常分超 99 百分位 → 标记"需纠错"送精细分析
3. 输出质量：>80 直接输出；60–80 观察；<60 重生成；连续 3 次<60 告警
4. 内容重复度：余弦相似度 >0.85 判定重复需重生成（比对最近 20 次）
5. RAG 置信度：>0.75 高；0.5–0.75 中；<0.5 低（提示"需查证"）
6. 安全护栏：任何安全规则命中即拦截，记录日志并输出安全替代回复

### 8.2 护栏规则（`GUARDRAIL_RULES`）

- **L1 输入验证**：检测注入模式（`忽略.*指令`/`ignore instructions`/`系统提示词`/`system prompt`/`你.*真实身份`）；识别超范围话题（数学题、写代码、看病、法律、投资、股票）→ 礼貌拒答并引导回语言学习。
- **L2 输出过滤**：用豆包做 LLM-as-Judge 校验教学准确性与事实性。
- **L3 行为策略**：儿童禁复杂语法/成人话题/职场/面试；老人回复须含步骤编号且关键内容重复。
- **L4 可观测**：记录每次输入/输出/中间决策，供评估。

> Coze 落地：L1 用工作流正则/关键字节点；L2 用"模型节点"二次校验；L3 在人设里写死；L4 用运行日志。

---

## 9. 防模板化策略（Coze 提示词变量）

将 `data/prompts/prompt_vars.json` 的变量池设为 Coze 提示词变量：
- `tones`（语气角色，如 鼓励型伙伴/严谨导师/轻松玩伴）
- `strategies`（教学策略，如 情境式/归纳式/游戏化）
- `openings`（开场白，12 条轮换）
- `scenes`（场景）、`roles`（角色）

工作流中每轮随机选取组合注入人设，配合 §3 的"本轮表达风格"段，实现去模板化。
（本地 SRT/语义排斥/多候选生成在 Coze 上可用"多候选生成节点 + 相似度过滤"近似替代。）

---

## 10. 七维度评估（Coze 落地方式）

`EVAL_DIMENSIONS` = accuracy / efficiency / safety / fairness / explainability / groundedness / compliance

- **竞赛演示**：用 `agent/evaluation.py` 在本地对 demo 输出打分，结果写入 `data/evaluation_logs/` 作为答辩证据。
- **Coze 落地**：在作品视频与介绍材料中展示评估维度与达标情况（如状态识别≥85%、闭环成功率≥80% 等，来自 Ima「小暑期」银发剪辑导师方案的指标口径，可复用为自评框架）。

---

## 11. 给 Trae 的开发任务清单（可直接复制下达）

**任务 A — 创建 Coze Bot 骨架**
> 在 Coze 新建 Bot「全龄段 AI 语言教练」，把 §3 人设模板 + §2 元信息填入，模型选 doubao。

**任务 B — 配置知识库**
> 按 §6 把 `data/pinyin`、`data/english`、`data/languages` 三个 JSON 转为文本上传为三个知识库。

**任务 C — 搭建分支工作流**
> 用意图识别/选择器节点实现 §4 路由；拼音/英语/多语种三分支各自调用对应知识库并注入 §3.2 流程。

**任务 D — 接入记忆数据库**
> 按 §7 建数据表；对话前读 weak 注入复习段，对话后写回 `__WEAK__:` 提取的薄弱点。

**任务 E — 全龄段自适应**
> 实现 §5 年龄识别与口音标记，注入人设 group_style 与 accent_note。

**任务 F — 护栏与防模板化**
> 实现 §8 护栏（L1 输入校验 + L2 输出 Judge + L3 人群策略）；按 §9 配置提示词变量随机轮换。

**任务 G — 产出参赛材料**
> 录制 3-5min 演示视频（覆盖三板块 + 老人/儿童适老演示）；用 `report_extracted.md`/`report_tech.md` 为素材做介绍材料与 PPT。

---

## 12. 与本地代码的对应关系（便于 Trae 反查）

| Coze 概念 | 本地代码文件 | 关键函数/常量 |
|---|---|---|
| 人设提示词 | `agent/engine.py` | `build_prompt()`, `GROUP_STYLE`, `BOARD_FLOW` |
| 分支路由 | `agent/engine.py` | `route()`, `PINYIN_KW`, `ENGLISH_KW`, `LANG_NAME` |
| 年龄/口音 | `agent/engine.py` | `AGE_RULES`, `ACCENT_HINTS`, `detect_group()` |
| 记忆 | `agent/engine.py` | `Memory`, `review_prompt()`, `add_weak()` |
| 阈值 | `agent/config.py` | `THRESHOLDS`, `ANTI_TEMPLATE` |
| 护栏规则 | `agent/config.py` | `GUARDRAIL_RULES` |
| 知识库映射 | `agent/config.py` | `RAG_CONFIG` |
| 评估 | `agent/evaluation.py` | `EVAL_DIMENSIONS` |
| 防模板化 | `agent/anti_template.py` | 六层引擎（Coze 用变量近似） |
| SVM 校验 | `agent/svm_models.py` | 竞赛演示可弱化 |

---

## 13. 语音发音评测落地方案（方案一：工作流旁路接入）

> **目标**：让用户用语音跟读 → 智能体**不把语音转成文字**，而是直接判断"哪个音发错了"并给出舌位指导 + 标准示范（TTS 朗读）。
> 这正是产品差异化的核心卖点（report_tech.md §工具集成层 / §发音评测）。

### 13.0 关键约束（动手前必读）

- Coze 自带的「语音对话」是 **语音 → ASR 转写 → LLM → TTS** 的端到端链路，**中间拿不到原始音频**，无法旁路给发音评测 API。
- 因此「不转文字、直接评测发音」**不能只靠 Coze 默认语音通道**，必须走**旁路架构**：由你自己的入口先采集音频，再送工作流评测。
- 若仅接受"先转文字、再让 LLM 判内容错误"，则直接在 Bot 设置开启语音对话即可（见 §13.6 备注），但那判断不了发音准不准。

### 13.1 旁路架构图

```
[用户在小程序/网页跟读录音]
        │  MediaRecorder 录制
        ▼
[你的后端 / 对象存储]  ←── 拿到 audio_url + reference_text(参考句)
        │  Coze API 调用工作流，传 {audio_url, reference_text, user_id, board}
        ▼
[Coze 工作流]
   ├─ 开始节点(入参)
   ├─ HTTP 请求节点 ──► 外部发音评测 API（腾讯云/讯飞）
   │       │  返回：音素级 JSON（每个字的 accuracy / error 标记，非转写文本）
   │       ▼
   ├─ 大模型节点 ──► 注入 §3 三层提示词 + 评测 JSON → 生成"错音+舌位+示范+跟读"
   │       ▼
   └─ 语音合成节点(TTS) ──► 朗读指导给用户
```

### 13.2 第 0 步：准备外部发音评测 API

| 厂商 | 产品 | 你需要拿到 | 返回形态 |
|---|---|---|---|
| 腾讯云 | 语音评测（SentenceRecognition `eval` 模式） | SecretId / SecretKey | 字级 `words[].pronunciation`(准度)、`match`(0-100) |
| 讯飞开放平台 | 语音评测（Android/iOS/Web 版，也支持服务端） | APPID / APIKey / APISecret | 音素级 `phone`(音素)、`score`、`content`(错误类型) |

> 这两者返回的都**不是转写文本**，而是"每个音素/字的准确度与错误类型"——正好满足"不转文字、直接评音"的诉求。
> 具体字段以各厂商最新文档为准；下例用通用结构示意。

### 13.3 第 1 步：搭建录音入口（拿 audio_url）

- **小程序/网页端**：用 `MediaRecorder` 录用户跟读音频（建议单句 3–8 秒），上传到你的对象存储（腾讯云 COS / 阿里 OSS）或后端接口，得到可公网访问的 `audio_url`。
- 同时把该句**参考文本** `reference_text`（如用户要读的 "thank you" / "zhī shi"）一起带上——评测 API 需要它来比对对错。
- 调用 Coze 工作流（API 方式，见 Coze「工作流 → API 调用」生成的 endpoint），入参：
  ```json
  {
    "audio_url": "https://your-bucket.cos.ap-xxx/my/file.wav",
    "reference_text": "thank you",
    "user_id": "demo_user",
    "board": "english"
  }
  ```

### 13.4 第 2 步：Coze 工作流节点搭建（核心，在 coze.cn 后台）

**节点 1 · 开始（Start）**：声明入参 `audio_url`(string)、`reference_text`(string)、`user_id`(string)、`board`(string)。

**节点 2 · HTTP 请求（调发音评测 API）**：
- 方法：`POST`
- URL：厂商评测接口地址（如腾讯云 `https://asr.tencentcloudapi.com` 走签名；讯飞走 WS/HTTP）
- Headers：鉴权字段（腾讯云 `Authorization` 签名头 / 讯飞 `Authorization: apikey=xxx`）
- Body（示意）：
  ```json
  { "audio_url": "{{audio_url}}", "reference_text": "{{reference_text}}", "mode": "eval" }
  ```
- 输出变量：`eval_result`（JSON 字符串，含音素级 accuracy/error）

> 腾讯云签名较复杂，建议放在「代码节点（Python）」里用官方 SDK 调，比纯 HTTP 节点更稳；讯飞 Web 版可直接在前端拿结果再传工作流。

**节点 3 · 大模型（LLM）节点**：
- 模型：`doubao`（与 Bot 一致）
- **系统提示词**：粘贴 §3 三层模板，**追加**下方 13.5 的"评测注入段"
- **用户提示词 / 变量**：
  ```
  用户跟读参考句：{{reference_text}}
  发音评测结果(JSON，非转写)：{{eval_result}}
  当前板块：{{board}}
  请基于以上评测结果生成指导（见系统提示词要求）。
  ```
- 输出变量：`coach_reply`（指导文本）

**节点 4 · 语音合成（TTS）节点**：
- 用 Coze 原生「语音合成」/「播报」节点（或 §1 映射的 Edge-TTS 等价插件），把 `coach_reply` 转成语音。
- 老人适配：调用前可据 §5 的 group 把语速参数调慢（若插件支持）。

### 13.5 第 3 步：提示词注入模板（复制进大模型节点的系统提示词末尾）

```
【发音评测指导模式】
你收到的是「发音评测 API 返回的 JSON 结果」，不是用户原话的转写文本。
它包含每个音素/字的准确度(accuracy)与错误标记(error)。请严格据此判断：
1) 哪些音素/字 错误(error) 或 偏差(低 accuracy)；
2) 对应发音部位与舌位指导——例如平舌(z/c/s,舌尖前) vs 翘舌(zh/ch/sh/r,舌尖后)、
   前鼻(-n) vs 后鼻(-ng)、n-l / f-h 混淆；术语须规范，禁止自创；
3) 给出该参考句的标准发音示范文本（将送 TTS 朗读，勿加多余解释）；
4) 设计一句针对性跟读练习。
未出现在评测结果中的音素，不得臆测；评测无误则给予肯定鼓励。
```

### 13.6 第 4 步：挂载与发布

- 把工作流挂到 Bot 的「对话入口」（API 触发型），替代默认的纯文本/默认语音链路。
- 发布到你的小程序/网页渠道（即 13.3 的录音入口所在渠道）。
- **备注（备选简化版）**：若暂时不接外部 API，可在 Bot 设置直接开启 Coze 默认「语音对话」做演示——它走 ASR 转文字，LLM 只能判**文字内容**对错（语法/用词），**判不了发音准不准**。该简化版仅建议作为临时演示，答辩时务必讲清 13.1 旁路架构才是"不转文字评发音"的真实方案。

### 13.7 与现有设计的衔接（无需另起炉灶）

- **复用 §1 映射第 36 行**：`Edge-TTS 语音 → Coze 语音合成插件 / 播报节点` —— 13.4 节点 4 的 TTS 直接复用。
- **复用 §1 映射第 33 行**：`SVM 校验 → 代码节点调用外部 API` —— 13.4 节点 2 的"代码节点调外部发音评测 API"正是同一模式。
- **复用 §3 / §5 / §7**：三层提示词、人群风格、记忆分区全部现成，只需在 13.5 追加"评测注入段"，并把 `eval_result` 作为新变量注入。

### 13.8 给 Trae 的新增任务（接在 §11 之后）

**任务 H — 接入语音发音评测（方案一）**
> 按 §13.0–13.6 实现旁路架构：① 申请腾讯云/讯飞发音评测 API 密钥；② 在录音入口上传音频得 audio_url+reference_text；③ Coze 工作流建「开始→代码/HTTP节点调评测API→大模型节点(注入 §13.5)→TTS节点」；④ 挂载到 Bot 对话入口并发布到录音渠道。
> 答辩亮点：强调"返回音素级误差而非转写文本"，对应 report_tech.md 发音评测/口音检测/声浪对比的产品定位。

---

### 13.9 方案 B：在现有工作流内嵌评测路径（不新建工作流）

适用：已在 Coze 搭好主工作流（开始 → 选择器 → 知识库检索 → 大模型×N → 代码 → 结束），希望**直接在原工作流里加节点**而非另起工作流。

**设计图**
```
[开始]  (新增入参 audio_url / reference_text / board)
   │
   └─► [输入类型判断 选择器]
          ├─ 分支A: audio_url 非空 ──► [代码节点:调发音评测API] ──► [大模型节点(注入§13.5)] ──► (可选[TTS]) ──► [结束]
          └─ 分支B: audio_url 为空  ──► [原选择器→知识库→大模型→代码→结束]   (现有文本路径，不变)
```

**操作步骤（在 coze.cn 工作流画布）**
1. **改「开始」节点**：新增三个选填入参 `audio_url`(string)、`reference_text`(string)、`board`(string)，保留原文本入参。
2. **加「输入类型判断」选择器**（放到开始之后、原选择器之前）：
   - 分支A 条件：`audio_url` 不为空 → 语音评测路径
   - 分支B 条件：`audio_url` 为空 → 原选择器（把原选择器作为分支B 的下级节点接上）
   - 操作：点画布底部「+ 添加节点」→ 选「选择器」→ 拖连线：开始→该选择器；该选择器分支B→原选择器。
3. **分支A 搭节点**（从判断选择器分支A 拉出）：
   - 「代码」节点（Python，用官方 SDK 调腾讯云/讯飞评测 API），入参 `audio_url`+`reference_text`，输出 `eval_result`。
   - 「大模型」节点：系统提示词 = 现有三层提示词 + §13.5「发音评测指导模式」；用户提示词变量 `参考句={{reference_text}}`、`评测结果={{eval_result}}`、`板块={{board}}`；输出 `coach_reply`。
   - （可选）「语音合成」节点把 `coach_reply` 转音频；最后接「结束」。
4. **分支B（原文本路径）**：一字不动，保留原选择器/知识库/大模型/代码/结束。

**关键现实约束**
- Coze 内置语音对话会先把语音 **ASR 转成文字** 再进工作流，此时 `audio_url` 为空，自动走分支B——只能判**文字内容**错误（语法/用词），**判不了发音准不准**。
- 要真正"不转文字、直接评音"，必须让开始节点收到 `audio_url`，即改用 **API 触发 + 外部录音入口**（见 §13.3）：你的小程序/网页录完音把 `audio_url` 传进来，才能走分支A 拿到音素级结果。

**与 §13 关系**：§13.0–13.7 描述"独立工作流"形态；本 13.9 是同一套评测逻辑在**既有工作流内嵌**的等价做法，复用同样的代码节点、提示词(§13.5)、TTS 节点。

---

### 13.10 讯飞语音评测稳定落地（云函数 + Coze 转发）

讯飞 ISE 是 **WebSocket + 签名鉴权**，Coze 代码节点沙箱直接调用容易出网络/依赖问题。最稳定的方案是：**腾讯云 SCF 云函数做代理，Coze 只做 HTTP fetch**。

#### 13.10.1 云函数代码（Node.js 20+，事件函数，无外部依赖）

```javascript
const { createHmac } = require("crypto");

const APPID = process.env.XF_APPID;
const APIKEY = process.env.XF_APIKEY;
const APISECRET = process.env.XF_APISECRET;
const HOST = "ise-api.xfyun.cn";
const PATH = "/v2/open-ise";  // 注意：不是 /v2/ise

function boardToLang(b) {
  b = (b || "").toLowerCase();
  if (b.includes("pinyin") || b.includes("拼音")) return { language: "zh_cn", category: "read_syllable" };
  if (b.includes("english") || b.includes("英语")) return { language: "en_us", category: "read_word" };
  return { language: "zh_cn", category: "read_sentence" };
}

function stripWavHeader(buf) {
  if (buf.slice(0, 4).toString() === "RIFF") return buf.slice(44);
  return buf;
}

async function evalSpeech(audioBase64, referenceText, language, category) {
  return new Promise((resolve, reject) => {
    const date = new Date().toUTCString();
    const sigOrigin = `host: ${HOST}\ndate: ${date}\nGET ${PATH} HTTP/1.1`;
    const signature = createHmac("sha256", APISECRET).update(sigOrigin).digest("base64");
    const authOrigin = `api_key="${APIKEY}", algorithm="hmac-sha256", headers="host date request-line", signature="${signature}"`;
    const authorization = Buffer.from(authOrigin).toString("base64");
    const wsUrl = `wss://${HOST}${PATH}?authorization=${encodeURIComponent(authorization)}&date=${encodeURIComponent(date)}&host=${encodeURIComponent(HOST)}`;

    const ws = new WebSocket(wsUrl);
    let acc = "";
    ws.on("open", () => {
      ws.send(JSON.stringify({
        common: { app_id: APPID },
        business: { language, category, evalue_mode: "1", rstcd: "utf8", group: "1", subjective_score: "1" },
        data: { status: 0, text: Buffer.from(referenceText, "utf-8").toString("base64") }
      }));
      ws.send(JSON.stringify({ data: { status: 2, audio: audioBase64, encoding: "raw", sample_rate: 16000 } }));
    });
    ws.on("message", (d) => {
      const m = JSON.parse(d.toString());
      if (m.code !== 0) return reject(new Error(m.message));
      if (m.data && m.data.sig) acc += m.data.sig;
      if (m.data && m.data.status === 2) { ws.close(); resolve(acc); }
    });
    ws.on("error", (e) => reject(e));
    setTimeout(() => reject(new Error("timeout")), 15000);
  });
}

function parseResult(sig) {
  const tm = sig.match(/<total_score>([\d.]+)<\/total_score>/);
  const overall = tm ? parseFloat(tm[1]) : 0;
  const words = [];
  const re = /<word[^>]*>\s*<content>([^<]*)<\/content>[\s\S]*?<total_score>([\d.]+)<\/total_score>/g;
  let wm;
  while ((wm = re.exec(sig)) !== null) words.push({ word: wm[1], score: parseFloat(wm[2]) });
  return { overall_score: overall, words };
}

exports.main_handler = async (event) => {
  try {
    const body = JSON.parse(event.body || "{}");
    const { audio_url, reference_text, board } = body;
    if (!audio_url || !reference_text)
      return { statusCode: 200, body: JSON.stringify({ error: "missing params" }) };
    const resp = await fetch(audio_url);
    const buf = stripWavHeader(Buffer.from(await resp.arrayBuffer()));
    const audioBase64 = buf.toString("base64");
    const { language, category } = boardToLang(board);
    const sig = await evalSpeech(audioBase64, reference_text, language, category);
    const parsed = parseResult(sig);
    return { statusCode: 200, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...parsed, reference_text, language, audio_url }) };
  } catch (e) {
    return { statusCode: 200, body: JSON.stringify({ error: String(e && e.message || e) }) };
  }
};
```

#### 13.10.2 Coze 代码节点（只做 HTTP 转发）

```typescript
async function main({ params }: Args) {
  const FUNC_URL = "https://你的API网关地址/";
  const resp = await fetch(FUNC_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      audio_url: params.audio_url,
      reference_text: params.reference_text,
      board: params.board
    })
  });
  const data = await resp.json();
  return { eval_result: JSON.stringify(data) };
}
```

#### 13.10.3 部署步骤

1. SCF 新建 **Node.js 20 事件函数**，粘贴 §13.10.1 代码。
2. 函数配置 → 环境变量：`XF_APPID`、`XF_APIKEY`、`XF_APISECRET`（从讯飞控制台获取，不要硬编码）。
3. 触发管理 → 创建 **API 网关触发**（勾选启用集成响应），拿到 HTTPS 地址。
4. 把该地址填进 Coze 代码节点的 `FUNC_URL`。
5. 录音端请输出 **16k / 16bit / 单声道 PCM 的 WAV**，云函数会自动去掉 44 字节 WAV 头。

#### 13.10.4 与 §13.9 关系

本 §13.10 是 §13.9 分支A「代码节点」的**稳定实现方式**：Coze 节点不直接 WebSocket 调讯飞，而是通过 HTTP 转发给 SCF 代理，SCF 完成签名、WebSocket、音频下载、结果解析。后面接 §13.9 的「大模型节点（注入 §13.5）」即可生成发音指导。

### 13.11 绕开 Coze 外网限制：前端直调云函数（推荐当前最稳）

#### 13.11.0 背景与问题
- 实测：Coze 工作流的「HTTP 请求」节点访问 `*.ap-guangzhou.tencentscf.com` 自定义域名时**统一报「设备环境异常，请稍后再试」**，日志仅含入口信息（logId/from:bot-api），无错误堆栈。
- 关键判断：云端本地 `curl` 测试云函数**正常返回**（`missing params` / `HTTP 404`），说明**云函数本体、依赖、讯飞链路均正常**，问题在 **Coze 平台对工作流外网自定义域名的访问限制/白名单**。
- 这意味着「让 Coze 工作流直接调外部 HTTP」这条路在当前账号/环境下走不通，需改架构。

#### 13.11.1 新架构（旁路评测，Coze 只做 LLM）
```
用户跟读录音
  → 前端（小程序/网页）直接 POST 腾讯云函数（传 audio_base64，免对象存储上传）
  → 云函数调讯飞返回 eval_result JSON
  → 前端把评测结果作为【文本消息】发给 Coze Bot
  → Coze 只做：根据评测结果生成发音指导 + TTS 朗读
```
Coze 完全不碰外部 HTTP，云函数/讯飞逻辑一行不改，且正是 §13 讲的「旁路评测」设计。

#### 13.11.2 云函数改造（已应用）
- `main_handler` 现同时支持 `audio_base64`（前端直传）与 `audio_url`（下载）两种入参；优先用 `audio_base64`。
- 改造文件：`scf_xf_proxy_clean/index.py`，需**重新打包并重新上传**到 SCF（覆盖原 `xf_ise_proxy.zip`）。
- 打包命令：进入 `scf_xf_proxy_clean/` 目录，`zip -r xf_ise_proxy.zip . -x xf_ise_proxy.zip`（含 `websocket/` 依赖）。

#### 13.11.3 前端演示页（已生成）
- 文件：`frontend/pronunciation_eval_demo.html`（单文件，无依赖）。
- 功能：麦克风录音 → 重采样到 16k → 封装 WAV → base64 → POST 云函数 → 取 `eval_result` → 调 Coze API 生成指导 → 浏览器 TTS 朗读。
- 需替换三处：`SCF_URL`（已填当前地址）、`COZE_TOKEN`（Coze 个人设置里的 PAT）、`COZE_BOT_ID`。
- 运行约束：麦克风需要**安全上下文**——用 `localhost` 或 **HTTPS** 打开页面（`file://` 直接双击通常无法授权麦克风）。本地用 `python -m http.server` 起服务即可。

#### 13.11.4 Coze Bot 侧提示词（识别评测结果）
在 Bot 系统提示词里追加 §13.5 的「发音评测指导模式」，并加一条路由规则：
```
当用户消息以【发音评测结果】开头时，消息内含讯飞返回的 JSON（overall_score / words）。
请直接基于该 JSON 给出发音诊断、标准示范与跟读练习，不要将其当作普通对话。
```
前端 `callCoze()` 会自动构造 `【发音评测结果】参考句：xxx；板块：xxx；评测JSON：{...}` 的用户消息。

#### 13.11.5 部署清单
1. 重新打包 `scf_xf_proxy_clean/` 并上传覆盖 SCF 函数代码（环境变量 XF_* 不变）。
2. 本地起服务打开 `pronunciation_eval_demo.html`，填 `COZE_TOKEN` / `COZE_BOT_ID`。
3. 选板块、填参考句、点录音跟读、提交 → 看评测 JSON 与 Coze 指导。
4. （比赛发布）将本页集成进你的小程序/网页发布渠道，Coze Bot 发布到同一渠道即可。
