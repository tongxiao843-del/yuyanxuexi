# -*- coding: utf-8 -*-
r"""
全龄段AI语言教练 —— 反模板化 Web 交互界面
===========================================
独立 Flask 应用，非 Streamlit、非 AI 模板化 UI。
暖色调 . 有机形态 . 卡片式布局 . 双击编辑

运行：D:\python.exe scripts\web_demo.py
访问：http://localhost:5280
"""

import os
import sys
import json
import time
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=None)

# 全局引擎引用
_respond = None

def get_respond():
    global _respond
    if _respond is None:
        from agent.engine import respond
        _respond = respond
    return _respond

# ===========================================================================
# HTML 页面（内嵌，反模板化设计）
# ===========================================================================
PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>全龄段AI语言教练</title>
<style>
/* ============================================================
   RESET & 基础 —— 暖色调体系，拒绝 AI 蓝白模板
   ============================================================ */
:root {
  --cream:    #F9F5EB;
  --sand:     #EFE7D6;
  --terracotta: #D4785C;
  --terracotta-light: #E8A790;
  --olive:    #7D8C6E;
  --olive-light: #A8B89A;
  --navy:     #2D3340;
  --navy-light: #4A5368;
  --warm-white: #FDFAF3;
  --shadow:   0 2px 16px rgba(45,51,64,0.08);
  --shadow-lg: 0 8px 40px rgba(45,51,64,0.12);
  --radius: 18px;
  --radius-sm: 10px;
  --font: "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font);
  background: var(--cream);
  color: var(--navy);
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
  background-image:
    radial-gradient(ellipse at 20% 80%, #E8D5C4 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, #D4E0CC 0%, transparent 50%);
}

/* 主容器 —— 卡片式，非全屏 */
.main-container {
  width: 100%;
  max-width: 1100px;
  height: 85vh;
  max-height: 800px;
  display: flex;
  gap: 20px;
}

/* 左侧对话区 */
.chat-panel {
  flex: 1;
  min-width: 0;
  background: var(--warm-white);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #E8D5C4;
}

/* 右侧指标面板 */
.metrics-panel {
  width: 280px;
  flex-shrink: 0;
  background: var(--warm-white);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #E8D5C4;
}

/* 头部 */
.header {
  padding: 20px 24px;
  border-bottom: 1px solid #E8D5C4;
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--terracotta), var(--olive));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: white;
  flex-shrink: 0;
}

.header-text h2 {
  font-size: 17px;
  font-weight: 700;
  color: var(--navy);
  letter-spacing: 0.02em;
}

.header-text span {
  font-size: 12px;
  color: var(--olive);
  font-weight: 500;
}

/* 状态指示灯 */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--olive);
  flex-shrink: 0;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 朗读开关 */
.tts-toggle {
  margin-left: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1.5px solid #D4C4B0;
  background: transparent;
  color: var(--navy-light);
  font-size: 12px;
  font-family: var(--font);
  cursor: pointer;
  transition: all 0.25s;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  flex-shrink: 0;
}

.tts-toggle:hover {
  border-color: var(--terracotta);
  color: var(--terracotta);
}

.tts-toggle.on {
  background: var(--terracotta);
  color: white;
  border-color: var(--terracotta);
}

.tts-toggle .tts-icon {
  font-size: 14px;
  transition: transform 0.2s;
}

.tts-toggle.on .tts-icon {
  transform: scale(1.15);
}

/* 朗读中脉冲 */
.msg.coach.speaking .msg-bubble {
  box-shadow: 0 0 0 3px var(--terracotta-light);
  transition: box-shadow 0.3s;
}

