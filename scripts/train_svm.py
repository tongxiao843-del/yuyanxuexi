"""
全龄段多语言学习智能体 —— SVM 模型训练脚本
============================================
报告第十二章三个 SVM 应用场景的统一训练入口。

用法：
    python scripts/train_svm.py            # 训练全部三个模型
    python scripts/train_svm.py dialect     # 只训练方言区分类器
    python scripts/train_svm.py pronunciation
    python scripts/train_svm.py quality

训练流程：
    1. 加载真实种子数据（data/pronunciation/weak_labels.json + data/pinyin/pinyin_kb.json）
    2. 用合成数据扩展为训练集（baseline，生产需替换为标注数据）
    3. SVC + CalibratedClassifierCV(method='sigmoid') 做 Platt Scaling 概率校准
    4. joblib 保存到 data/svm_models/ 下
    5. 用留出集打印分类报告，验证模型可用性

模型路径由 agent.config.SVM_MODELS / SVM_DIR 统一管理。
"""
import os
import sys
import time

# 兼容直接运行：把项目根加入 sys.path
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)  # huoshangbei002
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from agent.config import SVM_MODELS, SVM_DIR
from agent.svm_models import (
    DialectClassifier,
    PronunciationDetector,
    QualityClassifier,
    gen_dialect_samples,
    gen_pronunciation_samples,
    gen_quality_samples,
    _fit_calibrated,
    _score_from_proba,
)
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib


