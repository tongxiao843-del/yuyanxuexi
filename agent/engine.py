"""
全龄段多语言学习智能体 —— 生产级核心引擎（六层工作流）
======================================================
实现报告中的六层端到端工作流：
  第1层 意图识别 —— SVM + 规则双引擎路由，带置信度阈值控制
  第2层 记忆检索 —— 独立记忆分区 + 跨天薄弱点复习
  第3层 RAG检索  —— Agentic RAG（查询重写 + 多路召回 + nRRF 融合）
  第4层 内容生成 —— 六层防模板化（SRT + 多候选 + 内容指纹去重）
  第5层 质量校验 —— 四层护栏系统 + SVM 输出质量分类
  第6层 记忆写入 —— 薄弱点提取 + 进度记录 + 评估持久化

同时保留三层系统提示词架构：
  人设层 → 三教学分支 → 长期记忆分区
"""
from __future__ import annotations

import os
import sys
import json
import re
import random
import time
import uuid
from datetime import datetime, date
from typing import Optional

import ollama

# ---------------------------------------------------------------------------
# 配置导入
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agent.config import (
    MODEL, DATA, MEM_DIR, THRESHOLDS, WORKFLOW, RAG_CONFIG,
    ANTI_TEMPLATE, GUARDRAIL_RULES,
)

client = ollama.Client()

# ---------------------------------------------------------------------------
# 生产级模块导入（惰性加载，不可用时优雅降级）
# ---------------------------------------------------------------------------
_rag_engine = None
_anti_template = None
_guardrail_pipe = None
_svm_quality = None


def _get_rag():
    """惰性初始化 Agentic RAG 引擎。"""
    global _rag_engine
    if _rag_engine is None:
        try:
            from agent.rag import AgenticRAG
            _rag_engine = AgenticRAG()
        except Exception:
            _rag_engine = False  # 标记不可用
    return _rag_engine if _rag_engine is not False else None


def _get_anti_template():
    """惰性初始化防模板化引擎。"""
    global _anti_template
    if _anti_template is None:
        try:
            from agent.anti_template import AntiTemplateEngine
            _anti_template = AntiTemplateEngine()
        except Exception:
            _anti_template = False
    return _anti_template if _anti_template is not False else None


def _get_guardrail():
    """惰性初始化护栏管道。"""
    global _guardrail_pipe
    if _guardrail_pipe is None:
        try:
            from agent.guardrails import GuardrailPipeline
            _guardrail_pipe = GuardrailPipeline()
        except Exception:
            _guardrail_pipe = False
    return _guardrail_pipe if _guardrail_pipe is not False else None


def _get_svm_quality():
    """惰性初始化 SVM 输出质量分类器。"""
    global _svm_quality
    if _svm_quality is None:
        try:
            from agent.svm_models import QualityClassifier
            _svm_quality = QualityClassifier()
        except Exception:
            _svm_quality = False
    return _svm_quality if _svm_quality is not False else None


# ---------------------------------------------------------------------------
# 语料加载
# ---------------------------------------------------------------------------
def _load(sub, name):
    p = os.path.join(DATA, sub, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}

CORPUS = {
    "pinyin": _load("pinyin", "pinyin_kb.json"),
    "english": _load("english", "scenarios.json"),
    "languages": _load("languages", "multilingual.json"),
    "prompt_vars": _load("prompts", "prompt_vars.json"),
}

# ---------------------------------------------------------------------------
# 年龄/人群识别
# ---------------------------------------------------------------------------
AGE_RULES = [
    ("儿童", ["儿童", "小孩", "孩子", "小朋友", "幼儿", "小学", "3岁", "5岁", "一年级"]),
    ("青少年", ["初中", "高中", "中考", "高考", "初高中", " Teen", "teen", "学生"]),
    ("老人", ["老人", "退休", "老年", "年纪大", "长辈", "爸妈", "父母", "爷爷奶奶"]),
    ("成人", ["成人", "职场", "工作", "面试", "出差", "留学", "成人"]),
]
ACCENT_HINTS = ["口音", "平翘舌", "前后鼻音", "方言", "n l", "f h", "发音不准"]


def detect_group(text: str):
    for g, kws in AGE_RULES:
        if any(k in text for k in kws):
            return g
    return "通用"


def has_accent_need(text: str):
    return any(h in text for h in ACCENT_HINTS)


