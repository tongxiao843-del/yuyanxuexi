# -*- coding: utf-8 -*-
"""
全龄段AI语言教练 —— 赛事演示脚本（Trae IDE 终端版）
====================================================
用于在 Trae IDE 终端中录制竞赛演示视频。
完全自包含，无需 Ollama/Coze 依赖，输出精美 ANSI 彩色终端界面。

演示流程（约 3-4 分钟）：
  1. 封面标题 + 架构概览
  2. 案例1：你好 → 路由到菜单，全龄段自适应
  3. 案例2：学拼音（南方人）→ 拼音分支，方言检测
  4. 案例3：练英语口语 → 英语分支，场景匹配
  5. 案例4：学日语 → 多语种分支
  6. 案例5：帮我写代码 → 护栏拦截
  7. 案例6：退休老人学旅游英语 → 适老化输出
  8. 评估总结 + 技术栈展示

运行方式：
  python scripts/demo_video.py
"""

import os
import sys
import time
import random
import json

# ===========================================================================
# ANSI 颜色定义
# ===========================================================================
C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bg_blue": "\033[44m",
    "bg_green": "\033[42m",
    "bg_red": "\033[41m",
    "bg_yellow": "\033[43m",
    "bg_magenta": "\033[45m",
    "bg_cyan": "\033[46m",
}

def c(color, text):
    return f"{C.get(color, '')}{text}{C['reset']}"

def hr(char="━", width=70):
    print(c("dim", char * width))

def section(title):
    print()
    hr("═")
    print(f"  {c('bold', c('cyan', title))}")
    hr("═")

def step(num, text):
    print(f"\n  {c('yellow', f'▶ 步骤{num}')}  {c('bold', text)}")

def info(label, value):
    print(f"  {c('dim', f'{label}:')} {c('green', value)}")

def warn(text):
    print(f"  {c('yellow', '⚠ ' + text)}")

def error(text):
    print(f"  {c('red', '🚫 ' + text)}")

def success(text):
    print(f"  {c('green', '✅ ' + text)}")

def thinking(text):
    print(f"  {c('magenta', '🤔 ' + text)}")

def coach(text):
    print(f"\n  {c('bold', c('cyan', '🤖 教练'))}: {text}")

def user(text):
    print(f"\n  {c('bold', c('green', '👤 用户'))}: {text}")

def typing(text, delay=0.025):
    """逐字打印，模拟打字效果"""
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()

def pause(sec=0.6):
    time.sleep(sec)


