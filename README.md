# Vocabulary Flashcard Generator

PDF 文章词汇闪卡生成器 — 自动从 PDF 文章中提取重难点词汇，生成中英西三语闪卡 PDF。

## Features

- **Gemini AI 驱动**: 使用 Google Gemini 分析 PDF 文章，按美国五年级阅读水平提取约 30 个重难点词汇
- **NY NextGen ELA 课标对齐**: 遵循纽约州 Next Generation ELA 学习标准，区分 Tier 2 和 Tier 3 词汇
- **三语支持**:
  - **Tier 2 词汇** (跨学科高频学术词): 英文释义 + 中文翻译 + 西语翻译 + 例句 + 图片
  - **Tier 3 词汇** (学科专业词): 英文释义 + 中文概念性解释 + 西语概念性解释 + 例句 + 图片
- **自动图片搜索**: 通过 Google Custom Search API 为每个词汇配图
- **PDF 输出**: 每页 2 张闪卡，单面设计，可直接打印

## Quick Start

### 1. Install Dependencies

```bash
bash setup.sh
# or manually:
pip3 install -r requirements.txt
```

### 2. Set API Key

```bash
export GEMINI_API_KEY='your-gemini-api-key'
```

Get your free Gemini API key at: https://aistudio.google.com/apikey

### 3. Run

```bash
python3 main.py your_article.pdf
```

Output will be saved to `output/flashcards.pdf`.

## Options

```
python3 main.py <input.pdf> [options]

Arguments:
  pdf                   Path to the input PDF article

Options:
  --output, -o PATH     Output file path (default: output/flashcards.pdf)
  --words-json PATH     Save/load vocabulary JSON (for caching/debugging)
  --skip-images         Skip image fetching, use placeholders
```

## Optional: Image Search

For real images on flashcards, set up Google Custom Search:

```bash
export GOOGLE_CSE_API_KEY='your-api-key'
export GOOGLE_CSE_CX='your-search-engine-id'
```

Setup guide: https://developers.google.com/custom-search/v1/overview

Without these, placeholder images will be used.

## Optional: CJK Fonts

For proper Chinese character rendering in PDF output, install CJK fonts:

```bash
# Ubuntu/Debian
sudo apt-get install fonts-noto-cjk

# macOS — CJK fonts are pre-installed
```

## Project Structure

```
Flashcard/
├── main.py                     # Entry point
├── src/
│   ├── config.py               # Configuration
│   ├── gemini_client.py        # Gemini API (PDF upload + vocabulary extraction)
│   ├── image_fetcher.py        # Image search & download
│   └── flashcard_generator.py  # PDF/HTML flashcard generation
├── output/                     # Generated output
├── requirements.txt
├── setup.sh
└── README.md
```

## How It Works

1. **PDF → Gemini**: Upload the PDF to Gemini API, which reads the article content
2. **Vocabulary Extraction**: Gemini identifies ~30 challenging words, classifies each as Tier 2 or Tier 3, and generates definitions/translations/examples
3. **Image Fetching**: For each word, search for an illustrative image (or generate a placeholder)
4. **Flashcard PDF**: Generate a formatted PDF with 2 flashcards per page, each containing the word, tier badge, trilingual content, and image
