#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PROGRAM_URLS = {
    "all-about-health": "https://daai.tv/program/P0016",
    "easy-fitness": "https://www.youtube.com/@daaitvsport/videos",
}

ITEM_RE = re.compile(r'<div class="item"\s+id="episode-(?P<idx>\d+)">(?P<body>.*?)<script>', re.S)
TITLE_RE = re.compile(r'<div class="title">(?P<title>.*?)</div>', re.S)
DATE_RE = re.compile(r'<div class="date">(?P<date>\d{4}-\d{2}-\d{2})</div>')

EPID_RE = re.compile(r'\\"EpID\\":\\"(?P<epid>.*?)\\"')
PREMIERE_RE = re.compile(r'\\"EpPremiere\\":\\"(?P<premiere>.*?)\\"')
YTID_RE = re.compile(r'\\"YTID\\":\\"(?P<ytid>.*?)\\"')
EPTITLE_RE = re.compile(r'\\"EpTitle\\":\\"(?P<title>.*?)\\"')
YT_OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"', re.I)
YT_SHORT_DESC_RE = re.compile(r'"shortDescription":"(.*?)"', re.S)
YT_TIMESTAMP_LINE_RE = re.compile(r"^\s*(\d{1,2}:\d{2})｜.+$")
EASY_FITNESS_HEADING_RE = re.compile(r"^\s*➯\s*5\s*分鐘動起來！\s*$")
EASY_FITNESS_TIMESTAMP_RE = re.compile(r"^\s*\d{1,2}:\d{2}\s+\S.*$")


def _clean_html_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _decode_js_escaped_text(text: str) -> str:
    if "\\u" not in text and "\\/" not in text:
        return text
    try:
        return bytes(text, "utf-8").decode("unicode_escape")
    except Exception:
        return text