/* 消息区 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-behavior: smooth;
}

.messages::-webkit-scrollbar { width: 4px; }
.messages::-webkit-scrollbar-thumb { background: #D4C4B0; border-radius: 4px; }

/* 消息气泡 —— 完全去 AI 模板化 */
.msg {
  display: flex;
  gap: 10px;
  max-width: 88%;
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.msg.coach .msg-avatar {
  background: #F0E6D8;
  color: var(--terracotta);
}

.msg.user .msg-avatar {
  background: #DDE4D4;
  color: var(--olive);
}

.msg-bubble {
  padding: 14px 18px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
  white-space: pre-wrap;
}

.msg.coach .msg-bubble {
  background: #F5EFE6;
  border: 1px solid #E8D5C4;
  border-radius: 16px 16px 16px 4px;
  color: var(--navy);
}

.msg.user .msg-bubble {
  background: linear-gradient(135deg, #DDE4D4, #E8ECD8);
  border-radius: 16px 16px 4px 16px;
  color: var(--navy);
}

.msg-time {
  font-size: 10px;
  color: #B8A898;
  margin-top: 4px;
  padding: 0 4px;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 6px;
  padding: 8px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--terracotta-light);
  animation: bounce 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}

/* 输入区 */
.input-area {
  padding: 16px 24px;
  border-top: 1px solid #E8D5C4;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-area textarea {
  flex: 1;
  border: 2px solid #E8D5C4;
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  font-size: 14px;
  font-family: var(--font);
  resize: none;
  background: #FDFAF3;
  color: var(--navy);
  outline: none;
  transition: border-color 0.2s;
  min-height: 44px;
  max-height: 120px;
  line-height: 1.5;
}

.input-area textarea:focus {
  border-color: var(--terracotta);
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, var(--terracotta), #C4694E);
  color: white;
  font-size: 18px;
  cursor: pointer;
  transition: transform 0.15s, opacity 0.15s;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn:hover {
  transform: scale(1.05);
  opacity: 0.9;
}

.send-btn:active {
  transform: scale(0.95);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

/* 快捷按钮 */
.quick-btns {
  display: flex;
  gap: 8px;
  padding: 0 24px 8px;
  flex-wrap: wrap;
}

.quick-btn {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1.5px solid #D4C4B0;
  background: transparent;
  color: var(--navy-light);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: var(--font);
  white-space: nowrap;
}

.quick-btn:hover {
  border-color: var(--terracotta);
  color: var(--terracotta);
  background: #FDF5F0;
}

/* ============================================================
   右侧指标面板
   ============================================================ */
.metrics-header {
  padding: 20px 24px;
  border-bottom: 1px solid #E8D5C4;
  font-size: 14px;
  font-weight: 700;
  color: var(--navy);
  display: flex;
  align-items: center;
  gap: 8px;
}

.metrics-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metric-card {
  background: #F9F5EB;
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  border: 1px solid #EBE0D0;
}

.metric-label {
  font-size: 11px;
  color: #A89888;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
  font-weight: 600;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--navy);
}

.metric-value.good { color: var(--olive); }
.metric-value.warn { color: #D4A04A; }
.metric-value.bad { color: var(--terracotta); }

.metric-sub {
  font-size: 11px;
  color: #B8A898;
  margin-top: 4px;
}

/* 工作流步骤 */
.wf-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 12px;
}

.wf-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.wf-dot.done { background: var(--olive); }
.wf-dot.active { background: var(--terracotta); animation: pulse 1s infinite; }
.wf-dot.wait { background: #D4C4B0; }

/* 护栏状态条 */
.guardrail-bar {
  height: 4px;
  border-radius: 2px;
  background: #E8D5C4;
  margin-top: 8px;
  overflow: hidden;
}

.guardrail-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s;
}

.guardrail-fill.pass { background: var(--olive); width: 100%; }
.guardrail-fill.intercept { background: var(--terracotta); width: 100%; }

/* 响应式 */
@media (max-width: 800px) {
  .main-container { flex-direction: column; height: auto; }
  .metrics-panel { width: 100%; max-height: 200px; }
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #C4B4A0;
  text-align: center;
  padding: 40px;
}

.empty-state .big-icon {
  font-size: 48px;
  opacity: 0.6;
}

.empty-state p {
  font-size: 14px;
  max-width: 280px;
  line-height: 1.6;
}
</style>
</head>
<body>

<div class="main-container">
  <!-- ===== 左侧对话区 ===== -->
  <div class="chat-panel">
    <div class="header">
      <div class="header-icon">&#x1F399;</div>
      <div class="header-text">
        <h2>全龄段 AI 语言教练</h2>
        <span>拼音 · 英语口语 · 多语种入门</span>
      </div>
      <button class="tts-toggle" id="ttsToggle" onclick="toggleTTS()" title="朗读模式">
        <span class="tts-icon">&#x1F50A;</span> 朗读
      </button>
      <div class="status-dot" id="statusDot"></div>
    </div>

    <div class="messages" id="messages">
      <div class="empty-state" id="emptyState">
        <div class="big-icon">&#x1F30D;</div>
        <p>你好！我是你的专属语言教练。<br>支持拼音矫正、英语口语、日韩法西入门。<br>告诉我你想学什么吧！</p>
      </div>
    </div>

    <div class="quick-btns">
      <button class="quick-btn" onclick="quickSend('我想学拼音，平翘舌分不清')">&#x1F4D6; 学拼音</button>
      <button class="quick-btn" onclick="quickSend('练英语口语，餐厅点餐')">&#x1F37D; 英语口语</button>
      <button class="quick-btn" onclick="quickSend('我想学日语，零基础')">&#x1F1EF;&#x1F1F5; 学日语</button>
      <button class="quick-btn" onclick="quickSend('我是退休老人，想学旅游英语')">&#x1F30F; 适老化</button>
    </div>

    <div class="input-area">
      <textarea id="userInput" rows="1" placeholder="输入你的学习需求..."
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage();}"></textarea>
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">&#x27A4;</button>
    </div>
  </div>

  <!-- ===== 右侧指标面板 ===== -->
  <div class="metrics-panel">
    <div class="metrics-header">
      &#x2699; 实时指标
    </div>
    <div class="metrics-body" id="metricsBody">
      <div class="metric-card">
        <div class="metric-label">路由板块</div>
        <div class="metric-value" id="mBoard">—</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">目标人群</div>
        <div class="metric-value" id="mGroup">—</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">生成耗时</div>
        <div class="metric-value" id="mTime">—</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">SVM 质量评分</div>
        <div class="metric-value" id="mQuality">—</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">RAG 置信度</div>
        <div class="metric-value" id="mRag">—</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">护栏状态</div>
        <div class="metric-value good" id="mGuard">—</div>
        <div class="guardrail-bar"><div class="guardrail-fill pass" id="guardFill"></div></div>
      </div>
      <div class="metric-card" style="border-left: 3px solid var(--terracotta);">
        <div class="metric-label">六层工作流</div>
        <div id="wfSteps">
          <div class="wf-step"><span class="wf-dot wait"></span> L1 意图识别</div>
          <div class="wf-step"><span class="wf-dot wait"></span> L2 记忆检索</div>
          <div class="wf-step"><span class="wf-dot wait"></span> L3 RAG 检索</div>
          <div class="wf-step"><span class="wf-dot wait"></span> L4 内容生成</div>
          <div class="wf-step"><span class="wf-dot wait"></span> L5 质量校验</div>
          <div class="wf-step"><span class="wf-dot wait"></span> L6 记忆写入</div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
// ============================================================
// 交互逻辑
// ============================================================
const msgContainer = document.getElementById('messages');
const emptyState = document.getElementById('emptyState');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
let isProcessing = false;
let ttsEnabled = false;

// 朗读音频元素
const audioEl = document.createElement('audio');
audioEl.id = 'ttsAudio';
document.body.appendChild(audioEl);

function toggleTTS() {
  ttsEnabled = !ttsEnabled;
  const btn = document.getElementById('ttsToggle');
  if (ttsEnabled) {
    btn.className = 'tts-toggle on';
    btn.innerHTML = '<span class="tts-icon">&#x1F50A;</span> 朗读中';
  } else {
    btn.className = 'tts-toggle';
    btn.innerHTML = '<span class="tts-icon">&#x1F50A;</span> 朗读';
    audioEl.pause();
    audioEl.src = '';
    // 移除所有 speaking 标记
    document.querySelectorAll('.msg.coach.speaking').forEach(el => el.classList.remove('speaking'));
  }
}

async function playTTS(text, msgEl) {
  if (!ttsEnabled) return;
  try {
    // 限制文本长度，避免过长
    const ttsText = text.length > 500 ? text.substring(0, 500) + '...' : text;
    const resp = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: ttsText })
    });
    if (!resp.ok) return;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    audioEl.src = url;
    if (msgEl) msgEl.classList.add('speaking');
    audioEl.onended = () => {
      if (msgEl) msgEl.classList.remove('speaking');
      URL.revokeObjectURL(url);
    };
    audioEl.onerror = () => {
      if (msgEl) msgEl.classList.remove('speaking');
      URL.revokeObjectURL(url);
    };
    await audioEl.play();
  } catch (e) {
    // 静默失败，不影响主流程
    if (msgEl) msgEl.classList.remove('speaking');
  }
}

