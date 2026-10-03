"""Telegram OCR keyword scanner - entry point.

Examples:
  python main.py history  -c @somegroup -k "invoice,password" --limit 500
  python main.py realtime -c -1001234567890 -k "leak,dump"
  python main.py                      # interactive mode
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from telethon import TelegramClient

from src.config import DEFAULT_LANGS, EXPORT_DIR, SESSION_PATH, ensure_dirs, load_dotenv
from src.exporter import Exporter
from src.logger import setup_logging
from src.ocr import TesseractError, configure_tesseract, resolve_languages
from src.scanner import ScanSettings, Scanner, parse_target

log = logging.getLogger("telegram_ocr")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--chat", action="append", default=[],
                        help="Chat to scan: @username, t.me link, or numeric ID. Repeatable. "
                             "Omit to scan all groups/channels.")
    common.add_argument("-k", "--keywords", default="", help="Comma-separated keywords")
    common.add_argument("--keywords-file", type=Path, help="File with one keyword per line")
    common.add_argument("--threshold", type=float, default=85,
                        help="Fuzzy match threshold 0-100 (default 85)")
    common.add_argument("--langs", default=DEFAULT_LANGS,
                        help=f"Tesseract languages joined by '+' (default {DEFAULT_LANGS}). "
                             "Fewer languages = faster and more accurate.")
    common.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    common.add_argument("--no-save-images", action="store_true",
                        help="Do not keep images of matched messages")
    common.add_argument("--concurrency", type=int, default=2, help="Parallel OCR jobs")
    common.add_argument("--include-private", action="store_true",
                        help="Also scan private (1:1) chats when no --chat is given")
    common.add_argument("--tesseract-cmd", help="Path to the tesseract executable")
    common.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(description="Scan Telegram images with OCR for keywords")
    sub = parser.add_subparsers(dest="mode", required=True)
    hist = sub.add_parser("history", parents=[common], help="Scan past messages")
    hist.add_argument("--limit", type=int, default=200,
                      help="Max photos per chat (0 = unlimited, default 200)")
    sub.add_parser("realtime", parents=[common], help="Listen for new messages")
    return parser


def interactive_argv() -> list[str]:
    mode = ""
    while mode not in ("h", "r"):
        mode = input("Mode - history (h) or realtime (r): ").strip().lower()
    chat = input("Group ID / link / @username (empty = all groups): ").strip()
    keywords = input("Keywords (comma-separated): ").strip()
    argv = ["history" if mode == "h" else "realtime", "-k", keywords]
    if chat:
        argv += ["-c", chat]
    return argv


def collect_keywords(args: argparse.Namespace) -> list[str]:
    words = [w.strip() for w in args.keywords.split(",")]
    if args.keywords_file:
        words += [ln.strip() for ln in args.keywords_file.read_text(encoding="utf-8").splitlines()]
    seen: set[str] = set()
    out = []
    for w in words:
        if w and w.casefold() not in seen:
            seen.add(w.casefold())
            out.append(w)
    return out


def get_credentials() -> tuple[int, str]:
    api_id = os.getenv("TELEGRAM_API_ID") or input("Telegram API ID: ").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH") or input("Telegram API hash: ").strip()
    if not api_id.isdigit() or not api_hash:
        raise SystemExit("Invalid Telegram API credentials (see https://my.telegram.org).")
    return int(api_id), api_hash


async def run(args: argparse.Namespace) -> None:
    keywords = collect_keywords(args)
    if not keywords:
        raise SystemExit("No keywords given (-k or --keywords-file).")

    configure_tesseract(args.tesseract_cmd)
    langs = resolve_languages(args.langs)
    log.info("OCR languages: %s | keywords: %d | threshold: %s", langs, len(keywords), args.threshold)

    api_id, api_hash = get_credentials()
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await client.start(phone=os.getenv("TELEGRAM_PHONE") or None)

    try:
        entities = []
        for ref in args.chat:
            try:
                entities.append(await client.get_entity(parse_target(ref)))
            except Exception as exc:
                raise SystemExit(f"Could not resolve chat '{ref}': {exc}")

        settings = ScanSettings(
            keywords=keywords, langs=langs, threshold=args.threshold,
            save_images=not args.no_save_images, concurrency=args.concurrency,
            include_private=args.include_private,
        )
        exporter = Exporter(EXPORT_DIR, args.format)
        scanner = Scanner(client, settings, exporter)
        log.info("Results -> %s", exporter.path)

        if args.mode == "history":
            await scanner.scan_history(entities, args.limit or None)
        else:
            scanner.attach_realtime(entities)
            log.info("Listening for new messages... (Ctrl+C to stop)")
            await client.run_until_disconnected()
    finally:
        await client.disconnect()


def main() -> None:
    load_dotenv()
    ensure_dirs()
    args = build_parser().parse_args(interactive_argv() if len(sys.argv) == 1 else None)
    setup_logging(args.verbose)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        log.info("Stopped by user.")
    except TesseractError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
