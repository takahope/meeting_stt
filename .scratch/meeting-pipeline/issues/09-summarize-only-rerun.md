# 09: 只重跑會議總結（--summarize-only）

**What to build:** `agy` 失敗或想換模型時，使用者執行 08 印出的指令 `meeting_pipeline.py --summarize-only <x_transcript.md> [--agy-model M]`，只重新產生總結，不重跑耗時的本機推論；既有總結保留，新總結加後綴。

**Blocked by:** 08

**Status:** ready-for-agent

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 6（總結檔命名）、9（`--summarize-only` 模式）。

- [ ] `audio_path` 與 `--summarize-only` 必須二擇一；`--summarize-only` 只能搭配 `--agy-model`，否則結束碼 2
- [ ] 總結檔名由逐字稿檔名推導；已存在時依序用 `x_summary_1.md`、`x_summary_2.md`…；逐字稿檔名不符 `*_transcript.md` 或不存在時明確報錯
- [ ] 08 印出的重跑指令可在任意工作目錄直接貼上執行
