from pathlib import Path

from pipeline.models import SubtitleCue, format_srt_timestamp
from pipeline.speakers import display_name
from pipeline.text import join_word_tokens, split_two_lines


def export_srt(
    cues: list[SubtitleCue], output_path: Path, display_names: dict[str, str] | None = None
) -> Path:
    names = display_names or {}
    blocks = []
    for cue in cues:
        lines = split_two_lines(cue.tokens)
        lines[0] = f"[{display_name(cue.speaker, names)}] {lines[0]}"
        timing = f"{format_srt_timestamp(cue.start)} --> {format_srt_timestamp(cue.end)}"
        blocks.append("\n".join([str(cue.index), timing, *lines]) + "\n")
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path


def export_transcript_md(
    cues: list[SubtitleCue],
    output_path: Path,
    display_names: dict[str, str] | None = None,
    max_paragraph_sec: float = 60.0,
) -> Path:
    names = display_names or {}
    paragraphs: list[list[SubtitleCue]] = []
    for cue in cues:
        current = paragraphs[-1] if paragraphs else None
        if (
            current is None
            or cue.speaker != current[0].speaker
            or cue.end - current[0].start > max_paragraph_sec
        ):
            paragraphs.append([cue])
        else:
            current.append(cue)

    blocks = []
    for para in paragraphs:
        header = (
            f"**[{format_srt_timestamp(para[0].start)} - {format_srt_timestamp(para[-1].end)}] "
            f"[{display_name(para[0].speaker, names)}]**"
        )
        text = join_word_tokens([token for cue in para for token in cue.tokens])
        blocks.append(f"{header}\n{text}\n")
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path
