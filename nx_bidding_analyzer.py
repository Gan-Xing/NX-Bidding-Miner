import os
import sys

# --- 核心修复：解决打包后路径找不到和双窗口问题 ---
# 1. 强制路径引导
if sys.platform == "darwin":
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/Library/Caches/ms-playwright")
elif sys.platform == "win32":
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

# 2. 递归启动预防 (必须在导入 playwright 之前)
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-m" and "playwright" in sys.argv:
        from playwright.__main__ import main
        sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("playwright") + 1:]
        sys.exit(main())

import asyncio
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from playwright.async_api import async_playwright
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
        self.root.title("宁夏公共资源交易分析工具 v3.5 (GitHub 稳定版 - 修复)")
        self.root.geometry("1000x850")
        
        self.client = None
        # 专家提示词：完全保留，不改一个字
        self.system_prompt = """
你是招投标解析专家。我会给你一批带 [ID] 的公告内容。
你的任务：
1. 识别每条公告中的最终中标人（全称）和中标金额（数字）。
2. 必须忽略所有“第一候选人”、“排名”、“综合得分”。除非公告明确写了某人已中标。
3. 返回 JSON 数组。格式必须包含 ID：
{"results": [{"id": 0, "winner": "公司A", "amount": "123.45"}, {"id": 1, "winner": "公司B", "amount": "null"}]}
4. 如果某公告无明确中标人，该 ID 不输出。
"""
        self.setup_ui()
        
    def setup_ui(self):
        style = ttk.Style()
        style.configure("TButton", padding=6)
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="🛠️ 自动安装/修复运行环境", command=self.install_env).pack(side=tk.LEFT)
        
        config_frame = ttk.LabelFrame(main_frame, text="1. 账号配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)
        ttk.Label(config_frame, text="DeepSeek API Key:").grid(row=0, column=0, sticky=tk.W)
        self.api_key_var = tk.StringVar(value=DEEPSEEK_API_KEY or "")
        ttk.Entry(config_frame, textvariable=self.api_key_var, width=60, show="*").grid(row=0, column=1, padx=5)
        
        task_frame = ttk.LabelFrame(main_frame, text="2. 抓取/分析参数", padding="10")
        task_frame.pack(fill=tk.X, pady=5)
        ttk.Label(task_frame, text="搜索关键词:").grid(row=0, column=0)
        self.keyword_var = tk.StringVar(value="中铁十一局集团有限公司")
        ttk.Entry(task_frame, textvariable=self.keyword_var, width=40).grid(row=0, column=1, padx=5, sticky=tk.W)
        
        self.mode_var = tk.StringVar(value="web")
        ttk.Radiobutton(task_frame, text="网页全量自动抓取", variable=self.mode_var, value="web").grid(row=1, column=0, pady=5)
        ttk.Radiobutton(task_frame, text="粘贴板文本批量分析", variable=self.mode_var, value="text").grid(row=1, column=1, pady=5)

        btn_box = ttk.Frame(main_frame)
        btn_box.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(btn_box, text="🚀 启动执行任务", command=self.start_task)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="🧹 清空运行日志", command=self.clear_logs).pack(side=tk.RIGHT)

        self.input_text = tk.Text(main_frame, height=5, font=("微软雅黑", 9))
        self.input_text.pack(fill=tk.X, pady=5)

        self.log_text = tk.Text(main_frame, height=20, state=tk.DISABLED, bg="#f8f9fa", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def install_env(self):
        def run():
            try:
                self.log("正在尝试自动下载浏览器内核 (约需1-2分钟)...")
                # 修复: 在打包版中使用正确的参数切片调用安装命令
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
                    self.log("✅ 浏览器运行环境已配置完成！")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "浏览器运行环境已配置完成！"))
                else:
                    self.log("❌ 安装过程出现异常。")
            except Exception as e: self.log(f"安装失败: {e}")
        threading.Thread(target=run).start()

    def start_task(self):
        key = self.api_key_var.get().strip()
        if not key: return messagebox.showerror("错误", "请先在上方填写 API Key")
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        
        mode = self.mode_var.get()
        kw = self.keyword_var.get()
        
        if mode == "text":
            content = self.input_text.get(1.0, tk.END).strip()
            threading.Thread(target=self.run_text_task, args=(content, kw)).start()
        else:
            self.start_btn.config(state=tk.DISABLED)
            # 使用更稳定的线程方式启动异步循环
            def thread_run():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.crawl_all_pages(kw))
                except Exception as e:
                    self.log(f"程序崩溃: {e}")
                finally:
                    self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            threading.Thread(target=thread_run).start()

    async def crawl_all_pages(self, keyword):
        self.log(f"开始执行全量自动化抓取：{keyword}")
        raw_db = []
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as e:
                self.log(f"❌ 启动失败！通常是路径解析问题或环境未安装。详情:\n{e}")
                return

            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()
            
            async def handle_response(response):
                if "getFullTextDataNew" in response.url:
                    try:
                        data = await response.json()
                        recs = data.get("result", {}).get("records", [])
                        if recs:
                            self.root.after(0, lambda: self.log(f"📥 拦截成功: 捕获到本页 {len(recs)} 条原始数据包..."))
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
            
            self.log(f"正在加载起始页: {url}")
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(5)
            
            # --- 动态翻页逻辑：完全保留您的原始翻页逻辑 ---
            current_page_idx = 1
            while True:
                next_btn = await page.query_selector(f".m-pagination-page a[data-page-index='{current_page_idx}']")
                if next_btn:
                    btn_text = await next_btn.inner_text()
                    self.log(f"🔄 正在翻至下一页 (页码: {btn_text})...")
                    await next_btn.click()
                    await asyncio.sleep(8) 
                    current_page_idx += 1
                else:
                    self.log(f"✨ 翻页扫描结束，共抓取了 {current_page_idx} 页。")
                    break
            
            await browser.close()

        if not raw_db:
            self.log("❌ 最终未捕获到任何有效数据项目。")
        else:
            self.log(f"✅ 数据捕获完成，共 {len(raw_db)} 个项目。进入 AI 深度批处理分析...")
            all_final = []
            
            for i in range(0, len(raw_db), 5):
                batch = raw_db[i:i+5]
                self.log(f"分析批次 {i//5 + 1} / {(len(raw_db)-1)//5 + 1}...")
                ai_results = self.analyze_batch_json(batch, keyword)
                
                # 精准 ID 匹配
                for item in ai_results:
                    ref_id = item.get("id")
                    if ref_id is not None and int(ref_id) < len(raw_db):
                        orig = raw_db[int(ref_id)]
                        all_final.append({
                            "项目标题": orig["title"],
                            "中标单位": item.get("winner"),
                            "中标金额": item.get("amount"),
                            "发布日期": orig["date"],
                            "源链接": orig["url"]
                        })

            self.save_to_excel(all_final)

    def analyze_batch_json(self, batch, keyword):
        try:
            # 提示词：完全保留您的原始内容
            prompt = f"分析以下公告，识别谁中标了以及成交金额是多少（写数字即可）。必须返回 JSON 结构并包含 ID。关键词: {keyword}\n\n"
            for d in batch:
                prompt += f"--- [ID: {d['id']}] ---\n内容: {d['content'][:2500]}\n\n"

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt + "\n请务必以 JSON 格式返回。"}
                ],
                response_format={"type": "json_object"}
            )
            # 增加对返回结果的鲁棒性检查
            res_content = json.loads(response.choices[0].message.content)
            if isinstance(res_content, dict):
                return res_content.get("results", [])
            elif isinstance(res_content, list):
                return res_content
            return []
        except Exception as e:
            self.log(f"AI 分析过程出错: {e}")
            return []

    def run_text_task(self, content, keyword):
        self.log("正在按照时间戳分割粘贴文本...")
        raw_segs = re.split(r'\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}', content)
        raw_segs = [s.strip() for s in raw_segs if len(s.strip()) > 50]
        
        db = [{"id": i, "content": s, "title": f"手动输入项-{i+1}", "date": datetime.now(), "url": ""} for i, s in enumerate(raw_segs)]
        
        finals = []
        for i in range(0, len(db), 5):
            batch = db[i:i+5]
            res = self.analyze_batch_json(batch, keyword)
            for item in res:
                rid = item.get("id")
                if rid is not None and int(rid) < len(db):
                    orig = db[int(rid)]
                    finals.append({
                        "项目标题": orig["title"], 
                        "中标单位": item.get("winner"), 
                        "中标金额": item.get("amount"), 
                        "发布日期": orig["date"], 
                        "源链接": ""
                    })
        self.save_to_excel(finals)

    def save_to_excel(self, results):
        if not results: 
            self.log("🏁 分析任务结束，未找到有效的中标条目。")
            return
            
        df = pd.DataFrame(results)
        
        def clean(v):
            if v is None or str(v).lower() == "null" or v == 0: return 0
            s = str(v).replace(',', '').replace('¥', '').replace('￥', '').replace('元', '').replace(' ', '').strip()
            num = re.search(r'(\d+\.?\d*)', s)
            return float(num.group(1)) if num else 0
            
        if "中标金额" in df.columns:
            df["中标金额"] = df["中标金额"].apply(clean)
            
        name = f"中标分析结果_{datetime.now().strftime('%m%d_%H%M%S')}.xlsx"
        df.to_excel(name, index=False)
        self.log(f"✅ 任务成功完成！已保存 {len(results)} 条数据到：{name}")
        messagebox.showinfo("成功", f"结果已保存至 Excel 文件：\n{name}")

if __name__ == "__main__":
    t = tk.Tk()
    app = BiddingApp(t)
    t.mainloop()
