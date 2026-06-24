#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOH'
Usage:
  gen-sources [episodes_json] [output_dir]

Generate source DOCX files from the current folder using:
  - episodes_json: argument or ./episodes.json
  - subtitles:     ./subtitles by default, falling back to ./sources
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

episodes_json="${1:-./episodes.json}"

OUTPUT_DIR="${2:-./output}"

if [[ ! -d "$SUBTITLES_DIR" ]]; then
  if [[ "$SUBTITLES_DIR" == "./subtitles" && -d ./sources ]]; then
    SUBTITLES_DIR="./sources"
  else
    echo "[error] subtitles directory not found: $SUBTITLES_DIR" >&2
    exit 1
  fi
fi

if [[ ! -f "$episodes_json" ]]; then
  echo "[error] episodes json not found: $episodes_json" >&2
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

mkdir -p "$OUTPUT_DIR"

"$PYTHON_BIN" "$SCRIPT_PATH" \
  --episodes-json "$episodes_json" \
  --template "$TEMPLATE_PATH" \
  --sources-dir "$SUBTITLES_DIR" \
  --output-dir "$OUTPUT_DIR"

created=0
while IFS= read -r f; do
  echo "[created] $(basename "$f")"
  created=$((created + 1))
done < <(find "$OUTPUT_DIR" -maxdepth 1 -type f -name '*.docx' | sort)

if (( created == 0 )); then
  echo "[warn] no .docx files found in: $OUTPUT_DIR"
fi
