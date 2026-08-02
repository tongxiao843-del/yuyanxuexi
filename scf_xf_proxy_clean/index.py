import os
import json
import base64
import hmac
import hashlib
import time
import re
import concurrent.futures
import urllib.request
import urllib.parse
import urllib.error
import websocket

APPID = os.environ["XF_APPID"]
APIKEY = os.environ["XF_APIKEY"]
APISECRET = os.environ["XF_APISECRET"]
HOST = "ise-api.xfyun.cn"
PATH = "/v2/open-ise"

# Coze 工作流 / Bot 配置（可被环境变量覆盖；默认值来自用户已发布的工作流）
WORKFLOW_ID = os.environ.get("WORKFLOW_ID") or "7666863185047519270"
COZE_BOT_ID = os.environ.get("COZE_BOT_ID") or "7666779488595787827"


def board_to_lang(board: str):
    """根据板块选择讯飞评测的语言和题型。"""
    b = (board or "").lower()
    if "pinyin" in b or "拼音" in b:
        return {"language": "zh_cn", "category": "read_syllable"}
    if "english" in b or "英语" in b:
        return {"language": "en_us", "category": "read_word"}
    return {"language": "zh_cn", "category": "read_sentence"}


def strip_wav_header(buf: bytes) -> bytes:
    """讯飞要求纯 PCM，去掉 WAV 文件头（44 字节）。"""
    if buf[:4] == b"RIFF":
        return buf[44:]
    return buf


def build_ws_url() -> str:
    """构造带签名的讯飞语音评测 WebSocket URL。"""
    date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    sig_origin = f"host: {HOST}\ndate: {date}\nGET {PATH} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(APISECRET.encode("utf-8"), sig_origin.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    auth_origin = (
        f'api_key="{APIKEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(auth_origin.encode("utf-8")).decode("utf-8")
    return (
        f"wss://{HOST}{PATH}?"
        f"authorization={authorization}&date={date}&host={HOST}"
    )


def eval_speech(audio_base64: str, reference_text: str, language: str, category: str) -> str:
    """调用讯飞 ISE 流式语音评测，返回原始 sig XML 字符串。"""
    ws_url = build_ws_url()
    state = {"sig": "", "done": False, "error": None}

    def on_open(ws):
        ws.send(
            json.dumps(
                {
                    "common": {"app_id": APPID},
                    "business": {
                        "language": language,
                        "category": category,
                        "evalue_mode": "1",
                        "rstcd": "utf8",
                        "group": "1",
                        "subjective_score": "1",
                    },
                    "data": {
                        "status": 0,
                        "text": base64.b64encode(reference_text.encode("utf-8")).decode("utf-8"),
                    },
                }
            )
        )
        ws.send(
            json.dumps(
                {
                    "data": {
                        "status": 2,
                        "audio": audio_base64,
                        "encoding": "raw",
                        "sample_rate": 16000,
                    }
                }
            )
        )

    def on_message(ws, message):
        m = json.loads(message)
        if m.get("code", 0) != 0:
            state["error"] = m.get("message", "unknown")
            ws.close()
            return
        data = m.get("data", {})
        if "sig" in data:
            state["sig"] += data["sig"]
        if data.get("status") == 2:
            state["done"] = True
            ws.close()

    def on_error(ws, error):
        state["error"] = str(error)

    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
    ws.run_forever(timeout=15)

    if state["error"]:
        raise Exception(state["error"])
    if not state["done"]:
        raise Exception("evaluation did not complete")
    return state["sig"]


def parse_result(sig: str) -> dict:
    """从 sig XML 中提取总分和逐词得分。"""
    tm = re.search(r"<total_score>([\d.]+)</total_score>", sig)
    overall = float(tm.group(1)) if tm else 0.0
    words = []
    for m in re.finditer(
        r"<word[^>]*>\s*<content>([^<]*)</content>[\s\S]*?<total_score>([\d.]+)</total_score>",
        sig,
    ):
        words.append({"word": m.group(1), "score": float(m.group(2))})
    return {"overall_score": overall, "words": words}


# ---------------------------------------------------------------------------
# Coze 通用 HTTP 工具
# ---------------------------------------------------------------------------
def _http_json(method: str, url: str, token: str, payload=None, timeout: int = 40):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_assistant_text(msgs) -> str:
    reply = ""
    if isinstance(msgs, list):
        for m in msgs:
            if not isinstance(m, dict):
                continue
            if m.get("role") == "assistant" and m.get("type", "answer") in ("answer", None):
                reply += m.get("content", "")
    return reply


