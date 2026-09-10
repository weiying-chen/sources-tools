#!/home/weiying/python/word/.venv/bin/python
"""Report actionable PM work from the programme workflow folders."""

from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path.cwd()
CONFIG_PATH = SCRIPT_DIR / "report_sources.toml"
PROGRAMMES = (
    ("大愛醫生館", ROOT / "all-about-health"),
    ("大愛真健康", ROOT / "easy-fitness"),
)
DOCUMENT_SUFFIXES = {".doc", ".docx"}


def load_config(path: Path) -> tuple[int, dict[str, str]]:
    with path.open("rb") as config_file:
        data = tomllib.load(config_file)
    report_config = data.get("report", {})
    ready_target = int(report_config.get("translation_ready_target", 3))
    if ready_target < 1:
        raise SystemExit("translation_ready_target must be at least 1")
    translators = {
        str(key).casefold(): str(value)
        for key, value in report_config.get("translators", {}).items()
    }
    return ready_target, translators


def count_documents(folder: Path) -> int:
    if not folder.is_dir():
        raise SystemExit(f"Missing workflow folder: {folder}")
    return sum(
        1
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in DOCUMENT_SUFFIXES
        and not path.name.startswith("~$")
        and not path.name.endswith(":Zone.Identifier")
    )


def document_paths(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise SystemExit(f"Missing workflow folder: {folder}")
    return [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in DOCUMENT_SUFFIXES
        and not path.name.startswith("~$")
        and not path.name.endswith(":Zone.Identifier")
    ]


def translator_from_filename(path: Path, translators: dict[str, str]) -> str | None:
    """Return the configured translator whose key appears as a filename token."""
    tokens = [token.casefold() for token in re.split(r"[\W_]+", path.stem) if token]
    for token in reversed(tokens):
        if token in translators:
            return translators[token]
    return None


def editing_counts(
    folder: Path, translators: dict[str, str]
) -> list[tuple[str | None, int]]:
    counts = Counter(translator_from_filename(path, translators) for path in document_paths(folder))
    return sorted(counts.items(), key=lambda item: (item[0] is None, item[0] or ""))


def files_without_translator(folder: Path, translators: dict[str, str]) -> list[str]:
    """List every translated document that has no configured translator token."""
    return sorted(
        [
            path.name
            for path in document_paths(folder)
            if translator_from_filename(path, translators) is None
        ],
        key=str.casefold,
    )


def count_programme(project: Path) -> tuple[int, int]:
    return count_documents(project / "queued"), count_documents(project / "translated")


def format_section(title: str, counts: list[tuple[str, int]]) -> str:
    lines = [f"{title}："]
    nonzero = [(programme, count) for programme, count in counts if count]
    if not nonzero:
        lines.append("無")
    else:
        lines.extend(f"{count}集{programme}" for programme, count in nonzero)
    return "\n".join(lines)


def format_editing_section(
    counts: list[tuple[str, list[tuple[str | None, int]]]],
) -> str:
    lines = ["待edit的節目："]
    if not any(groups for _, groups in counts):
        lines.append("無")
    for programme, groups in counts:
        for translator, count in groups:
            suffix = f" ({translator}翻譯)" if translator else ""
            lines.append(f"{count}集{programme}{suffix}")
    return "\n".join(lines)


def format_translation_section(
    counts: list[tuple[str, int]], ready_target: int
) -> str:
    lines = ["待翻譯的節目："]
    nonzero = [(programme, count) for programme, count in counts if count]
    if not nonzero:
        lines.append("無")
    for programme, count in counts:
        if count:
            lines.append(f"{count}集{programme}")
        if count < ready_target:
            lines.append(f"(我會再選{ready_target - count}集{programme})")
    return "\n".join(lines)


def build_report() -> str:
    ready_target, translators = load_config(CONFIG_PATH)
    translations: list[tuple[str, int]] = []
    edits: list[tuple[str, list[tuple[str | None, int]]]] = []
    missing_translator: list[str] = []
    for programme, project in PROGRAMMES:
        translation_count, _ = count_programme(project)
        translations.append((programme, translation_count))
        edits.append((programme, editing_counts(project / "translated", translators)))
        missing_translator.extend(
            files_without_translator(project / "translated", translators)
        )
    sections = [
        format_translation_section(translations, ready_target),
        format_editing_section(edits),
    ]
    if missing_translator:
        filenames = "、".join(sorted(missing_translator, key=str.casefold))
        sections.append(
            f"警告：以下待edit檔案沒有已設定的譯者：{filenames}。"
            "請在檔名加入譯者代碼，並在需要時更新 report_sources.toml 的 "
            "[report.translators]。"
        )
    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-copy", action="store_true", help="print without calling wl-copy")
    args = parser.parse_args()
    report = build_report()
    print(report)
    if not args.no_copy:
        try:
            subprocess.run(["wl-copy"], input=report, text=True, check=True)
        except FileNotFoundError:
            raise SystemExit("wl-copy is not installed; report was printed but not copied.")
        except subprocess.CalledProcessError as error:
            raise SystemExit(f"wl-copy failed with status {error.returncode}; report was printed but not copied.")
        print("Success: Report copied to clipboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
