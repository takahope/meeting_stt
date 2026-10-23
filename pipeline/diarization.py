import gc
import os
from pathlib import Path
from typing import Any

from pipeline.models import SpeakerTurn

DEFAULT_DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"


def diarize_speakers(
    wav_path: Path,
    hf_token: str | None = None,
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> list[SpeakerTurn]:
    pipeline = _load_pyannote_pipeline(hf_token or os.environ.get("HF_TOKEN"))
    try:
        kwargs: dict[str, int] = {}
        if num_speakers is not None:
            kwargs["num_speakers"] = num_speakers
        if min_speakers is not None:
            kwargs["min_speakers"] = min_speakers
        if max_speakers is not None:
            kwargs["max_speakers"] = max_speakers
        annotation = pipeline(str(wav_path), **kwargs)
        turns = [
            SpeakerTurn(start=float(segment.start), end=float(segment.end), speaker=str(label))
            for segment, _track, label in annotation.itertracks(yield_label=True)
        ]
    finally:
        del pipeline
        _clear_torch_mps_memory()
    return sorted(turns, key=lambda t: t.start)


def _load_pyannote_pipeline(hf_token: str | None) -> Any:
    import torch
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(DEFAULT_DIARIZATION_MODEL, use_auth_token=hf_token)
    if pipeline is None:
        raise RuntimeError(
            "無法載入 pyannote 模型：請確認 HF token，並已在 Hugging Face 同意 "
            "pyannote/speaker-diarization-3.1 與 pyannote/segmentation-3.0 的條款"
        )
    pipeline.to(torch.device("mps"))
    return pipeline


def _clear_torch_mps_memory() -> None:
    import torch

    gc.collect()
    torch.mps.empty_cache()