def _wait_and_fetch_coze(conv_id: str, chat_id: str, token: str) -> str:
    q = urllib.parse.urlencode({"conversation_id": conv_id, "chat_id": chat_id})
    base = "https://api.coze.cn/v3/chat"
    for _ in range(10):
        status = ""
        try:
            st = _http_json("GET", f"{base}/retrieve?{q}", token, timeout=15)
            status = ((st or {}).get("data") or {}).get("status", "")
        except Exception:
            status = ""
        if status in ("completed", "failed", "requires_action"):
            break
        time.sleep(2)
    try:
        msgs = _http_json("GET", f"{base}/message/list?{q}", token, timeout=15)
        return _extract_assistant_text((msgs or {}).get("data"))
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Coze Bot 对话（多轮记忆 / 评测指导兜底）
# ---------------------------------------------------------------------------
def coze_chat(user_msg: str, conversation_id: str = None):
    token = os.environ.get("COZE_TOKEN")
    bot_id = COZE_BOT_ID
    if not token or not bot_id:
        return None, None
    payload = {
        "bot_id": bot_id,
        "user_id": "demo_user",
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [
            {"role": "user", "content": user_msg, "content_type": "text"}
        ],
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    try:
        data = _http_json("POST", "https://api.coze.cn/v3/chat", token, payload, timeout=45)
    except Exception:
        return None, None
    d = (data or {}).get("data") or {}
    conv_id = d.get("conversation_id") or conversation_id
    reply = _extract_assistant_text(d.get("messages"))
    if not reply:
        chat_id = d.get("id")
        if conv_id and chat_id:
            reply = _wait_and_fetch_coze(conv_id, chat_id, token)
    return (reply or None), conv_id


# ---------------------------------------------------------------------------
# Coze 工作流调用（核心：呈现用户在 Coze 上设计的工作流功能）
# ---------------------------------------------------------------------------
def coze_workflow_run(input_text: str, age: str = None, board: str = None):
    """调用用户在 Coze 设计的工作流 /v1/workflow/run。

    工作流入参只有 `input`（用户意图）。为强化意图明确性，可附加板块/画像上下文。
    返回工作流输出的纯文本；失败返回 None。
    """
    token = os.environ.get("COZE_TOKEN")
    if not token:
        return None
    ctx = []
    if board:
        ctx.append(f"板块：{board}")
    if age:
        ctx.append(f"用户画像：{age}")
    inp = input_text
    if ctx:
        inp = f"【语境】{'；'.join(ctx)}。" + input_text
    payload = {
        "bot_id": COZE_BOT_ID,
        "workflow_id": WORKFLOW_ID,
        "parameters": {"input": inp},
    }
    try:
        d = _http_json("POST", "https://api.coze.cn/v1/workflow/run", token, payload, timeout=45)
    except Exception:
        return None
    if d.get("code") not in (0, None):
        msg = d.get("msg", "")
        if d.get("code") == 4028 or "credit" in msg.lower() or "额度" in msg:
            return "【额度提示】Coze 工作流调用额度已用尽，请等待额度刷新（或升级付费版）后再试。语音研习室的发音评测不受影响，可继续使用。"
        return None
    out = (d or {}).get("data")
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except Exception:
            return out
    if isinstance(out, dict):
        return out.get("output")
    return None


def _looks_like_menu(text: str) -> bool:
    """启发式判断工作流输出是否为『重新选场景/年龄』的菜单式开场。
    精确化：避免把课程里"你可以选任意一句"等正常表述误判为菜单。"""
    t = text or ""
    ages = ["儿童", "青少年", "成人", "老人", "老年"]
    if sum(1 for a in ages if a in t) >= 3:
        return True
    if re.search(r"你的年龄段|选.*年龄段|告诉.*年龄段|先(选|告诉|提供).*年龄", t):
        return True
    if re.search(r"回复对应编号|回复对应数字|选对应编号|直接回复对应", t):
        return True
    if len(t) < 220 and (t.startswith("哈喽") or t.startswith("您好！我是")):
        return True
    return False


def _short_intent(inp: str, board: str = None) -> str:
    s = re.sub(
        r"^(我想练|我想|我要练|请|帮我|带我|我要|教我|我想学|练)", "", inp or ""
    ).strip(" ，,。、")
    if board:
        s = s.replace(board, "").replace("口语", "").replace("场景", "").strip(" ，,。、")
    return re.split(r"[，,。；;]", s)[0].strip()


def _coach_via_workflow(inp: str, age: str, board: str):
    """以工作流为主引擎。工作流输出非确定性（同句有时给课、有时弹选年龄菜单），
    且单次调用约 20-25s。故并发发起 4 个相同请求，谁先返回真实课程就用谁——
    延迟≈单次调用，命中率约 94%。全为菜单则返回一个菜单（前端渲染为优雅选择卡）。
    切忌写"不要提问"类指令——实测反而触发工作流问年龄分支。"""
    sc = _short_intent(inp, board)
    clean = f"带练{age}{board}{sc}，直接给课。"
    attempts = [inp, clean, clean, clean]
    last = [None]
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=len(attempts))
    futs = {ex.submit(coze_workflow_run, a, age, board): a for a in attempts}
    try:
        for fut in concurrent.futures.as_completed(futs, timeout=55):
            try:
                out = fut.result()
            except Exception:
                out = None
            if out:
                last[0] = out
                if not _looks_like_menu(out):
                    return out, "workflow"
    except concurrent.futures.TimeoutError:
        pass
    finally:
        ex.shutdown(wait=False)
    if last[0] is None:
        # 并发全部失败（可能是瞬时限流），退回单次串行重试
        last[0] = coze_workflow_run(clean, age, board)
    return last[0], "workflow"


