"""Configuration for the Flashcard generator.

Values can be updated at runtime via update() — used by the web GUI.
"""

import os

# Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"

# Google Custom Search (for images)
GOOGLE_CSE_API_KEY = os.environ.get("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX = os.environ.get("GOOGLE_CSE_CX", "")

# Pixabay API (for images — free key at https://pixabay.com/api/docs/)
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")

# Vocabulary extraction settings
TARGET_WORD_COUNT = 30
GRADE_LEVEL = 5

# Flashcard PDF layout (in points)
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
CARD_MARGIN = 36
CARD_GAP = 18

# Output
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def update(**kwargs):
    """Update config values at runtime. Used by the web GUI."""
    g = globals()
    for key, value in kwargs.items():
        if key in g:
            g[key] = value
