# Mac 本機會議錄音 → 字幕、逐字稿與會議總結管線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Apple Silicon Mac 本機把一份會議錄音轉成附說話者的 `.srt` 字幕與 `_transcript.md` 逐字稿，並以 `agy -p` 產出 `_summary.md` 會議總結。

**Spec:** `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`（所有數值與行為以 spec 為準；用語依 `GLOSSARY.md`）

**Architecture:** 四階段序列管線。第 1 階段 FFmpeg 正規化為暫存 WAV；第 2 階段依序執行 mlx-whisper 與 pyannote，各自結束即釋放記憶體；第 3 階段以純函式對齊、切分並匯出；第 4 階段以 stdin 把逐字稿交給 `agy -p`。引擎模組延遲 import，所以除了 Task 0 與 Task 10，其餘都能在非 Mac 環境以 mock 開發與測試。

**Tech Stack:** Python 3.11+、`opencc-python-reimplemented`、`mlx` / `mlx-whisper`、`torch` + `pyannote.audio>=3.3,<4`、FFmpeg、Antigravity CLI（`agy`）、`pytest`。

**驗證狀態：** Task 1–9 的測試與實作程式碼已在 Python 3.14 + pytest 上整套跑過：46 passed、1 skipped（Mac 冒煙測試）。實作時請原樣採用；若要偏離，先改測試。

## 模組地圖

| 檔案 | 責任 |
|---|---|
| `pipeline/models.py` | 資料類別與 SRT 時間格式 |
| `pipeline/text.py` | 字數單位、併字、兩行換行、轉繁 |
| `pipeline/audio.py` | FFmpeg 正規化與暫存檔生命週期 |
| `pipeline/hallucination.py` | 幻覺短語黑名單 |
| `pipeline/asr.py` | mlx-whisper 呼叫、單字擷取、MLX 釋放 |
| `pipeline/diarization.py` | pyannote 呼叫、MPS 釋放 |
| `pipeline/aligner.py` | 單字→說話者對齊、字幕條切分 |
| `pipeline/speakers.py` | 顯示名稱解析與查詢 |
| `pipeline/outputs.py` | 輸出檔命名與防覆寫後綴 |
| `pipeline/exporters.py` | `.srt` 與逐字稿匯出 |
| `pipeline/summarizer.py` | `agy -p` 呼叫與容錯 |
| `meeting_pipeline.py` | CLI 與管線串接 |

## 依賴關係

- Task 1 → 2 → 其餘；Task 3–8 彼此獨立（Task 4 依賴 Task 2 的 `to_traditional`，Task 7 依賴 Task 6 的 `display_name`）。
- Task 9 依賴 Task 1–8。
- **Task 0 在 Mac 上執行**，可與 Task 1–9 並行；它的結果可能修改 Task 4、Task 8 的常數。Task 10 依賴全部。

---

### Task 0: Mac 環境實測（在 Apple Silicon Mac 上執行）

本 Task 不寫程式碼，目的是把 spec 中「須實測確認」的事實寫死。結果記錄於 `docs/notes/2026-10-19-mac-environment-findings.md`。

- [ ] **Step 1: 安裝**

```bash
brew install ffmpeg
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[mac,dev]"
```

（`pyproject.toml` 於 Task 1 建立；若 Task 1 尚未完成，先完成 Task 1。）

- [ ] **Step 2: 確認 mlx-whisper 參數與 ModelHolder**

```bash
python -c "import inspect, mlx_whisper; print(inspect.signature(mlx_whisper.transcribe))"
python -c "from mlx_whisper.transcribe import ModelHolder; print([k for k in vars(ModelHolder) if not k.startswith('__')])"
python -c "import mlx.core as mx; print(hasattr(mx, 'clear_cache'))"
```

Expected：`transcribe` 簽名含 `language`、`word_timestamps`、`initial_prompt`、`condition_on_previous_text`、`hallucination_silence_threshold`；`ModelHolder` 有 `model`、`model_path`。任一不符：依實際名稱修改 `pipeline/asr.py` 的 `transcribe_words` 與 `_release_mlx_model`，並同步更新 `tests/test_engines.py`。

- [ ] **Step 3: 確認 pyannote 可在 MPS 上載入**

先在 Hugging Face 同意 `pyannote/speaker-diarization-3.1` 與 `pyannote/segmentation-3.0` 的條款，然後：

```bash
export HF_TOKEN=hf_xxx
python -c "import torch; from pyannote.audio import Pipeline; p = Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=None); p.to(torch.device('mps')); print('ok')"
```

Expected：印出 `ok`（`use_auth_token=None` 會改用 `HF_TOKEN`／登入快取）。

- [ ] **Step 4: 確認 `agy -p` 的旗標與 stdin 行為**

```bash
agy --version
agy --help
echo "會議逐字稿：王經理說週三前完成 OAuth。" | agy -p "請用一句話複述標準輸入的內容" --print-timeout 5m | cat
```

