"""Generate a PDF of flashcards — 2 cards per page.

Each card is single-sided and contains:
  - The vocabulary word (large, bold)
  - Tier badge (Tier 2 / Tier 3)
  - Chinese & Spanish translation or definition
  - English definition
  - Example sentence
  - Illustrative image

Uses ReportLab for PDF generation with CID fonts for CJK support.
Falls back to HTML output if ReportLab is not installed.
"""

import html as html_mod
import os

import src.config as config

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pdf(words: list[dict], images: dict[str, str],
                 output_path: str | None = None) -> str:
    """Generate flashcard PDF. Returns path to the generated file."""
    if output_path is None:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, "flashcards.pdf")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        return _generate_pdf_reportlab(words, images, output_path)
    except ImportError:
        print("  [info] ReportLab not installed. Generating HTML fallback...")
        html_path = output_path.replace(".pdf", ".html")
        return _generate_html_fallback(words, images, html_path)


# ===================================================================
#  ReportLab-based PDF generator
# ===================================================================

_CJK_FONT = None
_LATIN_FONT = "Helvetica"
_LATIN_FONT_BOLD = "Helvetica-Bold"
_LATIN_FONT_ITALIC = "Helvetica-Oblique"


def _setup_fonts():
    """Register fonts. Returns the CJK font name or None."""
    global _CJK_FONT
    from reportlab.pdfbase import pdfmetrics

    # 1) Try CID font (built into PDF spec, no external file needed)
    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        _CJK_FONT = 'STSong-Light'
        return _CJK_FONT
    except Exception:
        pass

    # 2) Try system TTF fonts
    from reportlab.pdfbase.ttfonts import TTFont
    ttf_candidates = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in ttf_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CJKFont", path))
                _CJK_FONT = "CJKFont"
                return _CJK_FONT
            except Exception:
                continue

    # 3) Try cached downloaded font
    font_dir = os.path.join(config.OUTPUT_DIR, ".fonts")
    cached = os.path.join(font_dir, "NotoSansSC-Regular.ttf")
    if os.path.exists(cached):
        try:
            pdfmetrics.registerFont(TTFont("NotoSansSC", cached))
            _CJK_FONT = "NotoSansSC"
            return _CJK_FONT
        except Exception:
            pass

    # 4) Download Noto Sans SC
    try:
        import requests
        os.makedirs(font_dir, exist_ok=True)
        url = ("https://github.com/google/fonts/raw/main/ofl/"
               "notosanssc/NotoSansSC%5Bwght%5D.ttf")
        print("  Downloading CJK font (Noto Sans SC)...")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(cached, "wb") as f:
            f.write(resp.content)
        pdfmetrics.registerFont(TTFont("NotoSansSC", cached))
        _CJK_FONT = "NotoSansSC"
        return _CJK_FONT
    except Exception:
        pass

    print("  [warn] No CJK font found. Chinese may not display.")
    return None


def _font_for(text: str) -> str:
    if _CJK_FONT and any(ord(ch) > 0x2E80 for ch in text):
        return _CJK_FONT
    return _LATIN_FONT


def _make_para_text(text: str, bold_prefix: str = "") -> str:
    """Build Paragraph XML with mixed CJK/Latin font tags."""
    escaped = html_mod.escape(text)
    if not _CJK_FONT:
        if bold_prefix:
            return f"<b>{html_mod.escape(bold_prefix)}</b>{escaped}"
        return escaped

    parts = []
    if bold_prefix:
        bp = html_mod.escape(bold_prefix)
        if any(ord(ch) > 0x2E80 for ch in bold_prefix):
            parts.append(f'<b><font name="{_CJK_FONT}">{bp}</font></b>')
        else:
            parts.append(f"<b>{bp}</b>")

    in_cjk = False
    buf: list[str] = []
    for ch in text:
        is_cjk = ord(ch) > 0x2E80
        if is_cjk and not in_cjk:
            if buf:
                parts.append(html_mod.escape("".join(buf)))
                buf = []
            in_cjk = True
        elif not is_cjk and in_cjk:
            if buf:
                parts.append(
                    f'<font name="{_CJK_FONT}">'
                    f'{html_mod.escape("".join(buf))}</font>')
                buf = []
            in_cjk = False
        buf.append(ch)
    if buf:
        joined = html_mod.escape("".join(buf))
        if in_cjk:
            parts.append(f'<font name="{_CJK_FONT}">{joined}</font>')
        else:
            parts.append(joined)
    return "".join(parts)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _draw_para(c, markup: str, x: float, y_top: float, width: float,
               font_name: str = "Helvetica", font_size: float = 11,
               leading: float = 0, color: str = "#333333") -> float:
    """Draw a Paragraph on canvas. Returns ACTUAL height consumed.

    No artificial height cap — text is pre-truncated before calling this.
    """
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.colors import HexColor

    if leading <= 0:
        leading = font_size * 1.6

    style = ParagraphStyle(
        'card_text',
        fontName=font_name,
        fontSize=font_size,
        leading=leading,
        textColor=HexColor(color),
        alignment=TA_LEFT,
        wordWrap='CJK',
    )
    p = Paragraph(markup, style)
    w, h = p.wrap(width, 500)
    p.drawOn(c, x, y_top - h)
    return h


