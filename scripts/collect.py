"""
全龄段多语言学习智能体 —— 素材自动采集流水线
================================================
用本地 Ollama (qwen3:1.7b) 作为生成引擎，自动产出报告第13章要求的语料：
  - data/pinyin/pinyin_kb.json     拼音知识库（结构化权威数据，非生成）
  - data/english/scenarios.json    英语口语场景库（模型生成）
  - data/languages/multilingual.json 多语种基础教材（模型生成）
  - data/prompts/prompt_vars.json  提示词变量池（模型生成）
  - data/pronunciation/weak_labels.json 发音错误弱标注 bootstrap（规则生成）
所有产出为标准 JSON，可直接喂给智能体的 RAG / 记忆 / 校验模块。
"""
import os, re, json, time
import ollama

MODEL = "qwen3:1.7b"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
client = ollama.Client()


def gen(prompt: str, temperature: float = 0.35, retries: int = 4):
    """调用本地模型并要求返回纯 JSON；容忍思考标签与多余文字。"""
    last = None
    for i in range(retries):
        try:
            r = client.generate(model=MODEL, prompt=prompt,
                                options={"thinking": False, "temperature": temperature})
            text = re.sub(r"<think>.*?</think>", "", r["response"], flags=re.S).strip()
            # 尝试对象
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e > s:
                return json.loads(text[s:e + 1])
            # 尝试数组
            s, e = text.find("["), text.rfind("]")
            if s != -1 and e > s:
                return json.loads(text[s:e + 1])
        except Exception as ex:
            last = ex
        prompt = prompt + "\n【重申】只输出一个合法 JSON 对象，不要任何额外解释文字。"
    raise ValueError(f"JSON 解析失败（{last}）")


def save(sub, name, obj):
    d = os.path.join(DATA, sub)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  [saved] {os.path.relpath(p, ROOT)}")
    return p


