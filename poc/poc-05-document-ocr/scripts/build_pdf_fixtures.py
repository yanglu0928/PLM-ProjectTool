from __future__ import annotations

import argparse
import random
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


SCAN_TERMS = [
    "PLM项目实施辅助工具",
    "需求确认",
    "合同编号：PLM-2026-005",
    "客户确认",
]


def find_chinese_font() -> Path:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("No Chinese font was found for the scanned fixture")


def build_text_pdf(output: Path) -> None:
    registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "FixtureTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=22,
        leading=28,
        textColor=colors.black,
        spaceAfter=18,
    )
    heading = ParagraphStyle(
        "FixtureHeading",
        parent=styles["Heading1"],
        fontName="STSong-Light",
        fontSize=16,
        leading=22,
        textColor=colors.black,
        spaceBefore=8,
        spaceAfter=10,
    )
    body = ParagraphStyle(
        "FixtureBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=11,
        leading=18,
        textColor=colors.black,
        spaceAfter=8,
    )
    table_style = TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#EAF2F8")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]
    )
    story = [
        Paragraph("POC 05 统一解析测试", title),
        Paragraph("项目概况", heading),
        Paragraph("项目名称：PLM 项目实施辅助工具", body),
        Paragraph("项目编号：PLM-2026-005", body),
        Paragraph("当前里程碑：需求确认", body),
        Spacer(1, 8),
        Table(
            [["字段", "值"], ["项目编号", "PLM-2026-005"], ["确认方", "客户确认"]],
            colWidths=[1.7 * inch, 4.4 * inch],
            style=table_style,
        ),
        PageBreak(),
        Paragraph("交付清单", heading),
        Paragraph("第二页用于验证 PDF 页码、章节和表格来源。", body),
        Table(
            [["交付物", "状态"], ["解析结果", "待验证"], ["来源定位", "待验证"]],
            colWidths=[2.2 * inch, 3.9 * inch],
            style=table_style,
        ),
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output), pagesize=letter, rightMargin=0.8 * inch, leftMargin=0.8 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title="POC 05 统一解析测试",
    )
    document.build(story)


def build_scan_pdf(output: Path) -> None:
    random.seed(20260917)
    canvas = Image.new("L", (2480, 3508), 245)
    draw = ImageDraw.Draw(canvas)
    font_path = find_chinese_font()
    title_font = ImageFont.truetype(str(font_path), 102)
    body_font = ImageFont.truetype(str(font_path), 76)
    draw.text((180, 260), SCAN_TERMS[0], font=title_font, fill=28)
    draw.text((180, 650), SCAN_TERMS[1], font=body_font, fill=38)
    draw.text((180, 950), SCAN_TERMS[2], font=body_font, fill=45)
    draw.text((180, 1250), SCAN_TERMS[3], font=body_font, fill=42)
    draw.rectangle((140, 1580, 2280, 2140), outline=75, width=5)
    draw.line((140, 1760, 2280, 1760), fill=85, width=4)
    draw.line((840, 1580, 840, 2140), fill=85, width=4)
    draw.text((220, 1620), "字段", font=body_font, fill=50)
    draw.text((930, 1620), "值", font=body_font, fill=50)
    draw.text((220, 1840), "项目编号", font=body_font, fill=50)
    draw.text((930, 1840), "PLM-2026-005", font=body_font, fill=50)

    pixels = canvas.load()
    for _ in range(18000):
        x = random.randrange(canvas.width)
        y = random.randrange(canvas.height)
        pixels[x, y] = random.choice((170, 185, 205, 225))
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=0.30))
    canvas = ImageEnhance.Contrast(canvas).enhance(0.94)
    canvas = canvas.rotate(0.65, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=250)

    with tempfile.TemporaryDirectory(prefix="poc05-scan-") as temp_dir:
        image_path = Path(temp_dir) / "scan.png"
        canvas.convert("RGB").save(image_path, dpi=(300, 300))
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.utils import ImageReader

        output.parent.mkdir(parents=True, exist_ok=True)
        pdf = pdf_canvas.Canvas(str(output), pagesize=letter)
        pdf.setTitle("POC 05 scanned fixture")
        pdf.drawImage(ImageReader(str(image_path)), 0, 0, width=letter[0], height=letter[1])
        pdf.showPage()
        pdf.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_text_pdf(args.output_dir / "sample-text.pdf")
    build_scan_pdf(args.output_dir / "sample-scan.pdf")
    print(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
