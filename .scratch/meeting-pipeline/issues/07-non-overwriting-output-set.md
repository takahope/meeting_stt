# 07: 輸出不覆寫（整組加後綴）

**What to build:** 對同一份錄音重跑時，舊的輸出原封不動，新輸出以成組後綴命名（`x_1.srt`、`x_1_transcript.md`，並預留 `x_1_summary.md`），字幕、逐字稿、總結之間的對應永遠一目了然。

**Blocked by:** 05

**Status:** done

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 6（輸出檔命名）、9（CLI 串接）。

- [ ] 三個檔名（含總結）任一已存在即改用下一個編號，取三者皆不存在的最小編號
- [ ] 未指定 `--output-dir` 時輸出到錄音所在目錄
- [ ] 端到端測試：既有 `x.srt` 不被修改，新輸出為 `x_1.*`
