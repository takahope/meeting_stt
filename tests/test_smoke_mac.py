import os
import sys
from pathlib import Path

import pytest

from meeting_pipeline import main
from pipeline.text import compute_text_units

pytestmark = [
    pytest.mark.mac,
    pytest.mark.skipif(
        sys.platform != "darwin" or not os.environ.get("MEETING_SMOKE_AUDIO"),
        reason="需在 macOS 上設定 MEETING_SMOKE_AUDIO=<短錄音路徑>",
    ),
]


def test_real_models_end_to_end_without_summary(tmp_path: Path):
    audio = Path(os.environ["MEETING_SMOKE_AUDIO"])
    assert main([str(audio), "--no-summary", "--output-dir", str(tmp_path)]) == 0

    srt = (tmp_path / f"{audio.stem}.srt").read_text(encoding="utf-8")
    blocks = [b for b in srt.strip().split("\n\n") if b]
    assert blocks, "SRT 不應為空"
    for block in blocks:
        _index, _timing, *lines = block.split("\n")
        assert 1 <= len(lines) <= 2
        text = "".join(lines).split("] ", 1)[1]
        assert compute_text_units(text) <= 28.0
    assert (tmp_path / f"{audio.stem}_transcript.md").exists()
    assert list(tmp_path.glob("*.wav")) == []
