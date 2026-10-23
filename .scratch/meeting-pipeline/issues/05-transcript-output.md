# 05: 逐字稿輸出

**What to build:** 除了 `.srt`，同時產出依說話者分段的 `<stem>_transcript.md`，作為之後會議總結的唯一輸入，並讓總結的時間戳記可回溯到約 1 分鐘內。

**Blocked by:** 02

**Status:** done

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 7（逐字稿匯出）、9（CLI 串接）。

- [ ] 同一說話者標籤的連續字幕條合併為一段；同一人連續超過 60 秒強制開新段
- [ ] 段落標頭為 `**[開始 - 結束] [說話者]**`，內容依併字規則串接（中文之間不多空白）
- [ ] CLI 一次執行同時輸出 `.srt` 與逐字稿，並於 stderr 顯示 `[1/4]`～`[3/4]` 進度
