import os
import sys
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

# 环境路径加固
USER_HOME = os.path.expanduser("~")
if sys.platform == "darwin":
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(USER_HOME, "Library/Caches/ms-playwright")
elif sys.platform == "win32":
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

# 解决打包递归启动
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-m" and "playwright" in sys.argv:
        from playwright.__main__ import main
        sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("playwright") + 1:]
        sys.exit(main())

# 加载配置
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

class BiddingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("宁夏公共资源交易分析工具 v3.5.4")
        self.root.geometry("1000x850")
        self.client = None
        self.system_prompt = "你是解析专家。请从文本提取[ID, winner, amount]。必须忽略候选人，只提取中标人。请以 JSON 格式返回。"
        self.setup_ui()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="🛠️ 1. 环境安装/检测", command=self.install_env).pack(side=tk.LEFT)
        
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        self.api_key_var = tk.StringVar(value=DEEPSEEK_API_KEY or "")
        ttk.Entry(config_frame, textvariable=self.api_key_var, width=60, show="*").pack(fill=tk.X)
        
        task_frame = ttk.LabelFrame(main_frame, text="参数", padding="10")
        task_frame.pack(fill=tk.X, pady=5)
        self.keyword_var = tk.StringVar(value="中铁十一局集团有限公司")
        ttk.Entry(task_frame, textvariable=self.keyword_var).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        self.mode_var = tk.StringVar(value="web")
        ttk.Radiobutton(task_frame, text="全量抓取", variable=self.mode_var, value="web").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(task_frame, text="文本分析", variable=self.mode_var, value="text").pack(side=tk.LEFT)

        self.start_btn = ttk.Button(main_frame, text="🚀 2. 执行任务", command=self.start_task)
        self.start_btn.pack(fill=tk.X, pady=5)
        
        self.log_text = tk.Text(main_frame, height=25, state=tk.DISABLED, bg="#f8f9fa", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=10)

    def log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def install_env(self):
        def run():
            self.log("正在检查并安装浏览器环境...")
            p = subprocess.Popen([sys.executable, "-m", "playwright", "install", "chromium"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout: self.log(line.strip())
            p.wait()
            self.log("✅ 环境准备完毕！")
            self.root.after(0, lambda: messagebox.showinfo("完成", "环境已就绪"))
        threading.Thread(target=run).start()

    def start_task(self):
        key = self.api_key_var.get().strip()
        if not key: return messagebox.showerror("错误", "API Key 未填写")
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        kw = self.keyword_var.get().strip()
        
        if self.mode_var.get() == "text":
            threading.Thread(target=self.run_text_task, args=(kw,)).start()
        else:
            self.start_btn.config(state=tk.DISABLED)
            def run_async():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.crawl_logic(kw))
                except Exception as e: self.log(f"程序崩溃: {e}")
                finally: self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            threading.Thread(target=run_async).start()

    async def crawl_logic(self, keyword):
        self.log(f"开始工作：关键词[{keyword}]")
        raw_db = []
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                self.log("❌ 启动失败，请点击环境安装按钮！")
                return

            page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            async def handle(r):
                if "getFullTextDataNew" in r.url:
                    try:
                        data = await r.json()
                        recs = data.get("result", {}).get("records", [])
                        for it in recs:
                            raw_db.append({
                                "id": len(raw_db),
                                "title": it.get("title", "").replace("<em>", "").replace("</em>", ""),
                                "content": it.get("content", "").replace("<em>", "").replace("</em>", ""),
                                "date": it.get("infodate", ""),
                                "url": "https://ggzyjy.fzggw.nx.gov.cn" + it.get("linkurl", "")
                            })
                        self.root.after(0, lambda: self.log(f"📥 拦截成功：捕获 {len(recs)} 条公告..."))
                    except: pass

            page.on("response", handle)
            encoded = urllib.parse.quote(keyword)
            await page.goto(f"https://ggzyjy.fzggw.nx.gov.cn/search/fullsearch.html?wd={encoded}")
            await asyncio.sleep(5)
            
            idx = 1
            while True:
                btn = await page.query_selector(f"a[data-page-index='{idx}']")
                if btn:
                    self.log(f"正在翻页: 第 {idx+1} 页")
                    await btn.click()
                    await asyncio.sleep(8)
                    idx += 1
                else: break
            await browser.close()

        if raw_db:
            self.log(f"✅ 抓取结束（共{len(raw_db)}条），开始 AI 深度分析...")
            self.process_with_ai(raw_db, keyword)
        else:
            self.log("⚠️ 未捕获到数据，请检查网络或关键词。")

    def process_with_ai(self, db, kw):
        finals = []
        for i in range(0, len(db), 5):
            batch = db[i:i+5]
            self.log(f"AI 分析进度：{i//5 + 1} / {(len(db)-1)//5 + 1}")
            try:
                prompt = f"分析以下公告，识别中标单位和金额。返回带ID的JSON。\n关键词:[{kw}]\n"
                for d in batch: prompt += f"--- [ID: {d['id']}] ---\n{d['content'][:2500]}\n"
                
                resp = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    timeout=30 # 增加超时防止卡死
                )
                
                # 增强型 JSON 解析逻辑
                content = json.loads(resp.choices[0].message.content)
                if isinstance(content, dict):
                    ai_list = content.get("results", [])
                elif isinstance(content, list):
                    ai_list = content
                else:
                    ai_list = []

                for item in ai_list:
                    rid = item.get("id")
                    if rid is not None and int(rid) < len(db):
                        orig = db[int(rid)]
                        finals.append({"项目标题": orig["title"], "中标单位": item.get("winner"), "中标金额": item.get("amount"), "发布日期": orig["date"], "源链接": orig["url"]})
            except Exception as e:
                self.log(f"⚠️ 批次分析异常（跳过）: {e}")
        
        self.log(f"🏁 AI 分析全部结束，最终成功提取 {len(finals)} 条。")
        if finals:
            df = pd.DataFrame(finals)
            name = f"结果_{datetime.now().strftime('%m%d_%H%M')}.xlsx"
            df.to_excel(name, index=False)
            self.log(f"✨ 导出成功！保存为: {name}")
            messagebox.showinfo("成功", f"文件已保存：{name}")
        else:
            messagebox.showwarning("结束", "任务已完成，但未能分析出有效的中标信息。")

    def run_text_task(self, keyword):
        self.log("本地模式暂未接入，请主要使用全量抓取模式")

if __name__ == "__main__":
    t = tk.Tk()
    app = BiddingApp(t)
    t.mainloop()
