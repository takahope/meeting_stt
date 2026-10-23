# 02: 錄音轉附說話者標籤 SRT 的最短路徑（tracer bullet）

**What to build:** 使用者執行 `python3 meeting_pipeline.py <錄音> [--output-dir DIR]`，得到一份每條字幕條都標有說話者標籤的 `.srt`。路徑貫穿：錄音正規化（暫存 WAV 任何結束路徑都刪除）→ 語音辨識取得單字 → 說話者辨識取得說話區間（兩者依序執行、各自結束即釋放記憶體）→ 單字對齊說話者 → 僅在說話者標籤改變時切分字幕條 → 匯出 SRT。引擎可 mock，端到端可在非 Mac 環境驗證。

**Blocked by:** None (can start immediately)

**Status:** done

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 1、3、4（僅引擎呼叫與記憶體釋放）、5（對齊與「換人即切」）、7（SRT 匯出）、9（最小 CLI）。

- [ ] 支援 .m4a/.mp3/.mp4/.wav；不支援的副檔名或不存在的錄音在執行 FFmpeg 前拒絕
- [ ] 暫存 WAV 在成功、例外、FFmpeg 失敗時都被刪除；FFmpeg 失敗訊息包含其錯誤輸出
- [ ] 語音辨識與說話者辨識即使失敗也會釋放各自的模型與快取
- [ ] 單字歸屬：交集最大者；平手取較早區間；無交集（含起訖相同的單字）以中點找最近區間；沒有任何說話區間時標為 SPEAKER_00
- [ ] 說話者標籤改變時切開字幕條；SRT 格式符合 spec 5.2（序號、時間軸、`[SPEAKER_XX] 文字`）
- [ ] 以 mock 引擎的端到端測試：錄音 → `.srt` 存在且內容正確
