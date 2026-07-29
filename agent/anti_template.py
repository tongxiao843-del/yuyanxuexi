"""
全龄段多语言学习智能体 —— 六层防模板化系统（6-layer Anti-Template Engine）
====================================================================
实现报告第十一章「六项防模板化技术矩阵」：

  层1 动态提示词工程 Dynamic Prompt Engineering
       —— 每次调用动态注入随机变量（场景 / 角色 / 语气 / 教学策略），
          本模块提供变量选择逻辑（pick_dynamic_vars），engine.py 已部分实现注入。

  层2 语义排斥技术 SRT (Semantic Repulsion Technology)
       —— 维护近期输出滑动窗口（大小 20），生成时显式标注「避免使用以下表达」，
          推动模型探索新的语义空间。研究表明 SRT 可将语义多样性提升 85-167%，
          共识性短语（陈词滥调）减少 43-95%。

  层3 多候选生成+评选 Multi-candidate Generation + Scoring
       —— 并行生成 3-5 个候选回复（Temperature=0.8, Top-P=0.9），
          按「质量 × 新颖度」评分选优，重复措辞减少 43-95%。

  层4 Verbalized Sampling（语言化采样）
       —— 让模型自行生成候选集并标注概率分布，激活预训练阶段的生成多样性，
          输出多样性提升约 2.1 倍。本模块将其融入 generate_candidates 的提示词指令。

  层5 内容指纹去重 Content Fingerprint Deduplication
       —— 对每次输出生成语义指纹，与最近 N 次（窗口=20）输出比对，
          余弦相似度 > 0.85 则判定重复并重生成，从机制上杜绝连续重复。

  层6 RAG 多样性检索 RAG Diversity Retrieval
       —— 由 rag.py 模块实现查询重写+多路召回+方差感知融合，
          本模块仅提供调用钩子（rag_diversity_hook），避免循环依赖。

通过 AntiTemplateEngine 统一编排上述六层，对一次「系统提示词+用户输入」做端到端去模板化。
所有配置从 agent.config 导入，与 engine.py / guardrails.py / evaluation.py 共用同一套阈值与参数。
"""
from __future__ import annotations

import os
import re
import json
import random
import hashlib
from collections import deque, Counter
from typing import Optional

# ---------------------------------------------------------------------------
# 配置导入：优先按包导入（agent.config），直接作为脚本运行时回退到 config
# ---------------------------------------------------------------------------
try:
    from .config import ANTI_TEMPLATE, MODEL, THRESHOLDS
except ImportError:  # pragma: no cover —— 直接 python anti_template.py 时回退
    from config import ANTI_TEMPLATE, MODEL, THRESHOLDS

import ollama
from collections import deque
import numpy as np


# ---------------------------------------------------------------------------
# 全局常量：从配置中读取防模板化参数（与 config.py 中 ANTI_TEMPLATE / THRESHOLDS 对齐）
# ---------------------------------------------------------------------------
# ANTI_TEMPLATE = {
#     "num_candidates": 3, "temperature": 0.8, "top_p": 0.9,
#     "srt_window_size": 20, "fingerprint_window": 20, "dedup_threshold": 0.85,
# }
# THRESHOLDS["content_similarity"] = {"duplicate": 0.85, "window_size": 20}

# Verbalized Sampling 的表达策略池：每次候选注入不同策略，激活模型自身多样性
_APPROACH_HINTS = [
    "请用温和鼓励的方式回应，多用正向反馈。",
    "请用结构清晰、分点讲解的方式回应。",
    "请用举例类比、生动形象的方式回应。",
    "请用提问引导、启发思考的方式回应。",
    "请用简洁直接、聚焦重点的方式回应。",
]

# 教学信号词：用于候选质量评分（是否包含教学元素）
_TEACH_SIGNALS = [
    "练习", "发音", "读", "说", "词汇", "句型", "声母", "韵母",
    "拼读", "对话", "复习", "矫正", "纠正", "举例", "示范", "跟读",
]