def _generate_pdf_reportlab(words: list[dict], images: dict[str, str],
                            output_path: str) -> str:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    _setup_fonts()

    page_w, page_h = letter
    margin = 36
    gap = 14
    card_w = page_w - 2 * margin
    card_h = (page_h - 2 * margin - gap) / 2

    c = canvas.Canvas(output_path, pagesize=letter)
    c.setTitle("Vocabulary Flashcards — Grade 5")

    for i, w in enumerate(words):
        slot = i % 2
        if slot == 0 and i > 0:
            c.showPage()
        if slot == 0:
            card_top = page_h - margin
        else:
            card_top = page_h - margin - card_h - gap
        _draw_card(c, w, images.get(w["word"], ""),
                   margin, card_top, card_w, card_h)

    c.save()
    print(f"  PDF saved to: {output_path}")
    return output_path


def _draw_card(c, word_data: dict, image_path: str,
               x: float, y_top: float, card_w: float, card_h: float):
    """Draw one flashcard: text on left, large image on right filling card height."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader

    word = word_data["word"]
    tier = word_data.get("tier", 2)
    chinese = _truncate(word_data.get("chinese", ""), 80)
    spanish = _truncate(word_data.get("spanish", ""), 120)
    eng_def = _truncate(word_data.get("english_definition", ""), 180)
    example = _truncate(word_data.get("example_sentence", ""), 180)

    pad = 14
    card_bottom = y_top - card_h

    # ── Card background ──
    bg = HexColor("#E8F4FD") if tier == 2 else HexColor("#FFF8E1")
    border = HexColor("#1976D2") if tier == 2 else HexColor("#F57C00")
    c.setFillColor(bg)
    c.setStrokeColor(border)
    c.setLineWidth(1.5)
    c.roundRect(x, card_bottom, card_w, card_h, 8, fill=1, stroke=1)

    # ── Image (right side, nearly full card height) ──
    img_pad = 10
    img_area_w = 180  # width reserved for image column
    img_area_h = card_h - 2 * img_pad  # nearly top-to-bottom
    img_x = x + card_w - img_pad - img_area_w
    img_y = card_bottom + img_pad
    has_image = False

    if image_path and os.path.exists(image_path):
        try:
            c.drawImage(ImageReader(image_path), img_x, img_y,
                        width=img_area_w, height=img_area_h,
                        preserveAspectRatio=True, mask='auto')
            c.setStrokeColor(HexColor("#CCCCCC"))
            c.setLineWidth(0.5)
            c.rect(img_x, img_y, img_area_w, img_area_h, fill=0, stroke=1)
            has_image = True
        except Exception as e:
            print(f"    [warn] Image render failed for '{word}': {e}")

    # Text column: left side, stops before image
    inner_x = x + pad
    text_w = card_w - 2 * pad - (img_area_w + img_pad + 6 if has_image else 0)
    y = y_top  # cursor moves downward

    # ── Tier badge ──
    y -= pad
    badge_color = HexColor("#1976D2") if tier == 2 else HexColor("#F57C00")
    c.setFillColor(badge_color)
    c.roundRect(inner_x, y - 18, 52, 18, 4, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont(_LATIN_FONT_BOLD, 10)
    c.drawString(inner_x + 9, y - 13, f"Tier {tier}")
    y -= 26

    # ── Word ──
    c.setFillColor(HexColor("#0D47A1"))
    c.setFont(_LATIN_FONT_BOLD, 20)
    c.drawString(inner_x, y - 16, word)
    y -= 28

    # ── Chinese ──
    cn_label = "中文翻译: " if tier == 2 else "中文释义: "
    cn_markup = _make_para_text(chinese, bold_prefix=cn_label)
    h = _draw_para(c, cn_markup, inner_x, y, text_w,
                   font_name=_font_for(cn_label + chinese),
                   font_size=10, leading=15, color="#333333")
    y -= h + 6

    # ── Spanish ──
    es_label = "Español: " if tier == 2 else "Definición (ES): "
    es_markup = _make_para_text(spanish, bold_prefix=es_label)
    h = _draw_para(c, es_markup, inner_x, y, text_w,
                   font_name=_font_for(es_label + spanish),
                   font_size=10, leading=15, color="#333333")
    y -= h + 8

    # ── English definition ──
    def_markup = _make_para_text(eng_def, bold_prefix="Definition: ")
    h = _draw_para(c, def_markup, inner_x, y, text_w,
                   font_name=_LATIN_FONT, font_size=10,
                   leading=15, color="#333333")
    y -= h + 6

    # ── Example sentence ──
    if y > card_bottom + pad + 14:
        ex_markup = f"<i>{_make_para_text(example, bold_prefix='Example: ')}</i>"
        _draw_para(c, ex_markup, inner_x, y, text_w,
                   font_name=_LATIN_FONT, font_size=9.5,
                   leading=14, color="#666666")


# ===================================================================
#  HTML fallback
# ===================================================================

def _generate_html_fallback(words: list[dict], images: dict[str, str],
                            output_path: str) -> str:
    import base64

    cards_html = []
    for i, w in enumerate(words):
        word = html_mod.escape(w["word"])
        tier = w.get("tier", 2)
        chinese = html_mod.escape(w.get("chinese", ""))
        spanish = html_mod.escape(w.get("spanish", ""))
        eng_def = html_mod.escape(w.get("english_definition", ""))
        example = html_mod.escape(w.get("example_sentence", ""))

        tier_cls = "t2" if tier == 2 else "t3"
        cn_label = "中文翻译" if tier == 2 else "中文释义"
        es_label = "Español" if tier == 2 else "Definición (ES)"

        img_tag = ""
        img_path = images.get(w["word"], "")
        if img_path and os.path.exists(img_path):
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                ext = img_path.rsplit(".", 1)[-1].lower()
                mime = {"png": "image/png", "jpg": "image/jpeg",
                        "jpeg": "image/jpeg", "gif": "image/gif",
                        "webp": "image/webp"}.get(ext, "image/png")
                img_tag = f'<img src="data:{mime};base64,{b64}" alt="{word}">'
            except Exception:
                pass

        page_break = ' style="page-break-before:always"' if (i > 0 and i % 2 == 0) else ''

        cards_html.append(f'''
<div class="card {tier_cls}"{page_break}>
  <div class="top-row">
    <div class="text-col">
      <span class="badge {tier_cls}-badge">Tier {tier}</span>
      <div class="word">{word}</div>
      <div class="line"><span class="label">{cn_label}:</span> {chinese}</div>
      <div class="line"><span class="label">{es_label}:</span> {spanish}</div>
      <div class="line"><span class="label">Definition:</span> {eng_def}</div>
      <div class="line example"><span class="label">Example:</span> <em>{example}</em></div>
    </div>
    <div class="img-col">{img_tag}</div>
  </div>
</div>''')

    page_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Vocabulary Flashcards</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap" rel="stylesheet">
<style>
  @page {{ size: letter; margin: 0.4in; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ height: 100%; }}
  body {{
    font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Microsoft YaHei', sans-serif;
    color: #222; font-size: 13px; line-height: 1.5;
  }}
  .card {{
    border: 2px solid #1976D2; border-radius: 10px;
    padding: 18px 20px; margin-bottom: 10px;
    height: 48.5%; overflow: hidden;
    background: #E8F4FD; display: flex; flex-direction: column;
  }}
  .card.t3 {{ border-color: #F57C00; background: #FFF8E1; }}
  .top-row {{ display: flex; gap: 14px; flex: 1; min-height: 0; }}
  .text-col {{ flex: 1; min-width: 0; }}
  .img-col {{
    width: 200px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }}
  .img-col img {{
    max-width: 190px; max-height: 100%; border-radius: 6px;
    border: 1px solid #bbb; object-fit: contain; background: #fff;
  }}
  .badge {{
    display: inline-block; padding: 3px 12px; border-radius: 4px;
    font-size: 11px; font-weight: 700; color: #fff; margin-bottom: 6px;
  }}
  .t2-badge {{ background: #1976D2; }}
  .t3-badge {{ background: #F57C00; }}
  .word {{
    font-size: 22px; font-weight: 700; color: #0D47A1;
    margin: 2px 0 8px; line-height: 1.2;
  }}
  .line {{ font-size: 13px; margin-bottom: 6px; line-height: 1.6; }}
  .label {{ font-weight: 700; }}
  .example {{ color: #555; }}
  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .card {{ break-inside: avoid; page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
{"".join(cards_html)}
</body>
</html>'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"  HTML flashcards saved to: {output_path}")
    return output_path