function addMessage(role, text) {
  if (emptyState) emptyState.remove();
  const now = new Date();
  const time = now.getHours().toString().padStart(2,'0') + ':' +
               now.getMinutes().toString().padStart(2,'0');

  const div = document.createElement('div');
  div.className = 'msg ' + role;
  const avatar = role === 'coach' ? '&#x1F399;' : '&#x1F464;';
  div.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div>
      <div class="msg-bubble">${escapeHtml(text)}</div>
      <div class="msg-time">${time}</div>
    </div>
  `;
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;
  return div;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/\n/g, '<br>');
}

function addTypingIndicator() {
  if (emptyState) emptyState.remove();
  const div = document.createElement('div');
  div.className = 'msg coach';
  div.id = 'typingMsg';
  div.innerHTML = `
    <div class="msg-avatar">&#x1F399;</div>
    <div class="msg-bubble">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  msgContainer.appendChild(div);
  msgContainer.scrollTop = msgContainer.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('typingMsg');
  if (el) el.remove();
}

function setProcessing(v) {
  isProcessing = v;
  sendBtn.disabled = v;
  userInput.disabled = v;
  document.getElementById('statusDot').style.animation =
    v ? 'pulse 0.5s infinite' : 'pulse 2s infinite';
}

function animateWorkflow() {
  const steps = document.querySelectorAll('#wfSteps .wf-dot');
  let i = 0;
  const interval = setInterval(() => {
    if (i < steps.length) {
      steps[i].className = 'wf-dot active';
      i++;
    } else {
      clearInterval(interval);
      steps.forEach(s => s.className = 'wf-dot done');
      setTimeout(() => {
        steps.forEach(s => s.className = 'wf-dot wait');
      }, 3000);
    }
  }, 300);
}