# ---------------------------------------------------------------------------
# 1) 拼音知识库（结构化权威数据）
# ---------------------------------------------------------------------------
def build_pinyin():
    initials = {
        "b": "双唇不送气清塞音，双唇闭合后突然打开", "p": "双唇送气清塞音",
        "m": "双唇鼻音", "f": "唇齿清擦音",
        "d": "舌尖中不送气清塞音", "t": "舌尖中送气清塞音",
        "n": "舌尖中鼻音", "l": "舌尖中边音",
        "g": "舌根不送气清塞音", "k": "舌根送气清塞音",
        "h": "舌根清擦音",
        "j": "舌面不送气清塞音（齐齿/撮口呼前）",
        "q": "舌面送气清塞音", "x": "舌面清擦音",
        "zh": "舌尖后不送气清塞音（翘舌）", "ch": "舌尖后送气清塞音（翘舌）",
        "sh": "舌尖后清擦音（翘舌）", "r": "舌尖后浊擦音（翘舌）",
        "z": "舌尖前不送气清塞音（平舌）", "c": "舌尖前送气清塞音（平舌）",
        "s": "舌尖前清擦音（平舌）",
    }
    finals = {
        "a": "开口呼，舌位低、口大开", "o": "开口呼，圆唇后半高",
        "e": "开口呼，展唇后半高", "i": "齐齿呼，前高不圆唇",
        "u": "合口呼，后高圆唇", "ü": "撮口呼，前高圆唇",
        "ai": "复元音，a→i", "ei": "复元音，e→i", "ao": "复元音，a→o", "ou": "复元音，o→u",
        "an": "前鼻尾韵母，舌尖抵上齿龈", "en": "前鼻尾韵母",
        "ang": "后鼻尾韵母，舌根抵软腭", "eng": "后鼻尾韵母",
        "ing": "后鼻尾韵母，i+ng", "ong": "后鼻尾韵母",
        "ia": "i+a", "ie": "i+e", "ua": "u+a", "uo": "u+o", "üe": "ü+e",
        "iao": "i+ao", "iou(iu)": "i+ou", "uai": "u+ai", "uei(ui)": "u+ei",
        "ian": "i+an", "uan": "u+an", "üan": "ü+an", "uen(un)": "u+en",
        "iang": "i+ang", "uang": "u+ang", "ueng": "u+eng", "iong": "i+ong",
    }
    # 方言错误类型 -> 矫正策略
    dialect_errors = [
        {"type": "平翘舌混淆", "desc": "南方方言区常见，zh/z、ch/c、sh/s 不分",
         "pairs": [["支持(zhī chí)", "zī cí"], ["老师(lǎo shī)", "lǎo sī"], ["吃饭(chī fàn)", "cī fàn"]],
         "tip": "翘舌音舌尖上翘抵硬腭前部，平舌音舌尖平伸抵上齿背"},
        {"type": "前后鼻音不分", "desc": "an/ang、en/eng、in/ing 混淆",
         "pairs": [["平安(píng ān)", "pín án"], ["更正(gēng zhèng)", "gēn zhèng"], ["心情(xīn qíng)", "xīng qíng"]],
         "tip": "前鼻音舌尖抵上齿龈，后鼻音舌根后缩抵软腭、鼻腔共鸣更重"},
        {"type": "n/l 混淆", "desc": "部分南方方言 n、l 不分",
         "pairs": [["牛奶(niú nǎi)", "liú lǎi"], ["蓝色(lán sè)", "nán sè"]],
         "tip": "n 为鼻音（气流从鼻出），l 为边音（舌尖抵齿龈、气流从舌侧出）"},
        {"type": "f/h 混淆", "desc": "部分方言 f、h 不分",
         "pairs": [["飞机(fēi jī)", "huī jī"], ["开发(kāi fā)", "kāi huā"]],
         "tip": "f 上齿触下唇，h 舌根接近软腭不接触"},
        {"type": "r/l 混淆", "desc": "部分方言 r、l 混读",
         "pairs": [["热闹(rè nao)", "lè lao"], ["入口(rù kǒu)", "lù kǒu"]],
         "tip": "r 为舌尖后浊擦音，声带振动"},
    ]
    kb = {
        "meta": {"name": "拼音知识库", "source": "结构化权威数据（声韵母表+方言矫正）", "coverage": "全部23声母/常见复韵母/5类方言错误"},
        "initials": initials,
        "finals": finals,
        "spell_rules": [
            "j/q/x 只与 i、ü 及齐齿/撮口呼韵母相拼，不与 u 相拼",
            "ü 与 j/q/x/y 相拼时去两点（ju/qu/xu/yu），但与 n/l 相拼保留（nü/lü）",
            "iou/uei/uen 前加声母时写成 iu/ui/un（如 liu、gui、lun）",
            "声调：阴平55、阳平35、上声214、去声51",
        ],
        "dialect_errors": dialect_errors,
    }
    return kb


# ---------------------------------------------------------------------------
# 2) 英语口语场景库（模型生成）
# ---------------------------------------------------------------------------
ENGLISH_SCENARIOS = ["餐厅点餐", "机场问路", "职场沟通", "面试模拟",
                     "医院就医", "商场购物", "校园交流", "酒店入住"]


def build_english():
    out = []
    for sc in ENGLISH_SCENARIOS:
        prompt = f"""你是一位资深英语口语教学设计师。请为语言学习智能体生成「{sc}」场景的口语练习卡。
只输出一个 JSON 对象，不要任何解释，格式严格如下：
{{"title":"{sc}","level":"基础","goal":"本场景学习目标","dialogue":[{{"role":"coach","text":"..."}},{{"role":"user","text":"..."}}],"key_sentences":["..."],"cultural_notes":"...","common_errors":["..."]}}
要求：dialogue 含 4-6 轮 coach 与 user 的英文对话；key_sentences 3-5 句实用句型；common_errors 列举中文母语者易错点。"""
        card = gen(prompt, temperature=0.4)
        card["scenario"] = sc
        out.append(card)
        print(f"  [en] {sc} done")
    return {"meta": {"name": "英语口语场景库", "count": len(out), "generator": MODEL}, "scenarios": out}