確認並記錄：
1. `--print-timeout` 的值格式（如 `5m` 或 `300`），填入 `pipeline/summarizer.py` 的 `AGY_PRINT_TIMEOUT` 與 `AGY_PRINT_TIMEOUT_SEC`。
2. 唯讀模式旗標（預設假設 `--mode plan`），填入 `AGY_READONLY_ARGS`；若不存在則設為 `()`。
3. `| cat`（non-TTY）下 stdout 有內容，且內容反映了 stdin 的文字。

**若 `agy -p` 不讀 stdin：停止，回報使用者重新決策（spec 3.7）**，不要自行改成把逐字稿放進命令列參數。

- [ ] **Step 5: 寫下結果並 commit**

```bash
git add docs/notes/2026-10-19-mac-environment-findings.md
git commit -m "docs: record Mac environment findings for mlx-whisper, pyannote and agy"
```

---

### Task 1: 專案骨架、資料類別與 SRT 時間格式（`pipeline/models.py`）

**Files:**

- Create: `pyproject.toml`
- Create: `pipeline/__init__.py`（空檔）
- Create: `pipeline/models.py`
- Test: `tests/test_models.py`

先建立虛擬環境：`python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`（pyproject 建好後執行）。Commit 時一併加入 `pipeline/__init__.py`。

- [ ] **Step 1: 撰寫失敗測試 `tests/test_models.py`**

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_models.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline'`）

- [ ] **Step 3: 實作**

`pyproject.toml`：

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "meeting-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["opencc-python-reimplemented>=0.1.7"]

[project.optional-dependencies]
mac = ["mlx>=0.20", "mlx-whisper>=0.4", "torch>=2.2", "pyannote.audio>=3.3,<4"]
dev = ["pytest>=8"]

