import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SUPPORTED_EXTENSIONS = frozenset({".m4a", ".mp3", ".mp4", ".wav"})


@contextmanager
def normalized_audio_wav(input_path: Path) -> Iterator[Path]:
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    with tempfile.NamedTemporaryFile(prefix="meeting_16k_", suffix=".wav", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(temp_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"FFmpeg 轉檔失敗：{(exc.stderr or '').strip()[-500:]}") from exc
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)
