from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.asr import DEFAULT_ASR_MODEL, DEFAULT_INITIAL_PROMPT, transcribe_words
from pipeline.diarization import diarize_speakers
from pipeline.hallucination import is_hallucination
from pipeline.models import SpeakerTurn, WordToken


def test_is_hallucination_matches_known_phrases_only():
    assert is_hallucination("字幕由Amara.org社区提供")
    assert is_hallucination("請不吝點讚 訂閱 轉發")
    assert not is_hallucination("我們下週三前要完成點檢")


def test_transcribe_words_passes_params_filters_converts_and_releases(tmp_path: Path):
    fake_result = {
        "segments": [
            {
                "text": "我们 OAuth",
                "words": [
                    {"word": "我们", "start": 1.24, "end": 1.80},
                    {"word": " OAuth", "start": 5.10, "end": 5.60},
                    {"word": " ", "start": 5.60, "end": 5.70},
                ],
            },
            {
                "text": "字幕由Amara.org社区提供",
                "words": [{"word": "字幕", "start": 9.0, "end": 9.5}],
            },
        ]
    }
    with (
        patch("pipeline.asr._call_mlx_whisper", return_value=fake_result) as mock_whisper,
        patch("pipeline.asr._release_mlx_model") as mock_release,
    ):
        words = transcribe_words(tmp_path / "temp.wav")
    mock_whisper.assert_called_once_with(
        str(tmp_path / "temp.wav"),
        path_or_hf_repo=DEFAULT_ASR_MODEL,
        language="zh",
        word_timestamps=True,
        initial_prompt=DEFAULT_INITIAL_PROMPT,
        condition_on_previous_text=False,
        hallucination_silence_threshold=2.0,
    )
    mock_release.assert_called_once()
    assert words == [
        WordToken(word="我們", start=1.24, end=1.80),
        WordToken(word=" OAuth", start=5.10, end=5.60),
    ]


def test_transcribe_words_releases_model_even_on_failure(tmp_path: Path):
    with (
        patch("pipeline.asr._call_mlx_whisper", side_effect=RuntimeError("metal oom")),
        patch("pipeline.asr._release_mlx_model") as mock_release,
    ):
        try:
            transcribe_words(tmp_path / "temp.wav")
        except RuntimeError:
            pass
    mock_release.assert_called_once()


def test_diarize_speakers_uses_env_token_bounds_and_clears_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_from_env")
    seg1 = MagicMock(start=5.0, end=8.5)
    seg2 = MagicMock(start=1.0, end=4.9)
    fake_annotation = MagicMock()
    fake_annotation.itertracks.return_value = [
        (seg1, "track_1", "SPEAKER_01"),
        (seg2, "track_0", "SPEAKER_00"),
    ]
    fake_pipeline = MagicMock(return_value=fake_annotation)
    with (
        patch("pipeline.diarization._load_pyannote_pipeline", return_value=fake_pipeline) as mock_load,
        patch("pipeline.diarization._clear_torch_mps_memory") as mock_clear,
    ):
        turns = diarize_speakers(tmp_path / "temp.wav", min_speakers=2, max_speakers=4)
    mock_load.assert_called_once_with("hf_from_env")
    fake_pipeline.assert_called_once_with(str(tmp_path / "temp.wav"), min_speakers=2, max_speakers=4)
    mock_clear.assert_called_once()
    assert turns == [
        SpeakerTurn(start=1.0, end=4.9, speaker="SPEAKER_00"),
        SpeakerTurn(start=5.0, end=8.5, speaker="SPEAKER_01"),
    ]
