from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WordToken:
    word: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True, slots=True)
class AlignedWord:
    word: str
    start: float
    end: float
    speaker: str


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    speaker: str
    tokens: tuple[str, ...]


def format_srt_timestamp(seconds: float) -> str:
    total_ms = round(max(0.0, seconds) * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
