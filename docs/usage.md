"""
# Wall_Bug Usage

Wall_Bug is a CLI tool for capturing spoken ideas and converting them into structured notes.

## Run the CLI

From the repository root:

```bash
PYTHONPATH=src python -m wallbug.cli help
```

General syntax:

```bash
PYTHONPATH=src python -m wallbug.cli [--verbose] COMMAND [ARGS]
```

## Global Option

- `-v`, `--verbose`: Increase output verbosity (can be repeated, e.g. `-vv`).

## Commands

### `status`

Show current Wall_Bug status.

```bash
PYTHONPATH=src python -m wallbug.cli status
```

### `daemon`

Run Wall_Bug in daemon mode.

Options:

- `--foreground`: Run in foreground instead of background mode.

```bash
PYTHONPATH=src python -m wallbug.cli daemon --foreground
```

### `record`

Record an audio note.

Options:

- `--duration SECONDS`: Optional recording duration.

```bash
PYTHONPATH=src python -m wallbug.cli record --duration 30
```

### `transcribe`

Transcribe recorded audio.

Arguments:

- `source` (optional): Path to audio input file.

```bash
PYTHONPATH=src python -m wallbug.cli transcribe
PYTHONPATH=src python -m wallbug.cli transcribe /path/to/audio.wav
```

### `search`

Search across saved notes.

Arguments:

- `query`: Search text.

```bash
PYTHONPATH=src python -m wallbug.cli search "standup ideas"
```

### `summarize-day`

Generate a daily summary from notes.

Options:

- `--date YYYY-MM-DD`: Date to summarize (defaults to today).

```bash
PYTHONPATH=src python -m wallbug.cli summarize-day --date 2026-03-05
```

### `help`

Show help for all commands or one command.

```bash
PYTHONPATH=src python -m wallbug.cli help
PYTHONPATH=src python -m wallbug.cli help record
```

## Current Implementation Status

The command interface is implemented, but command handlers currently print:

`Command '<name>' is not implemented yet.`

This means argument parsing and help output work now, while command internals are placeholders.

## Configuration

Wall_Bug loads config from defaults, then optional JSON file, then environment overrides.

### Load behavior

- `load_config()` uses built-in defaults.
- `load_config(path)` loads JSON from `path` if it exists.
- Environment variables with prefix `WALLBUG_` override both defaults and file values.

### Example config file (`config.json`)

```json
{
  "debug": false,
  "paths": {
    "base_dir": "~/.wallbug",
    "data_dir": "~/.wallbug/data",
    "audio_dir": "~/.wallbug/data/audio",
    "transcripts_dir": "~/.wallbug/data/transcripts",
    "notes_dir": "~/.wallbug/data/notes",
    "summaries_dir": "~/.wallbug/data/summaries",
    "logs_dir": "~/.wallbug/data/logs",
    "archive_dir": "~/.wallbug/data/archive"
  },
  "recorder": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "silence_timeout_seconds": 1.25,
    "max_record_seconds": 300,
    "output_format": "wav"
  },
  "transcription": {
    "model": "base",
    "language": "en",
    "device": "cpu",
    "beam_size": 5
  },
  "llm": {
    "backend": "none",
    "model": "",
    "temperature": 0.2,
    "max_tokens": 512
  },
  "logging": {
    "level": "INFO",
    "fmt": "%(asctime)s %(levelname)s %(name)s: %(message)s"
  },
  "tools": {
    "ffmpeg_path": "ffmpeg",
    "whisper_cpp_path": "whisper-cli"
  }
}
```

### Environment variable examples

```bash
export WALLBUG_DEBUG=true
export WALLBUG_DATA_DIR="$HOME/.wallbug/data"
export WALLBUG_SAMPLE_RATE=16000
export WALLBUG_TRANSCRIBE_MODEL=base
export WALLBUG_LOG_LEVEL=INFO
export WALLBUG_FFMPEG_PATH=ffmpeg
```
"""
