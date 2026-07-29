"""
全龄段多语言学习智能体 —— Chroma 向量库构建脚本
================================================
将已采集的 JSON 知识库灌入 Chroma 向量库，为 RAG 模块提供语义检索底座。

数据源与集合映射（集合名由 agent.config.RAG_CONFIG 统一管理）：
  - data/pinyin/pinyin_kb.json        -> collection_pinyin  (pinyin_kb)
      声母 / 韵母 / 方言错误 / 拼音规则，逐条切片为独立文本块
  - data/english/scenarios.json       -> collection_english (english_scenarios)
      每个口语场景作为一个完整文本块
  - data/languages/multilingual.json  -> collection_languages (multilingual)
      每个语种作为一个完整文本块

构建策略：
  1. 用 sentence-transformers 嵌入模型对每个文本块生成向量
  2. 若同名集合已存在则先删除再重建（全量重建，保证幂等）
  3. 将 (id, embedding, document, metadata) 写入 Chroma 持久化客户端

用法（在项目根目录执行）：
    python scripts/build_vector_db.py

依赖：
    pip install chromadb sentence-transformers
"""
import os
import sys
import json

# 兼容直接运行：把项目根加入 sys.path
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)  # huoshangbei002
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agent.config import CHROMA_DIR, DATA, RAG_CONFIG

# 依赖检查：缺包时给出友好提示并退出
try:
    import chromadb
