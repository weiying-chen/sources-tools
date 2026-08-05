"""Shared helpers for editing the PM master DOCX table."""

from __future__ import annotations

import copy
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile


WORD_DOCUMENT = "word/document.xml"


@dataclass(frozen=True)
class RowMatch:
    row_xml: str
    cell_xml: str
    cell_start_in_row: int
    cell_end_in_row: int
    chinese_title: str
    row_label: str


def normalize_title(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"【\s*大愛醫生館\s*】", "", text)
    text = re.sub(r"20\d{6}", "", text)
    text = re.sub(r"\s+", "", text)
    return text.replace("-", "").replace("－", "").replace("~", "").replace("～", "")


def extract_text(xml: str) -> str:
    parts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", xml, flags=re.S)
    return html.unescape("".join(parts))


def extract_paragraphs(xml: str) -> list[str]:
    paragraphs = re.findall(r"<w:p(?:\s[^>]*)?>.*?</w:p>", xml, flags=re.S)
    return [extract_text(paragraph) for paragraph in paragraphs]


def iter_tag_spans(xml: str, tag: str) -> Iterable[tuple[int, int, str]]:
    pattern = re.compile(rf"<{tag}(?:\s[^>]*)?>.*?</{tag}>", flags=re.S)
    for match in pattern.finditer(xml):
        yield match.start(), match.end(), match.group(0)


def cells_for_row(row_xml: str) -> list[tuple[int, int, str]]:
    return list(iter_tag_spans(row_xml, "w:tc"))


def row_needs_english(cell_xml: str) -> bool:
    paragraphs = [text.strip() for text in extract_paragraphs(cell_xml) if text.strip()]
    if len(paragraphs) <= 3:
        return True
    return not bool(re.search(r"[A-Za-z]", " ".join(paragraphs[3:])))


def extract_row_match(row_xml: str) -> RowMatch | None:
    cells = cells_for_row(row_xml)
    if len(cells) < 2:
        return None
    label = extract_text(cells[0][2]).strip()
    target_start, target_end, target_cell = cells[1]
    paragraphs = [text.strip() for text in extract_paragraphs(target_cell) if text.strip()]
    if len(paragraphs) < 3 or not row_needs_english(target_cell):
        return None
    chinese_title = normalize_title(paragraphs[0])
    if not chinese_title:
        return None
    return RowMatch(
        row_xml=row_xml,
        cell_xml=target_cell,
        cell_start_in_row=target_start,
        cell_end_in_row=target_end,
        chinese_title=chinese_title,
        row_label=label,
    )


def has_bold_run(paragraph_xml: str) -> bool:
    return "<w:b" in paragraph_xml


def find_template_paragraphs(document_xml: str) -> tuple[str, str]:
    for _, _, row in iter_tag_spans(document_xml, "w:tr"):
        cells = cells_for_row(row)
        if len(cells) < 2:
            continue
        paragraphs_xml = re.findall(r"<w:p(?:\s[^>]*)?>.*?</w:p>", cells[1][2], flags=re.S)
        paragraphs_text = [extract_text(paragraph).strip() for paragraph in paragraphs_xml]
        if len(paragraphs_xml) < 5:
            continue
        title_xml, description_xml = paragraphs_xml[3], paragraphs_xml[4]
        if (
            paragraphs_text[3]
            and paragraphs_text[4]
            and has_bold_run(title_xml)
            and re.search(r"[A-Za-z]", paragraphs_text[3])
        ):
            return title_xml, description_xml
    raise RuntimeError("Could not find a filled English title/description template row.")


def replace_paragraph_text(paragraph_xml: str, new_text: str) -> str:
    pattern = re.compile(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", flags=re.S)
    if not pattern.search(paragraph_xml):
        raise RuntimeError("Template paragraph has no text node.")
    escaped = html.escape(new_text, quote=False)
    seen_first = False

    def replace(match: re.Match[str]) -> str:
        nonlocal seen_first
        if seen_first:
            return f"{match.group(1)}{match.group(3)}"
        seen_first = True
        return f"{match.group(1)}{escaped}{match.group(3)}"

    return pattern.sub(replace, paragraph_xml)


def insert_after_timestamp(cell_xml: str, title_xml: str, description_xml: str) -> str:
    paragraphs = list(re.finditer(r"<w:p(?:\s[^>]*)?>.*?</w:p>", cell_xml, flags=re.S))
    if len(paragraphs) < 3:
        raise RuntimeError("Target cell lacks title/link/timestamp paragraphs.")
    insert_at = paragraphs[2].end()
    return cell_xml[:insert_at] + title_xml + description_xml + cell_xml[insert_at:]


def write_docx_copy(source: Path, destination: Path, document_xml: str) -> None:
    with ZipFile(source, "r") as source_zip:
        infos = source_zip.infolist()
        contents = {info.filename: source_zip.read(info.filename) for info in infos}
    contents[WORD_DOCUMENT] = document_xml.encode("utf-8")
    ElementTree.fromstring(contents[WORD_DOCUMENT])

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as output_zip:
        for info in infos:
            new_info = copy.copy(info)
            new_info.compress_type = ZIP_DEFLATED
            output_zip.writestr(new_info, contents[info.filename])
    with ZipFile(temporary) as test_zip:
        bad_member = test_zip.testzip()
    if bad_member:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Generated DOCX failed ZIP validation at {bad_member}")
    temporary.replace(destination)
