import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.audio import normalized_audio_wav


@pytest.fixture
def temp_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "tmp"
    d.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(d))
    return d


def test_normalized_audio_wav_runs_ffmpeg_and_cleans_up_on_success(tmp_path: Path, temp_dir: Path):
    src = tmp_path / "meeting.m4a"
    src.write_bytes(b"fake-audio")
    with patch("pipeline.audio.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with normalized_audio_wav(src) as wav_path:
            assert wav_path.suffix == ".wav"
            assert wav_path.exists()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "ffmpeg"
            assert cmd[cmd.index("-i") + 1] == str(src)
            assert cmd[cmd.index("-ar") + 1] == "16000"
            assert cmd[cmd.index("-ac") + 1] == "1"
            assert cmd[cmd.index("-c:a") + 1] == "pcm_s16le"
            assert "-vn" in cmd
            assert cmd[-1] == str(wav_path)
    assert list(temp_dir.iterdir()) == []


def test_normalized_audio_wav_cleans_up_on_exception(tmp_path: Path, temp_dir: Path):
    src = tmp_path / "meeting.mp4"
    src.write_bytes(b"fake-video")
    with patch("pipeline.audio.subprocess.run"):
        with pytest.raises(RuntimeError, match="boom"):
            with normalized_audio_wav(src):
                raise RuntimeError("boom")
    assert list(temp_dir.iterdir()) == []


def test_normalized_audio_wav_reports_ffmpeg_failure_and_cleans_up(tmp_path: Path, temp_dir: Path):
    src = tmp_path / "broken.mp3"
    src.write_bytes(b"not-audio")
    error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="Invalid data found")
    with patch("pipeline.audio.subprocess.run", side_effect=error):
        with pytest.raises(RuntimeError, match="Invalid data found"):
            with normalized_audio_wav(src):
                pass
    assert list(temp_dir.iterdir()) == []


def test_normalized_audio_wav_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        with normalized_audio_wav(tmp_path / "missing.wav"):
            pass
