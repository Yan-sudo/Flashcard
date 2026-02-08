#!/bin/bash
# Setup script for Vocabulary Flashcard Generator
# Run: bash setup.sh

set -e

echo "=== Vocabulary Flashcard Generator - Setup ==="
echo ""

# Check Python version
python3 --version || { echo "Error: Python 3 is required"; exit 1; }

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Check for CJK fonts (optional but recommended)
echo ""
echo "Checking for CJK fonts (needed for Chinese characters)..."
if fc-list :lang=zh 2>/dev/null | head -1 | grep -q "."; then
    echo "  CJK fonts found."
else
    echo "  WARNING: No CJK fonts found. Chinese characters may not render in PDF."
    echo "  Install with: sudo apt-get install fonts-noto-cjk"
    echo "  Or on macOS: CJK fonts are typically pre-installed."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  1. Set your Gemini API key:"
echo "     export GEMINI_API_KEY='your-key-here'"
echo ""
echo "  2. (Optional) For real images, set up Google Custom Search:"
echo "     export GOOGLE_CSE_API_KEY='your-key'"
echo "     export GOOGLE_CSE_CX='your-search-engine-id'"
echo ""
echo "  3. Run the generator:"
echo "     python3 main.py your_article.pdf"
echo ""
