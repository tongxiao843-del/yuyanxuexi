# -*- coding: utf-8 -*-
"""
全龄段AI语言教练 —— 交互式终端演示
===================================
在 Trae IDE 终端中直接运行，与智能体实时对话。
调用 agent/engine.py 的生产级引擎，展示六层工作流。

运行方式：
  D:\python.exe scripts/interactive_demo.py
"""

import os
import sys
import time

# 确保项目根在 sys.path 中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ===========================================================================
# 简单颜色定义（避免依赖）
# ===========================================================================
def bold(s): return f"\033[1m{s}\033[0m"
def dim(s): return f"\033[2m{s}\033[0m"
def cyan(s): return f"\033[36m{s}\033[0m"
def green(s): return f"\033[32m{s}\033[0m"
def yellow(s): return f"\033[33m{s}\033[0m"
def red(s): return f"\033[31m{s}\033[0m"
def magenta(s): return f"\033[35m{s}\033[0m"

def hr(char="─", w=60):
    print(dim(char * w))

# ===========================================================================
# 检查 Ollama
# ===========================================================================
def check_ollama():
    try:
        import ollama
        client = ollama.Client()
        models = client.list()
        return True
    except Exception as e:
        print(red(f"\n  Ollama 未就绪: {e}"))
        print(yellow("  请确保 Ollama 正在运行，且已安装 qwen3:1.7b 模型"))
        return False

# ===========================================================================
# 打印指标
# ===========================================================================
def print_metrics(res):
    print()
    hr()
    print(f"  {bold('指标面板')}")
    hr()
    print(f"  {cyan('路由板块')}    {res.get('board', '?')}")
    print(f"  {cyan('目标人群')}    {res.get('group', '?')}")
    print(f"  {cyan('语种')}        {res.get('lang', '?')}")
    print(f"  {cyan('生成耗时')}    {res.get('gen_time', 0):.2f}s")
    print(f"  {cyan('RAG置信度')}   {res.get('rag_confidence', 0):.2f}")
    qs = res.get('quality_score')
    if qs is not None:
        print(f"  {cyan('SVM质量评分')} {qs}/100")
    
    # 护栏状态
    trace = res.get('trace', {})
    guard = trace.get('guardrail')
    if guard:
        passed = guard.get('passed', True)
        if passed:
            print(f"  {cyan('护栏状态')}    {green('✅ 全部通过')}")
        else:
            print(f"  {cyan('护栏状态')}    {red('🚫 拦截')}")
    
    # 薄弱点
    weak = res.get('weak')
    if weak and weak != ["(none)"]:
        print(f"  {cyan('薄弱点')}      {yellow(', '.join(weak[-3:]))}")
    
    # 评估
    ev = res.get('evaluation')
    if ev and ev.get('overall'):
        print(f"  {cyan('综合评分')}    {ev['overall']:.1f}/100")
    hr()

# ===========================================================================
# 主循环
# ===========================================================================
def main():
    os.system("cls" if os.name == "nt" else "clear")
    
    print()
    print(bold(cyan("""
  ╔══════════════════════════════════════════════════════════╗
  ║        🗣️  全 龄 段  A I  语 言 教 练                    ║
  ║        All-Age AI Language Coach                         ║
  ║                                                          ║
  ║        🏆 火山杯 · Trae 赛道 · 交互式演示                 ║
  ╚══════════════════════════════════════════════════════════╝
    """)))
    print(f"  {dim('引擎：')}Ollama qwen3:1.7b | 六层工作流 | 四层护栏 | 七维评估")
    print(f"  {dim('输入 quit 退出  |  输入 reset 重置对话')}")
    hr("═")
    
    if not check_ollama():
        return
    
    print(green("\n  ✅ Ollama 已就绪，加载智能体引擎..."))
    
    try:
        from agent.engine import respond
        print(green("  ✅ 引擎加载成功！"))
    except Exception as e:
        print(red(f"\n  ❌ 引擎加载失败: {e}"))
        return
    
    print()
    print(f"  {cyan('🤖 教练')}: 您好！我是全龄段AI语言教练。")
    print(f"  {dim('请问您想练习：拼音 / 英语口语 / 多语种（日韩法西）？')}")
    print(f"  {dim('直接告诉我您的需求，我会根据您的年龄和基础自动调整教学方式。')}")
    print()
    hr("═")
    
    user_id = "demo_user"
    history = []
    
    while True:
        try:
            user_input = input(f"\n  {green('👤 你')}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {yellow('演示结束，感谢观看！')}")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() == 'quit':
            print(f"\n  {yellow('演示结束，感谢观看！')}")
            break
        
        if user_input.lower() == 'reset':
            history = []
            print(f"  {dim('对话已重置')}")
            continue
        
        # 调用引擎
        print(f"\n  {dim('⏳ 六层工作流处理中...')}")
        t0 = time.time()
        
        try:
            res = respond(user_id, user_input)
        except Exception as e:
            print(red(f"\n  ❌ 引擎错误: {e}"))
            continue
        
        elapsed = time.time() - t0
        
        # 显示回复
        reply = res.get('reply', '抱歉，我暂时无法回答。')
        print(f"\n  {bold(cyan('🤖 教练'))}: {reply}")
        print(f"  {dim(f'(响应耗时: {elapsed:.2f}s)')}")
        
        # 显示指标
        print_metrics(res)
        
        history.append({"role": "user", "content": user_input})
        history.append({"role": "coach", "content": reply})

if __name__ == "__main__":
    main()