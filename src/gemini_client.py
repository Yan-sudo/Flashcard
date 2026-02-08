"""Gemini API client using raw HTTP requests.

Handles PDF upload, vocabulary extraction, and vocabulary detail generation.
Uses the Gemini REST API directly via the `requests` library.
"""

import base64
import json
import requests

import src.config as config


def _api_url(path: str) -> str:
    return f"{config.GEMINI_BASE_URL}{path}?key={config.GEMINI_API_KEY}"


def _generate_content(contents: list, temperature: float = 0.3) -> str:
    """Call Gemini generateContent endpoint and return the text response."""
    url = _api_url(f"/v1beta/models/{config.GEMINI_MODEL}:generateContent")
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 8192,
        },
    }
    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data, indent=2)}")
    return candidates[0]["content"]["parts"][0]["text"]


def extract_vocabulary(pdf_path: str, on_progress=None) -> list[dict]:
    """Upload a PDF to Gemini and extract ~30 Tier 2/Tier 3 vocabulary words.

    Args:
        pdf_path: Path to the PDF file.
        on_progress: Optional callback(message: str) for progress updates.

    Returns a list of dicts with keys:
        word, tier, chinese, spanish, english_definition, example_sentence
    """
    def _log(msg):
        if on_progress:
            on_progress(msg)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    _log(f"Sending PDF to Gemini ({config.GEMINI_MODEL})...")

    prompt = f"""You are an expert ESL/ELA vocabulary specialist aligned with the New York State Next Generation English Language Arts Learning Standards for Grade 5.

Analyze the attached PDF article and extract approximately {config.TARGET_WORD_COUNT} challenging vocabulary words that a 5th-grade student would need to learn. Follow these guidelines:

**Tier Classification (per NY NextGen ELA Standards & Beck et al.):**
- **Tier 2 (Academic / High-Utility Words):** High-frequency academic words used across multiple content areas. These are words like "analyze", "evidence", "significant", "contrast", "establish", etc. They appear in academic texts across subjects but are not part of everyday conversational vocabulary for 5th graders.
- **Tier 3 (Domain-Specific Words):** Low-frequency words specific to a particular content area or discipline. These are technical terms like "photosynthesis", "legislative", "denominator", "metamorphosis", etc.

**For each Tier 2 word, provide:**
1. The English word
2. Chinese translation (简体中文翻译)
3. Spanish translation (traducción al español)
4. English definition (clear, student-friendly)
5. An example sentence using the word in context

**For each Tier 3 word, provide:**
1. The English word
2. Chinese definition — a conceptual explanation in Chinese, NOT a direct word-for-word translation. Explain the concept so a Chinese-speaking student understands the meaning in context.
3. Spanish definition — a conceptual explanation in Spanish, NOT a direct word-for-word translation. Explain the concept so a Spanish-speaking student understands the meaning in context.
4. English definition (clear, student-friendly)
5. An example sentence using the word in context

Return EXACTLY a JSON array. Each element must have these fields:
- "word": the vocabulary word (string)
- "tier": 2 or 3 (integer)
- "chinese": Chinese translation (Tier 2) or Chinese conceptual definition (Tier 3) (string)
- "spanish": Spanish translation (Tier 2) or Spanish conceptual definition (Tier 3) (string)
- "english_definition": student-friendly English definition (string)
- "example_sentence": example sentence using the word (string)

Return ONLY the JSON array, no markdown fences, no extra text."""

    contents = [
        {
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": pdf_b64,
                    }
                },
                {"text": prompt},
            ]
        }
    ]

    raw = _generate_content(contents, temperature=0.3)
    _log("Gemini response received. Parsing vocabulary...")

    # Clean up response — strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    words = json.loads(text)
    if not isinstance(words, list):
        raise RuntimeError(f"Expected JSON array from Gemini, got: {type(words)}")

    _log(f"Extracted {len(words)} vocabulary words.")
    return words
