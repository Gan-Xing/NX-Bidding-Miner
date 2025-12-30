# 宁夏公共资源交易中标数据抓取分析工具 (NX-Bidding-Miner)

这是一个基于 **Playwright** 和 **DeepSeek AI** 的专业级自动化抓取分析工具，专门用于提取宁夏公共资源交易网中的中标单位和金额。

## ✨ 核心特性

- **动态拦截技术**：直接从网络层拦截原始 JSON 数据包，避开了复杂的 HTML 解析，保证数据 100% 完整。
- **AI 智能分拣**：利用 DeepSeek 大模型，自动剔除“候选人”、“综合得分”等干扰项，只提取最终中标结果。
- **批处理优化**：每 5 条公告合成一个包进行分析，既保证了准确性又提高了处理效率。
- **精准对齐**：使用唯一的内部分配 ID 锁定技术，确保项目标题、发布日期、源链接与 AI 提取的中标信息绝对匹配。
- **双模运作**：
  - **自动抓取模式**：全自动翻页、全量数据挖掘。
  - **辅助分析模式**：支持手动粘贴网页内容，AI 自动从乱码中提取表格。

## 🚀 快速开始

### 1. 环境准备
确保您的电脑已安装 Python 3.8 或更高版本。

安装依赖库：
```bash
pip install -r requirements.txt
```

初始化浏览器引擎（自动抓取模式必选）：
```bash
playwright install chromium
```

### 2. 运行程序
```bash
python nx_bidding_analyzer.py
```

## 📦 打包为 EXE (给控制台不熟悉的朋友)

如果您想把工具分享给 Windows 用户，可以按照以下步骤打包：

1. 安装 PyInstaller：
   ```bash
   pip install pyinstaller
   ```
2. 运行打包命令：
   ```bash
   pyinstaller --noconsole --onefile --clean --collect-all playwright nx_bidding_analyzer.py
   ```
*生成的 EXE 文件将包含“环境一键安装”按钮，方便非技术人员使用。*

## 📂 项目结构
- `nx_bidding_analyzer.py`: 主程序 (包含 GUI 界面)
- `requirements.txt`: 依赖清单
- `.env`: API 密钥存放
- `中标分析结果_xxxx.xlsx`: 自动生成的分析报表

## ⚖️ 许可说明
本项目仅用于学习研究及日常办公效率提升，请遵守相关法律法规。
