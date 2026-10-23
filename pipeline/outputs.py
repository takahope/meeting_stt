from dataclasses import dataclass
from pathlib import Path

_TRANSCRIPT_SUFFIX = "_transcript.md"


@dataclass(frozen=True, slots=True)
class OutputSet:
    srt: Path
    transcript: Path
    summary: Path


def _output_set(output_dir: Path, stem: str) -> OutputSet:
    return OutputSet(
        srt=output_dir / f"{stem}.srt",
        transcript=output_dir / f"{stem}{_TRANSCRIPT_SUFFIX}",
        summary=output_dir / f"{stem}_summary.md",
    )


def allocate_output_set(output_dir: Path, basename: str) -> OutputSet:
    n = 0
    while True:
        candidate = _output_set(output_dir, basename if n == 0 else f"{basename}_{n}")
        if not any(p.exists() for p in (candidate.srt, candidate.transcript, candidate.summary)):
            return candidate
        n += 1


def summary_path_for(transcript_path: Path) -> Path:
    name = transcript_path.name
    if not name.endswith(_TRANSCRIPT_SUFFIX):
        raise ValueError(f"逐字稿檔名必須以 {_TRANSCRIPT_SUFFIX} 結尾：{name}")
    stem = name[: -len(_TRANSCRIPT_SUFFIX)]
    candidate = transcript_path.with_name(f"{stem}_summary.md")
    n = 1
    while candidate.exists():
        candidate = transcript_path.with_name(f"{stem}_summary_{n}.md")
        n += 1
    return candidate
