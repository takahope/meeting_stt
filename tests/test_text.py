from pipeline.text import compute_text_units, join_word_tokens, split_two_lines, to_traditional


def test_join_word_tokens_spacing_rules():
    assert join_word_tokens(["目前", " OAuth", "模組", "，", "OK", "!"]) == "目前 OAuth 模組，OK!"
    assert join_word_tokens(["第一句", "。", "第二句", "。"]) == "第一句。第二句。"
    assert join_word_tokens([" Hello", " world", "  "]) == "Hello world"


def test_compute_text_units_cjk_english_punctuation():
    assert compute_text_units("目前 OAuth 模組") == 5.5
    assert compute_text_units("目前 OAuth 模組，OK!") == 7.0
    assert compute_text_units("，。!?") == 0.0


def test_split_two_lines_keeps_short_text_on_one_line():
    tokens = ["字數"] * 7  # 14 units
    assert split_two_lines(tokens) == ["字數" * 7]


def test_split_two_lines_balances_and_never_starts_with_punctuation():
    assert split_two_lines(["字數"] * 10) == ["字數" * 5, "字數" * 5]
    tokens = ["一二三四", "五六七八", "，", "甲乙丙丁", "戊己庚辛"]  # 16 units
    assert split_two_lines(tokens) == ["一二三四五六七八，", "甲乙丙丁戊己庚辛"]


def test_to_traditional_converts_simplified():
    assert to_traditional("我们") == "我們"
    assert to_traditional("这个") == "這個"
    assert to_traditional(" OAuth") == " OAuth"
