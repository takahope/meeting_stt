import gc
from pathlib import Path
from typing import Any

from pipeline.hallucination import is_hallucination
from pipeline.models import WordToken
from pipeline.text import to_traditional

DEFAULT_ASR_MODEL = "mlx-community/whisper-large-v3-turbo"
DEFAULT_INITIAL_PROMPT = "以下是繁體中文的專案會議記錄，包含專業術語與待辦事項討論。"
ASR_LANGUAGE = "zh"
HALLUCINATION_SILENCE_THRESHOLD = 2.0


def transcribe_words(
    wav_path: Path,
    model_repo: str = DEFAULT_ASR_MODEL,
    initial_prompt: str = DEFAULT_INITIAL_PROMPT,
) -> list[WordToken]:
    try:
        result = _call_mlx_whisper(
            str(wav_path),
            path_or_hf_repo=model_repo,
            language=ASR_LANGUAGE,
            word_timestamps=True,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
            hallucination_silence_threshold=HALLUCINATION_SILENCE_THRESHOLD,
        )
    finally:
        _release_mlx_model()
    return extract_words(result)


def extract_words(result: dict[str, Any]) -> list[WordToken]:
    words: list[WordToken] = []
    for segment in result.get("segments", []):
        if is_hallucination(segment.get("text", "")):
            continue
        previous: WordToken | None = None
        for raw in segment.get("words", []):
            text = to_traditional(raw["word"])
            if not text.strip():
                previous = None
                continue
            if previous is not None and _continues_english_word(previous.word, text):
                previous = WordToken(word=previous.word + text, start=previous.start, end=float(raw["end"]))
                words[-1] = previous
                continue
            previous = WordToken(word=text, start=float(raw["start"]), end=float(raw["end"]))
            words.append(previous)
    return words


def _continues_english_word(previous: str, piece: str) -> bool:
    # language="zh" 時英文會被拆成子詞（"AP" + "I"）；沒有前導空白的英數子詞接在英數結尾之後，屬於同一個英文單字
    return previous[-1].isascii() and previous[-1].isalnum() and piece[0].isascii() and piece[0].isalnum()


def _call_mlx_whisper(audio: str, **kwargs: Any) -> dict[str, Any]:
    import mlx_whisper

    return mlx_whisper.transcribe(audio, **kwargs)


def _release_mlx_model() -> None:
    import mlx.core as mx
    from mlx_whisper.transcribe import ModelHolder

    ModelHolder.model = None
    ModelHolder.model_path = None
    gc.collect()
    clear_cache = getattr(mx, "clear_cache", None) or mx.metal.clear_cache
    clear_cache()
