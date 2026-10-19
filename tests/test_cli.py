from pathlib import Path
from unittest.mock import patch

import pytest

from meeting_pipeline import main, parse_args
from pipeline.models import SpeakerTurn, WordToken

FAKE_WORDS = [
    WordToken(word="我們", start=1.24, end=1.80),
    WordToken(word="確認", start=1.85, end=2.50),
]
FAKE_TURNS = [SpeakerTurn(start=1.0, end=3.0, speaker="SPEAKER_00")]


@pytest.mark.parametrize(
    "argv",
    [
        ["demo.m4a", "--num-speakers", "2", "--min-speakers", "1"],
        ["demo.m4a", "--min-speakers", "4", "--max-speakers", "2"],
        ["demo.m4a", "--num-speakers", "0"],
        [],
        ["demo.m4a", "--summarize-only", "demo_transcript.md"],
        ["--summarize-only", "demo_transcript.md", "--no-summary"],
        ["demo.m4a", "--speakers", "SPEAKER_00:王經理"],
        ["demo.txt"],
    ],
    ids=["num-with-min", "min-gt-max", "zero", "no-input", "both-inputs", "summarize-with-no-summary", "bad-speakers", "bad-ext"],
)
def test_parse_args_rejects_invalid_combinations(argv):
    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def _run_main(argv: list[str], tmp_path: Path, summary_ok: bool = True):
    with (
        patch("meeting_pipeline.normalized_audio_wav") as mock_norm,
        patch("meeting_pipeline.transcribe_words", return_value=FAKE_WORDS),
        patch("meeting_pipeline.diarize_speakers", return_value=FAKE_TURNS),
        patch("meeting_pipeline.generate_meeting_summary", return_value=summary_ok) as mock_sum,
    ):
        mock_norm.return_value.__enter__.return_value = tmp_path / "temp_16k.wav"
        exit_code = main(argv)
    return exit_code, mock_sum


def test_main_runs_full_pipeline_and_creates_outputs(tmp_path: Path):
    audio = tmp_path / "weekly_sync.m4a"
    audio.write_bytes(b"fake")
    out_dir = tmp_path / "output"
    exit_code, mock_sum = _run_main(
        [str(audio), "--num-speakers", "2", "--speakers", "SPEAKER_00=王經理",
         "--agy-model", "Gemini 3.7 Pro", "--output-dir", str(out_dir)],
        tmp_path,
    )
    assert exit_code == 0
    assert "[王經理] 我們確認" in (out_dir / "weekly_sync.srt").read_text(encoding="utf-8")
    assert (out_dir / "weekly_sync_transcript.md").exists()
    mock_sum.assert_called_once_with(
        out_dir / "weekly_sync_transcript.md",
        out_dir / "weekly_sync_summary.md",
        agy_model="Gemini 3.7 Pro",
    )


def test_main_suffixes_outputs_skips_summary_and_warns_unknown_label(tmp_path: Path, capsys):
    audio = tmp_path / "weekly_sync.m4a"
    audio.write_bytes(b"fake")
    (tmp_path / "weekly_sync.srt").write_text("old", encoding="utf-8")
    exit_code, mock_sum = _run_main(
        [str(audio), "--no-summary", "--speakers", "SPEAKER_03=陳主任"], tmp_path
    )
    assert exit_code == 0
    assert (tmp_path / "weekly_sync.srt").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "weekly_sync_1.srt").exists()
    assert (tmp_path / "weekly_sync_1_transcript.md").exists()
    mock_sum.assert_not_called()
    assert "SPEAKER_03" in capsys.readouterr().err


def test_main_returns_1_when_summary_fails(tmp_path: Path):
    audio = tmp_path / "weekly_sync.m4a"
    audio.write_bytes(b"fake")
    exit_code, _ = _run_main([str(audio)], tmp_path, summary_ok=False)
    assert exit_code == 1
    assert (tmp_path / "weekly_sync.srt").exists()


def test_main_summarize_only_uses_suffixed_summary_path(tmp_path: Path):
    transcript = tmp_path / "weekly_sync_transcript.md"
    transcript.write_text("逐字稿", encoding="utf-8")
    (tmp_path / "weekly_sync_summary.md").write_text("old", encoding="utf-8")
    with patch("meeting_pipeline.generate_meeting_summary", return_value=True) as mock_sum:
        assert main(["--summarize-only", str(transcript)]) == 0
    mock_sum.assert_called_once_with(transcript, tmp_path / "weekly_sync_summary_1.md", agy_model=None)
