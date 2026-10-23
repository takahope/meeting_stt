import pytest

from pipeline.aligner import assign_speakers, chunk_subtitles
from pipeline.models import AlignedWord, SpeakerTurn, WordToken
from pipeline.text import compute_text_units, join_word_tokens


def test_assign_speakers_overlap_and_midpoint_fallback():
    turns = [
        SpeakerTurn(start=3.0, end=5.0, speaker="SPEAKER_01"),
        SpeakerTurn(start=0.0, end=2.0, speaker="SPEAKER_00"),
    ]
    words = [
        WordToken(word="早安", start=0.5, end=1.2),  # 與 SPEAKER_00 重疊
        WordToken(word="好", start=2.1, end=2.3),  # 間隙，中點 2.2 離 2.0 較近
        WordToken(word="請問", start=2.7, end=2.9),  # 間隙，中點 2.8 離 3.0 較近
    ]
    assert [w.speaker for w in assign_speakers(words, turns)] == ["SPEAKER_00", "SPEAKER_00", "SPEAKER_01"]


def test_assign_speakers_overlapping_turns_prefers_larger_then_earlier():
    turns = [
        SpeakerTurn(start=0.0, end=2.0, speaker="SPEAKER_00"),
        SpeakerTurn(start=1.0, end=3.0, speaker="SPEAKER_01"),
    ]
    larger = WordToken(word="對", start=1.5, end=2.5)  # 00 重疊 0.5、01 重疊 1.0
    tie = WordToken(word="嗯", start=1.0, end=2.0)  # 兩者皆重疊 1.0
    assert [w.speaker for w in assign_speakers([larger, tie], turns)] == ["SPEAKER_01", "SPEAKER_00"]


def test_assign_speakers_zero_duration_word_and_empty_turns():
    words = [WordToken(word="嗯", start=2.0, end=2.0)]
    turns = [SpeakerTurn(start=0.0, end=1.5, speaker="SPEAKER_01")]
    assert assign_speakers(words, turns)[0].speaker == "SPEAKER_01"
    assert assign_speakers(words, [])[0].speaker == "SPEAKER_00"


def test_chunk_subtitles_splits_on_speaker_gap_units_and_duration():
    words_speaker = [
        AlignedWord(word="你好", start=0.0, end=0.5, speaker="SPEAKER_00"),
        AlignedWord(word="嗨", start=0.6, end=1.0, speaker="SPEAKER_01"),
    ]
    cues = chunk_subtitles(words_speaker)
    assert [c.speaker for c in cues] == ["SPEAKER_00", "SPEAKER_01"]
    assert cues[0].tokens == ("你好",)

    words_gap = [
        AlignedWord(word="第一段", start=0.0, end=1.0, speaker="SPEAKER_00"),
        AlignedWord(word="第二段", start=2.3, end=3.0, speaker="SPEAKER_00"),
    ]
    assert len(chunk_subtitles(words_gap)) == 2

    words_dur = [
        AlignedWord(word="拉長", start=0.0, end=3.5, speaker="SPEAKER_00"),
        AlignedWord(word="時間", start=3.6, end=6.2, speaker="SPEAKER_00"),
    ]
    assert len(chunk_subtitles(words_dur)) == 2

    words_units = [
        AlignedWord(word="字數", start=i * 0.2, end=(i + 1) * 0.2, speaker="SPEAKER_00") for i in range(15)
    ]  # 15 × 2 = 30 units
    cues_units = chunk_subtitles(words_units)
    assert len(cues_units) == 2
    assert compute_text_units(join_word_tokens(cues_units[0].tokens)) == 28.0
    assert [c.index for c in cues_units] == [1, 2]


def test_chunk_subtitles_min_display_extends_without_overlapping_next_cue():
    words = [
        AlignedWord(word="嗯", start=0.0, end=0.1, speaker="SPEAKER_00"),
        AlignedWord(word="好", start=0.5, end=0.6, speaker="SPEAKER_01"),
        AlignedWord(word="對", start=5.0, end=5.1, speaker="SPEAKER_00"),
    ]
    cues = chunk_subtitles(words)
    assert cues[0].end == pytest.approx(0.5)  # 被下一條的開始時間擋住
    assert cues[1].end == pytest.approx(1.3)  # 延長到 0.8 秒
    assert cues[2].end == pytest.approx(5.8)  # 最後一條直接延長
