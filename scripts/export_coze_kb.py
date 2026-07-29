"""
把 data/ 下的 JSON 语料导出为 Coze 知识库可上传的 Markdown 文档。
输出目录：data/coze_kb/
  - 拼音知识库.md
  - 英语口语场景库.md
  - 多语种教材库.md
"""
import os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "coze_kb")
os.makedirs(OUT, exist_ok=True)


def load(sub, name):
    p = os.path.join(DATA, sub, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


# ---------- 拼音 ----------
def export_pinyin():
    kb = load("pinyin", "pinyin_kb.json")
    lines = ["# 拼音知识库", ""]
    lines.append("## 声母表（发音要领）")
    for k, v in kb.get("initials", {}).items():
        lines.append(f"- **{k}**：{v}")
    lines.append("")
    lines.append("## 韵母表（发音要领）")
    for k, v in kb.get("finals", {}).items():
        lines.append(f"- **{k}**：{v}")
    lines.append("")
    lines.append("## 拼写规则")
    for r in kb.get("spell_rules", []):
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## 方言错误对照与矫正")
    for d in kb.get("dialect_errors", []):
        lines.append(f"### {d.get('type')} — {d.get('desc')}")
        lines.append(f"**矫正要点**：{d.get('tip')}")
        for correct, wrong in d.get("pairs", []):
            lines.append(f"- 正确：{correct} ｜ 易错：{wrong}")
        lines.append("")
    txt = "\n".join(lines)
    open(os.path.join(OUT, "拼音知识库.md"), "w", encoding="utf-8").write(txt)
    return len(txt)


# ---------- 英语 ----------
def export_english():
    kb = load("english", "scenarios.json")
    lines = ["# 英语口语场景库", ""]
    for s in kb.get("scenarios", []):
        lines.append(f"## 场景：{s.get('title')}")
        if s.get("scenario"):
            lines.append(f"情境：{s.get('scenario')}")
        lines.append("### 对话示范")
        for turn in s.get("dialogue", []):
            role = turn.get("role", "")
            txt = turn.get("text", "")
            lines.append(f"- **{role}**：{txt}")
        lines.append("### 关键句型")
        for k in s.get("key_sentences", []):
            lines.append(f"- {k}")
        lines.append("### 常见错误")
        for e in s.get("common_errors", []):
            lines.append(f"- {e}")
        lines.append("")
    txt = "\n".join(lines)
    open(os.path.join(OUT, "英语口语场景库.md"), "w", encoding="utf-8").write(txt)
    return len(txt)


# ---------- 多语种 ----------
def export_languages():
    kb = load("languages", "multilingual.json")
    lines = ["# 多语种教材库（日/韩/法/西 A1）", ""]
    for l in kb.get("languages", []):
        lines.append(f"## {l.get('language')}（code: {l.get('code')}）")
        if l.get("greetings"):
            lines.append("### 问候语")
            for g in l["greetings"]:
                lines.append(f"- {g}")
        if l.get("numbers_1_10"):
            lines.append("### 数字 1-10")
            for n in l["numbers_1_10"]:
                lines.append(f"- {n}")
        if l.get("common_phrases"):
            lines.append("### 常用短语")
            for p in l["common_phrases"]:
                native = p.get("native", "")
                roman = p.get("romanization", "")
                cn = p.get("meaning", "")
                lines.append(f"- {native}（{roman}）— {cn}")
        if l.get("basic_grammar"):
            lines.append(f"### 基础语法：{l['basic_grammar']}")
        lines.append("")
    txt = "\n".join(lines)
    open(os.path.join(OUT, "多语种教材库.md"), "w", encoding="utf-8").write(txt)
    return len(txt)


if __name__ == "__main__":
    a = export_pinyin()
    b = export_english()
    c = export_languages()
    print(f"拼音知识库.md   {a}B")
    print(f"英语口语场景库.md {b}B")
    print(f"多语种教材库.md  {c}B")
    print("导出完成 ->", OUT)
