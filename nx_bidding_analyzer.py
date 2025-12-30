import os
import sys

# --- 关键修复 1：在所有导入之前设置环境变量 ---
# 强制 Playwright 使用系统的全局路径，而不是打包后的临时路径
if sys.platform == "darwin": # Mac
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/Library/Caches/ms-playwright")
elif sys.platform == "win32": # Windows
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
else:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

# --- 关键修复 2：防止打包后的递归启动问题 ---
if __name__ == "__main__":
    # 如果检测到是 playwright 的子进程调用，则交还控制权
    if len(sys.argv) > 1 and (sys.argv[1] == "-m" or "playwright" in sys.argv[1]):
        from playwright.__main__ import main
        sys.argv = [s for s in sys.argv if s != "-m"]
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
        self.root.title("宁夏公共资源交易分析工具 v3.5.2 (打包修复版)")
        self.root.geometry("1000x850")
        
        self.client = None
        self.system_prompt = """
你是招投标解析专家。我会给你一批带 [ID] 的公告内容。
你的任务：
1. 识别每条公告中的最终中标人（全称）和中标金额（数字）。
2. 必须忽略所有“第一候选人”、“排名”、“综合得分”。除非公告明确写了某人已中标。
3. 返回 JSON 数组。格式必须包含 ID：
{"results": [{"id": 0, "winner": "公司A", "amount": "123.45"}]}
"""
        self.setup_ui()
        
    def setup_ui(self):
        style = ttk.Style()
        style.configure("TButton", padding=6)
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="🛠️ 初次运行点击：一键安装环境 (解决启动失败)", command=self.install_env).pack(side=tk.LEFT)
        
        config_frame = ttk.LabelFrame(main_frame, text="1. 账号配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        ttk.Label(config_frame, text="DeepSeek API Key:").grid(row=0, column=0, sticky=tk.W)
        self.api_key_var = tk.StringVar(value=DEEPSEEK_API_KEY or "")
        ttk.Entry(config_frame, textvariable=self.api_key_var, width=60, show="*").grid(row=0, column=1, padx=5)
        
        task_frame = ttk.LabelFrame(main_frame, text="2. 抓取参数", padding="10")
        task_frame.pack(fill=tk.X, pady=5)
        self.keyword_var = tk.StringVar(value="中铁十一局集团有限公司")
        ttk.Entry(task_frame, textvariable=self.keyword_var, width=40).grid(row=0, column=1, padx=5, sticky=tk.W)
        
        self.mode_var = tk.StringVar(value="web")
        ttk.Radiobutton(task_frame, text="网页自动抓取", variable=self.mode_var, value="web").grid(row=1, column=0)
        ttk.Radiobutton(task_frame, text="粘贴文本分析", variable=self.mode_var, value="text").grid(row=1, column=1)

        btn_box = ttk.Frame(main_frame)
        btn_box.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(btn_box, text="🚀 启动执行", command=self.start_task)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.input_text = tk.Text(main_frame, height=5, font=("微软雅黑", 9))
        self.input_text.pack(fill=tk.X, pady=5)

        self.log_text = tk.Text(main_frame, height=20, state=tk.DISABLED, bg="#f8f9fa", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def install_env(self):
        def run():
            try:
                self.log("正在尝试唤起系统环境安装程序...")
                # 使用特殊的调用方式，配合开头的 sys.argv 判断
                process = subprocess.Popen(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=os.environ.copy()
                )
                for line in process.stdout:
                    self.log(line.strip())
                process.wait()
                if process.returncode == 0:
                    self.log("✅ 浏览器组件已安装到系统全局目录。")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "环境已就绪，现在可以开始抓取！"))
                else:
                    self.log("❌ 安装未成功，请检查网络连接。")
            except Exception as e: self.log(f"错误: {e}")
        threading.Thread(target=run).start()

    def start_task(self):
        key = self.api_key_var.get().strip()
        if not key: return messagebox.showerror("错误", "请填写 Key")
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        kw = self.keyword_var.get()
        if self.mode_var.get() == "text":
            threading.Thread(target=self.run_text_task, args=(self.input_text.get(1.0, tk.END), kw)).start()
        else:
            self.start_btn.config(state=tk.DISABLED)
            threading.Thread(target=lambda: asyncio.run(self.crawl_logic(kw))).start()

    async def crawl_logic(self, keyword):
        self.log(f"启动抓取：{keyword}")
        raw_db = []
        async with async_playwright() as p:
            try:
                # 检查指定的路径下是否有浏览器
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                self.log(f"❌ 还是找不到浏览器。建议手动在终端运行: playwright install chromium\n详情: {e}")
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                return

            page = await browser.new_page()
            async def handle_response(response):
                if "getFullTextDataNew" in response.url:
                    try:
                        data = await response.json()
                        recs = data.get("result", {}).get("records", [])
                        for r in recs:
                            raw_db.append({
                                "id": len(raw_db),
                                "title": r.get("title", "").replace("<em>", "").replace("</em>", ""),
                                "content": r.get("content", "").replace("<em>", "").replace("</em>", ""),
                                "date": r.get("infodate", ""),
                                "url": "https://ggzyjy.fzggw.nx.gov.cn" + r.get("linkurl", "")
                            })
                    except: pass

            page.on("response", handle_response)
            encoded_kw = urllib.parse.quote(keyword)
            url = f"https://ggzyjy.fzggw.nx.gov.cn/search/fullsearch.html?wd={encoded_kw}"
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(5)
            
            # --- 全量翻页 ---
            idx = 1
            while True:
                btn = await page.query_selector(f"a[data-page-index='{idx}']")
                if btn:
                    self.log(f"翻页中: {idx+1}")
                    await btn.click()
                    await asyncio.sleep(8)
                    idx += 1
                else: break
            await browser.close()

        if raw_db:
            self.log(f"抓取成功 {len(raw_db)} 条，开始 AI 分析...")
            finals = []
            for i in range(0, len(raw_db), 5):
                batch = raw_db[i:i+5]
                ai_res = self.analyze_batch(batch, keyword)
                for item in ai_res:
                    rid = item.get("id")
                    if rid is not None and rid < len(raw_db):
                        orig = raw_db[rid]
                        finals.append({"项目标题": orig["title"], "中标单位": item.get("winner"), "中标金额": item.get("amount"), "发布日期": orig["date"], "源链接": orig["url"]})
            self.save(finals)
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

    def analyze_batch(self, batch, kw):
        try:
            prompt = f"分析以下公告，识别中标人和金额。关键词: {kw}\n\n"
            for d in batch: prompt += f"--- [ID: {d['id']}] ---\n{d['content'][:2500]}\n"
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content).get("results", [])
        except: return []

    def save(self, results):
        if not results: return
        df = pd.DataFrame(results)
        name = f"结果_{datetime.now().strftime('%m%d_%H%M%S')}.xlsx"
        df.to_excel(name, index=False)
        self.log(f"✅ 已保存至: {name}")
        messagebox.showinfo("完成", f"保存成功：{name}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BiddingApp(root)
    root.mainloop()
