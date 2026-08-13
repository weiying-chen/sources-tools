#!/usr/bin/env python3
"""
Fill missing English titles/descriptions in the current programme's master DOCX.

Run from a programme folder; the script scans its done/ folder,
extracts the English "建議標題/標題" and "簡介" fields, matches by Chinese
episode title, and updates the validated master DOCX by default.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from pm_docx_utils import (
    WORD_DOCUMENT,
    cells_for_row,
    extract_paragraphs,
    extract_row_match,
    extract_text,
    find_template_paragraphs,
    insert_after_timestamp,
    iter_tag_spans,
    normalize_title,
    replace_paragraph_text,
    write_docx_copy,
)

@dataclass(frozen=True)
class DoneEntry:
    source: Path
    chinese_title: str
    english_title: str
    description: str


def read_docx_paragraphs(path: Path) -> list[str]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as z:
        root = ElementTree.fromstring(z.read(WORD_DOCUMENT))
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", ns):
        text = "".join(t.text or "" for t in para.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def read_doc_paragraphs(path: Path) -> list[str]:
    result = subprocess.run(["antiword", str(path)], check=True, capture_output=True, text=True)
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current).strip())
    return paragraphs


def read_word_paragraphs(path: Path) -> list[str]:
    if path.suffix.lower() == ".docx":
        return read_docx_paragraphs(path)
    if path.suffix.lower() == ".doc":
        return read_doc_paragraphs(path)
    return []


def is_label(text: str, labels: tuple[str, ...]) -> bool:
    stripped = text.strip().rstrip(":：")
    return stripped in labels


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def english_prefix(text: str) -> str:
    match = re.search(r"[\u3400-\u9fff]", text)
    if match:
        text = text[: match.start()]
    return text.strip()


def first_nonempty_after(paragraphs: list[str], index: int) -> str:
    for text in paragraphs[index + 1 :]:
        if text.strip():
            return text.strip()
    return ""


def normalize_source_title(text: str) -> str:
    """Normalize an episode title in the same way as a PM-sheet row title."""
    normalized = normalize_title(text)
    normalized = re.sub(r"【?大愛真健康】?", "", normalized)
    # Older completed files include the source-program label, while the PM
    # master rows begin directly with the host/guest portion of the title.
    normalized = re.sub(r"^早點回家[|｜∣]?", "", normalized)
    return normalized


def matching_title_keys(title: str) -> tuple[str, ...]:
    """Return full and short matching forms for differently styled PM titles."""
    full = normalize_source_title(title)
    short = re.split(r"[|｜∣]", full, maxsplit=1)[0]
    return tuple(dict.fromkeys((full, short)))


def extract_chinese_title(paragraphs: list[str]) -> str:
    if not paragraphs:
        return ""
    for text in paragraphs[:8]:
        if "大愛醫生館" in text:
            return normalize_source_title(text)
    # Easy Fitness and similar files put the Chinese YouTube title first.
    return normalize_source_title(paragraphs[0])


def extract_english_title(paragraphs: list[str]) -> str:
    for i, text in enumerate(paragraphs):
        if is_label(text, ("建議標題", "標題")):
            candidate = first_nonempty_after(paragraphs, i)
            if candidate and re.search(r"[A-Za-z]", candidate) and not candidate.startswith("All About Health"):
                return candidate.strip()
        match = re.match(r"^(?:建議標題|標題)\s*[：:]\s*(.+)$", text)
        if match and re.search(r"[A-Za-z]", match.group(1)):
            return match.group(1).strip()
    return ""


def extract_description(paragraphs: list[str]) -> str:
    for i, text in enumerate(paragraphs):
        inline = re.match(r"^簡介\s*[：:]\s*(.+)$", text)
        if not (is_label(text, ("簡介",)) or re.match(r"^簡介\s*[：:]\s*$", text) or inline):
            continue
        parts: list[str] = []
        if inline:
            first = english_prefix(inline.group(1))
            if first and re.search(r"[A-Za-z]", first):
                parts.append(first)
        for candidate in paragraphs[i + 1 :]:
            candidate = candidate.strip()
            if not candidate:
                continue
            if candidate.startswith(("選圖", "00:", "建議", "標題")):
                break
            candidate = english_prefix(candidate)
            if not candidate:
                break
            if re.search(r"[A-Za-z]", candidate):
                parts.append(candidate)
            if parts and candidate.endswith((".", "?", "!")):
                # DOCX exports usually keep the full English description in one paragraph.
                # Old DOC extraction may wrap it across paragraphs; keep going until a label/CJK.
                continue
        return " ".join(parts).strip()
    return ""


def iter_done_entries(source_dir: Path) -> list[DoneEntry]:
    entries: list[DoneEntry] = []
    for path in sorted(source_dir.iterdir()):
        if path.name.endswith(":Zone.Identifier") or path.suffix.lower() not in {".doc", ".docx"}:
            continue
        paragraphs = read_word_paragraphs(path)
        chinese_title = extract_chinese_title(paragraphs)
        english_title = extract_english_title(paragraphs)
        description = extract_description(paragraphs)
        if chinese_title and english_title and description:
            entries.append(DoneEntry(path, chinese_title, english_title, description))
        else:
            print(
                f"skip {path.name}: "
                f"chinese={bool(chinese_title)} title={bool(english_title)} description={bool(description)}"
            )
    return entries


def discover_project_docx(project_dir: Path) -> Path:
    candidates = sorted(
        path
        for path in project_dir.glob("*.docx")
        if not path.stem.endswith("_updated") and not path.name.startswith("~$")
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SystemExit(
            f"No PM/master DOCX found in {project_dir}/. Put exactly one master DOCX there "
            "or pass it with --docx."
        )
    names = ", ".join(str(path) for path in candidates)
    raise SystemExit(f"Multiple PM/master DOCX files found; pass the one to update explicitly: {names}")


def build_output_path(input_path: Path, in_place: bool) -> Path:
    if in_place:
        return input_path
    return input_path.with_name(f"{input_path.stem}_updated{input_path.suffix}")


def choose_entry(candidates: list[DoneEntry]) -> tuple[DoneEntry | None, str]:
    """Choose one source safely, preferring a unique final deliverable."""
    unique = {entry.source: entry for entry in candidates}
    entries = list(unique.values())
    finals = [entry for entry in entries if entry.source.stem.lower().endswith("_final")]
    if len(finals) == 1:
        return finals[0], ""
    if len(entries) == 1:
        return entries[0], ""
    variants = {(entry.english_title, entry.description) for entry in entries}
    if len(variants) == 1:
        return entries[0], ""
    names = ", ".join(entry.source.name for entry in (finals or entries))
    return None, f"ambiguous matching sources: {names}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docx",
        type=Path,
        help="master DOCX (defaults to the only DOCX in the current programme folder)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="completed files folder (defaults to FOLDER/done)",
    )
    parser.add_argument("--dry-run", action="store_true", help="show matches without writing a DOCX")
    parser.add_argument(
        "--copy",
        dest="in_place",
        action="store_false",
        help="write MASTER_updated.docx instead of updating the master in place",
    )
    parser.add_argument("--in-place", dest="in_place", action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(in_place=True)
    parser.add_argument("--limit", type=int, default=0, help="maximum number of rows to update")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace English details in matching rows even when already filled",
    )
    args = parser.parse_args()

    project_dir = Path.cwd()
    if not project_dir.is_dir():
        raise SystemExit(f"Missing project folder: {project_dir}")
    docx_path = args.docx if args.docx else discover_project_docx(project_dir)
    source_dir = args.source_dir if args.source_dir else project_dir / "done"
    if not docx_path.exists():
        raise SystemExit(f"Missing DOCX: {docx_path}")
    if not source_dir.is_dir():
        raise SystemExit(f"Missing source folder: {source_dir}")

    with ZipFile(docx_path) as z:
        document_xml = z.read(WORD_DOCUMENT).decode("utf-8")
    ElementTree.fromstring(document_xml.encode("utf-8"))

    entries = iter_done_entries(source_dir)
    entries_by_title: dict[str, list[DoneEntry]] = {}
    for entry in entries:
        for key in matching_title_keys(entry.chinese_title):
            entries_by_title.setdefault(key, []).append(entry)
    title_template, desc_template = find_template_paragraphs(document_xml)
    template_title = extract_text(title_template).strip()
    title_prefix = "Easy Fitness - " if re.match(r"^Easy Fitness\s*[-–]", template_title) else ""

    replacements: list[tuple[str, str]] = []
    updates = 0
    for _, _, row_xml in iter_tag_spans(document_xml, "w:tr"):
        row = extract_row_match(row_xml, require_missing=not args.refresh)
        if not row:
            continue
        entry = None
        ambiguity = ""
        for key in matching_title_keys(row.chinese_title):
            candidates = entries_by_title.get(key, [])
            if candidates:
                entry, ambiguity = choose_entry(candidates)
                break
        if ambiguity:
            print(f"skip row {row.row_label}: {ambiguity}")
        if not entry:
            continue
        title_xml = replace_paragraph_text(title_template, title_prefix + entry.english_title)
        description_xml = replace_paragraph_text(desc_template, entry.description)
        new_cell = insert_after_timestamp(row.cell_xml, title_xml, description_xml)
        new_row = row_xml[: row.cell_start_in_row] + new_cell + row_xml[row.cell_end_in_row :]
        replacements.append((row_xml, new_row))
        updates += 1
        print(f"row {row.row_label}: {entry.english_title} ({entry.source.name})")
        if args.limit and updates >= args.limit:
            break

    if not replacements:
        print("No matching missing rows found.")
        return 0

    updated_xml = document_xml
    for old, new in replacements:
        updated_xml = updated_xml.replace(old, new, 1)
    ElementTree.fromstring(updated_xml.encode("utf-8"))

    output_path = build_output_path(docx_path, args.in_place)
    if args.dry_run:
        print(f"Dry run: would update {updates} row(s), output {output_path}")
        return 0

    write_docx_copy(docx_path, output_path, updated_xml)
    print(f"Wrote {output_path} with {updates} update(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
