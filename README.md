# band-dropbox-api-client

Terminal client for browsing a band's Dropbox library, selecting titles and instruments, and exporting combined PDF packets.

## Overview

The app is a Textual-based TUI that connects to Dropbox, loads a "library" list of titles, loads available instruments/voices, and lets you build a selection set. When you press Start, it downloads the matching PDFs for each instrument, then exports combined A4 packets in either A5-landscape or A6-portrait layouts.

## Requirements

- Python 3.14+ (see `.python-version` and `pyproject.toml`).
- Dropbox API access token with access to your band archive.

## Install

Using `uv`:

```bash
uv sync
```

## Run

```bash
uv run python -m src.app
```

### Run via launcher script

You can use the included `run.sh` as a portable launcher and optionally symlink it for a global command:

```bash
./run.sh
```

Example symlink (pick any command name you like):

```bash
ln -s /path/to/band-dropbox-api-client/run.sh /usr/local/bin/band
```

Then run from anywhere:

```bash
band
```

## Configuration

The app reads `src/resources/application.conf` on startup.

Key settings:

- `[app].title`: Top title shown in the splash screen.
- `[app].library_path`: Dropbox path used to build the list of titles.
- `[app].library_suffix`: Optional suffix to strip from titles (example: `_altosax1.pdf`).
- `[app].instruments_path`: Dropbox root for instrument folders.
- `[app].instruments_suffix`: Optional suffix stripped from instrument folder names.
- `[app].instruments_exclude_substrings`: Comma-separated substrings to filter instrument entries.
- `[app].export_path`: Local folder for export PDFs (default: `exports`).
- `[app].export_debug`: Set to `true` to write debug reports about page sizing/rotation.
- `[app].export_a6_instruments`: Comma-separated list of instruments exported in A6.
- `[dropbox].access_token`: Dropbox API access token (keep this private).

## Expected Dropbox Organization

The app assumes two things:

1) The "library" list is derived from one reference folder (usually a single instrument voice). Each entry in that folder becomes a title in the TUI.
2) The "instruments" list is derived from a separate root where each instrument folder contains PDFs named to match the titles.

Example (based on defaults in `src/resources/application.conf`):

```
/Band Folder - Songs
├── Alto Saxophone - Songs
│   ├── Alto Saxophone 1 - Songs
│   │   ├── First title_altosax1.pdf
│   │   ├── Title 2_altosax1.pdf
│   │   └── ...
│   └── Alto Saxophone 2 - Songs
│       ├── First title_altosax2.pdf
│       └── ...
├── Trombone - Songs
│   ├── First title_trombone.pdf
│   └── ...
└── Trumpet - Songs
    ├── Trumpet 1 - Songs
    │   ├── First title_trumpet1.pdf
    │   └── ...
    └── Trumpet 2 - Songs
        ├── First title_trumpet2.pdf
        └── ...
```

How this maps to config:

- `library_path` points to a single folder, e.g. `/Band Folder - Songs/Alto Saxophone - Songs/Alto Saxophone 1 - Songs`.
- `library_suffix` strips the voice-specific suffix (e.g. `_altosax1.pdf`) so the title matches other instruments.
- `instruments_path` points to the root folder (e.g. `/Band Folder - Songs`).
- `instruments_suffix` removes the repeated suffix (e.g. `- Songs`) so the list is cleaner.

Instruments can be either:

- A single folder containing PDFs, or
- A folder with voice subfolders. The app displays voices as `Instrument / Voice`.

## TUI Usage

The screen has three areas:

- Library (left): list of titles from `library_path`
- Details (upper right): selected titles + instrument counts
- Instruments (lower right): instruments/voices from `instruments_path`

Key bindings:

- `space`: toggle selection in the focused list
- `s`: Start (download + export)
- `u`: Undo last selection/instrument change
- `c`: Clear all selections and counts
- `d`: Clear the library filter input
- `q`: Quit

Library filtering:

- Type in the filter box to narrow the title list.
- Press `d` to clear the filter and refocus input.

Instrument counts:

- Selecting an instrument increments its count.
- Counts represent the number of copies to include in the export.

## Download + Export Flow

When you press Start:

1) The app validates that at least one title and one instrument are selected.
2) PDFs are downloaded to a temporary local `download/` directory.
3) PDFs are merged into A4 sheets:
   - A5 landscape (2-up) for most instruments.
   - A6 portrait (4-up) for instruments listed in `export_a6_instruments`.
4) Exports are written to `export_path` as:
   - `export_YYYYMMDD.pdf` (A5 layout)
   - `export_A6_YYYYMMDD.pdf` (A6 layout)
5) The temporary `download/` directory is removed.

### Matching logic

Each selected title is matched against PDFs in each instrument folder:

- Exact match on filename (with or without `.pdf`).
- Otherwise the shortest filename that starts with the title.
- Otherwise the shortest filename that contains the title.

Missing PDFs are reported in the processing log.

## Troubleshooting

- "Cannot connect! The DBX access token is missing": set `[dropbox].access_token` in `src/resources/application.conf`.
- "Unable to list folder": check the configured Dropbox paths and API permissions.
- No export generated: ensure PDFs exist for each selected title and instrument.

## Development Notes

- Tests live under `tests/` and can be run with `uv run pytest`.

The application opens with a short loading screen and then reveals the two-panel layout that will host the Dropbox browser in future iterations.
