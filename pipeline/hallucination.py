import re

from pipeline.text import to_traditional

# 比對前會先轉繁、去除空白與標點、轉小寫；發現新的幻覺短語時直接補在這裡。
HALLUCINATION_PHRASES: tuple[str, ...] = (
    "amaraorg",
    "點贊訂閱",
    "點讚訂閱",
    "明鏡與點點欄目",
    "字幕志願者",
    "優優獨播劇場",
)

_STRIP_RE = re.compile(r"[\W_]+")


def is_hallucination(text: str) -> bool:
    normalized = _STRIP_RE.sub("", to_traditional(text)).lower()
    return any(phrase in normalized for phrase in HALLUCINATION_PHRASES)
