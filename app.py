"""
全龄段多语言学习智能体 —— 生产级 Streamlit 界面
================================================
功能：
  - 对话交互（三层提示词 + 六层工作流）
  - 评估面板（七维度评分实时展示）
  - 护栏状态监控（拦截率 / 告警 / 连续低质量）
  - 阈值监控（RAG 置信度 / 防模板化指标 / 生成耗时）
  - 记忆分区查看
运行：streamlit run app.py
"""
import os, asyncio, json, tempfile
import streamlit as st
from agent.engine import respond, Memory, CORPUS, MODEL
from agent.config import THRESHOLDS, WORKFLOW, ANTI_TEMPLATE, EVAL_DIMENSIONS

st.set_page_config(page_title="全龄段多语言学习智能体", page_icon="🗣️", layout="wide")

# ===========================================================================
# 页面标题
# ===========================================================================
st.title("🗣️ 全龄段多语言学习智能体")
st.caption(
    f"引擎：本地 Ollama {MODEL} ｜ 六层工作流 ｜ "
    f"Agentic RAG + SVM + 四层护栏 + 七维评估 + 六层防模板化"
)

# ===========================================================================
# 侧边栏：设置 + 系统状态
# ===========================================================================
with st.sidebar:
    st.header("⚙️ 设置")
    user_id = st.text_input("用户ID（记忆分区键）", "demo_user")
    tts_on = st.toggle("语音播报 (Edge-TTS)", value=True)

    st.divider()

    # --- 记忆薄弱点 ---
    st.subheader("📌 当前记忆薄弱点")
    mem = Memory(user_id)
    weak_all = []
    for b in ["pinyin", "english"]:
        weak_all += mem.data.get(b, {}).get("weak", [])
    for k, v in mem.data.get("languages", {}).items():
        weak_all += v.get("weak", [])
    if weak_all:
        for w in weak_all[-8:]:
            st.write("• " + w)
    else:
        st.write("（暂无）")

    st.divider()

    # --- 护栏统计 ---
    st.subheader("🛡️ 护栏状态")
    try:
        from agent.guardrails import GuardrailPipeline
        _pipe = GuardrailPipeline()
        stats = _pipe.stats()
        col1, col2 = st.columns(2)
        col1.metric("总调用", stats.get("total_calls", 0))
        col2.metric("拦截率", f"{stats.get('intercept_rate', 0)*100:.1f}%")
        col1.metric("拦截", stats.get("intercepted", 0))
        col2.metric("标记", stats.get("flagged", 0))
        col1.metric("重定向", stats.get("redirected", 0))
        col2.metric("质量告警", stats.get("quality_alerts", 0))
        if stats.get("layer_breakdown"):
            with st.expander("层级明细"):
                for k, v in sorted(stats["layer_breakdown"].items()):
                    st.text(f"  {k}: {v}")
    except Exception as e:
        st.warning(f"护栏统计不可用：{e}")

    st.divider()

    # --- 评估汇总 ---
    st.subheader("📊 评估汇总")
    try:
        from agent.evaluation import EvaluationDashboard
        dash = EvaluationDashboard(days=7)
        summary = dash.summary()
        st.metric("评估记录数", summary.get("count", 0))
        st.metric("综合均分", f"{summary.get('overall', 0):.1f}")
        with st.expander("七维度均分"):
            for dim in EVAL_DIMENSIONS:
                val = summary.get(dim, 0)
                st.progress(min(val / 100, 1.0), text=f"{dim}: {val:.1f}")
        # 公平性报告
        fairness = dash.fairness_report()
        if fairness and "_fairness_gap" in fairness:
            st.caption(f"群体公平性极差：{fairness['_fairness_gap']:.1f} "
                       f"({fairness.get('_fairness_status', 'N/A')})")
    except Exception as e:
        st.warning(f"评估汇总不可用：{e}")

    st.divider()

    # --- 阈值配置 ---
    st.subheader("🎛️ 阈值配置")
    with st.expander("查看当前阈值"):
        st.json({
            "意图置信度": THRESHOLDS.get("intent_confidence", {}),
            "发音检测": THRESHOLDS.get("pronunciation_error", {}),
            "输出质量": THRESHOLDS.get("output_quality", {}),
            "内容重复度": THRESHOLDS.get("content_similarity", {}),
            "RAG置信度": THRESHOLDS.get("rag_confidence", {}),
            "安全护栏": THRESHOLDS.get("safety_guardrail", {}),
        })

    # --- 工作流开关 ---
    st.subheader("🔧 工作流开关")
    st.caption(f"SVM过滤: {'✅' if WORKFLOW.get('enable_svm_filter') else '❌'}  "
               f"护栏: {'✅' if WORKFLOW.get('enable_guardrails') else '❌'}")
    st.caption(f"多候选: {'✅' if WORKFLOW.get('enable_multi_candidate') else '❌'}  "
               f"评估: {'✅' if WORKFLOW.get('enable_evaluation') else '❌'}")
    st.caption(f"最大重生成: {WORKFLOW.get('max_regen_attempts', 2)} 次")

