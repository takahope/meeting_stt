import re
from collections.abc import Sequence

from opencc import OpenCC

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_ENG_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
_TO_TRADITIONAL = OpenCC("s2twp")


def to_traditional(text: str) -> str:
    return _TO_TRADITIONAL.convert(text)


def compute_text_units(text: str) -> float:
    cjk_count = len(_CJK_RE.findall(text))
    eng_count = len(_ENG_WORD_RE.findall(_CJK_RE.sub(" ", text)))
    return cjk_count * 1.0 + eng_count * 1.5


def _is_ascii_alnum(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()


def _needs_space(left: str, right: str) -> bool:
    a, b = left[-1], right[0]
    a_eng, b_eng = _is_ascii_alnum(a), _is_ascii_alnum(b)
    a_cjk, b_cjk = bool(_CJK_RE.match(a)), bool(_CJK_RE.match(b))
    return (a_eng and b_eng) or (a_eng and b_cjk) or (a_cjk and b_eng)


def join_word_tokens(tokens: Sequence[str]) -> str:
    out = ""
    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if out and _needs_space(out, token):
            out += " "
        out += token
    return out


def split_two_lines(tokens: Sequence[str], max_line_units: float = 14.0) -> list[str]:
    full = join_word_tokens(tokens)
    if compute_text_units(full) <= max_line_units or len(tokens) < 2:
        return [full]
    best_i, best_cost = None, float("inf")
    for i in range(1, len(tokens)):
        if compute_text_units(tokens[i]) == 0:
            continue  # 第二行不以標點開頭
        cost = max(
            compute_text_units(join_word_tokens(tokens[:i])),
            compute_text_units(join_word_tokens(tokens[i:])),
        )
        if cost < best_cost:
            best_i, best_cost = i, cost
    if best_i is None:
        return [full]
    return [join_word_tokens(tokens[:best_i]), join_word_tokens(tokens[best_i:])]
