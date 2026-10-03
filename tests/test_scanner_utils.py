from types import SimpleNamespace

import pytest

from src.scanner import is_image_message, message_link, parse_target


def test_parse_target_variants():
    assert parse_target("@mygroup") == "mygroup"
    assert parse_target("https://t.me/mygroup") == "mygroup"
    assert parse_target("t.me/mygroup/123") == "mygroup"
    assert parse_target("-1001234567890") == -1001234567890
    assert parse_target("https://t.me/c/1234567890/55") == -1001234567890


def test_parse_target_rejects_invite_and_empty():
    with pytest.raises(ValueError):
        parse_target("https://t.me/+AbCdEf")
    with pytest.raises(ValueError):
        parse_target("  ")


def test_message_link_public():
    chat = SimpleNamespace(username="pub")
    assert message_link(chat, 7) == "https://t.me/pub/7"
    assert message_link(SimpleNamespace(username=None), 7) is None


def test_is_image_message():
    assert is_image_message(SimpleNamespace(photo=object(), document=None))
    assert is_image_message(SimpleNamespace(photo=None, document=SimpleNamespace(mime_type="image/png")))
    assert not is_image_message(SimpleNamespace(photo=None, document=SimpleNamespace(mime_type="video/mp4")))
    assert not is_image_message(SimpleNamespace(photo=None, document=None))
