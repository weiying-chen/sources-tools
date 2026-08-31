#!/usr/bin/env python3
"""Show the next unfinished source episodes, oldest first."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from update_sources import matching_title_keys


WORKFLOW_FOLDERS = ("queued", "translated", "done")
DOCUMENT_SUFFIXES = {".doc", ".docx"}
YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?[^\s]*?v=|shorts/))([A-Za-z0-9_-]{6,})"
)


@dataclass(frozen=True)
class Episode:
    date: str
    title: str
    url: str
    video_id: str
    source_index: int


@dataclass
class WorkflowIndex:
    video_ids: set[str]
    title_keys: set[str]


@dataclass(frozen=True)
class Boundary:
    title: str
    video_id: str


def usable_document(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in DOCUMENT_SUFFIXES
        and not path.name.startswith("~$")
        and not path.name.endswith(":Zone.Identifier")
    )


def docx_paragraphs(path: Path) -> list[str]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (BadZipFile, KeyError, ElementTree.ParseError):
        return []
    return [
        "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        for paragraph in root.findall(".//w:p", namespace)
    ]


def doc_paragraphs(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["antiword", str(path)], check=True, capture_output=True, text=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def document_paragraphs(path: Path) -> list[str]:
    return docx_paragraphs(path) if path.suffix.lower() == ".docx" else doc_paragraphs(path)


def normalized_title_keys(title: str) -> set[str]:
    return {key.casefold() for key in matching_title_keys(title) if key}


def title_candidates(path: Path, paragraphs: list[str]) -> set[str]:
    candidates = {path.stem}
    candidates.update(text for text in paragraphs[:8] if re.search(r"[\u3400-\u9fff]", text))
    keys: set[str] = set()
    for candidate in candidates:
        keys.update(normalized_title_keys(candidate))
    return keys


def build_workflow_index(project: Path) -> WorkflowIndex:
    video_ids: set[str] = set()
    title_keys: set[str] = set()
    for folder_name in WORKFLOW_FOLDERS:
        folder = project / folder_name
        if not folder.is_dir():
            raise SystemExit(f"Missing workflow folder: {folder}")
        for path in folder.iterdir():
            if not usable_document(path):
                continue
            paragraphs = document_paragraphs(path)
            searchable = "\n".join(paragraphs)
            video_ids.update(YOUTUBE_ID_RE.findall(searchable))
            title_keys.update(title_candidates(path, paragraphs))
    return WorkflowIndex(video_ids, title_keys)


def discover_master(project: Path) -> Path:
    candidates = sorted(
        path
        for path in project.glob("*.docx")
        if not path.name.startswith("~$") and not path.stem.endswith("_updated")
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SystemExit(f"No master DOCX found directly inside {project}")
    raise SystemExit(
        "Multiple possible master DOCX files found: "
        + ", ".join(path.name for path in candidates)
    )


def read_master_boundary(path: Path) -> Boundary:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise SystemExit(f"Cannot read master DOCX {path}: {error}")
    table = root.find(".//w:tbl", namespace)
    if table is None:
        raise SystemExit(f"Master DOCX has no table: {path}")
    rows = table.findall("./w:tr", namespace)
    for row in rows[1:]:
        cells = row.findall("./w:tc", namespace)
        if len(cells) < 2:
            continue
        paragraphs = [
            "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
            for paragraph in cells[1].findall(".//w:p", namespace)
        ]
        title = next((text for text in paragraphs if text), "")
        if not title:
            continue
        searchable = "\n".join(paragraphs)
        match = YOUTUBE_ID_RE.search(searchable)
        return Boundary(title, match.group(1) if match else "")
    raise SystemExit(f"Master DOCX has no populated episode row: {path}")


def load_episodes(path: Path) -> list[Episode]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing episode metadata: {path}")
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid episode metadata in {path}: {error}")
    if not isinstance(raw, list):
        raise SystemExit(f"Episode metadata must be a JSON list: {path}")
    episodes: list[Episode] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = str(item.get("titleZh") or item.get("youtubeTitle") or "").strip()
        url = str(item.get("youtubeUrl") or "").strip()
        video_id = str(item.get("ytId") or "").strip()
        if not video_id:
            match = YOUTUBE_ID_RE.search(url)
            video_id = match.group(1) if match else ""
        if title:
            episodes.append(
                Episode(str(item.get("date") or ""), title, url, video_id, index)
            )
    return episodes


def display_date(date: str) -> str:
    """Format ISO episode dates for copying into the archive search form."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return date.replace("-", "/")
    return date


def is_finished(episode: Episode, workflow: WorkflowIndex) -> bool:
    if episode.video_id and episode.video_id in workflow.video_ids:
        return True
    return bool(normalized_title_keys(episode.title) & workflow.title_keys)


def matches_boundary(episode: Episode, boundary: Boundary) -> bool:
    if boundary.video_id and episode.video_id == boundary.video_id:
        return True
    return bool(normalized_title_keys(episode.title) & normalized_title_keys(boundary.title))


def next_episodes(
    episodes: list[Episode], boundary: Boundary, workflow: WorkflowIndex, limit: int
) -> list[Episode]:
    """Return the next episodes after the top master row, oldest first."""
    newest_first = sorted(
        episodes, key=lambda episode: (episode.date, -episode.source_index), reverse=True
    )
    boundary_index = next(
        (index for index, episode in enumerate(newest_first) if matches_boundary(episode, boundary)),
        None,
    )
    if boundary_index is None:
        raise SystemExit(f"Top master episode was not found in episodes.json: {boundary.title}")

    selected: list[Episode] = []
    for episode in reversed(newest_first[:boundary_index]):
        if is_finished(episode, workflow):
            continue
        selected.append(episode)
        if len(selected) == limit:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=3, help="number to show (default: 3)")
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    project = Path.cwd()
    episodes = load_episodes(project / "episodes.json")
    workflow = build_workflow_index(project)
    boundary = read_master_boundary(discover_master(project))
    selected = next_episodes(episodes, boundary, workflow, args.limit)
    if not selected:
        print("No unfinished episodes found.")
        return 0
    for index, episode in enumerate(selected, 1):
        print(f"{index}. {display_date(episode.date)}  {episode.title}")
        if episode.url:
            print(episode.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
