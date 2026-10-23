# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-CLI batch pipeline for Apple Silicon Macs: a finished meeting recording → speaker-labelled `.srt` + `_transcript.md` (fully local, mlx-whisper + pyannote on MPS) → `_summary.md` via the Antigravity CLI (`agy -p`, cloud). User-facing strings, docs, and comments are in Traditional Chinese; keep it that way.

Source of truth for behaviour: `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md` (spec), `docs/plans/...` (implementation plan, "if you deviate, change the tests first"), `GLOSSARY.md` (domain terms — use them: Recording, Word, Speaker Turn, Speaker Label, Display Name, Cue, Text Unit, Transcript, Summary). Work is tracked as tickets in `.scratch/meeting-pipeline/issues/` with status in `.scratch/progress.md`; tickets 01 (Mac env spike for mlx-whisper/pyannote) and 10 (Mac smoke test + README) are still open.

## Commands

```bash
brew install ffmpeg
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # unit tests only (any platform)
pip install -e ".[mac,dev]"      # + mlx, mlx-whisper, torch, pyannote.audio

pytest                            # all tests; the mac smoke test auto-skips
pytest tests/test_aligner.py -v   # one file
pytest tests/test_text.py::test_name   # one test
MEETING_SMOKE_AUDIO=/path/short.m4a pytest -m mac   # real-model end-to-end (macOS only)

python meeting_pipeline.py meeting.m4a [--speakers "SPEAKER_00=王經理"] [--num-speakers N] [--no-summary]
python meeting_pipeline.py --summarize-only out/meeting_transcript.md [--agy-model "..."]
```

On the Mac use Homebrew `python3.12` (system Python is 3.9). Don't loosen the upper bounds in the `mac` extras (`torch<2.6`, `torchaudio<2.6`, `huggingface_hub<1.0`, `speechbrain<1.1`) — each one breaks pyannote 3.x; see `docs/notes/2026-10-19-mac-environment-findings.md`. pyannote needs `HF_TOKEN` (or `--hf-token` / `huggingface-cli login`) and acceptance of the gated `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0` models.

## Architecture

`meeting_pipeline.py` does arg validation (bad input → `parser.error`, exit 2, before any output dir is created) and orchestrates the `pipeline/` modules in order:

1. `audio.normalized_audio_wav` — context manager; FFmpeg → 16 kHz mono s16le temp WAV shared by both engines, deleted on every exit path.
2. `asr.transcribe_words` then `diarization.diarize_speakers` — run **sequentially**, and each must free its model afterwards (MLX `ModelHolder` reset + `clear_cache`; pyannote `del` + `torch.mps.empty_cache`). Heavy imports (`mlx_whisper`, `torch`, `pyannote`) are lazy inside `_call_*`/`_load_*`/`_release_*` helpers so the package imports on non-Macs; tests patch these helpers (see `tests/test_engines.py`). ASR drops whole segments matching `hallucination.HALLUCINATION_PHRASES`, converts each word with OpenCC `s2twp`, and merges English subword pieces (with `language="zh"`, Whisper emits `'AP','I'`; only a leading space marks a new English word) so each Word is a whole English word.
3. `aligner.assign_speakers` (word-level: max overlap, ties → earlier turn; zero overlap → nearest by midpoint; no turns → `SPEAKER_00`) → `aligner.chunk_subtitles` (split on speaker change, gap > 1.2 s, > 28 Text Units, > 6 s; min display 0.8 s without overlapping the next cue) → `exporters` (SRT ≤ 2 lines split at 14 units; transcript paragraphs per speaker ≤ 60 s). Text Units and CJK/English spacing live in `text.py`.
4. `summarizer.generate_meeting_summary` — returns bool, never raises for agy failures.

Data types are frozen dataclasses in `models.py`. Speaker Labels are used for all alignment/chunking; Display Names (`--speakers`) are applied only at export time.

## Invariants that are easy to break

- **Never overwrite outputs.** `outputs.allocate_output_set` picks a `<stem>_N` suffix so that none of srt/transcript/summary exist; `summary_path_for` picks `_summary_N.md` for reruns. `--summarize-only` requires a `*_transcript.md` filename.
- **No empty/partial summary file.** Summary is written to `.tmp` then `os.replace`d. On any failure, keep srt/transcript, print the reason plus a pasteable rerun command (absolute `sys.executable` + absolute CLI path) to stderr, exit 1.
- **agy quirks** (`docs/notes/2026-10-19-agy-findings.md`): `agy -p` ignores stdin, so the transcript goes in the argv prompt with `stdin=DEVNULL`; prompts > 100,000 bytes are refused; `--print-timeout 5m` must be explicit (default is no timeout); empty stdout with exit 0 is a failure (tool permission denied); don't use `--mode plan`.
- **Privacy** (ADR 0001): everything except the summary step is local; `--no-summary` keeps the transcript on-device. Recordings and outputs are gitignored — never commit meeting content.
