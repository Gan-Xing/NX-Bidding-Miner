import os
import sys

# --- 关键修复 1：最最优先设置环境变量 ---
# 强制 Playwright 寻找系统级路径
USER_HOME = os.path.expanduser("~")
if sys.platform == "darwin": # Mac
    custom_path = os.path.join(USER_HOME, "Library/Caches/ms-playwright")
elif sys.platform == "win32": # Windows
    custom_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
else:
    custom_path = None

if custom_path:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = custom_path

# --- 关键修复 2：修正打包后 Playwright 内部重写逻辑 ---
if __name__ == "__main__":
    # 如果是 subprocess 调用的安装命令
    if len(sys.argv) > 1 and sys.argv[1] == "-m" and "playwright" in sys.argv:
        from playwright.__main__ import main
        # 移除前面的路径和 -m 参数，只保留真正的命令给 playwright
        sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("playwright") + 1:]
        sys.exit(main())

import asyncio
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from playwright.async_api import async_playwright
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import subprocess
from datetime import datetime
import re
import urllib.parse

# 加载配置
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

class BiddingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("宁夏公共资源交易分析工具 v3.5.3 - 终极修复版")
        self.root.geometry("1000x850")
        
        self.client = None
        self.system_prompt = "你是招投标解析专家。请从公告文本中提取中标单位（winner）和金额（amount），忽略候选人。必须返回带ID的JSON。"
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="🛠️ 1. 点击安装/修复环境 (初次必点)", command=self.install_env).pack(side=tk.LEFT)
        
        config_frame = ttk.LabelFrame(main_frame, text="账号配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        self.api_key_var = tk.StringVar(value=DEEPSEEK_API_KEY or "")
        ttk.Entry(config_frame, textvariable=self.api_key_var, width=60, show="*").pack(padx=5, fill=tk.X)
        
        task_frame = ttk.LabelFrame(main_frame, text="2. 运行参数", padding="10")
        task_frame.pack(fill=tk.X, pady=5)
        self.keyword_var = tk.StringVar(value="中铁十一局集团有限公司")
        ttk.Entry(task_frame, textvariable=self.keyword_var).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        self.mode_var = tk.StringVar(value="web")
        ttk.Radiobutton(task_frame, text="自动抓取", variable=self.mode_var, value="web").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(task_frame, text="粘贴分析", variable=self.mode_var, value="text").pack(side=tk.LEFT)

        btn_box = ttk.Frame(main_frame)
        btn_box.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(btn_box, text="🚀 2. 点击启动执行", command=self.start_task)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.log_text = tk.Text(main_frame, height=25, state=tk.DISABLED, bg="#f8f9fa", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=10)

    def log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def install_env(self):
        def run():
            try:
                self.log("正在为您配置环境，请稍候...")
                # 显式重设环境变量确保子进程能拿到
                env = os.environ.copy()
                process = subprocess.Popen(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env
                )
                for line in process.stdout:
                    self.log(line.strip())
                process.wait()
                if process.returncode == 0:
                    self.log("✅ 环境配置成功！可以点击启动了。")
                    messagebox.showinfo("成功", "环境配置成功！")
                else:
                    self.log("❌ 环境安装失败，请检查网络。")
            except Exception as e: self.log(f"错误: {e}")
        threading.Thread(target=run).start()

    def start_task(self):
        key = self.api_key_var.get().strip()
        if not key: return messagebox.showerror("错误", "请填写 Key")
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        kw = self.keyword_var.get().strip()
        
        if self.mode_var.get() == "text":
            threading.Thread(target=self.run_text_task, args=(kw,)).start()
        else:
            self.start_btn.config(state=tk.DISABLED)
            # 在新线程中启动事件循环
            def run_async():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.crawl_logic(kw))
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"❌ 运行崩溃: {e}"))
                finally:
                    self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            threading.Thread(target=run_async).start()

    async def crawl_logic(self, keyword):
        self.log(f"正在启动全量抓取程序，关键词：{keyword}")
        raw_db = []
        try:
            async with async_playwright() as p:
                try:
                    self.log("正在打开 Chromium 浏览器 (Headless)...")
                    browser = await p.chromium.launch(headless=True)
                except Exception as e:
                    self.log(f"❌ 启动失败！通常是环境未安装。详情:\n{e}")
                    return

                page = await browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
                
                async def handle_res(res):
                    if "getFullTextDataNew" in res.url:
                        try:
                            data = await res.json()
                            items = data.get("result", {}).get("records", [])
                            for r in items:
                                raw_db.append({
                                    "id": len(raw_db),
                                    "title": r.get("title", "").replace("<em>", "").replace("</em>", ""),
                                    "content": r.get("content", "").replace("<em>", "").replace("</em>", ""),
                                    "date": r.get("infodate", ""),
                                    "url": "https://ggzyjy.fzggw.nx.gov.cn" + r.get("linkurl", "")
                                })
                            self.root.after(0, lambda: self.log(f"📥 成功捕获 {len(items)} 条公告..."))
                        except: pass

                page.on("response", handle_res)
                encoded = urllib.parse.quote(keyword)
                await page.goto(f"https://ggzyjy.fzggw.nx.gov.cn/search/fullsearch.html?wd={encoded}", wait_until="networkidle")
                await asyncio.sleep(5)
                
                # 动态翻页
                idx = 1
                while True:
                    btn = await page.query_selector(f"a[data-page-index='{idx}']")
                    if btn:
                        self.log(f"🔄 正在点击第 {idx+1} 页...")
                        await btn.click()
                        await asyncio.sleep(8)
                        idx += 1
                        if len(raw_db) > 200: break # 安全限制
                    else: break
                await browser.close()
        except Exception as e:
            self.log(f"🚫 抓取过程异常终止: {e}")

        if raw_db:
            self.log(f"✅ 抓取结束，共收集 {len(raw_db)} 条，开始 AI 分析...")
            self.process_with_ai(raw_db, keyword)
        else:
            self.log("⚠️ 未捕获到任何数据。")

    def process_with_ai(self, db, kw):
        # 此处省略具体 AI 调用逻辑，保留与 v3.5 一致的结构...
        finals = []
        for i in range(0, len(db), 5):
            batch = db[i:i+5]
            self.log(f"分析批次 {i//5 + 1}...")
            # 模拟 AI 调用
            prompt = f"分析: {kw}\n" + "\n".join([f"ID:{d['id']} 内容:{d['content'][:1500]}" for d in batch])
            try:
                resp = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                ai_results = json.loads(resp.choices[0].message.content).get("results", [])
                for item in ai_results:
                    rid = item.get("id")
                    if rid is not None and int(rid) < len(db):
                        orig = db[int(rid)]
                        finals.append({"项目标题": orig["title"], "中标单位": item.get("winner"), "中标金额": item.get("amount"), "发布日期": orig["date"], "链接": orig["url"]})
            except Exception as e: self.log(f"批次分析失败: {e}")
        
        if finals:
            df = pd.DataFrame(finals)
            name = f"结果_{datetime.now().strftime('%m%d_%H%M')}.xlsx"
            df.to_excel(name, index=False)
            self.log(f"✨ 大功告成！文件保存为: {name}")
            messagebox.showinfo("成功", f"文件已保存: {name}")

    def run_text_task(self, keyword):
        # 粘贴模式逻辑...
        pass

if __name__ == "__main__":
    t = tk.Tk()
    app = BiddingApp(t)
    t.mainloop()