def _parse_episode_payload(payload: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        data = json.loads(payload.replace('\\"', '"'))
        out["epid"] = str(data.get("EpID", "")).strip()
        out["date"] = str(data.get("EpPremiere", "")).split(" ")[0].strip()
        out["title"] = str(data.get("EpTitle", "")).strip()
        out["ytid"] = str(data.get("YTID", "")).strip()
        return out
    except Exception:
        pass

    epid = EPID_RE.search(payload)
    premiere = PREMIERE_RE.search(payload)
    ytid = YTID_RE.search(payload)
    title = EPTITLE_RE.search(payload)
    if epid:
        out["epid"] = epid.group("epid").strip()
    if premiere:
        out["date"] = premiere.group("premiere").split(" ")[0].strip()
    if ytid:
        out["ytid"] = ytid.group("ytid").strip()
    if title:
        out["title"] = _decode_js_escaped_text(title.group("title").strip())
    return out


def extract_episode_rows_from_html(html: str) -> list[dict[str, str | int]]:
    rows_by_idx: dict[int, dict[str, str | int]] = {}

    for m in ITEM_RE.finditer(html):
        idx = int(m.group("idx"))
        body = m.group("body")
        title_match = TITLE_RE.search(body)
        date_match = DATE_RE.search(body)
        rows_by_idx[idx] = {
            "episode_index": idx,
            "epid": "",
            "date": date_match.group("date").strip() if date_match else "",
            "title": _clean_html_text(title_match.group("title")) if title_match else "",
            "ytid": "",
        }

    script_key = "document.getElementById('episode-"
    pos = 0
    while True:
        start = html.find(script_key, pos)
        if start == -1:
            break
        idx_start = start + len(script_key)
        idx_end = html.find("')", idx_start)
        if idx_end == -1:
            break
        idx_text = html[idx_start:idx_end]
        if not idx_text.isdigit():
            pos = idx_end + 2
            continue
        idx = int(idx_text)
        json_key = "var episodeJson = '"
        json_pos = html.find(json_key, idx_end)
        if json_pos == -1:
            pos = idx_end + 2
            continue
        payload_start = json_pos + len(json_key)
        end_marker = "openEpisodeModal("
        payload_end = html.find(end_marker, payload_start)
        if payload_end == -1:
            end_marker = "});"
            payload_end = html.find(end_marker, payload_start)
            if payload_end == -1:
                pos = payload_start
                continue
        payload = html[payload_start:payload_end]
        payload = payload.strip()
        if payload.endswith(";"):
            payload = payload[:-1].rstrip()
        if payload.endswith("'"):
            payload = payload[:-1].rstrip()
        parsed = _parse_episode_payload(payload)
        existing = rows_by_idx.get(
            idx,
            {"episode_index": idx, "epid": "", "date": "", "title": "", "ytid": ""},
        )
        for key in ("epid", "date", "title", "ytid"):
            value = parsed.get(key, "")
            if value:
                existing[key] = value
        rows_by_idx[idx] = existing
        pos = payload_end + len(end_marker)

    return [rows_by_idx[idx] for idx in sorted(rows_by_idx)]


def fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def _decode_json_escaped_text(text: str) -> str:
    try:
        return json.loads(f'"{text}"')
    except Exception:
        return _decode_js_escaped_text(text)


def _extract_last_timestamp_line(description: str) -> str:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    last = ""
    for line in lines:
        if YT_TIMESTAMP_LINE_RE.match(line):
            last = line
    return last


def extract_easy_fitness_description(description: str) -> str:
    """Keep the summary and the short exercise timestamp block."""
    lines = description.splitlines()
    heading_idx = next(
        (idx for idx, line in enumerate(lines) if EASY_FITNESS_HEADING_RE.match(line)),
        None,
    )
    if heading_idx is None:
        return description.strip()

    # The summary is the nearest non-empty paragraph before the heading. This
    # intentionally drops promotional links that appear above the summary.
    summary_end = heading_idx
    while summary_end > 0 and not lines[summary_end - 1].strip():
        summary_end -= 1
    summary_start = summary_end
    while summary_start > 0 and lines[summary_start - 1].strip():
        summary_start -= 1

    kept = [line.strip() for line in lines[summary_start:summary_end]]
    kept.append("")
    kept.append(lines[heading_idx].strip())
    for line in lines[heading_idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            if kept[-1] != "":
                break
            continue
        if not EASY_FITNESS_TIMESTAMP_RE.match(stripped):
            break
        kept.append(stripped)
    return "\n".join(kept).strip()


def _youtube_date(value: object) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def extract_youtube_channel(url: str, limit: int = 0) -> tuple[list[dict], list[dict]]:
    """Extract video metadata from a YouTube channel using yt-dlp."""
    command = [
        "yt-dlp",
        "--dump-json",
        "--skip-download",
        "--ignore-errors",
        "--no-warnings",
    ]
    if limit > 0:
        command.extend(["--playlist-end", str(limit)])
    command.append(url)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 and not result.stdout.strip():
        message = result.stderr.strip() or f"yt-dlp exited with status {result.returncode}"
        raise RuntimeError(message)

    raw_rows: list[dict] = []
    episodes: list[dict] = []
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("_type") == "playlist":
            continue
        video_id = str(item.get("id", "")).strip()
        if not video_id:
            continue
        description = extract_easy_fitness_description(
            str(item.get("description", ""))
        )
        raw_rows.append(
            {
                "video_id": video_id,
                "upload_date": _youtube_date(item.get("upload_date")),
                "title": str(item.get("title", "")).strip(),
                "description": description,
            }
        )
        episodes.append(
            {
                "episodeIndex": len(episodes),
                # YouTube-only programmes have no daai.tv EpID. Using the video
                # ID lets subtitle files use the existing "<epId>_...txt" rule.
                "epId": video_id,
                "date": _youtube_date(item.get("upload_date")),
                "titleZh": str(item.get("title", "")).strip(),
                "ytId": video_id,
                "youtubeUrl": f"https://www.youtube.com/watch?v={video_id}",
                "youtubeTitle": str(item.get("title", "")).strip(),
                "youtubeDescription": description,
                "descriptionLastTimestampLine": _extract_last_easy_fitness_timestamp(
                    description
                ),
            }
        )
    return raw_rows, episodes


def _extract_last_easy_fitness_timestamp(description: str) -> str:
    line = next(
        (
            line.strip()
            for line in reversed(description.splitlines())
            if EASY_FITNESS_TIMESTAMP_RE.match(line)
        ),
        "",
    )
    # The existing DOCX generator recognizes the daai.tv ``MM:SS｜label``
    # shape, so normalize only this helper field while keeping the retained
    # YouTube description exactly as published.
    return re.sub(r"^(\d{1,2}:\d{2})\s+", r"\1｜", line, count=1)


def _is_youtube_url(url: str) -> bool:
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def extract_youtube_fields(youtube_html: str) -> dict[str, str]:
    title = ""
    m_title = YT_OG_TITLE_RE.search(youtube_html)
    if m_title:
        title = _decode_json_escaped_text(m_title.group(1).strip())

    description = ""
    m_desc = YT_SHORT_DESC_RE.search(youtube_html)
    if m_desc:
        description = _decode_json_escaped_text(m_desc.group(1))

    return {
        "youtubeTitle": title,
        "youtubeDescription": description,
        "descriptionLastTimestampLine": _extract_last_timestamp_line(description),
    }


def build_episodes(rows: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    episodes: list[dict[str, str | int]] = []
    for row in rows:
        ytid = str(row.get("ytid", "")).strip()
        youtube_url = f"https://www.youtube.com/watch?v={ytid}" if ytid else ""
        episode = {
            "episodeIndex": int(row.get("episode_index", 0)),
            "epId": str(row.get("epid", "")).strip(),
            "date": str(row.get("date", "")).strip(),
            "titleZh": str(row.get("title", "")).strip(),
            "ytId": ytid,
            "youtubeUrl": youtube_url,
            "youtubeTitle": "",
            "youtubeDescription": "",
            "descriptionLastTimestampLine": "",
        }
        episodes.append(episode)
    return episodes


def enrich_with_youtube(episodes: list[dict[str, str | int]]) -> None:
    for episode in episodes:
        youtube_url = str(episode.get("youtubeUrl", "")).strip()
        if not youtube_url:
            continue
        try:
            yt_html = fetch_html(youtube_url)
        except Exception:
            continue
        fields = extract_youtube_fields(yt_html)
        episode.update(fields)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract episodes from a daai.tv programme page or YouTube channel."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Optional URL override; otherwise inferred from the current folder.",
    )
    parser.add_argument(
        "--url",
        dest="url_option",
        default="",
        help="URL override (retained for compatibility).",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "daai", "youtube"),
        default="auto",
        help="Source type. By default it is detected from the URL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum YouTube channel videos to extract; 0 means all videos.",
    )
    parser.add_argument("--out", default="episodes.json", help="Output JSON file path.")
    parser.add_argument(
        "--raw-out",
        default="episodes_raw.json",
        help="Optional raw extraction JSON output path (e.g. episodes_raw.json).",
    )
    args = parser.parse_args()

    folder_name = Path.cwd().name
    url = (args.url_option or args.url or PROGRAM_URLS.get(folder_name, "")).strip()
    if not url:
        parser.error(
            "cannot infer the programme from this folder; run from "
            "all-about-health/easy-fitness or provide a URL"
        )

    output_path = Path(args.out)
    raw_output_path = Path(args.raw_out) if args.raw_out else None
    requested_source = args.source
    source = (
        "youtube"
        if requested_source == "auto" and _is_youtube_url(url)
        else requested_source
    )
    if source == "auto":
        source = "daai"

    if source == "youtube":
        rows, episodes = extract_youtube_channel(url, args.limit)
    else:
        html = fetch_html(url)
        rows = extract_episode_rows_from_html(html)
        episodes = build_episodes(rows)
        enrich_with_youtube(episodes)
    if raw_output_path:
        raw_output_path.parent.mkdir(parents=True, exist_ok=True)
        raw_output_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(episodes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"count\t{len(episodes)}")
    print(f"out\t{output_path}")


if __name__ == "__main__":
    main()