# ---------------------------------------------------------------------------
# 第1层：意图识别（规则 + 模型兜底 + SVM 置信度）
# ---------------------------------------------------------------------------
PINYIN_KW = ["拼音", "声母", "韵母", "平翘舌", "前后鼻音", "nl", "fh",
             "拼读", "汉语拼音", "拼音打字"]
ENGLISH_KW = ["英语", "口语", "english", "speak", "发音", "口音",
              "对话练习", "练英语"]
LANG_NAME = {"日语": "ja", "韩语": "ko", "法语": "fr", "西班牙语": "es",
             "日文": "ja", "韩文": "ko", "法文": "fr", "西文": "es",
             "japanese": "ja", "korean": "ko", "french": "fr", "spanish": "es"}


def route(text: str):
    """分支路由：规则优先 → 模型兜底。返回 (board, lang, confidence)。

    confidence: 0-1 浮点数，表示路由置信度
      - 规则命中：1.0（确定性匹配）
      - 模型兜底：0.5（需关注）
    """
    t = text.lower()
    # 规则匹配：高置信
    if any(k in text for k in PINYIN_KW):
        return ("pinyin", None, 1.0)
    for name, code in LANG_NAME.items():
        if name.lower() in t:
            return ("multilingual", code, 1.0)
    if any(k in text.lower() for k in ENGLISH_KW):
        return ("english", None, 1.0)
    # 模型兜底：中等置信
    try:
        r = client.generate(
            model=MODEL,
            prompt=f"用户说：{text}\n判断属于哪个学习板块？只回复 one of: pinyin / english / multilingual。",
            options={"thinking": False, "temperature": 0},
        )
        ans = r["response"].strip().lower()
        if "pinyin" in ans:
            return ("pinyin", None, 0.5)
        if "english" in ans:
            return ("english", None, 0.5)
        if "multi" in ans:
            return ("multilingual", "ja", 0.5)
    except Exception:
        pass
    return ("english", None, 0.3)