# ===========================================================================
# TTS 语音合成
# ===========================================================================
VOICES = {"pinyin": "zh-CN-XiaoxiaoNeural", "english": "en-US-AriaNeural",
          "ja": "ja-JP-NanamiNeural", "ko": "ko-KR-SunHiNeural",
          "fr": "fr-FR-DeniseNeural", "es": "es-ES-ElviraNeural"}

def speak(text, board, lang):
    try:
        import edge_tts
        v = VOICES.get(lang, VOICES.get(board, "zh-CN-XiaoxiaoNeural"))
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        async def _run():
            comm = edge_tts.Communicate(text, v)
            await comm.save(path)
        asyncio.run(_run())
        return path
    except Exception:
        return None

# ===========================================================================
# 指标面板渲染
# ===========================================================================
def _render_metrics(metrics):
    """渲染单次调用的生产级指标面板。"""
    # 基本信息行
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("分支", metrics.get("board", "—"))
    col2.metric("人群", metrics.get("group", "—"))
    col3.metric("生成耗时", f"{metrics.get('gen_time', 0):.2f}s")
    col4.metric("RAG置信度", f"{metrics.get('rag_confidence', 0):.2f}")

    # 质量评分行
    qs = metrics.get("quality_score")
    if qs is not None:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("SVM质量评分", f"{qs}/100")
        col2.metric("候选数", metrics.get("candidates_count", 1))
        col3.metric("去重过滤", metrics.get("duplicates_filtered", 0))
        col4.metric("SRT状态", "激活" if metrics.get("srt_active") else "待激活")

    # 七维度评估
    ev = metrics.get("evaluation")
    if ev:
        st.markdown("**七维度评估**")
        scores = ev.get("scores", {})
        if scores:
            cols = st.columns(len(EVAL_DIMENSIONS))
            for i, dim in enumerate(EVAL_DIMENSIONS):
                val = scores.get(dim, 0)
                cols[i].metric(dim, f"{val}")
            overall = ev.get("overall", 0)
            st.progress(min(overall / 100, 1.0), text=f"综合分: {overall:.1f}")
            alerts = ev.get("alerts", [])
            if alerts:
                for a in alerts:
                    st.warning(f"⚠️ {a.get('message', '')}")

    # 护栏状态
    guardrail = metrics.get("guardrail")
    if guardrail:
        st.markdown("**护栏状态**")
        passed = guardrail.get("passed", True)
        status = guardrail.get("status", "pass")
        if passed and status == "pass":
            st.success("✅ 全部护栏通过")
        elif status == "flag":
            st.warning("⚠️ 护栏标记（内容可疑但未拦截）")
        else:
            st.error("🚫 护栏拦截")

# ===========================================================================
# 对话历史
# ===========================================================================
if "hist" not in st.session_state:
    st.session_state.hist = []

for m in st.session_state.hist:
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if m.get("audio"):
            st.audio(m["audio"])
        if m["role"] == "coach" and m.get("metrics"):
            with st.expander("📊 本次调用指标", expanded=False):
                _render_metrics(m["metrics"])

# ===========================================================================
# 聊天输入
# ===========================================================================
user_text = st.chat_input("对我说：例如『我想学拼音』『练英语口语餐厅点餐』『学日语』")

if user_text:
    st.session_state.hist.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.write(user_text)

    with st.chat_message("coach"):
        with st.spinner("六层工作流处理中…"):
            res = respond(user_id, user_text)

        st.write(res["reply"])
        st.caption(
            f"路由：{res['board']} ｜ 语种：{res['lang']} ｜ 人群：{res['group']} ｜ "
            f"耗时：{res.get('gen_time', 0):.2f}s"
        )

        # 语音播报
        audio = speak(res["reply"], res["board"], res["lang"]) if tts_on else None
        if audio:
            st.audio(audio)

        # 构建指标面板数据
        trace = res.get("trace", {})
        gen_trace = trace.get("generation", {})
        metrics = {
            "board": res["board"],
            "group": res["group"],
            "gen_time": res.get("gen_time", 0),
            "rag_confidence": res.get("rag_confidence", 0),
            "quality_score": res.get("quality_score"),
            "candidates_count": gen_trace.get("candidates_count", 1),
            "duplicates_filtered": gen_trace.get("duplicates_filtered", 0),
            "srt_active": gen_trace.get("srt_active", False),
            "evaluation": res.get("evaluation"),
            "guardrail": trace.get("guardrail"),
        }

        with st.expander("📊 本次调用指标", expanded=True):
            _render_metrics(metrics)

        st.session_state.hist.append({
            "role": "coach",
            "content": res["reply"],
            "audio": audio,
            "metrics": metrics,
        })

        # 薄弱点提示
        if res.get("weak"):
            with st.info(f"💡 已记录薄弱点：{', '.join(res['weak'][-3:])}"):
                pass
