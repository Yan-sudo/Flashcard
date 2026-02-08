"""Generate a PDF of flashcards — 2 cards per page.

Each card is single-sided and contains:
  - The vocabulary word (large, bold)
  - Tier badge (Tier 2 / Tier 3)
  - Chinese & Spanish translation or definition
  - English definition
  - Example sentence
  - Illustrative image

Uses ReportLab for PDF generation with full Unicode support.
Falls back to HTML output if ReportLab is not installed.
"""

import os
import textwrap

from src.config import OUTPUT_DIR, PAGE_WIDTH, PAGE_HEIGHT, CARD_MARGIN, CARD_GAP


def _card_height():
    """Height of each card (2 per page with margins and gap)."""
    usable = PAGE_HEIGHT - 2 * CARD_MARGIN - CARD_GAP
    return usable / 2


def generate_pdf(words: list[dict], images: dict[str, str], output_path: str | None = None) -> str:
    """Generate flashcard PDF. Returns path to the generated file."""
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "flashcards.pdf")

    try:
        return _generate_pdf_reportlab(words, images, output_path)
    except ImportError:
        print("  [info] ReportLab not installed. Generating HTML fallback...")
        html_path = output_path.replace(".pdf", ".html")
        return _generate_html_fallback(words, images, html_path)


# ---------------------------------------------------------------------------
# ReportLab-based PDF generator
# ---------------------------------------------------------------------------

def _generate_pdf_reportlab(words: list[dict], images: dict[str, str], output_path: str) -> str:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    # Register CJK-capable fonts if available
    _register_fonts()

    c = canvas.Canvas(output_path, pagesize=letter)
    c.setTitle("Vocabulary Flashcards")

    card_h = _card_height()
    card_w = PAGE_WIDTH - 2 * CARD_MARGIN

    for i, w in enumerate(words):
        slot = i % 2  # 0 = top card, 1 = bottom card

        if slot == 0 and i > 0:
            c.showPage()

        # Y origin for this card (top card starts higher)
        if slot == 0:
            y_base = PAGE_HEIGHT - CARD_MARGIN
        else:
            y_base = PAGE_HEIGHT - CARD_MARGIN - card_h - CARD_GAP

        _draw_card(c, w, images.get(w["word"], ""), CARD_MARGIN, y_base, card_w, card_h)

    # If odd number of words, finalize last page
    c.save()
    print(f"  PDF saved to: {output_path}")
    return output_path


