#!/home/weiying/python/word/.venv/bin/python
"""Report actionable PM work from the programme workflow folders."""

from __future__ import annotations

import argparse
import subprocess
import tomllib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path.cwd()
CONFIG_PATH = SCRIPT_DIR / "report_sources.toml"
PROGRAMMES = (
    ("大愛醫生館", ROOT / "all-about-health"),
    ("大愛真健康", ROOT / "easy-fitness"),
)
DOCUMENT_SUFFIXES = {".doc", ".docx"}


def load_config(path: Path) -> int:
    with path.open("rb") as config_file:
        data = tomllib.load(config_file)
    ready_target = int(data.get("report", {}).get("translation_ready_target", 3))
    if ready_target < 1:
        raise SystemExit("translation_ready_target must be at least 1")
    return ready_target


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


def build_report() -> str:
    ready_target = load_config(CONFIG_PATH)
    translations: list[tuple[str, int]] = []
    edits: list[tuple[str, int]] = []
    for programme, project in PROGRAMMES:
        translation_count, editing_count = count_programme(project)
        translations.append((programme, translation_count))
        edits.append((programme, editing_count))
    sections = [
        format_section("待翻譯的節目", translations),
        format_section("待edit的節目", edits),
    ]
    low_queues = [(programme, count) for programme, count in translations if count < ready_target]
    if low_queues:
        warning_lines = ["提醒："]
        warning_lines.extend(
            f"{programme}待翻譯節目不足{ready_target}集，目前{count}集，請再新增{ready_target - count}集。"
            for programme, count in low_queues
        )
        sections.append("\n".join(warning_lines))
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