def _handle_coach(body: dict) -> dict:
    """action=coach：以工作流为主引擎生成辅导（三连试容错）。"""
    inp = (body.get("input") or "").strip()
    if not inp:
        return _resp({"error": "missing input"})
    age = body.get("age")
    board = body.get("board")
    try:
        wf_out, source = _coach_via_workflow(inp, age, board)
        if not wf_out:
            return _resp({"error": "empty reply from coze"})
        return _resp({"reply": wf_out, "source": source})
    except Exception as e:
        return _resp({"error": str(e)})


def _handle_chat(body: dict) -> dict:
    """action=chat：文本对话转发 Coze Bot（保留兼容）。"""
    message = (body.get("message") or "").strip()
    if not message:
        return _resp({"error": "missing message"})
    try:
        reply, conv_id = coze_chat(message, body.get("conversation_id"))
        out = {"reply": reply or "", "conversation_id": conv_id}
        if not reply:
            out["error"] = "empty reply from coze"
        return _resp(out)
    except Exception as e:
        return _resp({"error": str(e)})


def _handle_eval(body: dict) -> dict:
    """action=eval：讯飞发音评测。"""
    reference_text = body.get("reference_text")
    board = body.get("board", "")
    audio_base64 = body.get("audio_base64")
    audio_url = body.get("audio_url")

    if not reference_text:
        return _resp({"error": "missing reference_text"})
    if not audio_base64 and not audio_url:
        return _resp({"error": "missing audio"})

    try:
        if audio_base64:
            buf = strip_wav_header(base64.b64decode(audio_base64))
        else:
            req = urllib.request.Request(audio_url, method="GET")
            with urllib.request.urlopen(req, timeout=20) as resp:
                buf = strip_wav_header(resp.read())
        audio_b64 = base64.b64encode(buf).decode("utf-8")

        lang = board_to_lang(board)
        sig = eval_speech(audio_b64, reference_text, lang["language"], lang["category"])
        parsed = parse_result(sig)
        parsed.update(
            {
                "reference_text": reference_text,
                "language": lang["language"],
            }
        )
        return _resp(parsed)
    except Exception as e:
        return _resp({"error": str(e)})


def _parse_event_body(event: dict) -> dict:
    raw = event.get("body", "{}") if isinstance(event, dict) else "{}"
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
        except Exception:
            decoded = raw
        try:
            return json.loads(decoded)
        except Exception:
            return {}
    return {}


def _resp(body_obj: dict, status: int = 200) -> dict:
    return {
        "isBase64Encoded": False,
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body_obj, ensure_ascii=False),
    }


def main_handler(event: dict, context=None):
    """Web 函数入口：按 action 路由。"""
    # 预检
    if isinstance(event, dict) and event.get("httpMethod") == "OPTIONS":
        return _resp({}, 204)
    body = _parse_event_body(event)
    action = body.get("action")
    if not action:
        action = "eval" if (body.get("audio_base64") or body.get("audio_url")) else "coach"
    if action == "chat":
        return _handle_chat(body)
    if action == "eval":
        return _handle_eval(body)
    # 默认 coach（工作流）
    return _handle_coach(body)
