"""Manuscript publishing helpers for PDF and EPUB exports."""

from __future__ import annotations

import html
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Formatter

from analysis_engine import strip_markdown


POINTS_PER_INCH = 72

PAGE_SIZES = {
    "5 x 8 in": (5 * POINTS_PER_INCH, 8 * POINTS_PER_INCH),
    "5.5 x 8.5 in": (5.5 * POINTS_PER_INCH, 8.5 * POINTS_PER_INCH),
    "6 x 9 in": (6 * POINTS_PER_INCH, 9 * POINTS_PER_INCH),
    "A5": (419.53, 595.28),
    "US Letter": (8.5 * POINTS_PER_INCH, 11 * POINTS_PER_INCH),
}

FONT_CHOICES = {
    "Times": {
        "regular": "Times-Roman",
        "bold": "Times-Bold",
        "italic": "Times-Italic",
        "bold_italic": "Times-BoldItalic",
    },
    "Helvetica": {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
        "bold_italic": "Helvetica-BoldOblique",
    },
    "Courier": {
        "regular": "Courier",
        "bold": "Courier-Bold",
        "italic": "Courier-Oblique",
        "bold_italic": "Courier-BoldOblique",
    },
}

SUPPORTED_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}

IMAGE_MEDIA_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class Chapter:
    name: str
    markdown: str

    @property
    def title(self) -> str:
        return extract_title(self.markdown) or Path(self.name).stem.replace("-", " ").title()


@dataclass(frozen=True)
class ChapterArt:
    chapter_name: str
    image_path: Path
    alt_text: str = ""


@dataclass(frozen=True)
class PublishMetadata:
    title: str
    subtitle: str = ""
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    copyright_year: str = ""
    edition_note: str = "First edition"
    rights_statement: str = "All rights reserved."
    language: str = "en"


@dataclass(frozen=True)
class PdfFormatOptions:
    trim_size: str = "6 x 9 in"
    font_family: str = "Times"
    font_size: int = 11
    line_spacing: float = 1.35
    margin_top: float = 0.75
    margin_bottom: float = 0.75
    margin_left: float = 0.75
    margin_right: float = 0.75


class TemplateValues(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def default_metadata() -> PublishMetadata:
    return PublishMetadata(copyright_year=str(date.today().year))


def render_template(template: str, metadata: PublishMetadata) -> str:
    values = TemplateValues(metadata.__dict__)
    return Formatter().vformat(template, (), values)


def extract_template_fields(template: str) -> list[str]:
    fields = []
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name and field_name not in fields:
            fields.append(field_name)
    return fields


def extract_title(markdown_text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown_text, flags=re.MULTILINE)
    if not match:
        return ""
    return strip_markdown(match.group(1)).strip()


def safe_filename(value: str, fallback: str = "manuscript") -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return clean.lower() or fallback


def generate_pdf(
    chapters: list[Chapter],
    metadata: PublishMetadata,
    title_template: str,
    copyright_template: str,
    options: PdfFormatOptions,
    output_dir: Path,
    chapter_art: dict[str, ChapterArt] | None = None,
    art_placement: str = "before_chapter",
) -> Path:
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_filename(metadata.title)}.pdf"
    page_size = PAGE_SIZES[options.trim_size]
    fonts = FONT_CHOICES[options.font_family]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        rightMargin=options.margin_right * POINTS_PER_INCH,
        leftMargin=options.margin_left * POINTS_PER_INCH,
        topMargin=options.margin_top * POINTS_PER_INCH,
        bottomMargin=options.margin_bottom * POINTS_PER_INCH,
        title=metadata.title,
        author=metadata.author,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ManuscriptTitle",
            parent=styles["Title"],
            fontName=fonts["bold"],
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManuscriptSubtitle",
            parent=styles["Normal"],
            fontName=fonts["italic"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FrontMatter",
            parent=styles["Normal"],
            fontName=fonts["regular"],
            fontSize=options.font_size,
            leading=options.font_size * options.line_spacing,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ChapterTitle",
            parent=styles["Heading1"],
            fontName=fonts["bold"],
            fontSize=16,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=22,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName=fonts["bold"],
            fontSize=13,
            leading=17,
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextManuscript",
            parent=styles["BodyText"],
            fontName=fonts["regular"],
            fontSize=options.font_size,
            leading=options.font_size * options.line_spacing,
            firstLineIndent=18,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LinePreservedText",
            parent=styles["BodyTextManuscript"],
            firstLineIndent=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BlockQuote",
            parent=styles["BodyTextManuscript"],
            leftIndent=22,
            rightIndent=22,
            firstLineIndent=0,
            fontName=fonts["italic"],
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            parent=styles["BodyText"],
            fontName="Courier",
            fontSize=max(8, options.font_size - 1),
            leading=max(10, options.font_size * 1.2),
            leftIndent=16,
            spaceAfter=8,
        )
    )

    story = []
    append_template_pdf(story, render_template(title_template, metadata), styles)
    story.append(PageBreak())
    append_template_pdf(story, render_template(copyright_template, metadata), styles)
    story.append(PageBreak())

    for index, chapter in enumerate(chapters):
        if index:
            story.append(PageBreak())
        art = get_chapter_art(chapter_art, chapter)
        if art and art_placement == "before_chapter":
            append_chapter_art_pdf(story, art, doc)
            story.append(PageBreak())
        story.append(Paragraph(escape_pdf_markup(chapter.title), styles["ChapterTitle"]))
        append_markdown_pdf(story, remove_first_heading(chapter.markdown), styles)
        if art and art_placement == "after_chapter":
            story.append(PageBreak())
            append_chapter_art_pdf(story, art, doc)

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setFont(fonts["regular"], 9)
        canvas.drawCentredString(page_size[0] / 2, 0.45 * POINTS_PER_INCH, str(canvas.getPageNumber()))
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output_path