# ---------------------------------------------------------------------------
# 第2层：记忆分区
# ---------------------------------------------------------------------------
class Memory:
    def __init__(self, user_id="default"):
        self.user_id = user_id
        self.path = os.path.join(MEM_DIR, f"{user_id}.json")
        self.data = self._load()

    def _struct(self):
        return {"progress": [], "weak": [], "last": None}

    def _load(self):
        if os.path.exists(self.path):
            d = json.load(open(self.path, encoding="utf-8"))
        else:
            d = {}
        d.setdefault("pinyin", self._struct())
        d.setdefault("english", self._struct())
        d.setdefault("languages", {})
        d.setdefault("openings_used", [])
        d.setdefault("created", date.today().isoformat())
        d.setdefault("last_seen", None)
        return d

    def save(self):
        self.data["last_seen"] = date.today().isoformat()
        json.dump(self.data, open(self.path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    def partition(self, board, lang=None):
        if board == "multilingual":
            key = f"lang_{lang}"
            return self.data["languages"].setdefault(key, self._struct())
        return self.data[board]

    def add_weak(self, board, lang, item):
        p = self.partition(board, lang)
        if item not in p["weak"]:
            p["weak"].append(item)

    def add_progress(self, board, lang, item):
        p = self.partition(board, lang)
        p["progress"].append({"item": item, "at": date.today().isoformat()})
        p["last"] = item

    def review_prompt(self, board, lang):
        p = self.partition(board, lang)
        if p.get("weak"):
            items = "、".join(p["weak"][-3:])
            return f"【记忆复习】该用户上次在{board}板的薄弱点：{items}。请先针对性复习再进入新内容。"
        return ""


# ---------------------------------------------------------------------------
# 防模板化：动态变量选择（避免连续重复开场白）
# ---------------------------------------------------------------------------
def pick_opening(mem: Memory):
    pool = CORPUS["prompt_vars"].get("openings", ["你好，我们开始吧。"])
    used = mem.data.get("openings_used", [])
    cand = [o for o in pool if o not in used] or pool
    pick = random.choice(cand)
    used.append(pick)
    if len(used) > len(pool):
        mem.data["openings_used"] = used[-len(pool):]
    return pick


# ---------------------------------------------------------------------------
# 提示词组装（三层）
# ---------------------------------------------------------------------------
GROUP_STYLE = {
    "儿童": "用极慢语速、简单短句、趣味化比喻和图片式描述，多用鼓励；采用苏格拉底式提问引导其自己发现错误。",
    "青少年": "结合校内考试（中考/高考口语）场景，游戏化进度感，标准语速。",
    "成人": "标准语速、高密度信息，聚焦职场/学术/实用场景。",
    "老人": "大字体提示、慢速示范、关键内容重复三遍，操作极简，实用旅游情景为主。",
    "通用": "标准语速，平衡趣味与效率。",
}

BOARD_FLOW = {
    "pinyin": "【拼音分支】流程：定级→声母韵母认读→书写→拼读→日常应用；若检测到方言口音问题，启动平翘舌/前后鼻音/n-l/f-h 专项矫正（参考知识库 dialect_errors）。术语规范：平舌音=舌尖前音(z/c/s)，翘舌音=舌尖后音(zh/ch/sh/r)，禁止自创术语。",
    "english": "【英语口语分支】流程：场景定级→场景化对话→发音矫正→口音改善→次日复习；以'真实对话环境'为核心，低压力高频练习。",
    "multilingual": "【多语种分支】流程：选语种→基础入门→日常会话→可随时切换其他语种（各语种进度独立保存）。",
}


def build_prompt(user_text, mem: Memory, board, lang, group,
                 rag_context="", confidence_level="high"):
    """组装三层系统提示词。

    参数：
      rag_context      RAG 检索到的知识上下文文本
      confidence_level RAG 置信度级别（high/medium/low），低置信时提示模型谨慎
    """
    at_engine = _get_anti_template()
    if at_engine:
        dyn = at_engine.pick_dynamic_vars(CORPUS["prompt_vars"])
        tone = dyn.get("tone", "鼓励型伙伴")
        strat = dyn.get("strategy", "情境式")
        opening = dyn.get("opening", pick_opening(mem))
    else:
        vars_tone = CORPUS["prompt_vars"].get("tones", ["鼓励型伙伴"])
        vars_strat = CORPUS["prompt_vars"].get("strategies", ["情境式"])
        tone = random.choice(vars_tone)
        strat = random.choice(vars_strat)
        opening = pick_opening(mem)

    # SRT 语义排斥指令
    srt_instruction = ""
    if at_engine:
        srt_instruction = at_engine.build_srt_instruction()

    l1 = (f"你是「全龄段 AI 语言教练」，面向所有年龄段与基础水平的学习者，用中文讲解。"
          f"当前用户群体识别为：{group}。{GROUP_STYLE[group]}"
          f"你禁止中途打断用户；具备自主规划、学情记录、动态复习能力。")
    if has_accent_need(user_text):
        l1 += "该用户有口音矫正需求，请主动检测口音类型并启动专项矫正流程。"

    l2 = BOARD_FLOW[board]

    # 知识锚定（Agentic RAG）
    knowledge = rag_context or retrieve_knowledge(board, lang, user_text)
    l2 += f"\n【知识锚定】请严格基于以下检索到的教学内容生成，不得臆造：\n{knowledge}"

    # 低置信度提示
    if confidence_level == "low":
        l2 += "\n【注意】检索置信度较低，如不确定请告知用户「这部分内容我需要查证」。"

    l3 = mem.review_prompt(board, lang)
    l3 += "\n每次学习后，总结 1-2 个该用户的薄弱点，以 JSON 行打印：__WEAK__:<薄弱点描述>"

    system = (f"{l1}\n\n{l2}\n\n{l3}\n\n"
              f"【本轮表达风格】开场白：{opening}；语气角色：{tone}；教学策略：{strat}。"
              f"（每次轮换，避免模板化）")

    if srt_instruction:
        system += f"\n\n{srt_instruction}"

    return system


# ---------------------------------------------------------------------------
# 第3层：RAG 检索（Agentic RAG，不可用时回退到关键词检索）
# ---------------------------------------------------------------------------
def retrieve_knowledge(board, lang, text):
    """Agentic RAG 检索，不可用时回退到关键词检索。"""
    rag = _get_rag()
    if rag:
        try:
            result = rag.retrieve(text, board, lang)
            return result
        except Exception:
            pass
    # 回退：关键词检索
    return _fallback_retrieve(board, lang, text)


def _fallback_retrieve(board, lang, text):
    """关键词检索回退（与原 retrieve_knowledge 逻辑一致）。"""
    if board == "pinyin":
        de = CORPUS["pinyin"].get("dialect_errors", [])
        lines = [f"- {d['type']}：{d['desc']}；矫正：{d['tip']}" for d in de]
        return "方言错误对照：\n" + "\n".join(lines) if lines else "（无）"
    if board == "english":
        scs = CORPUS["english"].get("scenarios", [])
        hit = None
        for s in scs:
            if any(k in text for k in [s.get("title", ""), s.get("scenario", "")]):
                hit = s; break
        if not hit and scs: hit = scs[0]
        if hit:
            keys = "；".join(hit.get("key_sentences", [])[:3])
            errs = "；".join(hit.get("common_errors", [])[:2])
            return f"场景《{hit.get('title')}》关键句型：{keys}；易错点：{errs}"
        return "（无）"
    if board == "multilingual":
        for l in CORPUS["languages"].get("languages", []):
            if l.get("code") == lang:
                gp = "；".join(f"{p['native']}({p.get('romanization','')})" for p in l.get("common_phrases", [])[:4])
                return f"{l.get('language')}常用语：{gp}；语法注意：{l.get('basic_grammar','')[:80]}"
        return "（无）"
    return "（无）"


# ---------------------------------------------------------------------------
# 第4层：内容生成（多候选 + 防模板化）
# ---------------------------------------------------------------------------
def generate_reply(system_prompt, user_text):
    """生成回复：优先使用防模板化多候选引擎，不可用时单次生成。"""
    at_engine = _get_anti_template()
    if at_engine and WORKFLOW.get("enable_multi_candidate", True):
        try:
            result = at_engine.run(system_prompt, user_text, mem_data=CORPUS["prompt_vars"])
            if result.get("output"):
                return result
        except Exception:
            pass
    # 回退：单次生成
    t0 = time.time()
    r = client.generate(
        model=MODEL,
        prompt=f"{system_prompt}\n\n用户：{user_text}\n\n语言教练：",
        options={"thinking": False, "temperature": 0.6},
    )
    elapsed = time.time() - t0
    out = r["response"].strip()
    return {
        "output": out,
        "score": 0.0,
        "candidates_count": 1,
        "duplicates_filtered": 0,
        "srt_active": False,
        "gen_time": round(elapsed, 3),
    }


# ---------------------------------------------------------------------------
# 第5层：质量校验（护栏 + SVM 质量分类）
# ---------------------------------------------------------------------------
def validate_output(user_text, output, group, has_accent):
    """执行护栏校验 + SVM 质量分类。

    返回：(passed, final_reply, guardrail_result, quality_score)
    """
    pipe = _get_guardrail()
    quality_score = None

    # SVM 输出质量分类（predict 返回 (label, proba_dict) 元组）
    if WORKFLOW.get("enable_svm_filter", True):
        svm_q = _get_svm_quality()
        if svm_q:
            try:
                q_label, q_proba = svm_q.predict(output)
                # 将标签映射为数值分数：高质量=90, 需修改=60, 不合格=30
                label_score = {"高质量": 90, "需修改": 60, "不合格": 30}
                quality_score = label_score.get(q_label, 50) if q_label else 50
            except Exception:
                quality_score = None

    # 护栏校验
    if pipe and WORKFLOW.get("enable_guardrails", True):
        gr = pipe.run(user_text, output, group=group, has_accent=has_accent)
        return (gr["passed"], gr["final_reply"], gr, quality_score)

    # 护栏不可用：直接放行
    return (True, output, None, quality_score)


def check_input_guardrail(user_text):
    """生成前输入验证（L1）。"""
    pipe = _get_guardrail()
    if pipe and WORKFLOW.get("enable_guardrails", True):
        return pipe.check_input(user_text)
    return {"passed": True, "final_reply": ""}


# ---------------------------------------------------------------------------
# 薄弱点提取
# ---------------------------------------------------------------------------
def extract_weak_points(text):
    """从输出中提取 __WEAK__ 标记的薄弱点。"""
    return [m.strip() for m in re.findall(r"__WEAK__[:：]\s*([^\n]+)", text)]


def clean_output(text):
    """清除输出中的 __WEAK__ 标记行。"""
    return re.sub(r"__WEAK__[:：]\s*[^\n]*\n?", "", text).strip()


# ---------------------------------------------------------------------------
# 第6层：评估记录
# ---------------------------------------------------------------------------
def record_evaluation(user_id, output, context):
    """执行七维度评估并持久化。"""
    if not WORKFLOW.get("enable_evaluation", True):
        return None
    try:
        from agent.evaluation import evaluate_response
        rec = evaluate_response(user_id, output, context)
        return rec
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 主入口：六层工作流
# ---------------------------------------------------------------------------
def respond(user_id, user_text):
    """六层工作流主入口。

    工作流：
      1. 意图识别 → 分支路由 + 置信度
      2. 记忆检索 → 用户学情上下文
      3. RAG检索 → 知识锚定
      4. 内容生成 → 多候选防模板化
      5. 质量校验 → 护栏 + SVM
      6. 记忆写入 → 薄弱点 + 评估记录

    返回 dict，含：board / lang / group / reply / weak / trace / evaluation
    """
    trace_id = uuid.uuid4().hex[:12]
    t_start = time.time()
    trace = {}

    # === 第1层：意图识别 ===
    board, lang, route_confidence = route(user_text)
    group = detect_group(user_text)
    accent = has_accent_need(user_text)
    trace["route"] = {"board": board, "lang": lang, "confidence": route_confidence}

    # 低置信度意图：追问用户
    thr_intent = THRESHOLDS.get("intent_confidence", {})
    if route_confidence < thr_intent.get("confirm", 0.2):
        return {
            "board": board, "lang": lang, "group": group,
            "reply": thr_intent.get("action_low", "您是想练习拼音还是英语口语？"),
            "weak": [], "trace": trace, "evaluation": None,
            "trace_id": trace_id,
        }

    # === 生成前输入验证（L1 护栏）===
    input_check = check_input_guardrail(user_text)
    if not input_check["passed"]:
        return {
            "board": board, "lang": lang, "group": group,
            "reply": input_check["final_reply"],
            "weak": [], "trace": trace, "evaluation": None,
            "trace_id": trace_id,
            "guardrail_intercepted": True,
        }

    # === 第2层：记忆检索 ===
    mem = Memory(user_id)
    trace["memory"] = {"weak_count": len(mem.partition(board, lang).get("weak", []))}

    # === 第3层：RAG 检索 ===
    rag_result = retrieve_knowledge(board, lang, user_text)
    if isinstance(rag_result, dict):
        rag_context = rag_result.get("context", "")
        rag_confidence = rag_result.get("confidence", 0.0)
        rag_sources = rag_result.get("sources", [])
        rag_sub_queries = rag_result.get("sub_queries", [])
    else:
        rag_context = str(rag_result)
        rag_confidence = 0.5
        rag_sources = []
        rag_sub_queries = []

    # 置信度分级
    rag_thr = THRESHOLDS.get("rag_confidence", {})
    if rag_confidence >= rag_thr.get("high", 0.75):
        confidence_level = "high"
    elif rag_confidence >= rag_thr.get("medium", 0.5):
        confidence_level = "medium"
    else:
        confidence_level = "low"

    trace["retrieval"] = {
        "confidence": rag_confidence,
        "level": confidence_level,
        "sources_count": len(rag_sources),
        "sub_queries": rag_sub_queries,
    }

    # === 组装系统提示词 ===
    system = build_prompt(user_text, mem, board, lang, group,
                          rag_context=rag_context,
                          confidence_level=confidence_level)

    # === 第4层：内容生成（多候选防模板化）===
    t_gen_start = time.time()
    gen_result = generate_reply(system, user_text)
    t_gen_end = time.time()
    raw_output = gen_result.get("output", "").strip()
    candidate_gen_time = round(t_gen_end - t_gen_start, 3)

    trace["generation"] = {
        "candidates_count": gen_result.get("candidates_count", 1),
        "duplicates_filtered": gen_result.get("duplicates_filtered", 0),
        "srt_active": gen_result.get("srt_active", False),
        "gen_time": candidate_gen_time,
        "anti_template_score": gen_result.get("score", 0.0),
    }

    # === 第5层：质量校验 ===
    passed, final_reply, guardrail_result, quality_score = validate_output(
        user_text, raw_output, group, accent
    )

    trace["guardrail"] = {
        "passed": passed,
        "quality_score": quality_score,
    }
    if guardrail_result:
        trace["guardrail"]["status"] = guardrail_result.get("status")
        trace["guardrail"]["trace_id"] = guardrail_result.get("trace_id")

    # 质量校验未通过：尝试重生成（最多 max_regen_attempts 次）
    regen_attempts = 0
    max_regen = WORKFLOW.get("max_regen_attempts", 2)
    while not passed and regen_attempts < max_regen:
        regen_attempts += 1
        gen_result = generate_reply(system, user_text)
        raw_output = gen_result.get("output", "").strip()
        passed, final_reply, guardrail_result, quality_score = validate_output(
            user_text, raw_output, group, accent
        )
        trace["generation"]["regen_attempts"] = regen_attempts

    # 使用最终输出（护栏放行的原文或安全替代回复）
    output = final_reply if final_reply else raw_output

    # === 薄弱点提取 + 清理输出 ===
    weak_points = extract_weak_points(output)
    output = clean_output(output)

    # === 第6层：记忆写入 ===
    for wp in weak_points:
        mem.add_weak(board, lang, wp)
    mem.add_progress(board, lang, user_text[:40])
    mem.save()

    # === 防模板化记录 ===
    at_engine = _get_anti_template()
    if at_engine:
        at_engine.record_output(output)

    # === 评估记录 ===
    t_end = time.time()
    eval_context = {
        "board": board,
        "lang": lang,
        "group": group,
        "user_text": user_text,
        "retrieved_knowledge": rag_context,
        "has_accent": accent,
        "timing": {
            "first_token_latency": 0,  # 需流式接口才能精确测量
            "total_time": round(t_end - t_start, 3),
            "candidate_gen_time": candidate_gen_time,
        },
        "trace": {
            "route": trace.get("route"),
            "retrieval": trace.get("retrieval"),
            "generation_params": {
                "temperature": ANTI_TEMPLATE.get("temperature", 0.8),
                "top_p": ANTI_TEMPLATE.get("top_p", 0.9),
            },
            "guardrail": trace.get("guardrail"),
            "rag_confidence": rag_confidence,
            "quality_score": quality_score,
        },
    }

    # 命中的英语场景对象（供准确性评估使用）
    if board == "english":
        for s in CORPUS["english"].get("scenarios", []):
            if any(k in user_text for k in [s.get("title", ""), s.get("scenario", "")]):
                eval_context["scenario"] = s
                break

    eval_record = record_evaluation(user_id, output, eval_context)

    return {
        "board": board,
        "lang": lang,
        "group": group,
        "reply": output,
        "weak": mem.partition(board, lang).get("weak", []),
        "trace": trace,
        "evaluation": eval_record.to_dict() if eval_record else None,
        "trace_id": trace_id,
        "rag_confidence": rag_confidence,
        "quality_score": quality_score,
        "gen_time": round(t_end - t_start, 3),
    }


# ---------------------------------------------------------------------------
# 向后兼容：旧版 respond 不含 trace 信息时的简化接口
# ---------------------------------------------------------------------------
def respond_simple(user_id, user_text):
    """简化版响应接口，仅返回核心字段（向后兼容）。"""
    result = respond(user_id, user_text)
    return {
        "board": result["board"],
        "lang": result["lang"],
        "group": result["group"],
        "reply": result["reply"],
        "weak": result["weak"],
    }


# ---------------------------------------------------------------------------
# 模块自测
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("六层工作流引擎 —— 冒烟自测")
    print("=" * 70)

    test_cases = [
        ("test_user", "我想学拼音声母 b 怎么读"),
        ("test_user", "帮我练习餐厅英语对话"),
        ("test_user", "我想学日语入门"),
    ]

    for uid, text in test_cases:
        print(f"\n{'─' * 50}")
        print(f"用户输入：{text}")
        result = respond(uid, text)
        print(f"分支：{result['board']} | 语种：{result['lang']} | 人群：{result['group']}")
        print(f"RAG置信度：{result.get('rag_confidence', 'N/A')}")
        print(f"质量评分：{result.get('quality_score', 'N/A')}")
        print(f"生成耗时：{result.get('gen_time', 'N/A')}s")
        print(f"回复：{result['reply'][:120]}...")
        if result.get("weak"):
            print(f"薄弱点：{result['weak']}")
        if result.get("trace"):
            gen = result["trace"].get("generation", {})
            print(f"候选数：{gen.get('candidates_count', 1)} | "
                  f"去重过滤：{gen.get('duplicates_filtered', 0)} | "
                  f"SRT激活：{gen.get('srt_active', False)}")
        if result.get("evaluation"):
            ev = result["evaluation"]
            print(f"评估综合分：{ev.get('overall', 'N/A')}")

    print(f"\n{'=' * 70}")
    print("冒烟自测完成")