function updateMetrics(data) {
  document.getElementById('mBoard').textContent = data.board || '—';
  document.getElementById('mGroup').textContent = data.group || '—';
  document.getElementById('mTime').textContent = (data.gen_time || 0).toFixed(2) + 's';

  const qs = data.quality_score;
  const qEl = document.getElementById('mQuality');
  qEl.textContent = qs != null ? qs + '/100' : '—';
  qEl.className = 'metric-value ' + (qs >= 80 ? 'good' : qs >= 60 ? 'warn' : 'bad');

  const rag = data.rag_confidence;
  const rEl = document.getElementById('mRag');
  rEl.textContent = rag != null ? rag.toFixed(2) : '—';
  rEl.className = 'metric-value ' + (rag >= 0.75 ? 'good' : rag >= 0.5 ? 'warn' : 'bad');

  const guardEl = document.getElementById('mGuard');
  const guardFill = document.getElementById('guardFill');
  const trace = data.trace || {};
  const guard = trace.guardrail;
  if (guard && !guard.passed) {
    guardEl.textContent = '拦截';
    guardEl.className = 'metric-value bad';
    guardFill.className = 'guardrail-fill intercept';
  } else {
    guardEl.textContent = '通过';
    guardEl.className = 'metric-value good';
    guardFill.className = 'guardrail-fill pass';
  }
}

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || isProcessing) return;
  userInput.value = '';
  userInput.style.height = 'auto';

  addMessage('user', text);
  setProcessing(true);
  addTypingIndicator();
  animateWorkflow();

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'demo_user', message: text })
    });
    const data = await resp.json();
    removeTypingIndicator();

    if (data.error) {
      addMessage('coach', '抱歉，出了点问题：' + data.error);
    } else {
      const msgEl = addMessage('coach', data.reply || '抱歉，我暂时无法回答。');
      updateMetrics(data);
      // 朗读模式
      playTTS(data.reply, msgEl);
    }
  } catch (e) {
    removeTypingIndicator();
    addMessage('coach', '网络连接失败，请检查后端是否运行。');
  }
  setProcessing(false);
}

