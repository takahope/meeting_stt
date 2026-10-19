from pipeline.models import AlignedWord, SpeakerTurn, SubtitleCue, WordToken, format_srt_timestamp


def test_format_srt_timestamp_standard_and_rounding():
    assert format_srt_timestamp(1.24) == "00:00:01,240"
    assert format_srt_timestamp(3661.005) == "01:01:01,005"
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(-0.5) == "00:00:00,000"


def test_models_instantiation():
    token = WordToken(word="測試", start=0.5, end=1.0)
    turn = SpeakerTurn(start=0.0, end=2.0, speaker="SPEAKER_00")
    aligned = AlignedWord(word=token.word, start=token.start, end=token.end, speaker=turn.speaker)
    cue = SubtitleCue(index=1, start=0.5, end=1.0, speaker="SPEAKER_00", tokens=("測試",))
    assert aligned.speaker == "SPEAKER_00"
    assert cue.tokens == ("測試",)
