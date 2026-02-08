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
            "maxOutputTokens": 65536,
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
6. An image search query — a short, concrete, VISUAL phrase (2-5 words) that would find a photo illustrating this word's meaning. For abstract words, describe a concrete scene. For example: "analyze" → "scientist examining data chart", "habitat" → "animals in forest environment", "explicit" → "clear written instructions closeup".

**For each Tier 3 word, provide:**
1. The English word
2. Chinese definition — a conceptual explanation in Chinese, NOT a direct word-for-word translation. Explain the concept so a Chinese-speaking student understands the meaning in context.
3. Spanish definition — a conceptual explanation in Spanish, NOT a direct word-for-word translation. Explain the concept so a Spanish-speaking student understands the meaning in context.
4. English definition (clear, student-friendly)
5. An example sentence using the word in context
6. An image search query — a short, concrete, VISUAL phrase (2-5 words) that would find a photo illustrating this concept. For example: "photosynthesis" → "plant leaves absorbing sunlight", "legislature" → "government congress chamber".

Return EXACTLY a JSON array. Each element must have these fields:
- "word": the vocabulary word (string)
- "tier": 2 or 3 (integer)
- "chinese": Chinese translation (Tier 2) or Chinese conceptual definition (Tier 3) (string)
- "spanish": Spanish translation (Tier 2) or Spanish conceptual definition (Tier 3) (string)
- "english_definition": student-friendly English definition (string)
- "example_sentence": example sentence using the word (string)
- "image_query": a concrete visual search phrase for finding an illustrative photo (string)

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

    words = _parse_json_response(raw)
    _log(f"Extracted {len(words)} vocabulary words.")
    return words


def _parse_json_response(raw: str) -> list[dict]:
    """Parse Gemini's response into a JSON list, tolerating common quirks.

    Handles: markdown fences, trailing commas, truncated output.
    """
    import re

    text = raw.strip()

    # Strip markdown fences:  ```json ... ```
    m = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n\s*```", text)
    if m:
        text = m.group(1).strip()
    elif text.startswith("```"):
        first_nl = text.index("\n")
        text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Helper: clean common issues and try parse
    def _try_parse(s: str) -> list | None:
        # Remove trailing commas before } or ]
        s = re.sub(r",\s*([}\]])", r"\1", s)
        try:
            result = json.loads(s)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        return None

    # Attempt 1: parse as-is
    result = _try_parse(text)
    if result is not None:
        return result

    # Attempt 2: extract [...] substring
    start = text.find("[")
    if start != -1:
        end = text.rfind("]")
        if end > start:
            result = _try_parse(text[start:end + 1])
            if result is not None:
                return result

    # Attempt 3: handle TRUNCATED JSON (no closing ])
    # Find the last complete JSON object "}" and close the array
    if start != -1:
        chunk = text[start:]
        last_brace = chunk.rfind("}")
        if last_brace != -1:
            truncated = chunk[:last_brace + 1].rstrip().rstrip(",") + "\n]"
            result = _try_parse(truncated)
            if result is not None:
                return result

    raise RuntimeError(
        f"Failed to parse Gemini response as JSON array. "
        f"First 500 chars: {text[:500]}"
    )