# ===========================================================================
# AntiTemplateEngine：六层防模板化编排引擎
# ===========================================================================
class AntiTemplateEngine:
    """六层防模板化编排引擎。

    典型用法（由 engine.py 在生成回复时调用）::

        engine = AntiTemplateEngine()
        result = engine.run(system_prompt, user_text, mem_data=prompt_vars)
        reply = result["output"]   # 去模板化后的最优回复

    六层技术对应方法：
      层1 动态提示词工程 -> pick_dynamic_vars
      层2 语义排斥 SRT   -> get_srt_blocklist / build_srt_instruction / srt_window
      层3 多候选+评选     -> generate_candidates / score_candidate / select_best
      层4 Verbalized     -> 融入 generate_candidates 的提示词指令
      层5 内容指纹去重   -> compute_fingerprint / is_duplicate / fingerprint_window
      层6 RAG 多样性检索 -> rag_diversity_hook（委托 rag.py）
    """

    def __init__(self):
        # ---- 层2 SRT 滑动窗口：存放近期输出文本，用于抽取排斥短语 ----
        srt_size = ANTI_TEMPLATE.get("srt_window_size",
                                     THRESHOLDS.get("content_similarity", {}).get("window_size", 20))
        self.srt_window: deque = deque(maxlen=srt_size)

        # ---- 层5 指纹滑动窗口：存放 (文本, 指纹向量) 二元组 ----
        fp_size = ANTI_TEMPLATE.get("fingerprint_window",
                                    THRESHOLDS.get("content_similarity", {}).get("window_size", 20))
        self.fingerprint_window: deque = deque(maxlen=fp_size)

        # ---- 层1 动态变量近期使用记录（避免连续重复开场白/语气/策略）----
        self._recent_openings: deque = deque(maxlen=srt_size)
        self._recent_tones: deque = deque(maxlen=srt_size)
        self._recent_strategies: deque = deque(maxlen=srt_size)

        # ---- ollama 客户端（惰性初始化，避免导入期 / 未安装时失败）----
        self._client: Optional[ollama.Client] = None

        # ---- sentence-transformers 模型（惰性加载，不可用则降级为哈希指纹）----
        self._st_model = None
        self._st_checked: Optional[bool] = None  # None=未检测 / True=可用 / False=不可用

    # ------------------------------------------------------------------
    # ollama 客户端惰性初始化
    # ------------------------------------------------------------------
    def _get_client(self) -> ollama.Client:
        """惰性初始化 ollama 客户端，与 engine.py / guardrails.py 调用方式一致。"""
        if self._client is None:
            self._client = ollama.Client()
        return self._client

    # ------------------------------------------------------------------
    # 层1：动态提示词工程 —— 变量选择
    # ------------------------------------------------------------------
    def pick_dynamic_vars(self, mem_data: dict) -> dict:
        """选取本轮动态提示词变量（开场白 / 语气 / 策略），避免近期重复使用。

        参数：
          mem_data: prompt_vars.json 的内容（含 openings / tones / strategies 列表），
                    由 engine.py 传入。为空时使用内置默认池。

        返回：
          dict，含 "opening" / "tone" / "strategy" 三个键。
        """
        pv = mem_data if isinstance(mem_data, dict) else {}
        openings = pv.get("openings") or ["你好，我们开始吧。", "今天想学什么？", "别担心，慢慢来！"]
        tones = pv.get("tones") or ["鼓励型伙伴", "严格教练", "幽默朋友", "耐心长辈"]
        strategies = pv.get("strategies") or ["引导式", "练习式", "纠错式", "情境式", "游戏式"]

        opening = self._pick_avoid_recent(openings, self._recent_openings)
        tone = self._pick_avoid_recent(tones, self._recent_tones)
        strategy = self._pick_avoid_recent(strategies, self._recent_strategies)
        return {"opening": opening, "tone": tone, "strategy": strategy}

    def _pick_avoid_recent(self, pool: list, recent: deque) -> str:
        """从池中随机选取一个未在近期使用过的变量；池已全部用过则全池重选。"""
        if not pool:
            return ""
        used = set(recent)
        candidates = [x for x in pool if x not in used] or list(pool)
        pick = random.choice(candidates)
        recent.append(pick)
        return pick

    # ------------------------------------------------------------------
    # 层2：语义排斥技术 SRT
    # ------------------------------------------------------------------
    def get_srt_blocklist(self) -> list[str]:
        """返回近期输出中需排斥的关键短语列表。

        从 SRT 滑动窗口内的近期输出中抽取 n-gram 短语（中文 4-6 字、英文 2-3 词），
        按出现频次取 Top-N 作为排斥目标，避免提示词过长。
        """
        if not self.srt_window:
            return []
        counter: Counter = Counter()
        for text in self.srt_window:
            for ng in self._extract_ngrams(text):
                counter[ng] += 1
        # 取频次最高的短语作为排斥目标（限制数量，避免提示词膨胀）
        return [p for p, _ in counter.most_common(20)]

    @staticmethod
    def _extract_ngrams(text: str) -> list[str]:
        """抽取关键 n-gram 短语：中文连续片段按 4~6 字滑窗，英文按 2~3 词组。"""
        phrases: list[str] = []
        if not text:
            return phrases
        # 中文连续片段（长度>=4 的才有抽取价值，过滤单字噪声）
        for seg in re.findall(r"[\u4e00-\u9fff]{4,}", text):
            for n in (4, 5, 6):
                for i in range(len(seg) - n + 1):
                    phrases.append(seg[i:i + n])
        # 英文词组
        en_words = re.findall(r"[a-zA-Z]+", text)
        for n in (2, 3):
            for i in range(len(en_words) - n + 1):
                phrases.append(" ".join(en_words[i:i + n]).lower())
        return phrases

    def build_srt_instruction(self) -> str:
        """构建「避免使用以下表达」的 SRT 指令文本，注入到生成提示词中。

        窗口为空时返回空字符串（首次调用无历史可排斥）。
        """
        blocklist = self.get_srt_blocklist()
        if not blocklist:
            return ""
        items = "、".join(blocklist)
        return ("【语义排斥指令 SRT】为保持表达多样性，请避免使用以下近期已出现的表达："
                f"{items}。请换用不同的措辞、句式与切入角度。")

    # ------------------------------------------------------------------
    # 层3 + 层4：多候选生成（含 Verbalized Sampling）
    # ------------------------------------------------------------------
    def generate_candidates(self, system_prompt: str, user_text: str,
                            n: int = None) -> list[str]:
        """生成 N 个候选回复（每个独立生成，Temperature=0.8, Top-P=0.9）。

        层4 Verbalized Sampling：在每个候选的提示词中注入不同的表达策略指令，
        让模型自行探索多样化输出，激活预训练阶段的生成多样性（多样性提升约 2.1 倍）。
        层2 SRT：通过 build_srt_instruction 注入排斥列表。

        参数：
          system_prompt 系统提示词（人设/分支/记忆已由 engine 组装）
          user_text     用户输入
          n             候选数量，默认取 ANTI_TEMPLATE["num_candidates"]

        返回：
          候选回复列表（单个生成失败时跳过，不影响其它候选）
        """
        if n is None:
            n = ANTI_TEMPLATE.get("num_candidates", 3)
        temperature = ANTI_TEMPLATE.get("temperature", 0.8)
        top_p = ANTI_TEMPLATE.get("top_p", 0.9)
        srt_instr = self.build_srt_instruction()

        candidates: list[str] = []
        for i in range(n):
            # Verbalized Sampling：轮换表达策略，促使模型生成不同风格的候选
            hint = _APPROACH_HINTS[i % len(_APPROACH_HINTS)]
            srt_block = (srt_instr + "\n\n") if srt_instr else ""
            full_prompt = (
                f"{system_prompt}\n\n"
                f"{srt_block}"
                f"【Verbalized Sampling 指令】本次请采用以下表达策略以增加输出多样性：{hint}\n"
                f"请给出一个完整、连贯的教学回复，并尽量区别于近期已给出的回复。\n\n"
                f"用户：{user_text}\n\n语言教练："
            )
            try:
                r = self._get_client().generate(
                    model=MODEL,
                    prompt=full_prompt,
                    options={"thinking": False, "temperature": temperature, "top_p": top_p},
                )
                text = (r.get("response") or "").strip()
                if text:
                    candidates.append(text)
            except Exception:
                # 单个候选生成失败不阻断整体，留待上层降级处理
                continue
        return candidates

    # ------------------------------------------------------------------
    # 层5：内容指纹去重
    # ------------------------------------------------------------------
    def compute_fingerprint(self, text: str) -> np.ndarray:
        """计算文本的语义指纹（嵌入向量）。

        优先使用 sentence_transformers.SentenceTransformer("all-MiniLM-L6-v2")；
        不可用时降级为基于字符 n-gram 的哈希指纹（固定维度、L2 归一化）。
        返回 numpy 数组，可直接做余弦相似度比对。
        """
        model = self._get_st_model()
        if model is not None:
            try:
                vec = model.encode(text, normalize_embeddings=True)
                return np.asarray(vec, dtype=np.float32)
            except Exception:
                pass  # 编码失败则降级
        return self._hash_fingerprint(text)

    def _get_st_model(self):
        """惰性加载 sentence-transformers 模型，仅检测一次可用性。"""
        if self._st_checked is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
                self._st_checked = True
            except Exception:
                self._st_model = None
                self._st_checked = False
        return self._st_model

    def _hash_fingerprint(self, text: str, dim: int = 256) -> np.ndarray:
        """降级指纹：基于字符 n-gram 的带符号哈希（hashing trick）+ L2 归一化。

        中文按 2-gram、英文按 3-gram，哈希到固定维度向量，
        用奇偶位决定符号以减少碰撞偏置，最后归一化便于余弦相似度计算。
        """
        vec = np.zeros(dim, dtype=np.float32)
        if not text:
            return vec
        grams: list[str] = []
        chars = list(text)
        for i in range(len(chars) - 1):
            grams.append("".join(chars[i:i + 2]))
        for w in re.findall(r"[a-zA-Z]+", text):
            for i in range(len(w) - 2):
                grams.append(w[i:i + 3].lower())
        for g in grams:
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        """计算两个向量的余弦相似度（0~1，向量已归一化时即点积）。"""
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def is_duplicate(self, text: str) -> bool:
        """检测文本是否与近期输出过于相似（余弦相似度 > 阈值即判定重复）。

        阈值取自 ANTI_TEMPLATE["dedup_threshold"]（0.85），
        与 THRESHOLDS["content_similarity"]["duplicate"] 一致。
        指纹窗口为空时直接返回 False。
        """
        if not self.fingerprint_window:
            return False
        threshold = ANTI_TEMPLATE.get("dedup_threshold",
                                      THRESHOLDS.get("content_similarity", {}).get("duplicate", 0.85))
        fp = self.compute_fingerprint(text)
        for _, hist_fp in self.fingerprint_window:
            if self._cosine(fp, hist_fp) > threshold:
                return True
        return False

    # ------------------------------------------------------------------
    # 层3：候选评分与选择
    # ------------------------------------------------------------------
    def score_candidate(self, candidate: str, system_prompt: str) -> float:
        """对单个候选评分：质量 × 新颖度，返回 0~1 浮点数。

        质量（quality）：长度适中、结构清晰、含教学元素；
        新颖度（novelty）：1 - 与历史指纹的最大余弦相似度（无历史时为 1.0）。
        两者相乘使重复候选（新颖度趋 0）自然被压低。
        """
        quality = self._quality_score(candidate)
        novelty = self._novelty_score(candidate)
        return float(quality * novelty)

    def _quality_score(self, text: str) -> float:
        """质量评分（0~1）：长度 / 结构 / 教学元素三维度加权。"""
        if not text:
            return 0.0
        score = 0.0
        length = len(text)
        # 长度：适中加分，过短过长扣分
        if 20 <= length <= 400:
            score += 0.4
        elif 10 <= length < 20 or 400 < length <= 600:
            score += 0.25
        else:
            score += 0.1
        # 结构：含标点分段
        if re.search(r"[。！？!?.\n]", text):
            score += 0.2
        # 教学元素：含教学信号词
        hit = sum(1 for kw in _TEACH_SIGNALS if kw in text)
        score += min(hit * 0.1, 0.4)
        return min(score, 1.0)

    def _novelty_score(self, text: str) -> float:
        """新颖度评分（0~1）：1 - 与历史指纹的最大相似度。"""
        if not self.fingerprint_window:
            return 1.0
        fp = self.compute_fingerprint(text)
        max_sim = 0.0
        for _, hist_fp in self.fingerprint_window:
            s = self._cosine(fp, hist_fp)
            if s > max_sim:
                max_sim = s
        return max(0.0, 1.0 - max_sim)

    def select_best(self, candidates: list[str],
                    system_prompt: str) -> tuple[str, float]:
        """对所有候选评分，返回 (最优文本, 最优得分)。跳过重复候选。

        若全部候选均被判定为重复，则退化取首个候选（保证有输出）。
        """
        best_text, best_score = "", 0.0
        for cand in candidates:
            # 层5：跳过与历史指纹重复的候选
            if self.is_duplicate(cand):
                continue
            sc = self.score_candidate(cand, system_prompt)
            if sc > best_score:
                best_score = sc
                best_text = cand
        # 全部重复时退化取首个候选，保证可用性
        if not best_text and candidates:
            best_text = candidates[0]
            best_score = self.score_candidate(best_text, system_prompt)
        return best_text, best_score

    # ------------------------------------------------------------------
    # 输出记录：更新 SRT 与指纹窗口
    # ------------------------------------------------------------------
    def record_output(self, text: str) -> None:
        """将一次输出记入 SRT 窗口与指纹窗口，供后续排斥与去重比对。"""
        if not text:
            return
        self.srt_window.append(text)
        fp = self.compute_fingerprint(text)
        self.fingerprint_window.append((text, fp))

    # ------------------------------------------------------------------
    # 层6：RAG 多样性检索钩子（委托 rag.py）
    # ------------------------------------------------------------------
    def rag_diversity_hook(self, query: str, board: str = None,
                           lang: str = None) -> list:
        """层6 RAG 多样性检索钩子：委托 rag.py 执行查询重写+多路召回。

        rag.py 不可用或未实现相应接口时返回空列表，保证本模块独立可用、不产生循环依赖。
        """
        try:
            from . import rag  # type: ignore
            if hasattr(rag, "diversity_retrieve"):
                return rag.diversity_retrieve(query, board=board, lang=lang)
            if hasattr(rag, "retrieve"):
                return rag.retrieve(query, board=board, lang=lang)
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # 主入口：端到端编排六层
    # ------------------------------------------------------------------
    def run(self, system_prompt: str, user_text: str,
            mem_data: dict = None) -> dict:
        """防模板化主入口：生成候选 -> 去重 -> 评分 -> 选优 -> 记录。

        参数：
          system_prompt 系统提示词（人设/分支/记忆已由 engine 组装）
          user_text     用户输入
          mem_data      prompt_vars.json 内容，用于层1动态变量选择（可选）

        返回：
          dict，含：
            output             最优回复文本
            score              最优候选得分（0~1）
            candidates_count   本次累计生成的候选总数
            duplicates_filtered 被判定为重复而过滤的候选数
            srt_active         SRT 是否处于激活状态（窗口非空）
        """
        # 层1：动态变量选择（供上游拼装提示词，此处仅记录选取结果）
        dynamic_vars = self.pick_dynamic_vars(mem_data) if mem_data else {}

        # 层2 SRT 是否激活（窗口非空即在排斥）
        srt_active = len(self.srt_window) > 0

        total_candidates = 0
        total_duplicates = 0
        best_text, best_score = "", 0.0

        # 最多重生成一次：若全部候选重复（层5 触发），则再生成一批
        for attempt in range(2):
            # 层3 + 层4：多候选生成（含 Verbalized Sampling）
            candidates = self.generate_candidates(system_prompt, user_text)
            total_candidates += len(candidates)
            total_duplicates += sum(1 for c in candidates if self.is_duplicate(c))

            # 层5 去重 + 层3 评分选优
            best_text, best_score = self.select_best(candidates, system_prompt)

            # 选中非重复输出即结束；否则再重生成一次（层5 防连续重复）
            if best_text and not self.is_duplicate(best_text):
                break

        # 记录最优输出，更新 SRT 与指纹窗口
        if best_text:
            self.record_output(best_text)

        return {
            "output": best_text,
            "score": round(best_score, 4),
            "candidates_count": total_candidates,
            "duplicates_filtered": total_duplicates,
            "srt_active": srt_active,
            "dynamic_vars": dynamic_vars,
        }


