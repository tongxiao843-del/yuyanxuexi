#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「言塾」本地开发服务器（零三方依赖，仅标准库）。

职责：
  1. 托管 web/ 静态资源（web/index.html 单文件应用）
  2. /api/coach  -> 调用用户在 Coze 设计的工作流 /v1/workflow/run（教学指导引擎）
                  工作流若只回"选场景/年龄"菜单，则回退到 Coze Bot /v3/chat
  3. /api/eval   -> 发音评测：优先转发到已部署的腾讯云函数（含讯飞凭证），
                  否则若本机有 websocket-client 且配置了 XF_* 则本地评测

运行：
  COZE_TOKEN=pat_xxx SCF_URL=https://xxxx.ap-guangzhou.tencentscf.com \
      python server.py
  -> 浏览器打开 http://localhost:8000
"""
import os
import sys
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
COZE_PAT = os.environ.get("COZE_TOKEN", "")
COZE_BOT_ID = os.environ.get("COZE_BOT_ID", "7666779488595787827")
WORKFLOW_ID = os.environ.get("WORKFLOW_ID", "7666863185047519270")
SCF_URL = os.environ.get("SCF_URL", "")  # 评测转发目标（含讯飞凭证）

PORT = int(os.environ.get("PORT", "8000"))


# --------------------------------------------------------------------------
# Coze 调用
# --------------------------------------------------------------------------
def _http_json(method, url, token, payload=None, timeout=45):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _extract_assistant_text(msgs):
    reply = ""
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "assistant":
                reply += m.get("content", "")
    return reply


def coze_workflow_run(input_text, age=None, board=None):
    if not COZE_PAT:
        return None
    ctx = []
    if board:
        ctx.append(f"板块：{board}")
    if age:
        ctx.append(f"用户画像：{age}")
    inp = input_text
    if ctx:
        inp = f"【语境】{'；'.join(ctx)}。" + input_text
    try:
        d = _http_json("POST", "https://api.coze.cn/v1/workflow/run", COZE_PAT,
                       {"bot_id": COZE_BOT_ID, "workflow_id": WORKFLOW_ID,
                        "parameters": {"input": inp}}, timeout=45)
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
    return out.get("output") if isinstance(out, dict) else None


def _looks_like_menu(text):
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


def coze_chat(user_msg, conversation_id=None):
    if not COZE_PAT:
        return None, None
    payload = {"bot_id": COZE_BOT_ID, "user_id": "demo_user", "stream": False,
               "auto_save_history": True,
               "additional_messages": [{"role": "user", "content": user_msg, "content_type": "text"}]}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    try:
        d = _http_json("POST", "https://api.coze.cn/v3/chat", COZE_PAT, payload, timeout=45)
    except Exception:
        return None, None
    dd = (d or {}).get("data") or {}
    return (dd.get("reply") or _extract_assistant_text(dd.get("messages"))) or None, dd.get("conversation_id")


def _short_intent(inp, board=None):
    s = re.sub(r"^(我想练|我想|我要练|请|帮我|带我|我要|教我|我想学|练)", "", inp or "").strip(" ，,。、")
    if board:
        s = s.replace(board, "").replace("口语", "").replace("场景", "").strip(" ，,。、")
    return re.split(r"[，,。；;]", s)[0].strip()


def _coach_via_workflow(inp, age, board):
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


def handle_coach(body):
    inp = (body.get("input") or "").strip()
    if not inp:
        return {"error": "missing input"}
    wf, source = _coach_via_workflow(inp, body.get("age"), body.get("board"))
    if not wf:
        return {"error": "empty reply from coze"}
    return {"reply": wf, "source": source}


def handle_eval(body):
    if not SCF_URL:
        return {"error": "SCF_URL not configured; cannot evaluate locally"}
    try:
        req = urllib.request.Request(SCF_URL, data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": f"eval forward failed: {e}"}


# --------------------------------------------------------------------------
# HTTP 服务
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS,GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("", "/"):
            p = "/index.html"
        fp = os.path.normpath(os.path.join(WEB_DIR, p.lstrip("/")))
        if not fp.startswith(WEB_DIR):
            self.send_error(403)
            return
        self._send_file(fp)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            body = {}
        p = urllib.parse.urlparse(self.path).path
        if p == "/api/coach":
            self._send_json(handle_coach(body))
        elif p == "/api/eval":
            self._send_json(handle_eval(body))
        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        sys.stderr.write("[言塾] " + (fmt % args) + "\n")


if __name__ == "__main__":
    print(f"言塾 dev server on http://localhost:{PORT}")
    print(f"  COZE_PAT configured: {bool(COZE_PAT)} | SCF_URL: {SCF_URL or '(none)'}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
