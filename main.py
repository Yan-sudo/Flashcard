#!/usr/bin/env python3
"""
Vocabulary Flashcard Generator
==============================

Takes a PDF article as input, uses Google Gemini to extract ~30 challenging
vocabulary words based on US 5th-grade reading level (aligned with NY NextGen
ELA Standards), classifies them as Tier 2 or Tier 3, generates bilingual
flashcards (English/Chinese/Spanish), and outputs a PDF with 2 cards per page.

Usage:
    python main.py <input.pdf> [--output flashcards.pdf]

Environment Variables:
    GEMINI_API_KEY      (required) Your Google Gemini API key
    GOOGLE_CSE_API_KEY  (optional) Google Custom Search API key for images
    GOOGLE_CSE_CX       (optional) Google Custom Search Engine ID
    GEMINI_MODEL        (optional) Gemini model name, default: gemini-2.5-flash
"""

import argparse
import os
import sys
import json


def main():
    parser = argparse.ArgumentParser(
        description="Generate vocabulary flashcards from a PDF article."
    )
    parser.add_argument(
        "pdf",
        help="Path to the input PDF article",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output PDF path (default: output/flashcards.pdf)",
    )
    parser.add_argument(
        "--words-json",
        default=None,
        help="Path to save/load extracted words JSON (for debugging/caching)",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip image fetching (use placeholders)",
    )
    args = parser.parse_args()

    # Validate input
    if not os.path.isfile(args.pdf):
        print(f"Error: PDF file not found: {args.pdf}")
        sys.exit(1)

    import src.config as cfg
    if not cfg.GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        print("  Get your key at: https://aistudio.google.com/apikey")
        print("  Then run: export GEMINI_API_KEY='your-key-here'")
        sys.exit(1)

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    # Step 1: Extract vocabulary using Gemini
    print("\n[Step 1/3] Extracting vocabulary from PDF...")
    words = None

    if args.words_json and os.path.exists(args.words_json):
        print(f"  Loading cached vocabulary from {args.words_json}")
        with open(args.words_json, "r", encoding="utf-8") as f:
            words = json.load(f)
    else:
        from src.gemini_client import extract_vocabulary
        words = extract_vocabulary(args.pdf)

        if args.words_json:
            with open(args.words_json, "w", encoding="utf-8") as f:
                json.dump(words, f, ensure_ascii=False, indent=2)
            print(f"  Saved vocabulary to {args.words_json}")

    # Print summary
    tier2 = [w for w in words if w.get("tier") == 2]
    tier3 = [w for w in words if w.get("tier") == 3]
    print(f"  Total: {len(words)} words ({len(tier2)} Tier 2, {len(tier3)} Tier 3)")

    # Step 2: Fetch images
    print("\n[Step 2/3] Fetching images...")
    if args.skip_images:
        print("  Skipping image fetch (--skip-images)")
        images = {}
    else:
        from src.image_fetcher import fetch_all_images
        images = fetch_all_images(words)

    # Step 3: Generate flashcard PDF
    print("\n[Step 3/3] Generating flashcard PDF...")
    from src.flashcard_generator import generate_pdf
    output_path = generate_pdf(words, images, args.output)

    print(f"\nDone! Output: {output_path}")
    print(f"Total flashcards: {len(words)} ({len(words) // 2 + len(words) % 2} pages)")


if __name__ == "__main__":
    main()