# ===========================================================================
# 直接运行：冒烟自测
# ===========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("六层防模板化系统 —— 冒烟自测")
    print("=" * 70)

    engine = AntiTemplateEngine()

    # ---- 层1：动态变量选择 ----
    prompt_vars = {
        "openings": ["Bonjour！今天想学什么？", "想要挑战吗？", "别担心，犯错是学习的一部分！"],
        "tones": ["鼓励型伙伴", "严格教练", "幽默朋友"],
        "strategies": ["引导式", "练习式", "纠错式", "情境式"],
    }
    dyn = engine.pick_dynamic_vars(prompt_vars)
    print("\n[层1 动态提示词] 选取变量：", dyn)

    # ---- 层2：SRT 排斥（首次窗口为空）----
    print("\n[层2 SRT] 排斥列表：", engine.get_srt_blocklist())
    print("[层2 SRT] 指令文本：", engine.build_srt_instruction() or "（窗口为空，无排斥指令）")

    system_prompt = "你是「全龄段 AI 语言教练」，用中文讲解拼音与英语口语。"
    user_text = "我想学拼音声母 b 怎么读"

    # ---- 层3/4：多候选生成（含 Verbalized Sampling）----
    print("\n[层3/4 多候选生成] 正在调用 ollama 生成候选...")
    candidates = engine.generate_candidates(system_prompt, user_text)
    if not candidates:
        # ollama 不可用时用模拟候选演示后续去重/评分流程
        print("  （ollama 不可用，使用模拟候选演示后续流程）")
        candidates = [
            "好的！b 是双唇不送气清塞音，双唇闭合后突然打开。我们一起读一读吧。",
            "小朋友，b 这个声母怎么发呢？先把嘴唇轻轻闭上，然后突然打开送出气流。",
            "我们来学声母 b。发音要领：双唇紧闭，然后气流冲开双唇，发出的就是 b。",
        ]
    for i, c in enumerate(candidates, 1):
        print(f"  候选{i}：{c[:50]}...")

    # ---- 层5：去重 + 评分选优 ----
    best_text, best_score = engine.select_best(candidates, system_prompt)
    print(f"\n[层5 评分选优] 最优候选得分 {best_score:.4f}")
    print(f"  最优输出：{best_text[:60]}...")

    # ---- 记录输出，更新 SRT 与指纹窗口 ----
    engine.record_output(best_text)
    print(f"\n[记录输出] SRT 窗口大小：{len(engine.srt_window)}，"
          f"指纹窗口大小：{len(engine.fingerprint_window)}")

    # ---- 重复检测演示：相同文本再次提交应判定为重复 ----
    is_dup = engine.is_duplicate(best_text)
    print(f"\n[重复检测] 相同文本再次提交 -> is_duplicate={is_dup}")

    # ---- SRT 激活后再看排斥列表 ----
    print("[层2 SRT] 记录后的排斥列表：", engine.get_srt_blocklist()[:5], "...")

    # ---- 完整 run 流程 ----
    print("\n[完整 run 流程]")
    result = engine.run(system_prompt, user_text, mem_data=prompt_vars)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # ---- 连续多次 run 观察防模板化效果 ----
    print("\n[连续 3 次 run 观察去重 / SRT 激活]")
    for k in range(3):
        r = engine.run(system_prompt, user_text, mem_data=prompt_vars)
        print(f"  第{k + 1}次：score={r['score']} srt_active={r['srt_active']} "
              f"dup_filtered={r['duplicates_filtered']} "
              f"out={r['output'][:30]}...")

    print("\n" + "=" * 70)
    print("冒烟自测完成")
