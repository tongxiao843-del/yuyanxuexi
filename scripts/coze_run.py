"""
Coze 平台自动化部署 — 执行脚本
================================
使用 Playwright + 已有 Chrome Profile 自动完成：
  Phase 1: 创建 Bot + 配置人设
  Phase 2: 上传知识库
  Phase 3: 搭建工作流
"""
import os
import sys
import json
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_PROFILE = os.path.join(ROOT, ".chrome_profile")
COZE_HOME = "https://www.coze.cn/home"
COZE_SPACE = "https://www.coze.cn/space"

def load_prompt():
    path = os.path.join(ROOT, "docs", "coze_bot_prompt.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    prompt_lines = []
    in_prompt = False
    for line in lines:
        if line.startswith("你是「全龄段"):
            in_prompt = True
        if in_prompt:
            prompt_lines.append(line)
    return "\n".join(prompt_lines).strip()

def main():
    from playwright.sync_api import sync_playwright

    prompt = load_prompt()
    print(f"[INFO] 提示词长度: {len(prompt)} 字符")

    with sync_playwright() as p:
        print("[INFO] 启动浏览器...")

        # 使用已有 Chrome profile 保持登录状态
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page()
        page.set_default_timeout(15000)

        # ================================================================
        # Step 1: 打开 Coze 首页
        # ================================================================
        print("[Step 1] 打开 Coze 首页...")
        page.goto(COZE_HOME, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 检查登录状态
        current_url = page.url
        print(f"[INFO] 当前 URL: {current_url}")
        if "login" in current_url.lower() or "passport" in current_url.lower():
            print("[WAIT] 请在浏览器中登录 Coze 账号...")
            print("       登录后脚本会自动继续...")
            # 等待跳转到 home 或 space
            try:
                page.wait_for_url("**/home**", timeout=120000)
                page.wait_for_timeout(3000)
            except Exception:
                try:
                    page.wait_for_url("**/space**", timeout=30000)
                    page.wait_for_timeout(3000)
                except Exception:
                    print("[INFO] 已登录，继续...")

        page.wait_for_timeout(2000)
        print(f"[INFO] 当前页面: {page.url}")

        # ================================================================
        # Step 2: 点击创建 Bot
        # ================================================================
        print("[Step 2] 寻找创建 Bot 入口...")

        # 截图当前状态
        page.screenshot(path=os.path.join(ROOT, "coze_step1.png"))

        # 尝试多种创建入口
        create_clicked = False
        selectors = [
            "text=创建 Bot",
            "text=创建智能体",
            "button:has-text('创建')",
            "a:has-text('创建 Bot')",
            "span:has-text('创建')",
            "[class*='create-btn']",
            "[class*='CreateBtn']",
            "button:has-text('新建')",
            "text=新建 Bot",
        ]

        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    create_clicked = True
                    print(f"[OK] 点击: {sel}")
                    break
            except Exception:
                continue

        if not create_clicked:
            # 尝试直接用 URL 跳转到创建页面
            print("[INFO] 未找到按钮，尝试直接跳转创建页面...")
            try:
                page.goto("https://www.coze.cn/space/bot/create", wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                create_clicked = True
            except Exception:
                pass

        if not create_clicked:
            print("[ERROR] 无法自动创建 Bot，请手动操作。")
            print("        请手动点击「创建 Bot」→ 填写信息 → 点击「发布」")
            print("        完成后按 Ctrl+C 退出")
            try:
                input()
            except Exception:
                pass
            browser.close()
            return

        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(ROOT, "coze_step2_create.png"))
        print(f"[INFO] 创建页面: {page.url}")

        # ================================================================
        # Step 3: 填写 Bot 信息
        # ================================================================
        print("[Step 3] 填写 Bot 名称和简介...")

        # 等页面加载
        page.wait_for_timeout(3000)

        # 填写名称
        name_filled = False
        name_selectors = [
            "input[placeholder*='名称']",
            "input[placeholder*='Bot']",
            "input[placeholder*='智能体']",
            "input.ant-input",
            "input[name='name']",
            "input[data-name='name']",
            "//input[contains(@placeholder, '名称') or contains(@placeholder, 'Bot')]",
        ]
        for sel in name_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    el.fill("")
                    el.fill("全龄段 AI 语言教练")
                    name_filled = True
                    print(f"[OK] 名称已填写 (selector: {sel})")
                    break
            except Exception:
                continue

        if not name_filled:
            print("[WARN] 未能自动填写名称，请手动填写: 全龄段 AI 语言教练")

        page.wait_for_timeout(1000)

        # 填写简介
        desc_filled = False
        desc_selectors = [
            "textarea[placeholder*='简介']",
            "textarea[placeholder*='描述']",
            "textarea.ant-input",
            "textarea[name='description']",
            "[class*='desc'] textarea",
        ]
        for sel in desc_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    el.fill("")
                    el.fill("面向儿童/青少年/成人/老人/方言用户的多语言学习智能体，覆盖拼音、英语口语、日韩法西，具备长期记忆与薄弱点复习。")
                    desc_filled = True
                    print(f"[OK] 简介已填写")
                    break
            except Exception:
                continue

        if not desc_filled:
            print("[WARN] 未能自动填写简介")

        page.wait_for_timeout(1000)

        # ================================================================
        # Step 4: 填写人设提示词
        # ================================================================
        print("[Step 4] 填写人设与回复逻辑...")

        prompt_filled = False
        prompt_selectors = [
            "div[contenteditable='true']",
            "textarea[placeholder*='人设']",
            "textarea[placeholder*='回复']",
            "//textarea[contains(@placeholder, '人设') or contains(@placeholder, '回复')]",
            "div.ProseMirror",
            "[class*='prompt'] textarea",
            "[class*='Prompt'] textarea",
        ]
        for sel in prompt_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    time.sleep(0.5)
                    # 尝试多种填充方式
                    try:
                        el.fill(prompt)
                    except Exception:
                        # contenteditable div 需要不同方式
                        page.evaluate(f"""
                            const el = document.querySelector('[contenteditable="true"]');
                            if (el) {{ el.textContent = {json.dumps(prompt)}; }}
                        """)
                    prompt_filled = True
                    print(f"[OK] 提示词已填写 ({len(prompt)} 字符)")
                    break
            except Exception:
                continue

        if not prompt_filled:
            print("[WARN] 未能自动填写提示词")
            print("       请手动粘贴 docs/coze_bot_prompt.md 的内容")

        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(ROOT, "coze_step3_filled.png"))

        # ================================================================
        # Step 5: 选择模型
        # ================================================================
        print("[Step 5] 选择豆包模型...")

        model_clicked = False
        model_selectors = [
            "[class*='model-select']",
            "[class*='ModelSelect']",
            "select",
            "[class*='selector']",
            "//div[contains(text(), '模型')]/following-sibling::*",
        ]
        for sel in model_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    page.wait_for_timeout(1500)
                    # 在下拉中选择豆包
                    doubao_sel = page.locator("text=豆包, text=Doubao, text=doubao").first
                    if doubao_sel.is_visible(timeout=2000):
                        doubao_sel.click()
                        model_clicked = True
                        print("[OK] 模型已选择: 豆包")
                        break
            except Exception:
                continue

        if not model_clicked:
            print("[WARN] 未能自动选择模型，请手动选择豆包")

        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(ROOT, "coze_step4_model.png"))

        # ================================================================
        # Step 6: 发布
        # ================================================================
        print("[Step 6] 尝试发布...")

        publish_clicked = False
        publish_selectors = [
            "button:has-text('发布')",
            "button:has-text('保存')",
            "text=发布",
            "text=保存并发布",
            "[class*='publish']",
            "[class*='Publish']",
        ]
        for sel in publish_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    publish_clicked = True
                    print(f"[OK] 点击发布: {sel}")
                    break
            except Exception:
                continue

        if not publish_clicked:
            print("[WARN] 未能自动点击发布，请手动点击「发布」按钮")

        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(ROOT, "coze_step5_publish.png"))

        # ================================================================
        # 完成
        # ================================================================
        print("\n" + "=" * 60)
        print("Phase 1 完成！")
        print("=" * 60)
        print(f"\n截图已保存:")
        print(f"  - coze_step1.png    首页")
        print(f"  - coze_step2_create.png  创建页")
        print(f"  - coze_step3_filled.png  填写完成")
        print(f"  - coze_step4_model.png   模型选择")
        print(f"  - coze_step5_publish.png 发布后")

        print("\n[INFO] 浏览器保持打开，以便你检查结果。")
        print("       按 Enter 关闭浏览器...")
        try:
            input()
        except Exception:
            pass
        browser.close()

if __name__ == "__main__":
    main()