# ---------------------------------------------------------------------------
# 3) 多语种基础教材（模型生成）
# ---------------------------------------------------------------------------
LANGS = [("日语", "ja"), ("韩语", "ko"), ("法语", "fr"), ("西班牙语", "es")]


def build_languages():
    out = []
    for name, code in LANGS:
        prompt = f"""为语言学习智能体生成「{name}」语 A1 入门教材卡。
只输出一个 JSON 对象，不要任何解释，格式严格如下：
{{"language":"{name}","code":"{code}","greetings":[{{"native":"...","romanization":"...","zh":"..."}}],"numbers_1_10":[{{"native":"...","romanization":"...","zh":"..."}}],"common_phrases":[{{"native":"...","romanization":"...","zh":"..."}}],"basic_grammar":"...","tips":"中文母语者学习{name}的注意点"}}
要求：greetings 4 条、numbers_1_10 完整 10 条、common_phrases 6 条。"""
        kit = gen(prompt, temperature=0.4)
        out.append(kit)
        print(f"  [lang] {name} done")
    return {"meta": {"name": "多语种基础教材", "count": len(out), "generator": MODEL}, "languages": out}


# ---------------------------------------------------------------------------
# 4) 提示词变量池（模型生成）
# ---------------------------------------------------------------------------
def build_prompt_vars():
    prompt = """为语言学习智能体生成提示词变量池，用于防止 AI 回复模板化。
只输出一个 JSON 对象，不要任何解释，格式严格如下：
{"openings":["...","..."],"tones":["鼓励型伙伴","严格教练","幽默朋友","耐心长辈"],"strategies":["引导式","练习式","纠错式","情境式","游戏式"],"scenario_adjectives":["..."]}
要求：openings 给 12 条不同的开场白（避免 Let's get started 这类陈词）；scenario_adjectives 给 10 个描述场景氛围的词。"""
    return {"meta": {"name": "提示词变量池", "generator": MODEL}, **gen(prompt, temperature=0.7)}


# ---------------------------------------------------------------------------
# 5) 发音错误弱标注 bootstrap（规则生成，非真实音频）
# ---------------------------------------------------------------------------
def build_pronunciation():
    """生成 '正确/偏差/错误' 三元组种子，作为 SVM 发音检测的弱标注训练格式。
    注意：这是基于规则的弱标签 schema 示例，真实生产需用标注音频训练。"""
    seeds = [
        {"type": "平翘舌", "correct": "老师 lǎo shī", "deviation": "lǎo sī", "error": "lǎo xī", "note": "翘舌sh→平舌s为偏差，→x为严重错误"},
        {"type": "前后鼻音", "correct": "平安 píng ān", "deviation": "pín án", "error": "pīng ān", "note": "ing→in为偏差"},
        {"type": "n/l", "correct": "牛奶 niú nǎi", "deviation": "liú nǎi", "error": "liú lǎi", "note": "n→l混淆"},
        {"type": "f/h", "correct": "飞机 fēi jī", "deviation": "huī jī", "error": "huī jī", "note": "f→h混淆"},
        {"type": "r/l", "correct": "热闹 rè nao", "deviation": "lè nao", "error": "lè lao", "note": "r→l混淆"},
        {"type": "th咬舌", "correct": "three θri:", "deviation": "tree tri:", "error": "sree sri:", "note": "英语θ→t为偏差，→s为错误"},
    ]
    return {"meta": {"name": "发音错误弱标注种子", "mode": "rule-based weak label (非真实音频)",
                     "usage": "作为 SVM 发音检测的训练格式示例，生产需用标注音频替换"},
            "seeds": seeds}


def main():
    print("=== 素材自动采集流水线启动 (engine: %s) ===" % MODEL)
    save("pinyin", "pinyin_kb.json", build_pinyin())
    save("english", "scenarios.json", build_english())
    save("languages", "multilingual.json", build_languages())
    save("prompts", "prompt_vars.json", build_prompt_vars())
    save("pronunciation", "weak_labels.json", build_pronunciation())
    print("=== 采集完成 ===")


if __name__ == "__main__":
    main()
