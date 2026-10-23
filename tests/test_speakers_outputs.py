from pathlib import Path

import pytest

from pipeline.outputs import allocate_output_set, summary_path_for
from pipeline.speakers import display_name, parse_display_names, unknown_labels


def test_parse_display_names_valid_and_invalid():
    assert parse_display_names(None) == {}
    assert parse_display_names(" SPEAKER_00 = 王經理 , SPEAKER_01=李工程師 , ") == {
        "SPEAKER_00": "王經理",
        "SPEAKER_01": "李工程師",
    }
    with pytest.raises(ValueError, match="Invalid speaker mapping"):
        parse_display_names("SPEAKER_00:王經理")
    with pytest.raises(ValueError, match="Invalid speaker mapping"):
        parse_display_names("SPEAKER_00=")


def test_display_name_and_unknown_labels():
    names = {"SPEAKER_00": "王經理", "SPEAKER_03": "陳主任"}
    assert display_name("SPEAKER_00", names) == "王經理"
    assert display_name("SPEAKER_01", names) == "SPEAKER_01"
    assert unknown_labels(names, {"SPEAKER_00", "SPEAKER_01"}) == ["SPEAKER_03"]


def test_allocate_output_set_suffixes_whole_set(tmp_path: Path):
    first = allocate_output_set(tmp_path, "weekly")
    assert (first.srt.name, first.transcript.name, first.summary.name) == (
        "weekly.srt",
        "weekly_transcript.md",
        "weekly_summary.md",
    )
    (tmp_path / "weekly_transcript.md").write_text("x", encoding="utf-8")
    second = allocate_output_set(tmp_path, "weekly")
    assert (second.srt.name, second.transcript.name, second.summary.name) == (
        "weekly_1.srt",
        "weekly_1_transcript.md",
        "weekly_1_summary.md",
    )
    (tmp_path / "weekly_1_summary.md").write_text("x", encoding="utf-8")
    assert allocate_output_set(tmp_path, "weekly").srt.name == "weekly_2.srt"


def test_summary_path_for_suffixes_existing_summary(tmp_path: Path):
    transcript = tmp_path / "weekly_1_transcript.md"
    assert summary_path_for(transcript).name == "weekly_1_summary.md"
    (tmp_path / "weekly_1_summary.md").write_text("old", encoding="utf-8")
    assert summary_path_for(transcript).name == "weekly_1_summary_1.md"
    with pytest.raises(ValueError):
        summary_path_for(tmp_path / "notes.md")