[tool.setuptools]
packages = ["pipeline"]
py-modules = ["meeting_pipeline"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = ["mac: requires Apple Silicon, FFmpeg and real models"]
```

`pipeline/models.py`：

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WordToken:
    word: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True, slots=True)
class AlignedWord:
    word: str
    start: float
    end: float
    speaker: str


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    speaker: str
    tokens: tuple[str, ...]


def format_srt_timestamp(seconds: float) -> str:
    total_ms = round(max(0.0, seconds) * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_models.py -v`

Expected: PASS（`2 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_models.py pyproject.toml pipeline/__init__.py pipeline/models.py
git commit -m "feat(models): add project skeleton, data classes and SRT timestamp formatter"
```

---

### Task 2: 字數單位、併字、兩行換行與轉繁（`pipeline/text.py`）

**Files:**

- Create: `pipeline/text.py`
- Test: `tests/test_text.py`

- [ ] **Step 1: 撰寫失敗測試 `tests/test_text.py`**

```python
from pipeline.text import compute_text_units, join_word_tokens, split_two_lines, to_traditional


def test_join_word_tokens_spacing_rules():
    assert join_word_tokens(["目前", " OAuth", "模組", "，", "OK", "!"]) == "目前 OAuth 模組，OK!"
    assert join_word_tokens(["第一句", "。", "第二句", "。"]) == "第一句。第二句。"
    assert join_word_tokens([" Hello", " world", "  "]) == "Hello world"


def test_compute_text_units_cjk_english_punctuation():
    assert compute_text_units("目前 OAuth 模組") == 5.5
    assert compute_text_units("目前 OAuth 模組，OK!") == 7.0
    assert compute_text_units("，。!?") == 0.0


def test_split_two_lines_keeps_short_text_on_one_line():
    tokens = ["字數"] * 7  # 14 units
    assert split_two_lines(tokens) == ["字數" * 7]


def test_split_two_lines_balances_and_never_starts_with_punctuation():
    assert split_two_lines(["字數"] * 10) == ["字數" * 5, "字數" * 5]
    tokens = ["一二三四", "五六七八", "，", "甲乙丙丁", "戊己庚辛"]  # 16 units
    assert split_two_lines(tokens) == ["一二三四五六七八，", "甲乙丙丁戊己庚辛"]


def test_to_traditional_converts_simplified():
    assert to_traditional("我们") == "我們"
    assert to_traditional("这个") == "這個"
    assert to_traditional(" OAuth") == " OAuth"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_text.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.text'`）

- [ ] **Step 3: 實作**

`pipeline/text.py`：

```python
import re
from collections.abc import Sequence

from opencc import OpenCC

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_ENG_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
_TO_TRADITIONAL = OpenCC("s2twp")


def to_traditional(text: str) -> str:
    return _TO_TRADITIONAL.convert(text)


def compute_text_units(text: str) -> float:
    cjk_count = len(_CJK_RE.findall(text))
    eng_count = len(_ENG_WORD_RE.findall(_CJK_RE.sub(" ", text)))
    return cjk_count * 1.0 + eng_count * 1.5


def _is_ascii_alnum(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()


def _needs_space(left: str, right: str) -> bool:
    a, b = left[-1], right[0]
    a_eng, b_eng = _is_ascii_alnum(a), _is_ascii_alnum(b)
    a_cjk, b_cjk = bool(_CJK_RE.match(a)), bool(_CJK_RE.match(b))
    return (a_eng and b_eng) or (a_eng and b_cjk) or (a_cjk and b_eng)


def join_word_tokens(tokens: Sequence[str]) -> str:
    out = ""
    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if out and _needs_space(out, token):
            out += " "
        out += token
    return out


def split_two_lines(tokens: Sequence[str], max_line_units: float = 14.0) -> list[str]:
    full = join_word_tokens(tokens)
    if compute_text_units(full) <= max_line_units or len(tokens) < 2:
        return [full]
    best_i, best_cost = None, float("inf")
    for i in range(1, len(tokens)):
        if compute_text_units(tokens[i]) == 0:
            continue  # 第二行不以標點開頭
        cost = max(
            compute_text_units(join_word_tokens(tokens[:i])),
            compute_text_units(join_word_tokens(tokens[i:])),
        )
        if cost < best_cost:
            best_i, best_cost = i, cost
    if best_i is None:
        return [full]
    return [join_word_tokens(tokens[:best_i]), join_word_tokens(tokens[best_i:])]
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_text.py -v`

Expected: PASS（`5 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_text.py pipeline/text.py
git commit -m "feat(text): add text units, token joining, two-line wrap and Traditional Chinese conversion"
```

---

### Task 3: FFmpeg 正規化與暫存檔清理（`pipeline/audio.py`）

**Files:**

- Create: `pipeline/audio.py`
- Test: `tests/test_audio.py`

- [ ] **Step 1: 撰寫失敗測試 `tests/test_audio.py`**

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_audio.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.audio'`）

- [ ] **Step 3: 實作**

`pipeline/audio.py`：

```python
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
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_audio.py -v`

Expected: PASS（`4 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_audio.py pipeline/audio.py
git commit -m "feat(audio): add FFmpeg 16kHz mono normalization with guaranteed temp cleanup"
```

---

### Task 4: 語音辨識、幻覺過濾與說話者辨識（`pipeline/asr.py`、`pipeline/hallucination.py`、`pipeline/diarization.py`）

**Files:**

- Create: `pipeline/hallucination.py`
- Create: `pipeline/asr.py`
- Create: `pipeline/diarization.py`
- Test: `tests/test_engines.py`

`mlx_whisper`、`mlx`、`torch`、`pyannote` 一律在函式內延遲 import，非 Mac 環境也能 import 本模組。`_release_mlx_model` 的屬性名稱以 Task 0 Step 2 為準。

- [ ] **Step 1: 撰寫失敗測試 `tests/test_engines.py`**

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_engines.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.asr'`）

- [ ] **Step 3: 實作**

`pipeline/hallucination.py`：

```python
import re

from pipeline.text import to_traditional

# 比對前會先轉繁、去除空白與標點、轉小寫；發現新的幻覺短語時直接補在這裡。
HALLUCINATION_PHRASES: tuple[str, ...] = (
    "amaraorg",
    "點贊訂閱",
    "點讚訂閱",
    "明鏡與點點欄目",
    "字幕志願者",
    "優優獨播劇場",
)

_STRIP_RE = re.compile(r"[\W_]+")


def is_hallucination(text: str) -> bool:
    normalized = _STRIP_RE.sub("", to_traditional(text)).lower()
    return any(phrase in normalized for phrase in HALLUCINATION_PHRASES)
```

`pipeline/asr.py`：

```python
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
        for raw in segment.get("words", []):
            text = to_traditional(raw["word"])
            if not text.strip():
                continue
            words.append(WordToken(word=text, start=float(raw["start"]), end=float(raw["end"])))
    return words


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
```

`pipeline/diarization.py`：

```python
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
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_engines.py -v`

Expected: PASS（`4 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_engines.py pipeline/hallucination.py pipeline/asr.py pipeline/diarization.py
git commit -m "feat(engines): add mlx-whisper ASR with hallucination filter and pyannote MPS diarization"
```

---

### Task 5: 單字對齊說話者與字幕條切分（`pipeline/aligner.py`）

**Files:**

- Create: `pipeline/aligner.py`
- Test: `tests/test_aligner.py`

- [ ] **Step 1: 撰寫失敗測試 `tests/test_aligner.py`**

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_aligner.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.aligner'`）

- [ ] **Step 3: 實作**

`pipeline/aligner.py`：

```python
from pipeline.models import AlignedWord, SpeakerTurn, SubtitleCue, WordToken
from pipeline.text import compute_text_units, join_word_tokens

DEFAULT_SPEAKER_LABEL = "SPEAKER_00"


def assign_speakers(words: list[WordToken], turns: list[SpeakerTurn]) -> list[AlignedWord]:
    ordered = sorted(turns, key=lambda t: t.start)
    return [
        AlignedWord(word=w.word, start=w.start, end=w.end, speaker=_pick_speaker(w, ordered))
        for w in words
    ]


def _pick_speaker(word: WordToken, turns: list[SpeakerTurn]) -> str:
    if not turns:
        return DEFAULT_SPEAKER_LABEL
    best: SpeakerTurn | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = max(0.0, min(word.end, turn.end) - max(word.start, turn.start))
        if overlap > best_overlap:  # 嚴格大於：平手保留較早的區間
            best, best_overlap = turn, overlap
    if best is not None:
        return best.speaker
    mid = (word.start + word.end) / 2.0
    nearest = min(  # min 回傳第一個最小值：平手取較早的區間
        turns,
        key=lambda t: 0.0 if t.start <= mid <= t.end else min(abs(mid - t.start), abs(mid - t.end)),
    )
    return nearest.speaker


def chunk_subtitles(
    words: list[AlignedWord],
    max_units: float = 28.0,
    max_duration: float = 6.0,
    max_gap: float = 1.2,
    min_display: float = 0.8,
) -> list[SubtitleCue]:
    groups: list[list[AlignedWord]] = []
    current: list[AlignedWord] = []
    for word in words:
        if not word.word.strip():
            continue
        if current:
            candidate = join_word_tokens([w.word for w in current] + [word.word])
            if (
                word.speaker != current[0].speaker
                or word.start - current[-1].end > max_gap
                or compute_text_units(candidate) > max_units
                or word.end - current[0].start > max_duration
            ):
                groups.append(current)
                current = []
        current.append(word)
    if current:
        groups.append(current)

    cues: list[SubtitleCue] = []
    for i, group in enumerate(groups):
        start, end = group[0].start, group[-1].end
        if end - start < min_display:
            target = start + min_display
            next_start = groups[i + 1][0].start if i + 1 < len(groups) else None
            end = target if next_start is None else max(end, min(target, next_start))
        cues.append(
            SubtitleCue(
                index=i + 1,
                start=start,
                end=end,
                speaker=group[0].speaker,
                tokens=tuple(w.word for w in group),
            )
        )
    return cues
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_aligner.py -v`

Expected: PASS（`5 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_aligner.py pipeline/aligner.py
git commit -m "feat(aligner): add word-level speaker assignment and subtitle cue chunking"
```

---

### Task 6: 顯示名稱與輸出檔命名（`pipeline/speakers.py`、`pipeline/outputs.py`）

**Files:**

- Create: `pipeline/speakers.py`
- Create: `pipeline/outputs.py`
- Test: `tests/test_speakers_outputs.py`

- [ ] **Step 1: 撰寫失敗測試 `tests/test_speakers_outputs.py`**

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_speakers_outputs.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.outputs'`）

- [ ] **Step 3: 實作**

`pipeline/speakers.py`：

```python
from collections.abc import Iterable


def parse_display_names(raw: str | None) -> dict[str, str]:
    if raw is None:
        return {}
    names: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        label, sep, name = item.partition("=")
        label, name = label.strip(), name.strip()
        if not sep or not label or not name:
            raise ValueError(f"Invalid speaker mapping: {item!r}（格式應為 SPEAKER_XX=名稱）")
        names[label] = name
    return names


def display_name(label: str, names: dict[str, str]) -> str:
    return names.get(label, label)


def unknown_labels(names: dict[str, str], labels_found: Iterable[str]) -> list[str]:
    return sorted(set(names) - set(labels_found))
```

`pipeline/outputs.py`：

```python
from dataclasses import dataclass
from pathlib import Path

_TRANSCRIPT_SUFFIX = "_transcript.md"


@dataclass(frozen=True, slots=True)
class OutputSet:
    srt: Path
    transcript: Path
    summary: Path


def _output_set(output_dir: Path, stem: str) -> OutputSet:
    return OutputSet(
        srt=output_dir / f"{stem}.srt",
        transcript=output_dir / f"{stem}{_TRANSCRIPT_SUFFIX}",
        summary=output_dir / f"{stem}_summary.md",
    )


def allocate_output_set(output_dir: Path, basename: str) -> OutputSet:
    n = 0
    while True:
        candidate = _output_set(output_dir, basename if n == 0 else f"{basename}_{n}")
        if not any(p.exists() for p in (candidate.srt, candidate.transcript, candidate.summary)):
            return candidate
        n += 1


def summary_path_for(transcript_path: Path) -> Path:
    name = transcript_path.name
    if not name.endswith(_TRANSCRIPT_SUFFIX):
        raise ValueError(f"逐字稿檔名必須以 {_TRANSCRIPT_SUFFIX} 結尾：{name}")
    stem = name[: -len(_TRANSCRIPT_SUFFIX)]
    candidate = transcript_path.with_name(f"{stem}_summary.md")
    n = 1
    while candidate.exists():
        candidate = transcript_path.with_name(f"{stem}_summary_{n}.md")
        n += 1
    return candidate
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_speakers_outputs.py -v`

Expected: PASS（`4 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_speakers_outputs.py pipeline/speakers.py pipeline/outputs.py
git commit -m "feat(outputs): add display name parsing and non-overwriting output naming"
```

---

### Task 7: SRT 與逐字稿匯出（`pipeline/exporters.py`）

**Files:**

- Create: `pipeline/exporters.py`
- Test: `tests/test_exporters.py`

- [ ] **Step 1: 撰寫失敗測試 `tests/test_exporters.py`**

```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_exporters.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.exporters'`）

- [ ] **Step 3: 實作**

`pipeline/exporters.py`：

```python
from pathlib import Path

from pipeline.models import SubtitleCue, format_srt_timestamp
from pipeline.speakers import display_name
from pipeline.text import join_word_tokens, split_two_lines


def export_srt(
    cues: list[SubtitleCue], output_path: Path, display_names: dict[str, str] | None = None
) -> Path:
    names = display_names or {}
    blocks = []
    for cue in cues:
        lines = split_two_lines(cue.tokens)
        lines[0] = f"[{display_name(cue.speaker, names)}] {lines[0]}"
        timing = f"{format_srt_timestamp(cue.start)} --> {format_srt_timestamp(cue.end)}"
        blocks.append("\n".join([str(cue.index), timing, *lines]) + "\n")
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path


def export_transcript_md(
    cues: list[SubtitleCue],
    output_path: Path,
    display_names: dict[str, str] | None = None,
    max_paragraph_sec: float = 60.0,
) -> Path:
    names = display_names or {}
    paragraphs: list[list[SubtitleCue]] = []
    for cue in cues:
        current = paragraphs[-1] if paragraphs else None
        if (
            current is None
            or cue.speaker != current[0].speaker
            or cue.end - current[0].start > max_paragraph_sec
        ):
            paragraphs.append([cue])
        else:
            current.append(cue)

    blocks = []
    for para in paragraphs:
        header = (
            f"**[{format_srt_timestamp(para[0].start)} - {format_srt_timestamp(para[-1].end)}] "
            f"[{display_name(para[0].speaker, names)}]**"
        )
        text = join_word_tokens([token for cue in para for token in cue.tokens])
        blocks.append(f"{header}\n{text}\n")
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_exporters.py -v`

Expected: PASS（`3 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_exporters.py pipeline/exporters.py
git commit -m "feat(exporters): add SRT and transcript exporters with display names"
```

---

### Task 8: `agy -p` 會議總結與容錯（`pipeline/summarizer.py`）

**Files:**

- Create: `pipeline/summarizer.py`
- Test: `tests/test_summarizer.py`

檔首三個 `AGY_*` 常數以 Task 0 Step 4 的實測結果為準；若 Task 0 尚未完成，先用下列預設值，完成後回頭更新。

- [ ] **Step 1: 撰寫失敗測試 `tests/test_summarizer.py`**

```python
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.summarizer import build_agy_command, build_agy_prompt, generate_meeting_summary


def test_build_agy_prompt_contains_required_sections():
    prompt = build_agy_prompt()
    for section in (
        "會議核心摘要",
        "關鍵決議事項 (Decisions)",
        "待辦事項清單 (Action Items)",
        "負責人 (Owner)",
        "預計完成期限 (Deadline)",
        "來源時間戳記 (Timestamp)",
    ):
        assert section in prompt


def test_build_agy_command_has_timeout_and_optional_model():
    cmd = build_agy_command("Gemini 3.7 Pro")
    assert cmd[:2] == ["agy", "-p"]
    assert "--print-timeout" in cmd
    assert cmd[-2:] == ["--model", "Gemini 3.7 Pro"]
    assert "--model" not in build_agy_command()


def test_generate_meeting_summary_sends_transcript_via_stdin_and_writes_atomically(tmp_path: Path):
    transcript = tmp_path / "meeting_transcript.md"
    transcript.write_text("逐字稿內容", encoding="utf-8")
    summary = tmp_path / "meeting_summary.md"
    with patch("pipeline.summarizer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="# 會議總結\n重點一\n\n", stderr="")
        ok = generate_meeting_summary(transcript, summary, agy_model="Gemini 3.7 Pro")
    assert ok is True
    assert summary.read_text(encoding="utf-8") == "# 會議總結\n重點一\n"
    assert mock_run.call_args.kwargs["input"] == "逐字稿內容"
    assert "逐字稿內容" not in mock_run.call_args.args[0]
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "run_kwargs",
    [
        {"return_value": MagicMock(returncode=1, stdout="", stderr="Not logged in")},
        {"return_value": MagicMock(returncode=0, stdout="  \n", stderr="")},
        {"side_effect": subprocess.TimeoutExpired(cmd="agy", timeout=330)},
        {"side_effect": FileNotFoundError("agy")},
    ],
    ids=["nonzero-exit", "empty-stdout", "timeout", "not-installed"],
)
def test_generate_meeting_summary_failure_keeps_outputs_and_prints_rerun(tmp_path: Path, capsys, run_kwargs):
    srt = tmp_path / "meeting.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n[SPEAKER_00] 保留測試\n", encoding="utf-8")
    transcript = tmp_path / "meeting_transcript.md"
    transcript.write_text("逐字稿內容", encoding="utf-8")
    summary = tmp_path / "meeting_summary.md"
    with patch("pipeline.summarizer.subprocess.run", **run_kwargs):
        ok = generate_meeting_summary(transcript, summary, agy_model="Gemini 3.7 Pro")
    assert ok is False
    assert srt.exists() and transcript.exists()
    assert not summary.exists()
    assert list(tmp_path.glob("*.tmp")) == []
    err = capsys.readouterr().err
    assert "--summarize-only" in err and str(transcript) in err and "Gemini 3.7 Pro" in err
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_summarizer.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'pipeline.summarizer'`）

- [ ] **Step 3: 實作**

`pipeline/summarizer.py`：

```python
import os
import shlex
import subprocess
import sys
from pathlib import Path

# 以下三個常數依 Task 0 在 Mac 上 `agy --help` 的實測結果填寫
AGY_PRINT_TIMEOUT = "5m"
AGY_PRINT_TIMEOUT_SEC = 300
AGY_READONLY_ARGS: tuple[str, ...] = ("--mode", "plan")

_SUBPROCESS_GRACE_SEC = 30
_CLI_PATH = Path(__file__).resolve().parents[1] / "meeting_pipeline.py"


def build_agy_prompt() -> str:
    return (
        "你是專業的會議記錄助理。標準輸入（stdin）是一份會議逐字稿，"
        "每段以 **[開始 - 結束] [說話者]** 標示時間與說話者。"
        "請只根據逐字稿內容，以繁體中文 Markdown 輸出以下三個章節，不要輸出其他前言或結語：\n\n"
        "## 會議核心摘要\n3 至 5 點濃縮重點。\n\n"
        "## 關鍵決議事項 (Decisions)\n會議中拍板定案的結論；若無，寫「無」。\n\n"
        "## 待辦事項清單 (Action Items)\n"
        "以 Markdown 表格呈現，欄位依序為："
        "| 負責人 (Owner) | 待辦任務內容 (Task) | 預計完成期限 (Deadline) | 來源時間戳記 (Timestamp) |。\n"
        "負責人請寫逐字稿中的說話者，並依上下文在括號內推論其姓名或角色；"
        "期限未提及時寫「未指定」；來源時間戳記必須是逐字稿中對應段落的開始時間。"
    )


def build_agy_command(agy_model: str | None = None) -> list[str]:
    cmd = ["agy", "-p", build_agy_prompt(), "--print-timeout", AGY_PRINT_TIMEOUT, *AGY_READONLY_ARGS]
    if agy_model:
        cmd += ["--model", agy_model]
    return cmd


def format_rerun_command(transcript_path: Path, agy_model: str | None = None) -> str:
    cmd = ["python3", str(_CLI_PATH), "--summarize-only", str(transcript_path)]
    if agy_model:
        cmd += ["--agy-model", agy_model]
    return shlex.join(cmd)


def generate_meeting_summary(
    transcript_path: Path, summary_path: Path, agy_model: str | None = None
) -> bool:
    transcript_text = transcript_path.read_text(encoding="utf-8")
    try:
        result = subprocess.run(
            build_agy_command(agy_model),
            input=transcript_text,
            capture_output=True,
            text=True,
            timeout=AGY_PRINT_TIMEOUT_SEC + _SUBPROCESS_GRACE_SEC,
        )
    except FileNotFoundError:
        return _fail("找不到 agy 執行檔，請確認 Antigravity CLI 已安裝並在 PATH 中", transcript_path, agy_model)
    except subprocess.TimeoutExpired:
        return _fail("agy 執行逾時", transcript_path, agy_model)
    if result.returncode != 0:
        return _fail(
            f"agy 結束碼 {result.returncode}（可能未登入）：{(result.stderr or '').strip()}",
            transcript_path,
            agy_model,
        )
    summary = (result.stdout or "").strip()
    if not summary:
        return _fail("agy 沒有輸出任何內容", transcript_path, agy_model)
    temp_path = summary_path.with_name(summary_path.name + ".tmp")
    temp_path.write_text(summary + "\n", encoding="utf-8")
    os.replace(temp_path, summary_path)
    return True


def _fail(reason: str, transcript_path: Path, agy_model: str | None) -> bool:
    print(
        f"[summary] 會議總結失敗：{reason}\n"
        f"已保留字幕與逐字稿。修正後可執行以下指令只重新產生總結：\n"
        f"  {format_rerun_command(transcript_path, agy_model)}",
        file=sys.stderr,
    )
    return False
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_summarizer.py -v`

Expected: PASS（`7 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_summarizer.py pipeline/summarizer.py
git commit -m "feat(summarizer): call agy -p via stdin with timeout, empty-output and atomic-write handling"
```

---

### Task 9: CLI 與管線串接（`meeting_pipeline.py`）

**Files:**

- Create: `meeting_pipeline.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 撰寫失敗測試 `tests/test_cli.py`**

```python
from pathlib import Path
from unittest.mock import patch

import pytest

from meeting_pipeline import main, parse_args
from pipeline.models import SpeakerTurn, WordToken

FAKE_WORDS = [
    WordToken(word="我們", start=1.24, end=1.80),
    WordToken(word="確認", start=1.85, end=2.50),
]
FAKE_TURNS = [SpeakerTurn(start=1.0, end=3.0, speaker="SPEAKER_00")]


@pytest.mark.parametrize(
    "argv",
    [
        ["demo.m4a", "--num-speakers", "2", "--min-speakers", "1"],
        ["demo.m4a", "--min-speakers", "4", "--max-speakers", "2"],
        ["demo.m4a", "--num-speakers", "0"],
        [],
        ["demo.m4a", "--summarize-only", "demo_transcript.md"],
        ["--summarize-only", "demo_transcript.md", "--no-summary"],
        ["demo.m4a", "--speakers", "SPEAKER_00:王經理"],
        ["demo.txt"],
    ],
    ids=["num-with-min", "min-gt-max", "zero", "no-input", "both-inputs", "summarize-with-no-summary", "bad-speakers", "bad-ext"],
)
def test_parse_args_rejects_invalid_combinations(argv):
    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def _run_main(argv: list[str], tmp_path: Path, summary_ok: bool = True):
    with (
        patch("meeting_pipeline.normalized_audio_wav") as mock_norm,
        patch("meeting_pipeline.transcribe_words", return_value=FAKE_WORDS),
        patch("meeting_pipeline.diarize_speakers", return_value=FAKE_TURNS),
        patch("meeting_pipeline.generate_meeting_summary", return_value=summary_ok) as mock_sum,
    ):
        mock_norm.return_value.__enter__.return_value = tmp_path / "temp_16k.wav"
        exit_code = main(argv)
    return exit_code, mock_sum


def test_main_runs_full_pipeline_and_creates_outputs(tmp_path: Path):
    audio = tmp_path / "weekly_sync.m4a"
    audio.write_bytes(b"fake")
    out_dir = tmp_path / "output"
    exit_code, mock_sum = _run_main(
        [str(audio), "--num-speakers", "2", "--speakers", "SPEAKER_00=王經理",
         "--agy-model", "Gemini 3.7 Pro", "--output-dir", str(out_dir)],
        tmp_path,
    )
    assert exit_code == 0
    assert "[王經理] 我們確認" in (out_dir / "weekly_sync.srt").read_text(encoding="utf-8")
    assert (out_dir / "weekly_sync_transcript.md").exists()
    mock_sum.assert_called_once_with(
        out_dir / "weekly_sync_transcript.md",
        out_dir / "weekly_sync_summary.md",
        agy_model="Gemini 3.7 Pro",
    )


def test_main_suffixes_outputs_skips_summary_and_warns_unknown_label(tmp_path: Path, capsys):
    audio = tmp_path / "weekly_sync.m4a"
    audio.write_bytes(b"fake")
    (tmp_path / "weekly_sync.srt").write_text("old", encoding="utf-8")
    exit_code, mock_sum = _run_main(
        [str(audio), "--no-summary", "--speakers", "SPEAKER_03=陳主任"], tmp_path
    )
    assert exit_code == 0
    assert (tmp_path / "weekly_sync.srt").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "weekly_sync_1.srt").exists()
    assert (tmp_path / "weekly_sync_1_transcript.md").exists()
    mock_sum.assert_not_called()
    assert "SPEAKER_03" in capsys.readouterr().err


