# agy 實測記錄（ticket 01 的 agy 部分）

環境：WSL2 Linux，`agy` 1.4.2，2026-10-19。mlx-whisper、pyannote 部分仍須在 Mac 上實測。
實驗只使用無害的假資料（非會議內容）。

## 旗標

- `--print-timeout`：預設 `0s`（**不設逾時**，會一直等到對話結束）；格式為時間長度字串（`60s`、`5m`）。
- `--mode`：`accept-edits | auto | plan`。
- `--output-format`：`text | json | stream-json`。
- `--model` 的值必須是 `agy models` 列出的名稱；`Gemini 3.7 Pro` 在此版本不被辨識（可用：Gemini 3.8 Flash (High/Medium/Low)、Claude Sonnet 4.6 / Opus 4.6 (Thinking)、GPT-OSS 120B (Medium)）。

## 行為（non-TTY，stdout 以管線或 subprocess 擷取）

| 實驗 | 結果 |
|---|---|
| 提示詞 + stdin 逐字稿 | **stdout 空白，結束碼 0**；stderr：agent 需要 `command` 權限，headless 模式自動拒絕 |
| 提示詞 + stdin + `--mode plan` | 同上，空白 |
| 全部文字放在 argv，stdin 為 `/dev/null` | 正常輸出，內容正確 |
| 提示詞指定檔案路徑 + `--add-dir` + `--mode plan` | 讀得到檔案，但 plan 模式產出「實作計畫」並在 `~/.gemini/antigravity-cli/brain/` 寫檔，不是摘要 |

## 結論

1. **`agy -p` 不會把 stdin 當作提示詞內容**（spec 3.7 的停止條件成立）。agent 會嘗試用工具去讀它，而 headless 模式拒絕該權限，造成「結束碼 0、stdout 空白」。「stdout 為空即失敗」的守衛因此是必要的，且已實際擋下這個情況。
2. `--mode plan` 不適合做摘要。
3. 預設 `--print-timeout` 為不逾時，必須明確指定。
