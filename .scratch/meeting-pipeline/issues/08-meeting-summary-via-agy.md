# 08: 會議總結（agy）與容錯

**What to build:** 管線最後把逐字稿放進提示詞交給 `agy -p`，產出含摘要、決議與待辦表格的 `<stem>_summary.md`。任何失敗都不會毀掉已產出的字幕與逐字稿，也不會留下空白或殘缺的總結檔，並告訴使用者如何只重跑總結。`--no-summary` 可完全不連線。

**Blocked by:** 01, 05, 07

**Status:** done（agy 1.4.2 實測後改為逐字稿放進提示詞；以真實 agy 端到端驗證過，見 docs/notes/2026-10-19-agy-findings.md）

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 8、9（`--no-summary` 與結束碼）。

- [x] 提示詞要求 spec 5.5 的三個章節與待辦表格四個欄位；逐字稿放在提示詞中，`stdin` 設為 DEVNULL（agy 不讀 stdin）；提示詞超過 100,000 bytes 時不呼叫 agy 並明確報錯
- [x] 帶 `--print-timeout 5m`，不使用 `--mode plan`；Python 端逾時多 30 秒緩衝；`--agy-model` 有給才附加
- [x] 未安裝、逾時、非零結束碼、stdout 為空皆判定失敗：保留 SRT 與逐字稿、不留總結檔或暫存檔、stderr 印出原因與可貼上的重跑指令（含 `--summarize-only` 與模型）
- [x] 成功時先寫暫存檔再原子更名
- [x] 結束碼：成功 0、總結失敗 1、參數錯誤 2；`--no-summary` 時不呼叫 agy 且結束碼 0
