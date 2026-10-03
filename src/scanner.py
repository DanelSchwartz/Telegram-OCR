"""Telegram scanning: historical + real-time, OCR, keyword match, export."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field

from telethon import TelegramClient, events
from telethon.tl.types import Channel, InputMessagesFilterPhotos

from src.config import IMAGES_DIR
from src.exporter import Exporter
from src.matcher import find_matches
from src.ocr import ocr_texts

log = logging.getLogger(__name__)

_TME_PRIVATE = re.compile(r"^(?:https?://)?(?:www\.)?t\.me/c/(\d+)(?:/\d+)*/?$")
_BATCH = 50


@dataclass
class ScanSettings:
    keywords: list[str]
    langs: str
    threshold: float = 85
    save_images: bool = True
    concurrency: int = 2
    include_private: bool = False
    stats: dict = field(default_factory=lambda: {"images": 0, "matches": 0})


def parse_target(raw: str) -> int | str:
    """Turn a user-supplied chat reference into something Telethon's get_entity accepts.

    Accepts @username, username, https://t.me/username[/123], t.me/c/<id>[/<msg>],
    and numeric IDs (channels/supergroups need the -100 prefix).
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty chat reference")
    m = _TME_PRIVATE.match(raw)
    if m:
        return int(f"-100{m.group(1)}")
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    raw = re.sub(r"^(?:https?://)?(?:www\.)?t\.me/", "", raw)
    if raw.startswith("+") or raw.startswith("joinchat/"):
        raise ValueError(
            "Invite links can't be resolved directly - join the chat first, "
            "then pass its @username or numeric ID."
        )
    return raw.split("/")[0].lstrip("@")


def message_link(chat, message_id: int) -> str | None:
    username = getattr(chat, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"
    if isinstance(chat, Channel):
        return f"https://t.me/c/{chat.id}/{message_id}"
    return None


def is_image_message(message) -> bool:
    if getattr(message, "photo", None):
        return True
    doc = getattr(message, "document", None)
    return bool(doc and (getattr(doc, "mime_type", "") or "").startswith("image/"))


class Scanner:
    def __init__(self, client: TelegramClient, settings: ScanSettings, exporter: Exporter) -> None:
        self.client = client
        self.settings = settings
        self.exporter = exporter
        self._sem = asyncio.Semaphore(max(1, settings.concurrency))
        self._processed: set[tuple[int, int]] = set()

    def _is_match(self, text: str) -> bool:
        return bool(find_matches(text, self.settings.keywords, self.settings.threshold))

    async def handle(self, message) -> bool:
        """Process one message. Returns True if it matched and was exported."""
        if not is_image_message(message):
            return False
        key = (message.chat_id, message.id)
        if key in self._processed or key in self.exporter.seen:
            return False
        self._processed.add(key)
        s = self.settings

        async with self._sem:
            try:
                data = await message.download_media(file=bytes)
                if not data:
                    log.warning("Empty download for message %s", message.id)
                    return False
                s.stats["images"] += 1
                texts = await asyncio.to_thread(ocr_texts, data, s.langs, self._is_match)
            except Exception:
                log.exception("Failed processing message %s in chat %s", message.id, message.chat_id)
                return False

        best_text, best_hits = "", []
        for text in texts:
            hits = find_matches(text, s.keywords, s.threshold)
            if hits and (not best_hits or hits[0].score > best_hits[0].score):
                best_text, best_hits = text, hits
        if not best_hits:
            return False

        chat = await message.get_chat()
        title = (
            getattr(chat, "title", None)
            or getattr(chat, "username", None)
            or getattr(chat, "first_name", None)
        )
        image_path = None
        if s.save_images:
            ext = (message.file.ext if message.file and message.file.ext else ".jpg")
            path = IMAGES_DIR / f"{abs(message.chat_id)}_{message.id}{ext}"
            await asyncio.to_thread(self._save, path, data)
            image_path = str(path)

        record = {
            "time": message.date.isoformat(),
            "chat_id": message.chat_id,
            "chat_title": title,
            "message_id": message.id,
            "sender_id": message.sender_id,
            "link": message_link(chat, message.id),
            "keywords": [h.keyword for h in best_hits],
            "score": best_hits[0].score,
            "text": best_text,
            "image_path": image_path,
        }
        await self.exporter.write(record)
        s.stats["matches"] += 1
        log.info(
            "MATCH chat=%s msg=%s keywords=%s score=%.1f",
            title, message.id, record["keywords"], record["score"],
        )
        return True

    @staticmethod
    def _save(path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def _default_targets(self):
        async for dialog in self.client.iter_dialogs():
            if dialog.is_user and not self.settings.include_private:
                continue
            yield dialog.entity

    async def scan_history(self, entities: list, limit: int | None) -> None:
        async def run(entity) -> None:
            tasks: list[asyncio.Task] = []
            name = getattr(entity, "title", None) or getattr(entity, "username", None) or entity
            log.info("Scanning history of %s (limit=%s)", name, limit or "all")
            async for msg in self.client.iter_messages(
                entity, limit=limit, filter=InputMessagesFilterPhotos
            ):
                tasks.append(asyncio.create_task(self.handle(msg)))
                if len(tasks) >= _BATCH:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks.clear()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        if entities:
            for entity in entities:
                await run(entity)
        else:
            async for entity in self._default_targets():
                await run(entity)
        log.info("History scan done: %(images)d images OCR'd, %(matches)d matches", self.settings.stats)

    def attach_realtime(self, entities: list) -> None:
        explicit = bool(entities)

        @self.client.on(events.NewMessage(chats=entities or None, incoming=True))
        async def _on_message(event):
            if not explicit and event.is_private and not self.settings.include_private:
                return
            await self.handle(event.message)