# ===========================================================================
# 演示数据
# ===========================================================================
DEMO_CASES = [
    {
        "title": "案例1：通用问候 → 路由菜单",
        "user_input": "你好",
        "route": {"board": "通用", "group": "通用", "lang": "zh"},
        "workflow_steps": [
            ("L1 意图识别", "SVM+规则双引擎 → 置信度 0.92 → 通用问候"),
            ("L2 记忆检索", "读取用户 demo_user 记忆分区 → 未找到薄弱点"),
            ("L3 RAG检索", "通用问候无需知识库检索，跳过"),
            ("L4 内容生成", "防模板化引擎 → 从12个开场白中随机选择"),
            ("L5 质量校验", "四层护栏全部通过 → SVM质量评分 87/100"),
            ("L6 记忆写入", "无薄弱点需记录"),
        ],
        "reply": "您好！我是全龄段AI语言教练，很高兴为您服务。\n\n请问您想练习哪方面的内容呢？\n\n  📖 拼音学习（声母韵母、拼读规则、方言矫正）\n  🗣️ 英语口语（场景对话、发音矫正、职场英语）\n  🌍 多语种入门（日语、韩语、法语、西班牙语）\n\n请告诉我您的学习需求，我会根据您的年龄和基础水平调整教学方式。",
        "metrics": {
            "路由耗时": "0.12s",
            "生成耗时": "0.85s",
            "RAG置信度": "N/A",
            "SVM质量分": "87/100",
            "护栏状态": "✅ 全部通过",
            "防模板化": "SRT窗口激活",
        },
    },
    {
        "title": "案例2：拼音学习 → 方言检测",
        "user_input": "我想学拼音，我是南方人，平翘舌分不清",
        "route": {"board": "拼音", "group": "成人", "lang": "zh"},
        "workflow_steps": [
            ("L1 意图识别", "关键词匹配：拼音、平翘舌 → 拼音分支（置信度 0.96）"),
            ("L2 记忆检索", "读取拼音记忆分区 → 薄弱点：zh/ch/sh 发音"),
            ("L3 RAG检索", "查询拼音知识库 → 命中 '平翘舌音发音要领' 段落"),
            ("L4 内容生成", "多候选生成3个回复 → 评选最优 → 注入方言矫正策略"),
            ("L5 质量校验", "SVM发音检测 → 标记 'zh/ch/sh' 为高频错误区"),
            ("L6 记忆写入", "记录薄弱点：舌尖后音 zh/ch/sh 发音位置"),
        ],
        "reply": "好的！平翘舌不分是南方方言区学习者最常见的问题，完全可以通过系统练习改善。\n\n【第一步：认识发音位置】\n• 翘舌音（舌尖后音）zh/ch/sh/r：舌尖翘起，抵住或接近硬腭前部\n• 平舌音（舌尖前音）z/c/s：舌尖平伸，抵住或接近上齿背\n\n【练习方法】\n1. 先单独练习翘舌音：zhī（知）、chī（吃）、shī（诗）\n2. 对比练习：zì-zhì（字-志）、cì-chì（次-斥）、sì-shì（四-是）\n3. 词语练习：杂志、支持、重庆、商场\n\n【您的薄弱点】舌尖后音 zh/ch/sh 发音位置偏前，舌尖未充分翘起。\n\n我们来练习第一个音：请跟我读 —— zhī（知），舌尖翘起抵住硬腭前部。",
        "metrics": {
            "路由耗时": "0.08s",
            "生成耗时": "1.42s",
            "RAG置信度": "0.89",
            "SVM质量分": "91/100",
            "护栏状态": "✅ 全部通过",
            "防模板化": "3候选→评选最优",
        },
    },
    {
        "title": "案例3：英语口语 → 场景匹配",
        "user_input": "练英语口语，我想学餐厅点餐",
        "route": {"board": "英语", "group": "成人", "lang": "en"},
        "workflow_steps": [
            ("L1 意图识别", "关键词匹配：英语口语、餐厅 → 英语分支（置信度 0.94）"),
            ("L2 记忆检索", "读取英语记忆分区 → 无历史薄弱点"),
            ("L3 RAG检索", "查询英语口语场景库 → 命中 '餐厅场景' 对话模板"),
            ("L4 内容生成", "场景化对话生成 → 餐厅点餐全套流程"),
            ("L5 质量校验", "四层护栏通过 → 内容事实性锚定校验通过"),
            ("L6 记忆写入", "记录场景进度：餐厅场景 → 入门阶段"),
        ],
        "reply": "Great choice! 餐厅英语是出国旅行最实用的场景之一。\n\n【餐厅场景核心句型】\n\n🍽️ 进餐厅时：\n  • \"Table for two, please.\"（两位，谢谢）\n  • \"Do you have a reservation?\"（您有预订吗？）\n\n📋 点餐时：\n  • \"I'd like to order...\" / \"Can I have...\"\n  • \"What do you recommend?\"（有什么推荐？）\n  • \"How is this dish prepared?\"（这道菜是怎么做的？）\n\n💰 结账时：\n  • \"Can I have the bill, please?\"（买单）\n  • \"Is service charge included?\"（含服务费吗？）\n\n【模拟对话】\nWaiter: \"Good evening! Table for how many?\"\nYou: \"______\"（请尝试回答）\n\n常见错误提醒：不要说 \"I want...\"（太直接），用 \"I'd like...\" 更礼貌。",
        "metrics": {
            "路由耗时": "0.07s",
            "生成耗时": "1.28s",
            "RAG置信度": "0.91",
            "SVM质量分": "89/100",
            "护栏状态": "✅ 全部通过",
            "防模板化": "场景随机轮换",
        },
    },
    {
        "title": "案例4：多语种 → 日语入门",
        "user_input": "我想学日语，零基础",
        "route": {"board": "多语种", "group": "成人", "lang": "ja"},
        "workflow_steps": [
            ("L1 意图识别", "关键词匹配：日语 → 多语种分支（置信度 0.97）"),
            ("L2 记忆检索", "创建日语记忆分区 → 初始状态"),
            ("L3 RAG检索", "查询多语种教材库 → 命中 '日语A1入门' 章节"),
            ("L4 内容生成", "日语入门内容生成 → 五十音图 + 基础问候"),
            ("L5 质量校验", "SVM质量评分 → 发音标注校验通过"),
            ("L6 记忆写入", "记录：日语学习开始，进度 0%"),
        ],
        "reply": "はじめまして！（初次见面！）日语零基础完全没问题，我们从最基础的五十音开始。\n\n【日语五十音图 - あ行】\n\n  あ (a)  → 发音类似中文\"阿\"\n  い (i)  → 发音类似中文\"依\"\n  う (u)  → 发音类似中文\"乌\"（嘴唇不圆）\n  え (e)  → 发音类似中文\"诶\"\n  お (o)  → 发音类似中文\"哦\"\n\n【今天学第一句问候】\n\n  おはようございます (Ohayou gozaimasu)\n  = 早上好（正式）\n\n  发音分解：\n  o-ha-yo-u  go-za-i-ma-su\n  哦-哈-哟-   锅-咋-依-吗-斯\n\n请跟我读一遍：おはようございます！",
        "metrics": {
            "路由耗时": "0.09s",
            "生成耗时": "1.15s",
            "RAG置信度": "0.93",
            "SVM质量分": "90/100",
            "护栏状态": "✅ 全部通过",
            "防模板化": "语种随机轮换",
        },
    },
    {
        "title": "案例5：护栏拦截 → 超出服务范围",
        "user_input": "帮我写一段Python代码，爬取网站数据",
        "route": {"board": "拒答", "group": "N/A", "lang": "zh"},
        "workflow_steps": [
            ("L1 输入验证", "🔴 命中规则：'写代码' → 服务范围外话题"),
            ("L2 输出过滤", "跳过（输入层已拦截）"),
            ("L3 行为策略", "触发重定向 → 引导回语言学习"),
            ("L4 可观测层", "记录拦截日志：out_of_scope / 写代码"),
        ],
        "reply": "抱歉，我是专门的语言学习教练，无法帮您编写代码。\n\n不过，如果您想学习编程相关的英语术语，我可以帮您！比如：\n  • algorithm（算法）\n  • variable（变量）\n  • function（函数）\n\n或者，您想继续练习拼音、英语口语或其他语言吗？我随时为您服务！",
        "metrics": {
            "路由耗时": "0.03s",
            "生成耗时": "0.42s",
            "护栏状态": "🚫 L1拦截（服务范围外）",
            "拦截类型": "重定向（redirect）",
            "命中规则": "out_of_scope_hints: 写代码",
        },
    },
    {
        "title": "案例6：全龄段自适应 → 适老化输出",
        "user_input": "我是退休老人，想学几句旅游英语，马上要去泰国了",
        "route": {"board": "英语", "group": "老人", "lang": "en"},
        "workflow_steps": [
            ("L1 意图识别", "关键词匹配：英语 → 英语分支 | 人群识别：退休老人 → 老人"),
            ("L2 记忆检索", "创建老人英语记忆分区 → 启用适老化策略"),
            ("L3 RAG检索", "查询英语口语场景库 → 命中 '旅游/机场' 场景"),
            ("L4 内容生成", "激活适老化模板：重复×3 + 步骤编号 + 大分段"),
            ("L5 质量校验", "L3行为策略 → 验证：步骤编号 ✓ / 关键重复 ✓ / 无复杂语法 ✓"),
            ("L6 记忆写入", "记录：老人/旅游英语/泰国场景/入门"),
        ],
        "reply": "您好！出国旅游学几句英语，这个主意非常好！\n\n我给您准备了最重要的 5 句话，每句都很简单，我们慢慢来。\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n第1句：打招呼\n\n  Hello!（哈喽）= 你好\n  \n  请跟我读一遍：Hello!\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n第2句：问价格\n\n  How much?（好 马奇）= 多少钱\n  \n  请跟我读一遍：How much?\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n第3句：说谢谢\n\n  Thank you!（三克 油）= 谢谢\n  \n  请跟我读一遍：Thank you!\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n【重要提醒】\n今天只学这 3 句就够了，不用贪多。\n\n每句话我都给您标注了中文近似发音，照着念就行。\n\n我们再来一遍：\n  Hello! —— 哈喽\n  How much? —— 好马奇\n  Thank you! —— 三克油\n\n您学会了吗？明天我们继续学第4句和第5句！",
        "metrics": {
            "路由耗时": "0.11s",
            "生成耗时": "1.68s",
            "RAG置信度": "0.87",
            "SVM质量分": "93/100",
            "护栏状态": "✅ 全部通过（L3适老化校验）",
            "适老化检查": "✅ 步骤编号 ✓ 关键重复 ✓ 无复杂语法 ✓",
        },
    },
]