def test_main_returns_1_when_summary_fails(tmp_path: Path):
    audio = tmp_path / "weekly_sync.m4a"
    audio.write_bytes(b"fake")
    exit_code, _ = _run_main([str(audio)], tmp_path, summary_ok=False)
    assert exit_code == 1
    assert (tmp_path / "weekly_sync.srt").exists()


def test_main_summarize_only_uses_suffixed_summary_path(tmp_path: Path):
    transcript = tmp_path / "weekly_sync_transcript.md"
    transcript.write_text("逐字稿", encoding="utf-8")
    (tmp_path / "weekly_sync_summary.md").write_text("old", encoding="utf-8")
    with patch("meeting_pipeline.generate_meeting_summary", return_value=True) as mock_sum:
        assert main(["--summarize-only", str(transcript)]) == 0
    mock_sum.assert_called_once_with(transcript, tmp_path / "weekly_sync_summary_1.md", agy_model=None)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'meeting_pipeline'`）

- [ ] **Step 3: 實作**

`meeting_pipeline.py`：

```python
import argparse
import sys
from pathlib import Path

from pipeline.aligner import assign_speakers, chunk_subtitles
from pipeline.asr import transcribe_words
from pipeline.audio import SUPPORTED_EXTENSIONS, normalized_audio_wav
from pipeline.diarization import diarize_speakers
from pipeline.exporters import export_srt, export_transcript_md
from pipeline.outputs import allocate_output_set, summary_path_for
from pipeline.speakers import parse_display_names, unknown_labels
from pipeline.summarizer import generate_meeting_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mac 本機會議錄音轉字幕、逐字稿與會議總結")
    parser.add_argument("audio_path", nargs="?", type=Path, help="會議錄音（.m4a/.mp3/.mp4/.wav）")
    parser.add_argument("--summarize-only", type=Path, metavar="TRANSCRIPT", help="只根據既有逐字稿重新產生會議總結")
    parser.add_argument("--num-speakers", type=int)
    parser.add_argument("--min-speakers", type=int)
    parser.add_argument("--max-speakers", type=int)
    parser.add_argument("--speakers", help='顯示名稱，例如 "SPEAKER_00=王經理,SPEAKER_01=李工程師"')
    parser.add_argument("--agy-model")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--hf-token")
    parser.add_argument("--no-summary", action="store_true", help="不呼叫 agy，逐字稿不離開本機")
    args = parser.parse_args(argv)

    if (args.audio_path is None) == (args.summarize_only is None):
        parser.error("必須擇一提供 audio_path 或 --summarize-only")
    if args.summarize_only is not None:
        audio_only = [args.num_speakers, args.min_speakers, args.max_speakers, args.speakers, args.output_dir, args.hf_token]
        if args.no_summary or any(v is not None for v in audio_only):
            parser.error("--summarize-only 只能搭配 --agy-model")
    else:
        if args.audio_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            parser.error(f"不支援的錄音格式：{args.audio_path.suffix}（支援 {', '.join(sorted(SUPPORTED_EXTENSIONS))}）")
    if args.num_speakers is not None and (args.min_speakers is not None or args.max_speakers is not None):
        parser.error("--num-speakers 不可與 --min-speakers/--max-speakers 併用")
    for value in (args.num_speakers, args.min_speakers, args.max_speakers):
        if value is not None and value < 1:
            parser.error("說話者人數必須 >= 1")
    if args.min_speakers is not None and args.max_speakers is not None and args.min_speakers > args.max_speakers:
        parser.error("--min-speakers 不可大於 --max-speakers")
    try:
        args.display_names = parse_display_names(args.speakers)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run_pipeline(args: argparse.Namespace) -> int:
    if args.summarize_only is not None:
        transcript = args.summarize_only
        if not transcript.is_file():
            _log(f"找不到逐字稿：{transcript}")
            return 1
        ok = generate_meeting_summary(transcript, summary_path_for(transcript), agy_model=args.agy_model)
        return 0 if ok else 1

    output_dir = args.output_dir or args.audio_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = allocate_output_set(output_dir, args.audio_path.stem)

    _log("[1/4] 正規化音訊")
    with normalized_audio_wav(args.audio_path) as wav_path:
        _log("[2/4] 語音辨識（mlx-whisper）")
        words = transcribe_words(wav_path)
        _log("[2/4] 說話者辨識（pyannote）")
        turns = diarize_speakers(
            wav_path,
            hf_token=args.hf_token,
            num_speakers=args.num_speakers,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
        )

    _log("[3/4] 對齊與匯出")
    cues = chunk_subtitles(assign_speakers(words, turns))
    for label in unknown_labels(args.display_names, {cue.speaker for cue in cues}):
        _log(f"警告：--speakers 指定的 {label} 不存在於本次錄音的說話者標籤中，已忽略")
    export_srt(cues, outputs.srt, args.display_names)
    export_transcript_md(cues, outputs.transcript, args.display_names)
    _log(f"已輸出 {outputs.srt}\n已輸出 {outputs.transcript}")

    if args.no_summary:
        return 0
    _log("[4/4] 會議總結（agy）")
    ok = generate_meeting_summary(outputs.transcript, outputs.summary, agy_model=args.agy_model)
    if ok:
        _log(f"已輸出 {outputs.summary}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    return run_pipeline(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_cli.py -v`

Expected: PASS（`12 passed`）

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py meeting_pipeline.py
git commit -m "feat(cli): wire up end-to-end meeting pipeline CLI with --summarize-only and --no-summary"
```

- [ ] **Step 6: 全套測試**

Run: `pytest -v`

Expected: `46 passed, 1 skipped`

---

### Task 10: Mac 真實模型冒煙測試與驗收（在 Apple Silicon Mac 上執行）

**Files:**

- Create: `tests/test_smoke_mac.py`
- Create: `README.md`
- Create: `docs/notes/2026-10-19-acceptance.md`

- [ ] **Step 1: 撰寫冒煙測試 `tests/test_smoke_mac.py`**

```python
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
```

- [ ] **Step 2: 以 30 秒短錄音執行冒煙測試**

Run: `MEETING_SMOKE_AUDIO=/path/to/short_clip.m4a pytest tests/test_smoke_mac.py -v`

Expected: PASS（`1 passed`）。失敗時先對照 Task 0 的記錄檢查引擎參數。

- [ ] **Step 3: 撰寫 `README.md`**

內容：安裝（`brew install ffmpeg`、`pip install -e ".[mac,dev]"`）、Hugging Face 兩個 gated 模型的授權步驟與 `HF_TOKEN`、`agy` 登入、CLI 範例（含 `--summarize-only`、`--no-summary`），以及隱私說明（spec 1.1、ADR 0001：一般會議預設上雲產生總結；機密會議請用 `--no-summary`，待日後加入 mlx-lm 地端總結）。

- [ ] **Step 4: 依 spec 第 7 節執行驗收**

以自錄的模擬會議（5～10 分鐘、3 人以上、中英混雜）逐項檢查 spec 第 7 節清單，結果與效能基準（錄音長度、各階段耗時、Mac 機型與記憶體）寫入 `docs/notes/2026-10-19-acceptance.md`。發現新的幻覺短語時補進 `pipeline/hallucination.py` 的 `HALLUCINATION_PHRASES`。

- [ ] **Step 5: Commit**

```bash
git add tests/test_smoke_mac.py README.md docs/notes/2026-10-19-acceptance.md
git commit -m "test: add Mac smoke test, README and acceptance record"
```
