# Obsidian Auto Classifier (OAC)

## Purpose

This project provides a lightweight tool to automatically classify and move Markdown notes from an Obsidian vault folder `00_Inbox` into one of five IPARAG folders:
- `10_Projects`
- `20_Areas`
- `30_Resources`
- `40_Archives`
- `50_Galaxy`

Classification is performed by the Google Gemini generative AI model via the `google-genai` Python SDK. The script reads each `.md` file, generates a classified folder name, then moves the file.

## How it works (`main.py`)

1. **Initialization**
   - Reads `VAULT_PATH` (default `/app/vault`) and `SOURCE_DIR = VAULT_PATH/00_Inbox`
   - Verifies source folder exists
   - Checks `GEMINI_API_KEY` environment variable
   - Sets up logging to `app.log` with rotating file handler (1MB max, 5 backup files)
   - Loads optional `GEMINI.md` from vault root for custom classification instructions

2. **File Discovery & Processing**
   - Counts total markdown files in `00_Inbox`
   - For each file:
     - Creates LATCH frontmatter if missing
     - Calls Gemini `gemini-2.5-flash` (or custom model) with note content and folder criteria
     - Incorporates custom instructions from `GEMINI.md` if available
     - Normalizes and validates the returned folder name

3. **Classification & Movement**
   - If classification succeeds: moves file to appropriate folder with updated frontmatter
   - If classification fails: creates frontmatter with default `00_Inbox` category and keeps file in inbox for manual review
   - Creates target folders in vault if missing

4. **Progress & Logging**
   - Displays file progress: `[X/Y] Processing: filename`
   - Logs all actions to console and rotating `app.log` file
   - Summary report: total processed, moved, and skipped counts

## Features

### Logging
- **Console Output**: Real-time progress messages with `[TIMESTAMP] LEVEL` format
- **File Logging**: Rotating log file handler saves to `app.log`
  - Max file size: 1MB
  - Backup files: 5 (automatically rotates old logs)
  - Auto-archives old logs as `app.log.1`, `app.log.2`, etc.
- **Log Levels**: DEBUG (details), INFO (events), WARNING (issues), ERROR (failures)

### Custom Classification (`GEMINI.md`)
- Create a `GEMINI.md` file at vault root (`VAULT_PATH/GEMINI.md`)
- Include custom classification rules and instructions for Gemini
- Example:
  ```markdown
  # Custom Classification Rules
  
  - Health/fitness notes → 20_Areas
  - Meeting notes → 10_Projects  
  - Code snippets → 30_Resources
  - Random thoughts → 50_Galaxy
  ```
- If `GEMINI.md` exists, its content is passed to Gemini for every classification decision
- If `GEMINI.md` does not exist, uses default IPARAG folder definitions

### Frontmatter Handling
- Automatically creates LATCH frontmatter if missing:
  ```yaml
  ---
  tags: [tag/here]
  created: YYYY-MM-DD
  type: Projects
  location: 10_Projects
  up: 
  ---
  ```
  - `tags`: User-defined tags (initialized with placeholder)
  - `created`: Date note was created (YYYY-MM-DD format)
  - `type`: Extracted from folder name (Projects, Areas, Resources, Archives, Galaxy, or Unclassified)
  - `location`: Full folder path (e.g., 20_Areas, 30_Resources)
  - `up`: Parent note reference (empty by default, for user to fill)
- Updates frontmatter with target folder when file is classified
- For invalid classifications: creates frontmatter with `00_Inbox` as fallback category

## Requirements

- Python 3.13+
- `google-genai` Python library
- `GEMINI_API_KEY` set in environment
- `GEMINI_MODEL` (optional, defaults to `gemini-2.5-flash`)

## Docker usage

### Build image

```sh
docker build -t oac:latest .
```

### Run container (default 24h loop)

```sh
docker run --rm \
  -e GEMINI_API_KEY="your_api_key_here" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  -e LOOP_HOUR=24 \
  -v /path/to/local/vault:/app/vault \
  -v /path/to/local/logs:/app/logs \
  oac:latest
```

**Volume mounts:**
- `/path/to/local/vault:/app/vault` — Your Obsidian vault directory
- `/path/to/local/logs:/app/logs` — Directory to store rotating log files (`app.log`, `app.log.1`, etc.)

**Environment variables:**
- `GEMINI_API_KEY` — Your Google Gemini API key (required)
- `GEMINI_MODEL` — Model to use (defaults to `gemini-2.5-flash`)
- `VAULT_PATH` — Path inside container to vault (defaults to `/app/vault`, override only if needed)
- `LOOP_HOUR` — Hours between processing cycles (defaults to `24`)

### Override interval (optional)

Set `LOOP_HOUR` to desired hourly interval, e.g. one hour:

```sh
docker run --rm \
  -e GEMINI_API_KEY="your_api_key_here" \
  -e LOOP_HOUR=1 \
  -v /path/to/local/vault:/app/vault \
  -v /path/to/local/logs:/app/logs \
  oac:latest
```

## Notes

- **Classification Success**: Files are moved to appropriate folder with updated frontmatter
- **Classification Failure**: Files receive default `00_Inbox` frontmatter and remain in inbox for manual review (not deleted or moved)
- **Frontmatter**: All notes receive simplified LATCH-format metadata (tags, created, type, location, up)
- **Log Files**: Stored in `/app/logs` (or mounted directory) with automatic rotation at 1MB per file (5 backups kept)
- **Custom Instructions**: Provide `GEMINI.md` at vault root to override default IPARAG classification behavior
- **Volume Mounts**: Always mount both vault directory and logs directory in Docker to persist data and logs locally
