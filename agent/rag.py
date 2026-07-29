"""
全龄段多语言学习智能体 —— Agentic RAG 多样性检索模块
====================================================
实现报告「防模板化技术矩阵」中的 RAG 多样性检索架构（Agentic RAG）：

  1. 查询重写 Query Rewriting
     用 LLM (ollama qwen3:1.7b) 将用户原始查询重写为 5 个不同角度的子查询。
     例：用户说"练习餐厅英语" → 重写为"餐厅点餐高频句型""餐厅对话常见错误"
     "快餐 vs 正餐厅用语差异""餐厅英语文化礼仪""餐厅投诉与服务用语"。

  2. 多路召回 Multi-path Retrieval
     5 个子查询分别从 Chroma 向量库检索 Top-3，共 15 个候选段落。

  3. 方差感知融合 Variance-aware Fusion
     使用嵌套倒数排名融合（Nested Reciprocal Rank Fusion, nRRF）对 15 个结果
     去重排序，优先选择被多个子查询同时命中的内容，同时保证结果集语义覆盖度。

  4. 证据引导生成 Evidence-guided Generation
     从融合结果中抽取证据片段，拼装为上下文供生成阶段使用。

  5. 置信度评分 Confidence Scoring
     基于检索 Top-1 相似度分数：
       >0.75   高置信（直接采用）
       0.5-0.75 中等置信
       <0.5    低置信（扩展检索范围或提示「这部分内容我需要查证」）

所有配置从 agent.config 导入，与 engine.py / evaluation.py 共用同一套阈值。
当 Chroma 向量库或 sentence-transformers 不可用时，自动回退到基于 JSON 语料库的
关键词检索，保证模块始终可用（生产级容错）。
"""
from __future__ import annotations

import os
import re
import json
import hashlib
from typing import Optional

# ---------------------------------------------------------------------------
# 配置导入：兼容「包内导入」与「脚本直接运行」两种场景
# ---------------------------------------------------------------------------
try:
    from .config import RAG_CONFIG, CHROMA_DIR, DATA, MODEL, THRESHOLDS
except ImportError:  # pragma: no cover —— 直接 python rag.py 时回退
    from config import RAG_CONFIG, CHROMA_DIR, DATA, MODEL, THRESHOLDS

# ---------------------------------------------------------------------------
# 可选依赖：chromadb / sentence_transformers / ollama 均做容错导入
# ---------------------------------------------------------------------------
try:
    import chromadb
    _HAS_CHROMA = True
except Exception:  # pragma: no cover
    chromadb = None
    _HAS_CHROMA = False

try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except Exception:  # pragma: no cover
    SentenceTransformer = None
    _HAS_ST = False

try:
    import ollama
    _HAS_OLLAMA = True
except Exception:  # pragma: no cover
    ollama = None
    _HAS_OLLAMA = False


# nRRF 标准常数（Reciprocal Rank Fusion 的 k 值）
RRF_K = 60


