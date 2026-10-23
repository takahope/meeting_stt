# 01: Mac 環境實測（spike，需本人於 Mac 操作）

**What to build:** 在 Apple Silicon Mac 上確認三個引擎/工具的實際行為，把 spec 中「須實測確認」的事實記錄下來，讓後續票不必猜測。

**Blocked by:** None (can start immediately)

**Status:** done（agy 見 docs/notes/2026-10-19-agy-findings.md；mlx-whisper 與 pyannote 見 docs/notes/2026-10-19-mac-environment-findings.md；Mac 上 agy 1.4.2 已確認）

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 0。

- [x] FFmpeg、Mac extras（mlx、mlx-whisper、torch、pyannote.audio 3.4.0）安裝成功；須為 torch<2.6 等加上限，見 Mac 實測記錄
- [x] 記錄 mlx-whisper `transcribe` 是否支援 `language`、`condition_on_previous_text`、`hallucination_silence_threshold`，以及模型快取持有者的實際屬性名稱
- [x] 已在 Hugging Face 同意兩個 gated 模型條款，pyannote 3.1 可在 MPS 上載入
- [x] 記錄 `agy` 版本、`--print-timeout` 值格式、唯讀模式旗標（agy 1.4.2；唯讀模式 plan 不適用）
- [x] 確認 non-TTY 下 `agy -p` 不讀 stdin（結束碼 0、stdout 空白）；已重新決策為放進提示詞，見 docs/notes/2026-10-19-agy-findings.md
- [x] 結果寫成環境實測記錄文件並 commit