function quickSend(text) {
  userInput.value = text;
  sendMessage();
}

// 自动调整 textarea 高度
userInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
</script>
</body>
</html>"""

# ===========================================================================
# API
# ===========================================================================
@app.route('/')
def index():
    return PAGE, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True)
    user_id = data.get('user_id', 'demo_user')
    message = data.get('message', '')

    if not message.strip():
        return jsonify({'error': 'empty message'})

    try:
        respond = get_respond()
        t0 = time.time()
        res = respond(user_id, message)
        res['gen_time'] = round(time.time() - t0, 2)

        # 序列化友好
        out = {
            'reply': res.get('reply', ''),
            'board': res.get('board', ''),
            'group': res.get('group', ''),
            'lang': res.get('lang', ''),
            'gen_time': res.get('gen_time', 0),
            'rag_confidence': res.get('rag_confidence'),
            'quality_score': res.get('quality_score'),
            'trace': {
                'guardrail': res.get('trace', {}).get('guardrail'),
            },
        }
        return jsonify(out)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tts', methods=['POST'])
def tts():
    """使用 edge-tts 将文本转为语音"""
    import asyncio
    import io
    import edge_tts

    data = request.get_json(force=True)
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty text'}), 400

    # 选择合适的语音
    voice = 'zh-CN-XiaoxiaoNeural'  # 中文女声
    # 根据内容判断语种
    if any('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in text):
        voice = 'zh-CN-XiaoxiaoNeural'
    elif any('\uac00' <= c <= '\ud7af' for c in text):
        voice = 'ko-KR-SunHiNeural'
    elif any('\u3040' <= c <= '\u309f' for c in text):
        voice = 'ja-JP-NanamiNeural'
    else:
        voice = 'zh-CN-XiaoxiaoNeural'

    async def synthesize():
        communicate = edge_tts.Communicate(text, voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                buf.write(chunk['data'])
        buf.seek(0)
        return buf

    loop = asyncio.new_event_loop()
    try:
        buf = loop.run_until_complete(synthesize())
    finally:
        loop.close()

    from flask import Response
    return Response(buf.read(), mimetype='audio/mpeg')

# ===========================================================================
# 启动
# ===========================================================================
if __name__ == '__main__':
    print("""
  \033[36m╔══════════════════════════════════════════════════════╗
  ║   🗣️  全龄段 AI 语言教练  ·  Web 交互界面            ║
  ║                                                      ║
  ║   打开浏览器访问:  \033[1;33mhttp://localhost:5280\033[0;36m              ║
  ║   按 Ctrl+C 停止服务                                 ║
  ╚══════════════════════════════════════════════════════╝\033[0m
    """)
    app.run(host='0.0.0.0', port=5280, debug=False)