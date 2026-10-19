import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.summarizer import (
    build_agy_command,
    build_agy_prompt,
    format_rerun_command,
    generate_meeting_summary,
)


def test_build_agy_prompt_contains_required_sections():
    prompt = build_agy_prompt()
    for section in (
        "會議核心摘要",
        "關鍵決議事項 (Decisions)",
        "待辦事項清單 (Action Items)",
        "負責人 (Owner)",
        "預計完成期限 (Deadline)",
        "來源時間戳記 (Timestamp)",
    ):
        assert section in prompt


def test_build_agy_command_has_timeout_and_optional_model():
    cmd = build_agy_command("Gemini 3.7 Pro")
    assert cmd[:2] == ["agy", "-p"]
    assert "--print-timeout" in cmd
    assert cmd[-2:] == ["--model", "Gemini 3.7 Pro"]
    assert "--model" not in build_agy_command()


def test_format_rerun_command_is_pasteable_from_any_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd = shlex.split(format_rerun_command(Path("output") / "weekly_transcript.md", "Gemini 3.8 Flash (High)"))
    assert cmd[0] == sys.executable  # 虛擬環境內的直譯器，否則缺少依賴
    assert Path(cmd[1]).is_absolute() and Path(cmd[1]).name == "meeting_pipeline.py"
    assert cmd[2] == "--summarize-only"
    assert Path(cmd[3]) == tmp_path / "output" / "weekly_transcript.md"  # 絕對路徑
    assert cmd[4:] == ["--agy-model", "Gemini 3.8 Flash (High)"]


def test_generate_meeting_summary_sends_transcript_via_stdin_and_writes_atomically(tmp_path: Path):
    transcript = tmp_path / "meeting_transcript.md"
    transcript.write_text("逐字稿內容", encoding="utf-8")
    summary = tmp_path / "meeting_summary.md"
    with patch("pipeline.summarizer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="# 會議總結\n重點一\n\n", stderr="")
        ok = generate_meeting_summary(transcript, summary, agy_model="Gemini 3.7 Pro")
    assert ok is True
    assert summary.read_text(encoding="utf-8") == "# 會議總結\n重點一\n"
    assert mock_run.call_args.kwargs["input"] == "逐字稿內容"
    assert "逐字稿內容" not in mock_run.call_args.args[0]
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "run_kwargs",
    [
        {"return_value": MagicMock(returncode=1, stdout="", stderr="Not logged in")},
        {"return_value": MagicMock(returncode=0, stdout="  \n", stderr="")},
        {"side_effect": subprocess.TimeoutExpired(cmd="agy", timeout=330)},
        {"side_effect": FileNotFoundError("agy")},
    ],
    ids=["nonzero-exit", "empty-stdout", "timeout", "not-installed"],
)
def test_generate_meeting_summary_failure_keeps_outputs_and_prints_rerun(tmp_path: Path, capsys, run_kwargs):
    srt = tmp_path / "meeting.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n[SPEAKER_00] 保留測試\n", encoding="utf-8")
    transcript = tmp_path / "meeting_transcript.md"
    transcript.write_text("逐字稿內容", encoding="utf-8")
    summary = tmp_path / "meeting_summary.md"
    with patch("pipeline.summarizer.subprocess.run", **run_kwargs):
        ok = generate_meeting_summary(transcript, summary, agy_model="Gemini 3.7 Pro")
    assert ok is False
    assert srt.exists() and transcript.exists()
    assert not summary.exists()
    assert list(tmp_path.glob("*.tmp")) == []
    err = capsys.readouterr().err
    assert "--summarize-only" in err and str(transcript) in err and "Gemini 3.7 Pro" in err