def get_chapter_art(
    chapter_art: dict[str, ChapterArt] | None, chapter: Chapter
) -> ChapterArt | None:
    if not chapter_art:
        return None
    art = chapter_art.get(chapter.name)
    if art and art.image_path.exists():
        return art
    return None


def append_chapter_art_pdf(story: list, art: ChapterArt, doc) -> None:
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, Spacer

    image_reader = ImageReader(str(art.image_path))
    image_width, image_height = image_reader.getSize()
    max_width = doc.width
    max_height = doc.height * 0.88
    scale = min(max_width / image_width, max_height / image_height)
    image = Image(str(art.image_path))
    image.drawWidth = image_width * scale
    image.drawHeight = image_height * scale
    image.hAlign = "CENTER"
    story.append(Spacer(1, max(0, (doc.height - image.drawHeight) / 2)))
    story.append(image)


def append_template_pdf(story: list, markdown_text: str, styles) -> None:
    from reportlab.platypus import Paragraph, Spacer

    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 12))
            continue
        if stripped.startswith("# "):
            story.append(Spacer(1, 96))
            story.append(Paragraph(format_inline_pdf(stripped[2:].strip()), styles["ManuscriptTitle"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(format_inline_pdf(stripped[3:].strip()), styles["ManuscriptSubtitle"]))
        else:
            story.append(Paragraph(format_inline_pdf(strip_markdown(stripped)), styles["FrontMatter"]))


def append_markdown_pdf(story: list, markdown_text: str, styles) -> None:
    from reportlab.platypus import Paragraph, Spacer

    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph_lines:
            style_name = "LinePreservedText" if len(paragraph_lines) > 1 else "BodyTextManuscript"
            paragraph_text = "<br/>".join(format_inline_pdf(line) for line in paragraph_lines)
            story.append(
                Paragraph(paragraph_text, styles[style_name])
            )
            paragraph_lines.clear()

    def flush_code() -> None:
        if code_lines:
            code_text = "<br/>".join(escape_pdf_markup(line) for line in code_lines)
            story.append(Paragraph(code_text, styles["CodeBlock"]))
            code_lines.clear()

    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_paragraph()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw_line.rstrip())
            continue
        if not stripped:
            flush_paragraph()
            story.append(Spacer(1, 2))
            continue
        heading = re.match(r"^(#{2,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            story.append(Paragraph(format_inline_pdf(heading.group(2)), styles["SectionHeading"]))
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            quote = stripped.lstrip("> ").strip()
            story.append(Paragraph(format_inline_pdf(quote), styles["BlockQuote"]))
            continue
        if re.match(r"^[-*+]\s+", stripped):
            flush_paragraph()
            item = re.sub(r"^[-*+]\s+", "", stripped)
            story.append(Paragraph("- " + format_inline_pdf(item), styles["BodyTextManuscript"]))
            continue
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_code()


def generate_epub(
    chapters: list[Chapter],
    metadata: PublishMetadata,
    title_template: str,
    copyright_template: str,
    output_dir: Path,
    chapter_art: dict[str, ChapterArt] | None = None,
    art_placement: str = "before_chapter",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_filename(metadata.title)}.epub"
    identifier = f"urn:uuid:{uuid.uuid4()}"
    today = date.today().isoformat()

    title_page = xhtml_document(
        "Title Page",
        markdown_to_xhtml(render_template(title_template, metadata)),
    )
    copyright_page = xhtml_document(
        "Copyright",
        markdown_to_xhtml(render_template(copyright_template, metadata)),
    )

    chapter_files = []
    for index, chapter in enumerate(chapters, start=1):
        file_name = f"chapter-{index:03d}.xhtml"
        chapter_files.append((file_name, chapter))
    art_assets = build_epub_art_assets(chapters, chapter_art)

    nav_items = [
        ("title-page.xhtml", "Title Page"),
        ("copyright.xhtml", "Copyright"),
        *[(file_name, chapter.title) for file_name, chapter in chapter_files],
    ]

    with zipfile.ZipFile(output_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container_xml())
        archive.writestr("OEBPS/style.css", epub_css())
        archive.writestr("OEBPS/title-page.xhtml", title_page)
        archive.writestr("OEBPS/copyright.xhtml", copyright_page)
        for file_name, chapter in chapter_files:
            body = markdown_to_xhtml(chapter.markdown)
            art_asset = art_assets.get(chapter.name)
            if art_asset and art_placement == "before_chapter":
                body = chapter_art_xhtml(art_asset["href"], art_asset["alt_text"]) + "\n" + body
            elif art_asset and art_placement == "after_chapter":
                body = body + "\n" + chapter_art_xhtml(art_asset["href"], art_asset["alt_text"])
            archive.writestr(f"OEBPS/{file_name}", xhtml_document(chapter.title, body))
        for asset in art_assets.values():
            archive.write(asset["path"], f"OEBPS/{asset['href']}")
        archive.writestr("OEBPS/nav.xhtml", nav_xhtml(metadata, nav_items))
        archive.writestr("OEBPS/toc.ncx", toc_ncx(metadata, identifier, nav_items))
        archive.writestr(
            "OEBPS/content.opf",
            package_opf(metadata, identifier, today, chapter_files, list(art_assets.values())),
        )
    return output_path


def build_epub_art_assets(
    chapters: list[Chapter], chapter_art: dict[str, ChapterArt] | None
) -> dict[str, dict[str, str | Path]]:
    assets = {}
    for index, chapter in enumerate(chapters, start=1):
        art = get_chapter_art(chapter_art, chapter)
        if not art:
            continue
        media_type = image_media_type(art.image_path)
        if not media_type:
            continue
        suffix = art.image_path.suffix.lower()
        href = f"images/chapter-art-{index:03d}{suffix}"
        assets[chapter.name] = {
            "href": href,
            "path": art.image_path,
            "media_type": media_type,
            "alt_text": art.alt_text or f"{chapter.title} chapter art",
        }
    return assets


def image_media_type(path: Path) -> str:
    return IMAGE_MEDIA_TYPES.get(path.suffix.lower(), "")


def chapter_art_xhtml(href: str | Path, alt_text: str | Path) -> str:
    return (
        '<figure class="chapter-art">'
        f'<img src="{html.escape(str(href))}" alt="{html.escape(str(alt_text))}" />'
        "</figure>"
    )


def markdown_to_xhtml(markdown_text: str) -> str:
    html_lines: list[str] = []
    paragraph_lines: list[str] = []
    list_open = False
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph_lines:
            class_name = ' class="line-preserved"' if len(paragraph_lines) > 1 else ""
            paragraph_text = "<br />\n".join(format_inline_xhtml(line) for line in paragraph_lines)
            html_lines.append(f"<p{class_name}>{paragraph_text}</p>")
            paragraph_lines.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html_lines.append("</ul>")
            list_open = False

    def flush_code() -> None:
        if code_lines:
            html_lines.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
            code_lines.clear()

    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_paragraph()
                close_list()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw_line.rstrip())
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)), 6)
            text = format_inline_xhtml(heading.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            html_lines.append(f"<blockquote><p>{format_inline_xhtml(stripped.lstrip('> ').strip())}</p></blockquote>")
            continue
        if re.match(r"^[-*+]\s+", stripped):
            flush_paragraph()
            if not list_open:
                html_lines.append("<ul>")
                list_open = True
            item = re.sub(r"^[-*+]\s+", "", stripped)
            html_lines.append(f"<li>{format_inline_xhtml(item)}</li>")
            continue
        paragraph_lines.append(stripped)

    flush_paragraph()
    close_list()
    flush_code()
    return "\n".join(html_lines)


def remove_first_heading(markdown_text: str) -> str:
    return re.sub(r"^#\s+.+?\s*\n+", "", markdown_text, count=1, flags=re.MULTILINE)


def format_inline_pdf(text: str) -> str:
    escaped = escape_pdf_markup(text)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<i>\1</i>", escaped)
    return escaped


def format_inline_xhtml(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
    return escaped


def escape_pdf_markup(text: str) -> str:
    return html.escape(text, quote=False)


def xhtml_document(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
{body}
</body>
</html>
"""


def container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml" />
  </rootfiles>
</container>
"""


def epub_css() -> str:
    return """body {
  font-family: serif;
  line-height: 1.45;
  margin: 5%;
}
h1, h2, h3 {
  text-align: center;
  margin-top: 2em;
}
p {
  margin: 0 0 0.85em;
  text-indent: 1.2em;
}
p.line-preserved {
  text-indent: 0;
}
blockquote {
  margin: 1em 2em;
  font-style: italic;
}
pre {
  white-space: pre-wrap;
  font-family: monospace;
}
nav ol {
  list-style: none;
  padding-left: 0;
}
figure.chapter-art {
  margin: 1.5em 0 2em;
  page-break-before: always;
  text-align: center;
}
figure.chapter-art img {
  max-height: 92vh;
  max-width: 100%;
}
"""


def nav_xhtml(metadata: PublishMetadata, nav_items: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f'      <li><a href="{html.escape(href)}">{html.escape(label)}</a></li>'
        for href, label in nav_items
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{html.escape(metadata.language)}">
<head>
  <title>Table of Contents</title>
  <link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{html.escape(metadata.title)}</h1>
    <ol>
{items}
    </ol>
  </nav>
</body>
</html>
"""


def toc_ncx(
    metadata: PublishMetadata, identifier: str, nav_items: list[tuple[str, str]]
) -> str:
    nav_points = []
    for index, (href, label) in enumerate(nav_items, start=1):
        nav_points.append(
            f"""    <navPoint id="navPoint-{index}" playOrder="{index}">
      <navLabel><text>{html.escape(label)}</text></navLabel>
      <content src="{html.escape(href)}" />
    </navPoint>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{html.escape(identifier)}" />
    <meta name="dtb:depth" content="1" />
    <meta name="dtb:totalPageCount" content="0" />
    <meta name="dtb:maxPageNumber" content="0" />
  </head>
  <docTitle><text>{html.escape(metadata.title)}</text></docTitle>
  <navMap>
{chr(10).join(nav_points)}
  </navMap>
</ncx>
"""


def package_opf(
    metadata: PublishMetadata,
    identifier: str,
    modified_date: str,
    chapter_files: list[tuple[str, Chapter]],
    art_assets: list[dict[str, str | Path]] | None = None,
) -> str:
    manifest_chapters = "\n".join(
        f'    <item id="chapter-{index}" href="{html.escape(file_name)}" media-type="application/xhtml+xml" />'
        for index, (file_name, _) in enumerate(chapter_files, start=1)
    )
    spine_chapters = "\n".join(
        f'    <itemref idref="chapter-{index}" />'
        for index, _ in enumerate(chapter_files, start=1)
    )
    manifest_art = "\n".join(
        f'    <item id="art-{index}" href="{html.escape(str(asset["href"]))}" media-type="{html.escape(str(asset["media_type"]))}" />'
        for index, asset in enumerate(art_assets or [], start=1)
    )
    subtitle = (
        f"    <dc:description>{html.escape(metadata.subtitle)}</dc:description>\n"
        if metadata.subtitle
        else ""
    )
    publisher = (
        f"    <dc:publisher>{html.escape(metadata.publisher)}</dc:publisher>\n"
        if metadata.publisher
        else ""
    )
    isbn = (
        f"    <dc:identifier id=\"isbn\">{html.escape(metadata.isbn)}</dc:identifier>\n"
        if metadata.isbn
        else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{html.escape(identifier)}</dc:identifier>
{isbn}    <dc:title>{html.escape(metadata.title)}</dc:title>
    <dc:creator>{html.escape(metadata.author)}</dc:creator>
    <dc:language>{html.escape(metadata.language)}</dc:language>
{publisher}{subtitle}    <meta property="dcterms:modified">{modified_date}T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />
    <item id="toc" href="toc.ncx" media-type="application/x-dtbncx+xml" />
    <item id="style" href="style.css" media-type="text/css" />
    <item id="title-page" href="title-page.xhtml" media-type="application/xhtml+xml" />
    <item id="copyright" href="copyright.xhtml" media-type="application/xhtml+xml" />
{manifest_chapters}
{manifest_art}
  </manifest>
  <spine toc="toc">
    <itemref idref="title-page" />
    <itemref idref="copyright" />
{spine_chapters}
  </spine>
</package>
"""
