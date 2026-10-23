import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.summarizer import (
    MAX_PROMPT_BYTES,
    build_agy_command,
    build_agy_prompt,
    format_rerun_command,
    generate_meeting_summary,
)

MODEL = "Gemini 3.8 Flash (High)"


def test_build_agy_prompt_contains_required_sections_and_the_transcript():
    prompt = build_agy_prompt("**[00:00:01,000 - 00:00:02,000] [SPEAKER_00]**\n逐字稿內容")
    for section in (
        "會議核心摘要",
        "關鍵決議事項 (Decisions)",
        "待辦事項清單 (Action Items)",
        "負責人 (Owner)",
        "預計完成期限 (Deadline)",
        "來源時間戳記 (Timestamp)",
        "逐字稿內容",
    ):
        assert section in prompt
    assert "stdin" not in prompt and "標準輸入" not in prompt  # agy 不會讀 stdin


def test_build_agy_command_has_timeout_and_optional_model_and_no_mode_flag():
    cmd = build_agy_command("逐字稿內容", MODEL)
    assert cmd[:2] == ["agy", "-p"]
    assert "逐字稿內容" in cmd[2]
    assert cmd[3] == "--print-timeout"
    assert cmd[-2:] == ["--model", MODEL]
    assert "--mode" not in cmd  # plan 模式會產出實作計畫檔而非摘要
    assert "--dangerously-skip-permissions" not in cmd
    assert "--model" not in build_agy_command("逐字稿內容")


def test_format_rerun_command_is_pasteable_from_any_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd = shlex.split(format_rerun_command(Path("output") / "weekly_transcript.md", MODEL))
    assert cmd[0] == sys.executable  # 虛擬環境內的直譯器，否則缺少依賴
    assert Path(cmd[1]).is_absolute() and Path(cmd[1]).name == "meeting_pipeline.py"
    assert cmd[2] == "--summarize-only"
    assert Path(cmd[3]) == tmp_path / "output" / "weekly_transcript.md"  # 絕對路徑
    assert cmd[4:] == ["--agy-model", MODEL]


def test_generate_meeting_summary_passes_transcript_in_argv_and_writes_atomically(tmp_path: Path):
    transcript = tmp_path / "meeting_transcript.md"
    transcript.write_text("逐字稿內容", encoding="utf-8")
    summary = tmp_path / "meeting_summary.md"
    with patch("pipeline.summarizer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="# 會議總結\n重點一\n\n", stderr="")
        ok = generate_meeting_summary(transcript, summary, agy_model=MODEL)
    assert ok is True
    assert summary.read_text(encoding="utf-8") == "# 會議總結\n重點一\n"
    assert "逐字稿內容" in mock_run.call_args.args[0][2]
    # agy 會嘗試讀 stdin，必須關掉，否則 headless 模式可能卡住或被拒絕
    assert mock_run.call_args.kwargs["stdin"] == subprocess.DEVNULL
    assert "input" not in mock_run.call_args.kwargs
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "run_kwargs",
    [
        {"return_value": MagicMock(returncode=1, stdout="", stderr="Not logged in")},
        {"return_value": MagicMock(returncode=0, stdout="  \n", stderr="")},
        {"side_effect": subprocess.TimeoutExpired(cmd="agy", timeout=330)},
        {"side_effect": FileNotFoundError("agy")},
        {"side_effect": OSError(7, "Argument list too long")},
    ],
    ids=["nonzero-exit", "empty-stdout", "timeout", "not-installed", "argv-too-long"],
)
def test_generate_meeting_summary_failure_keeps_outputs_and_prints_rerun(tmp_path: Path, capsys, run_kwargs):
    srt = tmp_path / "meeting.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n[SPEAKER_00] 保留測試\n", encoding="utf-8")
    transcript = tmp_path / "meeting_transcript.md"
    transcript.write_text("逐字稿內容", encoding="utf-8")
    summary = tmp_path / "meeting_summary.md"
    with patch("pipeline.summarizer.subprocess.run", **run_kwargs):
        ok = generate_meeting_summary(transcript, summary, agy_model=MODEL)
    assert ok is False
    assert srt.exists() and transcript.exists()
    assert not summary.exists()
    assert list(tmp_path.glob("*.tmp")) == []
    err = capsys.readouterr().err
    assert "--summarize-only" in err and str(transcript) in err and MODEL in err


def test_generate_meeting_summary_rejects_oversized_transcript_without_calling_agy(tmp_path: Path, capsys):
    transcript = tmp_path / "long_transcript.md"
    transcript.write_text("字" * (MAX_PROMPT_BYTES // 3 + 1), encoding="utf-8")  # 每字 3 bytes
    summary = tmp_path / "long_summary.md"
    with patch("pipeline.summarizer.subprocess.run") as mock_run:
        ok = generate_meeting_summary(transcript, summary)
    assert ok is False
    mock_run.assert_not_called()
    assert not summary.exists()
    assert "過長" in capsys.readouterr().err
