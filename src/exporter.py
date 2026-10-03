"""Append-only export (JSONL or CSV) with persistent de-duplication."""
from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

FIELDS = [
    "time", "chat_id", "chat_title", "message_id", "sender_id",
    "link", "keywords", "score", "text", "image_path",
]


class Exporter:
    def __init__(self, directory: Path, fmt: str = "jsonl") -> None:
        if fmt not in ("jsonl", "csv"):
            raise ValueError(f"Unsupported export format: {fmt}")
        self.fmt = fmt
        self.path = Path(directory) / f"export.{fmt}"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self.seen: set[tuple[int, int]] = set()
        self._load_seen()

    def _load_seen(self) -> None:
        if not self.path.is_file():
            return
        try:
            with open(self.path, encoding="utf-8-sig", newline="") as fh:
                if self.fmt == "jsonl":
                    for line in fh:
                        try:
                            rec = json.loads(line)
                            self.seen.add((int(rec["chat_id"]), int(rec["message_id"])))
                        except (ValueError, KeyError, TypeError):
                            continue
                else:
                    for row in csv.DictReader(fh):
                        try:
                            self.seen.add((int(row["chat_id"]), int(row["message_id"])))
                        except (ValueError, KeyError, TypeError):
                            continue
        except OSError as exc:
            log.error("Could not read existing export %s: %s", self.path, exc)

    def _write_sync(self, record: dict) -> None:
        if self.fmt == "jsonl":
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            return
        row = {k: record.get(k) for k in FIELDS}
        row["keywords"] = "|".join(record.get("keywords", []))
        new_file = not self.path.exists() or self.path.stat().st_size == 0
        with open(self.path, "a", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow(row)

    async def write(self, record: dict) -> None:
        async with self._lock:
            await asyncio.to_thread(self._write_sync, record)
            self.seen.add((int(record["chat_id"]), int(record["message_id"])))
