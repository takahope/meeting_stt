# 10: Mac 冒煙測試、README 與驗收（需本人於 Mac 操作）

**What to build:** 以真實模型證明整條管線在 Mac 上可用，並讓新使用者能依 README 從零開始操作。

**Blocked by:** 01, 03, 04, 06, 09

**Status:** ready-for-human

**參考：** spec `docs/specs/2026-10-19-mlx-pyannote-meeting-pipeline-design.md`；用語依 `GLOSSARY.md`；已驗證的測試與實作在實作計畫 Task 10；驗收清單為 spec 第 7 節。

- [ ] 真實模型冒煙測試（只在 macOS 且設定測試錄音時執行）以 30 秒錄音通過：SRT 非空、每條 ≤ 28 單位且 ≤ 兩行、暫存 WAV 已刪
- [ ] README：FFmpeg 與 Mac extras 安裝、HF 兩個 gated 模型授權與 `HF_TOKEN`、`agy` 登入、CLI 範例（含 `--summarize-only`、`--no-summary`）、隱私說明（預設上雲；機密會議用 `--no-summary`，見 ADR 0001）
- [ ] 以自錄模擬會議（5～10 分鐘、3 人以上、中英混雜）逐項通過 spec 第 7 節驗收，並記錄效能基準
- [ ] 驗收中發現的新幻覺短語已補進黑名單
