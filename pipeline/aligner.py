from pipeline.models import AlignedWord, SpeakerTurn, SubtitleCue, WordToken
from pipeline.text import compute_text_units, join_word_tokens

DEFAULT_SPEAKER_LABEL = "SPEAKER_00"


def assign_speakers(words: list[WordToken], turns: list[SpeakerTurn]) -> list[AlignedWord]:
    ordered = sorted(turns, key=lambda t: t.start)
    return [
        AlignedWord(word=w.word, start=w.start, end=w.end, speaker=_pick_speaker(w, ordered))
        for w in words
    ]


def _pick_speaker(word: WordToken, turns: list[SpeakerTurn]) -> str:
    if not turns:
        return DEFAULT_SPEAKER_LABEL
    best: SpeakerTurn | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = max(0.0, min(word.end, turn.end) - max(word.start, turn.start))
        if overlap > best_overlap:  # 嚴格大於：平手保留較早的區間
            best, best_overlap = turn, overlap
    if best is not None:
        return best.speaker
    mid = (word.start + word.end) / 2.0
    nearest = min(  # min 回傳第一個最小值：平手取較早的區間
        turns,
        key=lambda t: 0.0 if t.start <= mid <= t.end else min(abs(mid - t.start), abs(mid - t.end)),
    )
    return nearest.speaker


def chunk_subtitles(
    words: list[AlignedWord],
    max_units: float = 28.0,
    max_duration: float = 6.0,
    max_gap: float = 1.2,
    min_display: float = 0.8,
) -> list[SubtitleCue]:
    groups: list[list[AlignedWord]] = []
    current: list[AlignedWord] = []
    for word in words:
        if not word.word.strip():
            continue
        if current:
            candidate = join_word_tokens([w.word for w in current] + [word.word])
            if (
                word.speaker != current[0].speaker
                or word.start - current[-1].end > max_gap
                or compute_text_units(candidate) > max_units
                or word.end - current[0].start > max_duration
            ):
                groups.append(current)
                current = []
        current.append(word)
    if current:
        groups.append(current)

    cues: list[SubtitleCue] = []
    for i, group in enumerate(groups):
        start, end = group[0].start, group[-1].end
        if end - start < min_display:
            target = start + min_display
            next_start = groups[i + 1][0].start if i + 1 < len(groups) else None
            end = target if next_start is None else max(end, min(target, next_start))
        cues.append(
            SubtitleCue(
                index=i + 1,
                start=start,
                end=end,
                speaker=group[0].speaker,
                tokens=tuple(w.word for w in group),
            )
        )
    return cues