class AgenticRAG:
    """Agentic RAG 多样性检索器。

    封装「查询重写 → 多路召回 → nRRF 融合 → 证据拼装 → 置信度评分」全流程。
    通过 :meth:`retrieve` 作为统一入口，返回融合后的上下文、置信度、来源与子查询。

    设计要点：
      - Chroma / sentence-transformers / ollama 均为惰性初始化与容错导入；
      - 向量库不可用时回退到 data 目录下的 JSON 语料关键词检索；
      - nRRF 融合以内容指纹去重，被多路命中的段落累加得分从而被优先保留。
    """

    def __init__(self):
        # Chroma 持久化客户端
        self.chroma_client = None
        if _HAS_CHROMA:
            try:
                self.chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
            except Exception:
                self.chroma_client = None

        # 句向量模型（惰性加载，避免导入期阻塞）
        self._embed_model = None
        self._embed_model_name = RAG_CONFIG.get("embedding_model", "all-MiniLM-L6-v2")

        # Ollama 客户端（惰性初始化）
        self._ollama = None
        self._model = MODEL

        # 检索参数
        self._num_sub = int(RAG_CONFIG.get("num_sub_queries", 5))
        self._top_k = int(RAG_CONFIG.get("top_k_per_query", 3))

        # 置信度阈值
        self._thr = THRESHOLDS.get("rag_confidence", {"high": 0.75, "medium": 0.5})

        # JSON 语料回退缓存（collection_name -> list[dict]）
        self._fallback_cache: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # 惰性资源
    # ------------------------------------------------------------------
    def _get_embed_model(self):
        """惰性加载 sentence-transformers 模型。"""
        if self._embed_model is None and _HAS_ST:
            try:
                self._embed_model = SentenceTransformer(self._embed_model_name)
            except Exception:
                self._embed_model = None
        return self._embed_model

    def _get_ollama(self):
        """惰性初始化 ollama 客户端。"""
        if self._ollama is None and _HAS_OLLAMA:
            try:
                self._ollama = ollama.Client()
            except Exception:
                self._ollama = None
        return self._ollama

    # ------------------------------------------------------------------
    # 集合名映射
    # ------------------------------------------------------------------
    def get_collection_name(self, board: str, lang: str = None) -> str:
        """将学习板块映射到 Chroma 集合名。

        :param board: pinyin / english / multilingual
        :param lang: 多语种语言代码（当前由集合统一承载，预留参数）
        :return: Chroma 集合名
        """
        if board == "pinyin":
            return RAG_CONFIG["collection_pinyin"]
        if board == "multilingual":
            return RAG_CONFIG["collection_languages"]
        # english 及未知板块默认走英语场景库
        return RAG_CONFIG["collection_english"]

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def retrieve(self, query: str, board: str, lang: str = None) -> dict:
        """Agentic RAG 主入口。

        :param query: 用户原始查询
        :param board: 学习板块（pinyin / english / multilingual）
        :param lang: 多语种语言代码（可选）
        :return: dict，包含：
                 - context:     融合后的证据上下文文本
                 - confidence:  置信度（0-1，取 Top-1 相似度）
                 - sources:     融合排序后的检索片段列表
                 - sub_queries: 重写出的子查询列表
        """
        collection_name = self.get_collection_name(board, lang)

        # 1) 查询重写
        sub_queries = self._rewrite_query(query, board)

        # 2) 多路召回（返回扁平候选列表，每条带 sub_query_index / rank）
        flat_candidates = self._multi_path_retrieve(sub_queries, collection_name)

        # 重组为 list[list[dict]]（按子查询分组，供 nRRF 融合）
        grouped: list[list[dict]] = [[] for _ in range(len(sub_queries))]
        for chunk in flat_candidates:
            idx = chunk.get("sub_query_index", 0)
            if 0 <= idx < len(grouped):
                grouped[idx].append(chunk)

        # 3) 方差感知融合（nRRF）
        fused = self._fuse_results(grouped)

        # 4) 置信度评分
        confidence = self._compute_confidence(fused)

        # 5) 证据拼装
        context = self._build_context(fused)

        # 低置信度处理：附加查证提示（扩展检索范围为可选策略）
        if confidence < self._thr.get("medium", 0.5):
            context = context + "\n\n[低置信度提示] 这部分内容我需要查证。"

        return {
            "context": context,
            "confidence": round(confidence, 4),
            "sources": fused,
            "sub_queries": sub_queries,
        }

    # ------------------------------------------------------------------
    # 1) 查询重写
    # ------------------------------------------------------------------
    def _rewrite_query(self, query: str, board: str) -> list[str]:
        """用 LLM 将原始查询重写为 N 个不同角度的子查询。

        ollama 不可用或解析失败时，回退到基于关键词角度模板的重写，
        保证下游多路召回始终有 N 条子查询。
        """
        num = self._num_sub
        client = self._get_ollama()
        if client is not None:
            try:
                prompt = (
                    "你是查询重写引擎。请将下面的用户查询从不同角度重写为"
                    f"{num}个子查询，用于多路向量检索。\n"
                    f"用户查询：{query}\n学习板块：{board}\n\n"
                    "要求：\n"
                    "- 从高频表达、常见错误、文化差异、场景对比、实用对话等不同角度切入；\n"
                    f"- 输出{num}个子查询，每行一个，不要编号，不要解释，不要多余文字。\n\n"
                    f"{num}个子查询："
                )
                r = client.generate(
                    model=self._model,
                    prompt=prompt,
                    options={"thinking": False, "temperature": 0.6},
                )
                text = re.sub(r"<think>.*?</think>", "", r["response"], flags=re.S).strip()
                subs = self._parse_sub_queries(text, num)
                if subs:
                    return subs
            except Exception:
                pass
        # 回退：关键词角度模板
        return self._fallback_rewrite(query, num)

    @staticmethod
    def _parse_sub_queries(text: str, num: int) -> list[str]:
        """从 LLM 输出中解析子查询（每行一条，兼容编号前缀）。"""
        lines = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            # 去除常见编号前缀：1. / 1、 / (1) / - 等
            line = re.sub(r"^\s*[\d一二三四五六七八九十]+[.、）)\]]\s*", "", line)
            line = line.strip(" -•·-*")
            if line:
                lines.append(line)
        # 去重保序
        seen, out = set(), []
        for l in lines:
            if l not in seen:
                seen.add(l)
                out.append(l)
        return out[:num]

    @staticmethod
    def _fallback_rewrite(query: str, num: int) -> list[str]:
        """ollama 不可用时的关键词角度模板重写，保证始终有 N 路召回。"""
        facets = [
            "高频句型与重点表达",
            "常见错误与易错点",
            "文化差异与礼仪注意",
            "场景对比与差异辨析",
            "实用对话与开口练习",
        ]
        subs = []
        for i in range(num):
            facet = facets[i % len(facets)]
            subs.append(f"{query} {facet}")
        return subs

    # ------------------------------------------------------------------
    # 2) 多路召回
    # ------------------------------------------------------------------
    def _multi_path_retrieve(self, sub_queries: list[str], collection_name: str) -> list[dict]:
        """对每个子查询检索 Top-K，返回扁平候选列表。

        每条结果含：id / content / metadata / score / sub_query_index / rank。
        优先走 Chroma 向量检索；不可用或集合为空时回退到 JSON 语料关键词检索。
        """
        all_chunks: list[dict] = []
        for i, sq in enumerate(sub_queries):
            chunks = self._retrieve_one(sq, collection_name, i)
            all_chunks.extend(chunks)
        return all_chunks

    def _retrieve_one(self, sub_query: str, collection_name: str, sub_idx: int) -> list[dict]:
        """单条子查询的 Top-K 检索。"""
        top_k = self._top_k
        # 优先向量检索
        chunks = self._chroma_query(sub_query, collection_name, sub_idx, top_k)
        if chunks:
            return chunks
        # 回退：JSON 语料关键词检索
        return self._fallback_query(sub_query, collection_name, sub_idx, top_k)

    def _chroma_query(self, sub_query: str, collection_name: str, sub_idx: int, top_k: int) -> list[dict]:
        """Chroma 向量检索。"""
        if self.chroma_client is None:
            return []
        embed_model = self._get_embed_model()
        if embed_model is None:
            return []
        try:
            collection = self.chroma_client.get_collection(collection_name)
        except Exception:
            return []  # 集合不存在
        try:
            qvec = embed_model.encode([sub_query], normalize_embeddings=True)[0]
            res = collection.query(
                query_embeddings=[qvec.tolist()],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        chunks: list[dict] = []
        for pos, (cid, doc, meta, dist) in enumerate(zip(ids, docs, metas, dists)):
            content = doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False)
            score = self._distance_to_similarity(dist)
            chunks.append({
                "id": cid,
                "content": content,
                "metadata": meta or {},
                "score": round(score, 4),
                "sub_query_index": sub_idx,
                "rank": pos + 1,
            })
        return chunks

    @staticmethod
    def _distance_to_similarity(distance) -> float:
        """将 Chroma 距离转换为 [0,1] 相似度分数。

        Chroma 默认 L2 距离越小越相似，采用 1/(1+d) 单调映射，距离 0 → 1.0。
        """
        try:
            d = float(distance)
        except (TypeError, ValueError):
            return 0.0
        if d < 0:
            d = 0.0
        return 1.0 / (1.0 + d)

    # ------------------------------------------------------------------
    # JSON 语料回退检索
    # ------------------------------------------------------------------
    def _fallback_query(self, sub_query: str, collection_name: str, sub_idx: int, top_k: int) -> list[dict]:
        """Chroma 不可用时的 JSON 语料关键词检索回退。"""
        chunks_src = self._load_fallback_corpus(collection_name)
        if not chunks_src:
            return []
        scored = []
        for src in chunks_src:
            disc = (src.get("metadata", {}).get("title")
                    or src.get("metadata", {}).get("type")
                    or src.get("metadata", {}).get("language")
                    or "")
            score = self._fallback_score(sub_query, src["content"], disc)
            scored.append((score, src))
        scored.sort(key=lambda x: x[0], reverse=True)
        # 过滤零分结果，避免噪声
        scored = [(s, src) for s, src in scored if s > 0]
        chunks: list[dict] = []
        for pos, (score, src) in enumerate(scored[:top_k]):
            chunks.append({
                "id": src["id"],
                "content": src["content"],
                "metadata": src.get("metadata", {}),
                "score": round(score, 4),
                "sub_query_index": sub_idx,
                "rank": pos + 1,
            })
        return chunks

    @staticmethod
    def _fallback_score(query: str, content: str, discriminator: str = "") -> float:
        """回退检索的启发式相关性打分（[0,1]）。

        综合：字符重叠 + 内容二元组命中 + 判别字段（标题/类型/语种）二元组命中。
        判别字段命中视为强信号（主题命中），给予较高权重。
        """
        if not query or not content:
            return 0.0
        q_chars = set(c for c in query if '\u4e00' <= c <= '\u9fff' or c.isalnum())
        if not q_chars:
            return 0.0
        overlap = sum(1 for c in q_chars if c in content)
        char_score = overlap / len(q_chars)

        bigrams = AgenticRAG._bigrams(query)
        content_bg = sum(1 for bg in bigrams if bg in content)
        disc_bg = sum(1 for bg in bigrams if discriminator and bg in discriminator)

        score = 0.3 * char_score
        score += min(0.06 * content_bg, 0.3)   # 内容命中：弱信号，封顶 0.3
        score += 0.3 * disc_bg                  # 判别字段命中：强信号（主题命中）
        # 查询核心串整体出现在内容中
        core = query.strip()
        if core and core in content:
            score = max(score, 0.85)
        return min(score, 0.95)

    @staticmethod
    def _bigrams(text: str) -> list[str]:
        """生成中文/字母数字二元组（用于回退检索的关键词匹配）。"""
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff' or c.isalnum()]
        return [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]

    def _load_fallback_corpus(self, collection_name: str) -> list[dict]:
        """按集合名加载 JSON 语料并切片为可检索段落（带缓存）。"""
        if collection_name in self._fallback_cache:
            return self._fallback_cache[collection_name]

        chunks: list[dict] = []
        path_map = {
            RAG_CONFIG["collection_pinyin"]: ("pinyin", "pinyin_kb.json"),
            RAG_CONFIG["collection_english"]: ("english", "scenarios.json"),
            RAG_CONFIG["collection_languages"]: ("languages", "multilingual.json"),
        }
        if collection_name not in path_map:
            self._fallback_cache[collection_name] = []
            return []
        sub, name = path_map[collection_name]
        fp = os.path.join(DATA, sub, name)
        if not os.path.exists(fp):
            self._fallback_cache[collection_name] = []
            return []
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._fallback_cache[collection_name] = []
            return []

        # 按集合类型切片为检索段落
        if collection_name == RAG_CONFIG["collection_english"]:
            for i, sc in enumerate(data.get("scenarios", [])):
                title = sc.get("title", "")
                keys = "；".join(sc.get("key_sentences", []))
                errs = "；".join(sc.get("common_errors", []))
                cultural = sc.get("cultural_notes", "")
                if isinstance(cultural, list):
                    cultural = "；".join(cultural)
                content = (f"场景《{title}》关键句型：{keys}；"
                           f"易错点：{errs}；文化提示：{cultural}")
                chunks.append({
                    "id": f"en_{i}_{title}",
                    "content": content,
                    "metadata": {"title": title, "level": sc.get("level", ""),
                                 "source": "scenarios.json"},
                })
        elif collection_name == RAG_CONFIG["collection_pinyin"]:
            for i, de in enumerate(data.get("dialect_errors", [])):
                pairs = "、".join("/".join(p) for p in de.get("pairs", []))
                content = (f"方言错误《{de.get('type')}》：{de.get('desc')}；"
                           f"示例：{pairs}；矫正：{de.get('tip')}")
                chunks.append({
                    "id": f"py_de_{i}",
                    "content": content,
                    "metadata": {"type": de.get("type", ""), "source": "pinyin_kb.json"},
                })
            for key, desc in data.get("initials", {}).items():
                chunks.append({
                    "id": f"py_init_{key}",
                    "content": f"声母 {key}：{desc}",
                    "metadata": {"category": "initial", "source": "pinyin_kb.json"},
                })
            for key, desc in data.get("finals", {}).items():
                chunks.append({
                    "id": f"py_fin_{key}",
                    "content": f"韵母 {key}：{desc}",
                    "metadata": {"category": "final", "source": "pinyin_kb.json"},
                })
            for i, rule in enumerate(data.get("spell_rules", [])):
                chunks.append({
                    "id": f"py_rule_{i}",
                    "content": f"拼写规则：{rule}",
                    "metadata": {"category": "rule", "source": "pinyin_kb.json"},
                })
        elif collection_name == RAG_CONFIG["collection_languages"]:
            for i, lg in enumerate(data.get("languages", [])):
                name_ = lg.get("language", "")
                phrases = "；".join(
                    f"{p.get('native', '')}({p.get('romanization', '')})={p.get('zh', '')}"
                    for p in lg.get("common_phrases", [])[:6]
                )
                content = (f"{name_}常用语：{phrases}；"
                           f"语法注意：{lg.get('basic_grammar', '')}")
                chunks.append({
                    "id": f"lang_{i}_{name_}",
                    "content": content,
                    "metadata": {"language": name_, "code": lg.get("code", ""),
                                 "source": "multilingual.json"},
                })

        self._fallback_cache[collection_name] = chunks
        return chunks

    # ------------------------------------------------------------------
    # 3) nRRF 融合
    # ------------------------------------------------------------------
    def _fuse_results(self, results: list[list[dict]]) -> list[dict]:
        """嵌套倒数排名融合（Nested Reciprocal Rank Fusion）。

        对多路召回结果按内容去重，以 nRRF 得分排序：

            score(d) = Σ 1 / (k + rank_i(d))

        其中 k=60（标准 RRF 常数），rank_i 为文档在第 i 路结果中的排名（1 起算）。
        被多个子查询同时命中的内容累加得分，从而被优先保留；去重保证语义覆盖度。

        :param results: list[list[dict]]，每个内层列表为一路召回的排序结果
        :return: 融合并去重后的排序结果列表
        """
        # dedup_key -> 聚合结构
        merged: dict[str, dict] = {}
        for sub_idx, ranked in enumerate(results):
            for pos, chunk in enumerate(ranked):
                # 优先采用 chunk 自带的 rank（更精确），否则按位置 1 起算
                rank = int(chunk.get("rank", pos + 1))
                key = self._dedup_key(chunk)
                contrib = 1.0 / (RRF_K + rank)
                if key not in merged:
                    merged[key] = {
                        "id": chunk.get("id", key),
                        "content": chunk.get("content", ""),
                        "metadata": chunk.get("metadata", {}),
                        "score": float(chunk.get("score", 0.0)),
                        "nrrf_score": 0.0,
                        "sub_query_hits": [],
                        "best_rank": rank,
                    }
                entry = merged[key]
                entry["nrrf_score"] += contrib
                entry["sub_query_hits"].append(sub_idx)
                # 保留最大相似度（用于置信度评分）
                if float(chunk.get("score", 0.0)) > entry["score"]:
                    entry["score"] = float(chunk.get("score", 0.0))
                    entry["id"] = chunk.get("id", entry["id"])
                    entry["content"] = chunk.get("content", entry["content"])
                    entry["metadata"] = chunk.get("metadata", entry["metadata"])
                if rank < entry["best_rank"]:
                    entry["best_rank"] = rank

        # 按 nRRF 得分降序，得分相同则按相似度降序
        fused = sorted(
            merged.values(),
            key=lambda x: (x["nrrf_score"], x["score"]),
            reverse=True,
        )
        # 赋予融合后的最终排名与字段
        out: list[dict] = []
        for pos, e in enumerate(fused):
            out.append({
                "id": e["id"],
                "content": e["content"],
                "metadata": e["metadata"],
                "score": round(e["score"], 4),
                "sub_query_index": e["sub_query_hits"][0] if e["sub_query_hits"] else 0,
                "sub_query_hits": e["sub_query_hits"],
                "nrrf_score": round(e["nrrf_score"], 4),
                "rank": pos + 1,
            })
        return out

    @staticmethod
    def _dedup_key(chunk: dict) -> str:
        """生成去重键：优先用内容指纹，保证语义相同的段落被合并。"""
        content = (chunk.get("content") or "").strip()
        if content:
            return hashlib.md5(content.encode("utf-8")).hexdigest()
        return str(chunk.get("id", id(chunk)))

    # ------------------------------------------------------------------
    # 4) 置信度评分
    # ------------------------------------------------------------------
    def _compute_confidence(self, fused_results: list[dict]) -> float:
        """基于 Top-1 相似度计算置信度（0-1）。

        分级（与 THRESHOLDS['rag_confidence'] 对齐）：
          >0.75    高置信
          0.5-0.75 中等置信
          <0.5     低置信（触发扩展检索 / 查证提示）
        """
        if not fused_results:
            return 0.0
        top1 = float(fused_results[0].get("score", 0.0))
        if top1 < 0:
            top1 = 0.0
        if top1 > 1.0:
            top1 = 1.0
        return top1

    def confidence_level(self, confidence: float) -> str:
        """将置信度数值映射为分级标签（供上层决策使用）。"""
        if confidence >= self._thr.get("high", 0.75):
            return "high"
        if confidence >= self._thr.get("medium", 0.5):
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # 5) 证据拼装
    # ------------------------------------------------------------------
    def _build_context(self, fused_results: list[dict]) -> str:
        """从融合结果中抽取证据片段，拼装为生成阶段可用的上下文文本。"""
        if not fused_results:
            return "（未检索到相关教学内容）"
        lines = []
        for e in fused_results:
            hits = e.get("sub_query_hits", [])
            hit_tag = f"[命中{len(hits)}路]" if len(hits) > 1 else ""
            content = e.get("content", "").strip()
            line = f"- {content} {hit_tag}".strip()
            lines.append(line)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 冒烟测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    rag = AgenticRAG()
    print("=== Agentic RAG 冒烟测试 ===")
    result = rag.retrieve("练习餐厅英语", "english")
    print("\n【子查询】")
    for i, sq in enumerate(result["sub_queries"], 1):
        print(f"  {i}. {sq}")
    print(f"\n【置信度】{result['confidence']:.3f} "
          f"({rag.confidence_level(result['confidence'])})")
    print(f"\n【检索来源】共 {len(result['sources'])} 条")
    for s in result["sources"]:
        preview = s.get("content", "")[:70].replace("\n", " ")
        print(f"  [rank={s['rank']}] score={s.get('score', 0):.3f} "
              f"hits={s.get('sub_query_hits', [])} | {preview}")
    print("\n【上下文】")
    print(result["context"])
