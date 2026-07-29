"""
全龄段多语言学习智能体 —— 生产级配置中心
==========================================
实现报告第十二章：阈值控制机制（6个控制环节）
所有阈值基于验证数据集的统计分布设定，非拍脑袋决定。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MEM_DIR = os.path.join(DATA, "memory")
CHROMA_DIR = os.path.join(DATA, "chroma_db")
SVM_DIR = os.path.join(DATA, "svm_models")
EVAL_DIR = os.path.join(DATA, "evaluation_logs")

for d in [MEM_DIR, CHROMA_DIR, SVM_DIR, EVAL_DIR]:
    os.makedirs(d, exist_ok=True)

MODEL = "qwen3:1.7b"

# ---------------------------------------------------------------------------
# 六个控制环节阈值（报告第十二章表）
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # 1. 意图识别置信度：SVM决策函数值
    "intent_confidence": {
        "pass": 0.5,       # >0.5 放行
        "confirm": 0.2,    # 0.2-0.5 需二次确认
        # <0.2 触发人工（追问用户）
        "action_low": "向用户追问「您是想练习拼音还是英语口语？」"
    },
    # 2. 发音错误检测：SVM异常分数（99百分位）
    "pronunciation_error": {
        "threshold_percentile": 99,
        "action": "超阈值标记为「需纠错」，送入LLM做精细分析"
    },
    # 3. 输出质量评分：综合评分（0-100）
    "output_quality": {
        "excellent": 80,   # >80 直接输出
        "observe": 60,     # 60-80 标记观察
        # <60 重生成
        "alert_consecutive": 3,  # 连续3次低于60分触发告警
    },
    # 4. 内容重复度：余弦相似度
    "content_similarity": {
        "duplicate": 0.85,  # >0.85 判定重复，重生成
        "window_size": 20,  # 与最近20次输出比对
    },
    # 5. RAG检索置信度：检索Top-1相似度分数
    "rag_confidence": {
        "high": 0.75,      # >0.75 高置信
        "medium": 0.5,     # 0.5-0.75 中等
        # <0.5 低置信
        "action_low": "扩展检索范围或提示「这部分内容我需要查证」"
    },
    # 6. 安全护栏：规则匹配+LLM裁判评分
    "safety_guardrail": {
        "action": "任何安全规则命中即拦截",
        "post_action": "拦截后记录日志，输出安全替代回复"
    },
}

# ---------------------------------------------------------------------------
# 防模板化参数
# ---------------------------------------------------------------------------
ANTI_TEMPLATE = {
    "num_candidates": 3,          # 多候选生成数量
    "temperature": 0.8,           # 多候选生成温度
    "top_p": 0.9,                 # Top-P参数
    "srt_window_size": 20,        # SRT滑动窗口大小
    "fingerprint_window": 20,     # 内容指纹比对窗口
    "dedup_threshold": 0.85,     # 去重相似度阈值
}

# ---------------------------------------------------------------------------
# Agentic RAG参数
# ---------------------------------------------------------------------------
RAG_CONFIG = {
    "num_sub_queries": 5,         # 查询重写子查询数
    "top_k_per_query": 3,        # 每个子查询返回Top-K
    "embedding_model": "all-MiniLM-L6-v2",  # sentence-transformers模型
    "collection_pinyin": "pinyin_kb",
    "collection_english": "english_scenarios",
    "collection_languages": "multilingual",
}

# ---------------------------------------------------------------------------
# 护栏规则
# ---------------------------------------------------------------------------
GUARDRAIL_RULES = {
    # L1 输入验证：禁止的注入模式
    "injection_patterns": [
        r"忽略.*指令", r"ignore.*instructions", r"系统提示词",
        r"system.*prompt", r"你.*真实身份",
    ],
    # L1 输入验证：服务范围外的话题
    "out_of_scope_hints": [
        "数学题", "写代码", "看病", "法律", "投资", "股票",
    ],
    # L3 行为策略：儿童禁用内容
    "child_forbidden": ["复杂语法", "成人话题", "职场", "面试"],
    # L3 行为策略：老人必须包含
    "elder_required": ["步骤编号", "重复"],
}

# ---------------------------------------------------------------------------
# SVM模型路径
# ---------------------------------------------------------------------------
SVM_MODELS = {
    "dialect": os.path.join(SVM_DIR, "svm_dialect.pkl"),
    "pronunciation": os.path.join(SVM_DIR, "svm_pronunciation.pkl"),
    "quality": os.path.join(SVM_DIR, "svm_quality.pkl"),
    "calibrated": True,  # 是否已做Platt Scaling概率校准
}

# ---------------------------------------------------------------------------
# 七维度评估配置
# ---------------------------------------------------------------------------
EVAL_DIMENSIONS = [
    "accuracy",      # 教学内容是否与知识库一致
    "efficiency",    # 首字延迟、回复时间
    "safety",        # 是否包含不当内容
    "fairness",      # 不同年龄段/方言区教学质量一致性
    "explainability",# 教学决策是否可追溯
    "groundedness",  # 输出是否基于知识库而非臆造
    "compliance",    # 是否符合教育内容监管要求
]

# ---------------------------------------------------------------------------
# 六层工作流配置
# ---------------------------------------------------------------------------
WORKFLOW = {
    "max_regen_attempts": 2,    # 质量校验未通过时最大重生成次数
    "enable_svm_filter": True,  # 是否启用SVM前置过滤
    "enable_guardrails": True,  # 是否启用护栏
    "enable_multi_candidate": True,  # 是否启用多候选生成
    "enable_evaluation": True,  # 是否启用七维度评估记录
}