def _register_fonts():
    """Register Unicode-capable fonts for CJK and Latin text."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_search_paths = [
        # Noto fonts (best CJK coverage)
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        # Noto Sans SC
        ("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf", "NotoSansSC"),
        ("/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf", "NotoSansSC"),
        # WenQuanYi
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WQYZenHei"),
        ("/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc", "WQYZenHei"),
        # DejaVu as Latin fallback
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
    ]

    registered = set()
    for path, name in font_search_paths:
        if os.path.exists(path) and name not in registered:
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registered.add(name)
            except Exception:
                pass

    return registered


def _pick_font(text: str, registered_fonts: set | None = None) -> str:
    """Pick the best available font for the given text."""
    from reportlab.pdfbase import pdfmetrics

    # Check if text has CJK characters
    has_cjk = any(ord(ch) > 0x2E80 for ch in text)

    if has_cjk:
        for name in ["NotoSansCJK", "NotoSansSC", "WQYZenHei"]:
            try:
                pdfmetrics.getFont(name)
                return name
            except KeyError:
                pass

    for name in ["DejaVuSans", "Helvetica"]:
        try:
            pdfmetrics.getFont(name)
            return name
        except KeyError:
            pass

    return "Helvetica"


def _draw_card(c, word_data: dict, image_path: str,
               x: float, y_top: float, card_w: float, card_h: float):
    """Draw a single flashcard on the canvas."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader

    word = word_data["word"]
    tier = word_data.get("tier", 2)
    chinese = word_data.get("chinese", "")
    spanish = word_data.get("spanish", "")
    eng_def = word_data.get("english_definition", "")
    example = word_data.get("example_sentence", "")

    pad = 12  # inner padding
    y_cursor = y_top - pad  # current drawing position (moves downward)

    # --- Card background and border ---
    tier_color = HexColor("#E8F0FE") if tier == 2 else HexColor("#FFF3E0")
    border_color = HexColor("#4285F4") if tier == 2 else HexColor("#FB8C00")

    c.setFillColor(tier_color)
    c.setStrokeColor(border_color)
    c.setLineWidth(2)
    c.roundRect(x, y_top - card_h, card_w, card_h, 10, fill=1, stroke=1)

    # --- Layout: text on left, image on right ---
    img_w = 120
    img_h = 90
    img_x = x + card_w - pad - img_w
    img_y = y_top - pad - img_h

    text_right_margin = img_w + pad * 2  # leave room for image
    text_w = card_w - 2 * pad - text_right_margin

    # --- Tier badge ---
    tier_label = f"Tier {tier}"
    badge_color = HexColor("#4285F4") if tier == 2 else HexColor("#FB8C00")
    c.setFillColor(badge_color)
    c.roundRect(x + pad, y_cursor - 16, 50, 16, 4, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + pad + 8, y_cursor - 13, tier_label)
    y_cursor -= 24

    # --- Word (large, bold) ---
    c.setFillColor(HexColor("#1A237E"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(x + pad, y_cursor - 18, word)
    y_cursor -= 28

    # --- Image ---
    if image_path and os.path.exists(image_path):
        try:
            img = ImageReader(image_path)
            c.drawImage(img, img_x, img_y, width=img_w, height=img_h,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # --- Chinese ---
    cjk_font = _pick_font(chinese)
    label_prefix = "中文翻译: " if tier == 2 else "中文释义: "
    _draw_wrapped_text(c, f"{label_prefix}{chinese}",
                       x + pad, y_cursor, text_w + text_right_margin - 10,
                       font_name=cjk_font, font_size=10,
                       color=HexColor("#333333"))
    y_cursor -= 16

    # --- Spanish ---
    es_font = _pick_font(spanish)
    es_prefix = "Español: " if tier == 2 else "Definición: "
    _draw_wrapped_text(c, f"{es_prefix}{spanish}",
                       x + pad, y_cursor, text_w + text_right_margin - 10,
                       font_name=es_font, font_size=10,
                       color=HexColor("#333333"))
    y_cursor -= 16

    # --- English definition ---
    _draw_wrapped_text(c, f"Definition: {eng_def}",
                       x + pad, y_cursor, text_w + text_right_margin - 10,
                       font_name="Helvetica", font_size=10,
                       color=HexColor("#333333"))
    y_cursor -= 16

    # --- Example sentence ---
    _draw_wrapped_text(c, f"Example: {example}",
                       x + pad, y_cursor, text_w + text_right_margin - 10,
                       font_name="Helvetica-Oblique", font_size=9,
                       color=HexColor("#555555"))


def _draw_wrapped_text(c, text: str, x: float, y: float, max_width: float,
                       font_name: str = "Helvetica", font_size: float = 10,
                       color=None, line_height: float = 13):
    """Draw text with basic word wrapping."""
    if color:
        c.setFillColor(color)
    c.setFont(font_name, font_size)

    # Approximate characters per line based on font size
    avg_char_width = font_size * 0.5
    chars_per_line = max(20, int(max_width / avg_char_width))

    lines = textwrap.wrap(text, width=chars_per_line)
    for i, line in enumerate(lines[:3]):  # max 3 lines to prevent overflow
        c.drawString(x, y - i * line_height, line)


# ---------------------------------------------------------------------------
# HTML fallback (if ReportLab is unavailable)
# ---------------------------------------------------------------------------

def _generate_html_fallback(words: list[dict], images: dict[str, str], output_path: str) -> str:
    """Generate an HTML file with flashcards styled for printing 2 per page."""
    import base64

    cards_html = []
    for i, w in enumerate(words):
        word = w["word"]
        tier = w.get("tier", 2)
        chinese = w.get("chinese", "")
        spanish = w.get("spanish", "")
        eng_def = w.get("english_definition", "")
        example = w.get("example_sentence", "")

        tier_class = "tier2" if tier == 2 else "tier3"
        cn_label = "中文翻译" if tier == 2 else "中文释义"
        es_label = "Español" if tier == 2 else "Definición"

        # Embed image as base64
        img_tag = ""
        img_path = images.get(word, "")
        if img_path and os.path.exists(img_path):
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                ext = img_path.rsplit(".", 1)[-1].lower()
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
                img_tag = f'<img src="data:{mime};base64,{b64}" alt="{word}" />'
            except Exception:
                pass

        cards_html.append(f"""
    <div class="card {tier_class}">
      <div class="card-content">
        <div class="card-text">
          <span class="tier-badge {tier_class}-badge">Tier {tier}</span>
          <h2 class="word">{word}</h2>
          <p><strong>{cn_label}:</strong> {chinese}</p>
          <p><strong>{es_label}:</strong> {spanish}</p>
          <p><strong>Definition:</strong> {eng_def}</p>
          <p class="example"><strong>Example:</strong> <em>{example}</em></p>
        </div>
        <div class="card-image">{img_tag}</div>
      </div>
    </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Vocabulary Flashcards</title>
<style>
  @page {{
    size: letter;
    margin: 0.5in;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
    font-size: 11px;
    line-height: 1.4;
    color: #333;
  }}
  .card {{
    width: 100%;
    height: 48vh;
    border: 2px solid #4285F4;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 12px;
    page-break-inside: avoid;
    background: #E8F0FE;
    overflow: hidden;
  }}
  .card.tier3 {{
    border-color: #FB8C00;
    background: #FFF3E0;
  }}
  .card-content {{
    display: flex;
    height: 100%;
  }}
  .card-text {{
    flex: 1;
    padding-right: 12px;
  }}
  .card-image {{
    width: 140px;
    flex-shrink: 0;
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }}
  .card-image img {{
    max-width: 130px;
    max-height: 100px;
    border-radius: 6px;
    border: 1px solid #ccc;
  }}
  .tier-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: bold;
    color: white;
    margin-bottom: 6px;
  }}
  .tier2-badge {{ background: #4285F4; }}
  .tier3-badge {{ background: #FB8C00; }}
  .word {{
    font-size: 22px;
    color: #1A237E;
    margin: 4px 0 8px 0;
  }}
  .card p {{
    margin-bottom: 4px;
    font-size: 11px;
  }}
  .example {{ color: #555; }}

  @media print {{
    .card {{
      height: 46vh;
      break-inside: avoid;
    }}
  }}
</style>
</head>
<body>
{"".join(cards_html)}
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML flashcards saved to: {output_path}")
    return output_path
