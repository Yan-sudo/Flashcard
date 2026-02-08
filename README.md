# Vocabulary Flashcard Generator

PDF 文章词汇闪卡生成器 — 自动从 PDF 文章中提取重难点词汇，生成中英西三语闪卡 PDF。

## Features

- **Web GUI**: 浏览器操作界面，上传 PDF、配置 API Key、实时查看进度、下载结果
- **Gemini AI 驱动**: 使用 Google Gemini 分析 PDF 文章，按美国五年级阅读水平提取约 30 个重难点词汇
- **NY NextGen ELA 课标对齐**: 遵循纽约州 Next Generation ELA 学习标准，区分 Tier 2 和 Tier 3 词汇
- **三语支持**:
  - **Tier 2 词汇** (跨学科高频学术词): 英文释义 + 中文翻译 + 西语翻译 + 例句 + 图片
  - **Tier 3 词汇** (学科专业词): 英文释义 + 中文概念性解释 + 西语概念性解释 + 例句 + 图片
- **自动图片搜索**: 通过 Google Custom Search API 为每个词汇配图
- **PDF 输出**: 每页 2 张闪卡，单面设计，可直接打印

---

## Quick Start (5 分钟上手)

### Step 1: 安装 Python 依赖

```bash
pip install flask google-generativeai reportlab Pillow requests
```

> 需要 Python 3.10+。如果需要中文字体渲染：`sudo apt-get install fonts-noto-cjk` (Ubuntu/Debian)

### Step 2: 获取 Gemini API Key (免费)

1. 打开 https://aistudio.google.com/apikey
2. 用 Google 账号登录
3. 点击 **"Create API Key"**
4. 复制生成的 Key

### Step 3: 启动 Web 界面

```bash
cd Flashcard
python app.py
```

然后在浏览器打开 **http://localhost:5000**

### Step 4: 使用

1. 在 **Settings** 标签页粘贴你的 Gemini API Key，点击 Save
2. 回到 **Generate** 标签页，上传 PDF 文件
3. 点击 **Generate Flashcards**
4. 等待处理完成，下载生成的 PDF

---

## 详细配置说明

### 必需配置

| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| **Gemini API Key** | 调用 Gemini AI 的密钥 | https://aistudio.google.com/apikey (免费) |

### 可选配置 (图片搜索)

如果想要真实图片（而非占位图），需要设置 Google Custom Search：

| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| Google CSE API Key | 图片搜索的 API 密钥 | https://console.cloud.google.com/apis/credentials |
| Search Engine ID (cx) | 自定义搜索引擎 ID | https://programmablesearchengine.google.com/ |

**设置步骤：**

1. 打开 [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. 创建新的搜索引擎，设置 "Search the entire web"
3. 复制 **Search Engine ID**
4. 在 [Google Cloud Console](https://console.cloud.google.com/apis/library/customsearch.googleapis.com) 启用 Custom Search API
5. 在 [Credentials](https://console.cloud.google.com/apis/credentials) 创建 API Key
6. 在 Web 界面的 Settings 中填入这两个值

### CJK 字体 (中文显示)

PDF 中需要 CJK 字体来正确渲染中文字符：

```bash
# Ubuntu / Debian
sudo apt-get install fonts-noto-cjk

# macOS — CJK 字体已预装，无需额外操作

# Windows — 系统自带中文字体，通常无需额外操作
```

---

## CLI 模式 (命令行)

除了 Web GUI，也可以通过命令行使用：

```bash
# 设置环境变量
export GEMINI_API_KEY='your-key-here'

# 运行
python main.py your_article.pdf

# 更多选项
python main.py article.pdf --output my_cards.pdf --words-json cache.json --skip-images
```

---

## Project Structure

```
Flashcard/
├── app.py                      # Web GUI (Flask)
├── main.py                     # CLI entry point
├── src/
│   ├── config.py               # Configuration
│   ├── gemini_client.py        # Gemini API (PDF → vocabulary extraction)
│   ├── image_fetcher.py        # Image search & download
│   └── flashcard_generator.py  # PDF/HTML flashcard generation
├── output/                     # Generated output (gitignored)
├── uploads/                    # Temp uploaded PDFs (gitignored)
├── requirements.txt
├── setup.sh
└── README.md
```

## How It Works

```
PDF ──→ Gemini AI ──→ ~30 Vocabulary Words (Tier 2/3)
                           │
                           ├── Chinese/Spanish translations or definitions
                           ├── English definitions
                           ├── Example sentences
                           └── Images (via Google Search or placeholder)
                                   │
                                   ▼
                          Flashcard PDF (2 per page)
```
