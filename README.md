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
