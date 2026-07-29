"""
Coze 知识库自动上传 — 直接操作 Bot 页面
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_PROFILE = os.path.join(ROOT, ".chrome_profile")
BOT_URL = "https://www.coze.cn/space/7568504513364508710/bot/7666779488595787827"

KB_FILES = [
    {
        "name": "拼音知识库",
        "path": os.path.join(ROOT, "data", "coze_kb", "拼音知识库.md"),
    },
    {
        "name": "英语口语场景库",
        "path": os.path.join(ROOT, "data", "coze_kb", "英语口语场景库.md"),
    },
    {
        "name": "多语种教材库",
        "path": os.path.join(ROOT, "data", "coze_kb", "多语种教材库.md"),
    },
]

def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        print("[INFO] 启动浏览器...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page()
        page.set_default_timeout(15000)

        # ================================================================
        # Step 1: 打开 Bot 编辑页
        # ================================================================
        print(f"[Step 1] 打开 Bot 页面: {BOT_URL}")
        page.goto(BOT_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(ROOT, "kb_step1_bot.png"))

        # 检查登录
        if "login" in page.url.lower() or "signin" in page.url.lower():
            print("[WAIT] 需要登录，请在浏览器中完成登录...")
            try:
                page.wait_for_url("**/bot/**", timeout=120000)
                page.wait_for_timeout(3000)
            except Exception:
                print("[INFO] 继续尝试...")

        print(f"[INFO] 当前页面: {page.url}")
        page.wait_for_timeout(3000)

        # ================================================================
        # Step 2: 点击「知识库」Tab
        # ================================================================
        print("[Step 2] 寻找「知识库」Tab...")

        kb_tab_clicked = False
        kb_selectors = [
            "text=知识库",
            "span:has-text('知识库')",
            "div:has-text('知识库')",
            "[class*='tab']:has-text('知识')",
            "//div[contains(text(), '知识库')]",
            "//span[contains(text(), '知识库')]",
            "//*[contains(@class, 'tab') and contains(text(), '知识')]",
        ]

        for sel in kb_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    kb_tab_clicked = True
                    print(f"[OK] 点击知识库: {sel}")
                    break
            except Exception:
                continue

        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(ROOT, "kb_step2_tab.png"))

        # ================================================================
        # Step 3: 遍历上传知识库
        # ================================================================
        for i, kb in enumerate(KB_FILES):
            print(f"\n[Step 3.{i+1}] 上传知识库: {kb['name']}")

            if not os.path.exists(kb['path']):
                print(f"  [ERROR] 文件不存在: {kb['path']}")
                continue

            with open(kb['path'], "r", encoding="utf-8") as f:
                content = f.read()
            print(f"  文件大小: {len(content)} 字符")

            # 点击「新建知识库」或「添加知识库」
            add_clicked = False
            add_selectors = [
                "button:has-text('新建知识库')",
                "button:has-text('添加知识库')",
                "button:has-text('创建知识库')",
                "text=新建知识库",
                "text=添加知识库",
                "span:has-text('新建')",
                "[class*='add']:has-text('知识')",
                "button:has-text('新建')",
                "//button[contains(text(), '新建')]",
                "//button[contains(text(), '添加')]",
            ]
            for sel in add_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        add_clicked = True
                        print(f"  [OK] 点击: {sel}")
                        break
                except Exception:
                    continue

            if not add_clicked:
                print("  [WARN] 未找到新建按钮，尝试手动...")
                page.screenshot(path=os.path.join(ROOT, f"kb_step3_{i}_noadd.png"))
                continue

            page.wait_for_timeout(3000)
            page.screenshot(path=os.path.join(ROOT, f"kb_step3_{i}_create.png"))

            # 填写知识库名称
            name_filled = False
            name_selectors = [
                "input[placeholder*='名称']",
                "input[placeholder*='知识库']",
                "input.ant-input",
                "input[name='name']",
                "//input[contains(@placeholder, '名称')]",
            ]
            for sel in name_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        el.fill("")
                        time.sleep(0.3)
                        el.fill(kb['name'])
                        name_filled = True
                        print(f"  [OK] 名称: {kb['name']}")
                        break
                except Exception:
                    continue

            if not name_filled:
                print("  [WARN] 未能填写名称")

            page.wait_for_timeout(1000)

            # 上传文件 — 找文件上传按钮
            upload_clicked = False
            upload_selectors = [
                "input[type='file']",
                "button:has-text('上传')",
                "text=上传文件",
                "text=上传文档",
                "span:has-text('上传')",
                "[class*='upload']",
                "//button[contains(text(), '上传')]",
            ]

            # 先尝试直接设置 file input
            try:
                file_input = page.locator("input[type='file']").first
                if file_input.count() > 0:
                    file_input.set_input_files(kb['path'])
                    upload_clicked = True
                    print(f"  [OK] 文件已选择: {kb['path']}")
            except Exception:
                pass

            if not upload_clicked:
                for sel in upload_selectors:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=2000):
                            el.click()
                            page.wait_for_timeout(2000)
                            # 尝试找到文件选择器
                            try:
                                file_input = page.locator("input[type='file']").first
                                file_input.set_input_files(kb['path'])
                                upload_clicked = True
                                print(f"  [OK] 文件已选择: {kb['path']}")
                                break
                            except Exception:
                                continue
                    except Exception:
                        continue

            if not upload_clicked:
                print("  [WARN] 未能自动上传文件")

            page.wait_for_timeout(3000)
            page.screenshot(path=os.path.join(ROOT, f"kb_step3_{i}_uploaded.png"))

            # 点击确认/保存
            confirm_clicked = False
            confirm_selectors = [
                "button:has-text('确认')",
                "button:has-text('保存')",
                "button:has-text('确定')",
                "button:has-text('创建')",
                "text=确认",
                "text=保存",
            ]
            for sel in confirm_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        confirm_clicked = True
                        print(f"  [OK] 点击确认")
                        break
                except Exception:
                    continue

            page.wait_for_timeout(5000)
            page.screenshot(path=os.path.join(ROOT, f"kb_step3_{i}_done.png"))

            # 等待向量化完成
            print(f"  [INFO] 等待向量化...")
            page.wait_for_timeout(3000)

        # ================================================================
        # 完成
        # ================================================================
        print("\n" + "=" * 60)
        print("Phase 2 完成！")
        print("=" * 60)
        print("\n截图已保存:")
        print("  kb_step1_bot.png")
        print("  kb_step2_tab.png")
        print("  kb_step3_*_uploaded.png")
        print("  kb_step3_*_done.png")
        print("\n浏览器保持打开，检查结果后按 Enter 关闭...")
        try:
            input()
        except Exception:
            pass
        browser.close()

if __name__ == "__main__":
    main()