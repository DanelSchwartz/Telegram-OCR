# Telegram OCR Scanner

Scans images in Telegram groups and channels, runs OCR (Tesseract), and exports the messages whose image text
contains your keywords. Matching is tolerant to OCR errors and works with Hebrew.

## Installation
```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Install Tesseract and the language packs:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki (select Hebrew/Arabic/Russian during setup)
- Linux: `sudo apt install tesseract-ocr tesseract-ocr-heb tesseract-ocr-ara tesseract-ocr-rus`
- macOS: `brew install tesseract tesseract-lang`

Configuration: copy `.env.example` to `.env` and fill in `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`
(from https://my.telegram.org). On the first run Telethon asks for a verification code.
The session file is stored in `data/` (never commit it to GitHub).

## Usage
```bash
# History: scan up to the last 500 photos of a group
python main.py history -c @somegroup -k "invoice,password" --limit 500

# Real-time, multiple groups
python main.py realtime -c @group1 -c -1001234567890 -k "leak,dump"

# All groups/channels, keywords from a file, CSV output
python main.py history --keywords-file words.txt --format csv --limit 0

# Interactive mode (like the original version)
python main.py
```
Main options: `--threshold 85` (match sensitivity), `--langs eng+heb` (fewer languages = faster and more accurate),
`--concurrency 2`, `--no-save-images`, `--include-private`, `--tesseract-cmd`.

Output: `data/exports/export.jsonl` (or `.csv`), matched images in `data/matched_images/`, logs in `data/logs/`.
Re-running does not export messages that were already exported.

## What was fixed compared to the original version
- `process_image_for_ocr` returned a list, but the caller treated it as a single path. Image variants are now created in memory (no more `_filterN` files).
- `iter_messages` is an async iterator, but the loop used a plain `for`. Fixed to `async for`, including direct filtering for photos.
- Real-time mode is now actually implemented (`events.NewMessage`). Previously it scanned the entire history.
- `found_match` / `file_path` could be undefined on failure paths, and some async calls were missing `await`. Fixed.
- The Tesseract check ran at import time and prompted with `input()`. It now checks PATH, `TESSERACT_CMD` and common Windows paths, and validates the installed language packs.
- `ZeroDivisionError` on an empty keyword. Added keyword cleanup, `rapidfuzz` matching, Hebrew normalization (niqqud, punctuation), and whole-word matching for short keywords.
- OCR stops at the first variant that matches (much faster) and runs in `asyncio.to_thread` with limited concurrency.
- JSONL/CSV export instead of rewriting a whole JSON file on every message, with persistent de-duplication.
- Message links are built correctly (public username or `t.me/c/<id>`).
- Missing/conflicting packages in requirements (`pytesseract`, `rapidfuzz`; removed the opencv conflict). OpenCV is optional.

## Tests
```bash
pip install -r requirements-dev.txt && python -m pytest
```