except ImportError:
    print("[ERROR] 未安装 chromadb，请先执行：pip install chromadb")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("[ERROR] 未安装 sentence-transformers，请先执行：pip install sentence-transformers")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _load_json(path):
    """读取 JSON 文件；文件不存在时返回 None。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _join_list(val, sep="；"):
    """将列表拼接为字符串，非列表直接转为字符串。"""
    if isinstance(val, list):
        return sep.join(str(x) for x in val)
    return str(val)


# ---------------------------------------------------------------------------
# 文本块构造（每条返回 {"text": ..., "metadata": {...}}）
# ---------------------------------------------------------------------------
def chunks_from_pinyin(kb):
    """从拼音知识库生成文本块：声母 / 韵母 / 方言错误 / 拼音规则。"""
    chunks = []

    # 声母
    for key, desc in kb.get("initials", {}).items():
        text = f"声母 {key}：{desc}"
        chunks.append({"text": text, "metadata": {"type": "initial", "key": key}})

    # 韵母
    for key, desc in kb.get("finals", {}).items():
        text = f"韵母 {key}：{desc}"
        chunks.append({"text": text, "metadata": {"type": "final", "key": key}})

    # 方言错误
    for d in kb.get("dialect_errors", []):
        dtype = d.get("type", "")
        pairs = "；".join(f"{a} -> {b}" for a, b in d.get("pairs", []))
        text = (f"方言错误：{dtype}\n"
                f"描述：{d.get('desc', '')}\n"
                f"易混对比：{pairs}\n"
                f"矫正建议：{d.get('tip', '')}")
        chunks.append({"text": text, "metadata": {"type": "dialect_error", "key": dtype}})

    # 拼音规则（JSON 中键名为 spell_rules）
    for i, rule in enumerate(kb.get("spell_rules", [])):
        text = f"拼音规则：{rule}"
        chunks.append({"text": text, "metadata": {"type": "rule", "key": str(i)}})

    return chunks


def chunks_from_scenarios(data):
    """从英语口语场景库生成文本块：每个场景一个完整块。"""
    chunks = []
    for s in data.get("scenarios", []):
        title = s.get("title", "")
        scenario = s.get("scenario", "")
        key_sentences = _join_list(s.get("key_sentences", []))
        common_errors = _join_list(s.get("common_errors", []))
        text = (f"场景：{title}\n"
                f"情境：{scenario}\n"
                f"关键句型：{key_sentences}\n"
                f"常见错误：{common_errors}")
        chunks.append({"text": text, "metadata": {"type": "scenario", "title": title}})
    return chunks


def chunks_from_multilingual(data):
    """从多语种教材生成文本块：每个语种一个完整块。"""
    chunks = []
    for lang in data.get("languages", []):
        name = lang.get("language", "")
        code = lang.get("code", "")
        phrases = lang.get("common_phrases", [])
        grammar = lang.get("basic_grammar", "")
        # 常用语为对象列表：{native, romanization, zh}
        if isinstance(phrases, list):
            ph_text = "；".join(
                f"{p.get('native', '')}（{p.get('romanization', '')}）{p.get('zh', '')}"
                for p in phrases
            )
        else:
            ph_text = str(phrases)
        text = (f"语言：{name}（{code}）\n"
                f"常用语：{ph_text}\n"
                f"基础语法：{grammar}")
        chunks.append({"text": text, "metadata": {"type": "language", "code": code}})
    return chunks


# ---------------------------------------------------------------------------
# 集合构建
# ---------------------------------------------------------------------------
def build_collection(client, model, collection_name, data_path, chunk_fn, id_prefix):
    """
    构建单个 Chroma 集合。

    参数：
        client          : chromadb 持久化客户端
        model           : SentenceTransformer 嵌入模型
        collection_name : 集合名
        data_path       : 源 JSON 路径
        chunk_fn        : 由原始 JSON 生成文本块列表的函数
        id_prefix       : 文档 ID 前缀

    返回：写入的文本块数量（失败/跳过返回 0）
    """
    # 幂等：同名集合先删除再重建
    try:
        client.delete_collection(collection_name)
        print(f"  [reset] 已删除旧集合 '{collection_name}'")
    except Exception:
        # 集合不存在时忽略
        pass

    # 源文件缺失：警告并跳过
    data = _load_json(data_path)
    if data is None:
        print(f"  [warn] 数据文件不存在，跳过：{os.path.relpath(data_path, _ROOT)}")
        return 0

    chunks = chunk_fn(data)
    if not chunks:
        print(f"  [warn] '{collection_name}' 无可用文本块，跳过")
        return 0

    collection = client.get_or_create_collection(collection_name)

    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    ids = [f"{id_prefix}_{i:04d}" for i in range(len(chunks))]

    # 嵌入并写入
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    print(f"Building {collection_name} collection: {len(chunks)} chunks added")
    return len(chunks)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("Chroma 向量库构建脚本 (build_vector_db.py)")
    print(f"  向量库目录：{CHROMA_DIR}")
    print(f"  嵌入模型：{RAG_CONFIG['embedding_model']}")
    print("=" * 70)

    # 初始化嵌入模型（首次运行会自动下载权重）
    print(f"\n加载嵌入模型 {RAG_CONFIG['embedding_model']} ...")
    model = SentenceTransformer(RAG_CONFIG["embedding_model"])

    # 初始化 Chroma 持久化客户端
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 三个数据源的路径
    pinyin_path = os.path.join(DATA, "pinyin", "pinyin_kb.json")
    english_path = os.path.join(DATA, "english", "scenarios.json")
    langs_path = os.path.join(DATA, "languages", "multilingual.json")

    summary = {}

    print("\n[1/3] 拼音知识库")
    summary["pinyin"] = build_collection(
        client, model, RAG_CONFIG["collection_pinyin"],
        pinyin_path, chunks_from_pinyin, "pinyin")

    print("\n[2/3] 英语口语场景库")
    summary["english"] = build_collection(
        client, model, RAG_CONFIG["collection_english"],
        english_path, chunks_from_scenarios, "english")

    print("\n[3/3] 多语种教材")
    summary["languages"] = build_collection(
        client, model, RAG_CONFIG["collection_languages"],
        langs_path, chunks_from_multilingual, "lang")

    # 汇总
    print("\n" + "=" * 70)
    print("构建完成，汇总：")
    for name, n in summary.items():
        coll = RAG_CONFIG[f"collection_{name}"]
        print(f"  {coll:20s} -> {n} chunks")
    print("=" * 70)


if __name__ == "__main__":
    main()
