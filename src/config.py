"""Configuration constants for the Flashcard generator."""

import os

# Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"

# Google Custom Search (for images)
GOOGLE_CSE_API_KEY = os.environ.get("GOOGLE_CSE_API_KEY", "")  # falls back to GEMINI_API_KEY
GOOGLE_CSE_CX = os.environ.get("GOOGLE_CSE_CX", "")  # Custom Search Engine ID

# Vocabulary extraction settings
TARGET_WORD_COUNT = 30
GRADE_LEVEL = 5  # US 5th grade

# Flashcard PDF layout (in points, 1 inch = 72 points)
PAGE_WIDTH = 612   # Letter size
PAGE_HEIGHT = 792
CARD_MARGIN = 36   # 0.5 inch margin
CARD_GAP = 18      # gap between two cards on same page

# Output
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
