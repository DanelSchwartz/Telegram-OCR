import asyncio
import json

from src.exporter import Exporter


def rec(mid, **kw):
    base = {"time": "t", "chat_id": -100, "chat_title": "x", "message_id": mid, "sender_id": 1,
            "link": None, "keywords": ["a", "b"], "score": 99.0, "text": "שלום", "image_path": None}
    base.update(kw)
    return base


def test_jsonl_roundtrip_and_dedup(tmp_path):
    ex = Exporter(tmp_path, "jsonl")
    asyncio.run(ex.write(rec(1)))
    asyncio.run(ex.write(rec(2)))
    lines = ex.path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["message_id"] for x in lines] == [1, 2]
    assert "שלום" in lines[0]  # ensure_ascii=False

    ex2 = Exporter(tmp_path, "jsonl")  # reload persisted state
    assert (-100, 1) in ex2.seen and (-100, 2) in ex2.seen


def test_csv_header_once_and_dedup(tmp_path):
    ex = Exporter(tmp_path, "csv")
    asyncio.run(ex.write(rec(1)))
    asyncio.run(ex.write(rec(2)))
    text = ex.path.read_text(encoding="utf-8-sig")
    assert text.count("message_id") == 1
    assert "a|b" in text
    assert (-100, 2) in Exporter(tmp_path, "csv").seen