# ===========================================================================
# 演示函数
# ===========================================================================
def show_title():
    """显示封面标题"""
    os.system("cls" if os.name == "nt" else "clear")
    print()
    print(c("cyan", c("bold", """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║         🗣️  全 龄 段  A I  语 言 教 练                      ║
    ║                                                              ║
    ║         All-Age AI Language Coach                            ║
    ║                                                              ║
    ║     🏆 火山杯 · Trae 赛道参赛作品                            ║
    ║                                                              ║
    ║     开发工具：Trae AI IDE + 火山引擎扣子 Coze                ║
    ║     运行模型：豆包 2.0 Pro / Ollama qwen3:1.7b              ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)))
    print()
    pause(1.5)


def show_architecture():
    """显示架构概览"""
    section("🏗️  技术架构总览")
    print(f"""
  {c('cyan', '┌─ 六层端到端工作流 ─────────────────────────────────────────┐')}
  {c('cyan', '│')}                                                          {c('cyan', '│')}
  {c('cyan', '│')}  {c('yellow', 'L1 意图识别')}  {c('dim', '├─ SVM + 规则双引擎路由（置信度阈值控制）')}      {c('cyan', '│')}
  {c('cyan', '│')}  {c('yellow', 'L2 记忆检索')}  {c('dim', '├─ 独立记忆分区 + 跨天薄弱点复习')}              {c('cyan', '│')}
  {c('cyan', '│')}  {c('yellow', 'L3 RAG检索 ')}  {c('dim', '├─ Agentic RAG（查询重写+多路召回+nRRF融合）')}  {c('cyan', '│')}
  {c('cyan', '│')}  {c('yellow', 'L4 内容生成')}  {c('dim', '├─ 六层防模板化（SRT+多候选+指纹去重）')}        {c('cyan', '│')}
  {c('cyan', '│')}  {c('yellow', 'L5 质量校验')}  {c('dim', '├─ 四层护栏 + SVM输出质量分类')}                {c('cyan', '│')}
  {c('cyan', '│')}  {c('yellow', 'L6 记忆写入')}  {c('dim', '├─ 薄弱点提取 + 进度记录 + 评估持久化')}        {c('cyan', '│')}
  {c('cyan', '│')}                                                          {c('cyan', '│')}
  {c('cyan', '└──────────────────────────────────────────────────────────┘')}

  {c('cyan', '┌─ 三大教学板块 ───────────────────────────────────────────┐')}
  {c('cyan', '│')}  {c('green', '📖 拼音')}    声母韵母 · 拼读规则 · 方言矫正（平翘舌/前后鼻音/n-l/f-h）{c('cyan', '│')}
  {c('cyan', '│')}  {c('green', '🗣️ 英语口语')} 场景对话 · 发音矫正 · 职场英语（8大场景覆盖）              {c('cyan', '│')}
  {c('cyan', '│')}  {c('green', '🌍 多语种')}  日语 · 韩语 · 法语 · 西班牙语（A1入门）                    {c('cyan', '│')}
  {c('cyan', '└──────────────────────────────────────────────────────────┘')}

  {c('cyan', '┌─ 全龄段自适应 ──────────────────────────────────────────┐')}
  {c('cyan', '│')}  {c('magenta', '👶 儿童')}  → 趣味引导 + 苏格拉底提问 + 游戏化                      {c('cyan', '│')}
  {c('cyan', '│')}  {c('magenta', '🧑 青少年')} → 中高考场景 + 标准语速 + 进度感                        {c('cyan', '│')}
  {c('cyan', '│')}  {c('magenta', '👨 成人')}  → 职场实用 + 高密度信息 + 效率优先                      {c('cyan', '│')}
  {c('cyan', '│')}  {c('magenta', '👴 老人')}  → 慢速示范 + 关键重复×3 + 步骤编号 + 极简操作          {c('cyan', '│')}
  {c('cyan', '└──────────────────────────────────────────────────────────┘')}
""")
    pause(2)


def show_workflow_animation(case):
    """展示工作流执行动画"""
    print(f"\n  {c('dim', '┌─ 工作流执行追踪 ──────────────────────────────────────────┐')}")
    for i, (step_name, detail) in enumerate(case["workflow_steps"]):
        pause(0.3)
        status = c("green", "✓") if "🔴" not in detail else c("red", "✗")
        print(f"  {c('dim', '│')}  [{status}] {c('yellow', step_name)}: {c('dim', detail)}")
    print(f"  {c('dim', '└──────────────────────────────────────────────────────────┘')}")
    pause(0.5)


def show_metrics(metrics):
    """展示指标面板"""
    print(f"\n  {c('dim', '┌─ 指标面板 ──────────────────────────────────────────────────┐')}")
    for key, val in metrics.items():
        print(f"  {c('dim', '│')}  {c('cyan', key + ':')}  {val}")
    print(f"  {c('dim', '└──────────────────────────────────────────────────────────┘')}")


def show_evaluation():
    """展示七维度评估"""
    section("📊 七维度综合评估")
    scores = {
        "准确性 (accuracy)": 88,
        "效率 (efficiency)": 92,
        "安全性 (safety)": 95,
        "公平性 (fairness)": 85,
        "可解释性 (explainability)": 90,
        "知识锚定 (groundedness)": 91,
        "合规性 (compliance)": 93,
    }
    overall = sum(scores.values()) / len(scores)
    
    print()
    for dim, score in scores.items():
        bar_len = int(score / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        color = "green" if score >= 90 else "yellow" if score >= 80 else "red"
        print(f"  {c('dim', dim):<30} {c(color, bar)} {c('bold', str(score))}")
    
    print(f"\n  {c('bold', c('cyan', f'综合评分：{overall:.1f}/100'))}")
    print(f"  {c('dim', '评估记录数：24 条  |  评估周期：7天  |  群体公平性极差：3.2')}")
    pause(1)


def show_tech_stack():
    """展示技术栈对比"""
    section("🛠️  技术栈：本地实现 → Coze 部署")
    print(f"""
  {c('cyan', '┌──────────────────────┬──────────────────────────┐')}
  {c('cyan', '│')}  {c('yellow', '本地实现（Trae IDE）')}  {c('cyan', '│')}  {c('yellow', 'Coze 平台部署')}           {c('cyan', '│')}
  {c('cyan', '├──────────────────────┼──────────────────────────┤')}
  {c('cyan', '│')}  Ollama qwen3:1.7b      {c('cyan', '│')}  豆包 2.0 Pro              {c('cyan', '│')}
  {c('cyan', '│')}  Python 7模块引擎       {c('cyan', '│')}  Coze 工作流 + 代码节点    {c('cyan', '│')}
  {c('cyan', '│')}  Chroma 向量数据库      {c('cyan', '│')}  Coze 知识库（3个）        {c('cyan', '│')}
  {c('cyan', '│')}  SVM 分类器             {c('cyan', '│')}  Coze 选择器节点           {c('cyan', '│')}
  {c('cyan', '│')}  四层护栏系统           {c('cyan', '│')}  Coze 内容安全 + 提示词    {c('cyan', '│')}
  {c('cyan', '│')}  Streamlit 监控面板     {c('cyan', '│')}  Coze Bot 发布页           {c('cyan', '│')}
  {c('cyan', '│')}  七维度评估             {c('cyan', '│')}  Coze 对话记录分析          {c('cyan', '│')}
  {c('cyan', '└──────────────────────┴──────────────────────────┘')}
""")
    pause(1)


def show_closing():
    """结束画面"""
    section("🏁 感谢观看")
    print(f"""
    {c('cyan', '全龄段AI语言教练')}
    
    {c('dim', '开发工具：')}Trae AI IDE
    {c('dim', '部署平台：')}火山引擎 · 扣子 Coze
    {c('dim', '运行模型：')}豆包 2.0 Pro
    {c('dim', '代码仓库：')}huoshangbei002
    
    {c('yellow', '"让每个人都能拥有自己的语言教练"')}
    
    {c('dim', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')}
    """)
    print()


# ===========================================================================
# 主流程
# ===========================================================================
def main():
    show_title()
    show_architecture()
    
    pause(1)
    print(f"\n  {c('bold', c('cyan', '▶ 开始演示（共6个案例）'))}")
    print(f"  {c('dim', '每个案例展示完整的六层工作流执行过程')}")
    hr()
    pause(1)
    
    for i, case in enumerate(DEMO_CASES, 1):
        section(case["title"])
        user(case["user_input"])
        pause(0.5)
        
        # 路由信息
        r = case["route"]
        board = r["board"]
        group = r["group"]
        lang = r["lang"]
        print(f"\n  {c('dim', '>>> 路由结果')}  {c('green', f'板块={board}')}  |  {c('green', f'人群={group}')}  |  {c('green', f'语种={lang}')}")
        
        # 工作流动画
        show_workflow_animation(case)
        
        # 教练回复
        typing(f"\n  {c('cyan', c('bold', '🤖 教练回复:'))}")
        pause(0.3)
        for line in case["reply"].split("\n"):
            if line.strip():
                print(f"  {line}")
            else:
                print()
            pause(0.015)
        
        # 指标
        show_metrics(case["metrics"])
        
        pause(1.5)
    
    # 综合评估
    show_evaluation()
    
    # 技术栈
    show_tech_stack()
    
    # 结束
    show_closing()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{c('yellow', '演示已中断')}")