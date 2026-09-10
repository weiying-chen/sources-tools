# Source document tools

The executable tools live in this repository, while programme data stays in the PM project. Run the commands from the programme folder you want to process.

```text
~/text/pm/
├── all-about-health/
│   ├── episodes.json
│   ├── episodes_raw.json
│   ├── subtitles/
│   └── output/
└── easy-fitness/
    ├── episodes.json
    ├── episodes_raw.json
    ├── subtitles/
    └── output/
```

## Fetch metadata

`fetch-sources` recognizes these two folder names and selects the correct URL and extraction rules automatically:

```bash
cd ~/text/pm/all-about-health
fetch-sources

cd ~/text/pm/easy-fitness
fetch-sources
```

Override the URL when fetching a specific All About Health page:

```bash
fetch-sources "https://daai.tv/program/P0016?p=2"
```

For a quicker Easy Fitness test, limit the newest videos:

```bash
fetch-sources --limit 10
```

The command writes `episodes.json` and `episodes_raw.json` in the current folder.

## Generate DOCX files

Put subtitle text files in `./subtitles`, then run from the programme folder:

```bash
gen-sources
```

Only JSON entries with a matching subtitle file generate a DOCX. Results are written to `./output`.

## Add generated sources to the master list

Put generated DOCX files in `./queued` (or leave them in `./output` when
`./queued` is empty), then run from the programme folder:

```bash
add-sources
```

The command finds the single master DOCX directly inside the current folder,
adds only titles that are not already present, and updates the master in place.
Use `add-sources --dry-run` to preview or `add-sources --copy` to write an
`_updated.docx` copy instead.

## Update English details

Put completed translated DOCX or DOC files in `./done`, then run:

```bash
update-sources
```

The command matches rows by their Chinese titles, adds the English title and
description, and updates the master in place. Use `update-sources --dry-run`
to preview or `update-sources --copy` to write an `_updated.docx` copy.

Both commands work with All About Health and Easy Fitness because the current
programme folder selects the master and its `queued`, `output`, or `done`
subfolder. Use `--master`/`--docx` only when the folder contains more than one
possible master DOCX.

## Report current workload

Run from the PM root so both programme folders are included:

```bash
cd ~/text/pm
report-sources
```

The command counts document files directly inside each programme's `queued/`
folder as waiting for translation and files directly inside `translated/` as
waiting for editing. Subfolders such as `translated/ok/` are not counted. It
warns when a programme has fewer than the configured number of translation
files ready, then copies the same report with `wl-copy`. The ready-task target
is configured in `report_sources.toml`. Use
`report-sources --no-copy` to print without changing the clipboard.

For files waiting for editing, the report also shows the translator when a
configured translator key appears as a separate filename token (for example,
`_Shawn.docx`). Translator keys and their report display names are configured
under `[report.translators]` in `report_sources.toml`. The master DOCX is not
used for this because it does not currently record the translator.

## Show the next unfinished sources

Run from either programme folder:

```bash
next-sources
```

The command uses the top episode in the programme's master DOCX as the durable
continuation point, finds it in `episodes.json`, and prints the next three newer
episodes from oldest to newest. Episodes already represented by documents
directly inside `queued/`, `translated/`, or `done/` are skipped. Isolated gaps
older than the master boundary are intentionally ignored. Use
`next-sources --limit N` to show a different number.
