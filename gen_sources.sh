#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOH'
Usage:
  gen-sources [episodes_file] [output_dir]

Generate source DOCX files from the current folder using:
  - episodes_file: argument or ./episodes.json
  - subtitles:     ./subtitles by default
  - output_dir:    second argument or ./output

Environment overrides:
  GENERATE_SOURCES_SCRIPT   default: $HOME/python/word/generate_sources.py
  GENERATE_SOURCES_PYTHON   default: $HOME/python/word/.venv/bin/python
  GENERATE_SOURCES_TEMPLATE default: $HOME/python/word/templates/sources_template.docx
  GENERATE_SOURCES_SUBTITLES_DIR default: ./subtitles
EOH
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_PATH="${GENERATE_SOURCES_SCRIPT:-$HOME/python/word/generate_sources.py}"
PYTHON_BIN="${GENERATE_SOURCES_PYTHON:-$HOME/python/word/.venv/bin/python}"
TEMPLATE_PATH="${GENERATE_SOURCES_TEMPLATE:-$HOME/python/word/templates/sources_template.docx}"
SUBTITLES_DIR="${GENERATE_SOURCES_SUBTITLES_DIR:-./subtitles}"
EPISODES_FILE_OVERRIDE="${1:-}"
OUTPUT_DIR_OVERRIDE="${2:-}"

if [[ ! -d "$SUBTITLES_DIR" ]]; then
  echo "[error] subtitles directory not found: $SUBTITLES_DIR" >&2
  exit 1
fi

episodes_file="${EPISODES_FILE_OVERRIDE:-./episodes.json}"
if [[ ! -f "$episodes_file" ]]; then
  echo "[error] episodes file not found: $episodes_file" >&2
  exit 1
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "[error] generate_sources script not found: $SCRIPT_PATH" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[error] python binary not executable: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE_PATH" ]]; then
  echo "[error] template not found: $TEMPLATE_PATH" >&2
  exit 1
fi

output_dir="${OUTPUT_DIR_OVERRIDE:-./output}"
mkdir -p "$output_dir"

args=(--template "$TEMPLATE_PATH")

if [[ -n "$EPISODES_FILE_OVERRIDE" ]]; then
  args+=(--episodes-file "$EPISODES_FILE_OVERRIDE")
fi

if [[ "$SUBTITLES_DIR" != "./subtitles" ]]; then
  args+=(--subtitles-dir "$SUBTITLES_DIR")
fi

if [[ -n "$OUTPUT_DIR_OVERRIDE" ]]; then
  args+=(--output-dir "$OUTPUT_DIR_OVERRIDE")
fi

"$PYTHON_BIN" "$SCRIPT_PATH" "${args[@]}"

created=0
while IFS= read -r f; do
  echo "[created] $(basename "$f")"
  created=$((created + 1))
done < <(find "$output_dir" -maxdepth 1 -type f -name '*.docx' | sort)

if (( created == 0 )); then
  echo "[warn] no .docx files found in: $output_dir"
fi