# ---------------------------------------------------------------------------
# 各模型的训练 + 评估
# ---------------------------------------------------------------------------
def train_dialect():
    """训练方言区用户分类器（场景一）。"""
    print("\n[1/3] 训练方言区用户分类器 (DialectClassifier)")
    print("  数据来源：合成数据（地域 + 发音测试文本特征），生产需替换为真实声学特征")
    X, y = gen_dialect_samples(n_per_class=40, seed=42)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    base = Pipeline([
        ("scaler", StandardScaler()),
        ("svc", SVC(kernel="rbf", C=1.0, random_state=42)),
    ])
    cal = _fit_calibrated(base, X_train, y_train, method="sigmoid")

    # 评估
    y_pred = cal.predict(X_test)
    print("  留出集分类报告：")
    for line in classification_report(y_test, y_pred, zero_division=0).splitlines():
        print("    " + line)

    # 保存（覆盖 agent.svm_models 默认 bundle 结构，保留训练集评估元信息）
    bundle = {
        "model": cal,
        "labels": DialectClassifier.LABELS,
        "feature_names": [
            "region_华南", "region_华中", "region_西南", "region_江淮",
            "region_北方", "region_东北", "region_其他",
            "cnt_平翘舌", "cnt_n-l", "cnt_f-h", "cnt_前后鼻音", "text_len_norm",
        ],
        "meta": {
            "source": "synthetic_baseline",
            "n_samples": len(y),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "calibrated": True,
            "method": "sigmoid",
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    _save_model(SVM_MODELS["dialect"], bundle)
    return bundle


def train_pronunciation():
    """训练发音错误检测器（场景二）。"""
    print("\n[2/3] 训练发音错误检测器 (PronunciationDetector)")
    print("  数据来源：data/pronunciation/weak_labels.json + data/pinyin/pinyin_kb.json 种子扩展")
    texts, y = gen_pronunciation_samples(target=180, seed=7)
    texts_train, texts_test, y_train, y_test = train_test_split(
        texts, y, test_size=0.2, random_state=42, stratify=y)

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    X_train = vec.fit_transform(texts_train)
    X_test = vec.transform(texts_test)

    base = SVC(kernel="rbf", C=1.0, random_state=42)
    cal = _fit_calibrated(base, X_train, y_train, method="sigmoid")

    y_pred = cal.predict(X_test)
    print("  留出集分类报告：")
    for line in classification_report(y_test, y_pred, zero_division=0).splitlines():
        print("    " + line)

    bundle = {
        "model": cal,
        "vectorizer": vec,
        "labels": PronunciationDetector.LABELS,
        "meta": {
            "source": "weak_labels_seed",
            "n_samples": len(y),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "calibrated": True,
            "method": "sigmoid",
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    _save_model(SVM_MODELS["pronunciation"], bundle)
    return bundle


def train_quality():
    """训练输出质量分类器（场景三）。"""
    print("\n[3/3] 训练输出质量分类器 (QualityClassifier)")
    print("  数据来源：合成 LLM 输出 + data/pinyin/pinyin_kb.json 知识库锚定")
    X, y, kb_vectorizer, kb_vec, vocab = gen_quality_samples(target=150, seed=11)
    # 转为 list 以便 stratify 切分
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    base = Pipeline([
        ("scaler", StandardScaler()),
        ("svc", SVC(kernel="rbf", C=1.0, random_state=42)),
    ])
    cal = _fit_calibrated(base, X_train, y_train, method="sigmoid")

    y_pred = cal.predict(X_test)
    print("  留出集分类报告：")
    for line in classification_report(y_test, y_pred, zero_division=0).splitlines():
        print("    " + line)

    # 推理延迟评估（场景三要求约 8ms）
    latency = _bench_latency(cal, X_test[:50])

    bundle = {
        "model": cal,
        "kb_vectorizer": kb_vectorizer,
        "kb_vec": kb_vec,
        "vocab": vocab,
        "labels": QualityClassifier.LABELS,
        "feature_names": ["length_norm", "structure_markers", "vocab_coverage", "kb_similarity"],
        "meta": {
            "source": "synthetic_baseline",
            "n_samples": len(y),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "calibrated": True,
            "method": "sigmoid",
            "avg_inference_ms": latency,
            "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    _save_model(SVM_MODELS["quality"], bundle)
    return bundle


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _save_model(path, bundle):
    """保存模型包并打印路径。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(bundle, path)
    print(f"  [saved] {os.path.relpath(path, _ROOT)}")


def _bench_latency(model, X, rounds=3):
    """测量平均推理延迟（毫秒），用于验证场景三「约 8ms」目标。"""
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        model.predict(X)
        times.append((time.perf_counter() - t0) * 1000.0)
    avg = sum(times) / len(times) / max(len(X), 1)
    print(f"  平均推理延迟：{avg:.3f} ms/样本（目标约 8ms）")
    return round(avg, 3)


def _verify_loaded():
    """加载刚训练好的模型，验证可正常预测。"""
    print("\n=== 验证：加载已保存模型并预测 ===")
    dc = DialectClassifier()  # force_retrain=False，加载已有
    label, proba = dc.predict("华南", "zī cī sī lǎo shī")
    print(f"  方言分类(华南) -> {label} | top概率={max(proba.values()):.3f}")

    pd = PronunciationDetector()
    label, proba = pd.predict("lǎo shī")
    print(f"  发音检测(lǎo shī) -> {label} | 跳过LLM={pd.should_skip_llm('lǎo shī')}")

    qc = QualityClassifier()
    decision, label, proba = qc.intercept(
        "1. 翘舌音：舌尖上翘。 2. 平舌音：舌尖平伸。")
    print(f"  质量分类 -> 决策={decision} 标签={label} 评分={qc.quality_score('1. 翘舌音：舌尖上翘。 2. 平舌音：舌尖平伸。')}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
TRAINERS = {
    "dialect": train_dialect,
    "pronunciation": train_pronunciation,
    "quality": train_quality,
}


def main(targets=None):
    print("=" * 70)
    print("SVM 模型训练脚本 (train_svm.py)")
    print(f"  模型目录：{SVM_DIR}")
    print(f"  概率校准：Platt Scaling (CalibratedClassifierCV, method=sigmoid)")
    print("=" * 70)

    os.makedirs(SVM_DIR, exist_ok=True)
    targets = targets or ["dialect", "pronunciation", "quality"]
    for name in targets:
        if name not in TRAINERS:
            print(f"  [warn] 未知目标 '{name}'，可选: {list(TRAINERS)}")
            continue
        TRAINERS[name]()

    _verify_loaded()
    print("\n训练完成。模型文件：")
    for k, v in SVM_MODELS.items():
        if k == "calibrated":
            continue
        print(f"  {k:14s} -> {v} ({'OK' if os.path.exists(v) else 'MISSING'})")
    print("=" * 70)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args if args else None)
