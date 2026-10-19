# 06: 說話者人數參數與顯示名稱

**What to build:** 使用者可用 `--num-speakers` 或 `--min-speakers/--max-speakers` 提示人數，並以 `--speakers "SPEAKER_00=王經理,…"` 讓 SRT 與逐字稿顯示真實姓名；錯誤輸入在耗時推論前就被擋下。

**Blocked by:** 05

**Status:** ready-for-agent

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 6（顯示名稱）、7（匯出套用）、9（參數驗證與警告）。

- [ ] `--num-speakers` 與 min/max 併用、min > max、人數 < 1 皆在執行 FFmpeg 前以結束碼 2 拒絕；合法值傳給說話者辨識
- [ ] `--speakers` 容忍前後空白與空項；缺少 `=` 或名稱為空時以結束碼 2 拒絕
- [ ] 顯示名稱只在匯出時套用到 SRT 與逐字稿；對齊與切分仍用說話者標籤（兩個標籤對應同一人時不合併字幕條）
- [ ] 指定了本次錄音不存在的標籤時，stderr 警告並照常完成
