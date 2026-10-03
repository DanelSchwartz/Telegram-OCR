from src.matcher import find_matches, normalize


def test_exact_and_fuzzy():
    assert find_matches("Please pay the invoice today", ["invoice"])[0].score == 100
    hits = find_matches("Please pay the invoce today", ["invoice"])
    assert hits and hits[0].score >= 85


def test_no_match():
    assert find_matches("hello world", ["invoice", "password"]) == []


def test_short_keyword_requires_whole_word():
    assert find_matches("this is a bank statement", ["ban"]) == []
    assert find_matches("ban list", ["ban"])


def test_empty_keywords_and_text_are_safe():
    assert find_matches("some text", ["", "  "]) == []
    assert find_matches("", ["abc"]) == []


def test_hebrew_with_niqqud_and_punctuation():
    assert normalize("שָׁלוֹם, עולם!") == "שלום עולם"
    assert find_matches("הסיסמה שלי היא 1234", ["סיסמה"])


def test_case_insensitive():
    assert find_matches("PASSWORD: hunter2", ["password"])
