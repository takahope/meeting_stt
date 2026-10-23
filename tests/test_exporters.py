from pathlib import Path

from pipeline.exporters import export_srt, export_transcript_md
from pipeline.models import SubtitleCue


def test_export_srt_matches_spec_format_with_display_names_and_wrap(tmp_path: Path):
    cues = [
        SubtitleCue(
            index=1, start=1.24, end=4.82, speaker="SPEAKER_00",
            tokens=("我們", "今天", "確認", " API", "進度", "。"),
        ),
        SubtitleCue(
            index=2, start=5.10, end=8.45, speaker="SPEAKER_01",
            tokens=("目前", " OAuth", "模組", "已經", "完成", "，", "但我", "週三", "前", "需要", "憑證", "。"),
        ),
    ]
    srt_path = export_srt(cues, tmp_path / "demo.srt", {"SPEAKER_01": "李工程師"})
    assert srt_path.read_text(encoding="utf-8") == (
        "1\n"
        "00:00:01,240 --> 00:00:04,820\n"
        "[SPEAKER_00] 我們今天確認 API 進度。\n"
        "\n"
        "2\n"
        "00:00:05,100 --> 00:00:08,450\n"
        "[李工程師] 目前 OAuth 模組已經完成，\n"
        "但我週三前需要憑證。\n"
    )


def test_export_transcript_md_groups_consecutive_speaker_cues(tmp_path: Path):
    cues = [
        SubtitleCue(index=1, start=1.24, end=3.00, speaker="SPEAKER_00", tokens=("第一句", "。")),
        SubtitleCue(index=2, start=3.20, end=4.82, speaker="SPEAKER_00", tokens=("第二句", "。")),
        SubtitleCue(index=3, start=5.10, end=8.45, speaker="SPEAKER_01", tokens=("換人", "回應", "。")),
    ]
    content = export_transcript_md(cues, tmp_path / "demo_transcript.md", {"SPEAKER_00": "王經理"}).read_text(
        encoding="utf-8"
    )
    assert content == (
        "**[00:00:01,240 - 00:00:04,820] [王經理]**\n"
        "第一句。第二句。\n"
        "\n"
        "**[00:00:05,100 - 00:00:08,450] [SPEAKER_01]**\n"
        "換人回應。\n"
    )


def test_export_transcript_md_breaks_paragraph_after_60_seconds(tmp_path: Path):
    cues = [
        SubtitleCue(index=1, start=0.0, end=30.0, speaker="SPEAKER_00", tokens=("一",)),
        SubtitleCue(index=2, start=31.0, end=61.0, speaker="SPEAKER_00", tokens=("二",)),
        SubtitleCue(index=3, start=62.0, end=70.0, speaker="SPEAKER_00", tokens=("三",)),
    ]
    content = export_transcript_md(cues, tmp_path / "long_transcript.md").read_text(encoding="utf-8")
    assert content.count("[SPEAKER_00]**") == 2
    assert "**[00:00:31,000 - 00:01:10,000] [SPEAKER_00]**\n二三\n" in content
