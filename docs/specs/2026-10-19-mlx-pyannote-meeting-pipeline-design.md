# 規格書：Mac 本機語音轉錄暨說話者單字級對齊與 Antigravity CLI 會議總結管線

- 日期：2026-10-19
- 用語：依循專案根目錄 `GLOSSARY.md`（錄音、單字、說話區間、說話者標籤、顯示名稱、字幕條、字數單位、逐字稿、會議總結）
- 實作計畫：`docs/plans/2026-10-19-mlx-pyannote-meeting-pipeline.md`

## 1. 核心意圖與背景

針對多人專案會議錄音，打造一套在 Apple Silicon Mac 上執行的批次處理管線，解決三個痛點：

1. **隱私與算力**：語音辨識（ASR）與說話者辨識（Diarization）全程在 Mac 本機以 Apple Silicon GPU（MLX + PyTorch MPS）離線完成，錄音不離開本機。
2. **精準標記「誰說了什麼」**：以單字級時間戳記對齊說話者，而非句子級，避免多人交談時的邊界偏移；產出標準 `.srt` 字幕與結構化逐字稿。
3. **高品質會議總結**：將本機產出的逐字稿交給已認證的 Antigravity CLI（`agy`）呼叫線上模型，提取摘要、決議與待辦事項。

### 1.1 隱私邊界（重要）

- 錄音、單字、說話區間、字幕與逐字稿的**生成**全程在本機。
- **逐字稿內容會送往 `agy` 所連線的線上模型**以產生會議總結。逐字稿的敏感度等同錄音本身。
- 使用 `--no-summary` 可完全不連線。
- **機構政策（2026-10-19 確認）**：一般會議預設允許上雲產生總結。機密會議的總結將由後續加入的本機模型（mlx-lm）處理，不在本版範圍；在那之前，機密會議請使用 `--no-summary`。決策紀錄見 `docs/adr/0001-cloud-summary-by-default.md`。

## 2. 目標、非目標與反目標

### 目標

- 支援 `.m4a`、`.mp3`、`.mp4`、`.wav` 錄音，正規化為 16kHz 單聲道 PCM s16le WAV，兩個引擎共用同一份音訊，消除時間軸偏移。
- 以 `mlx-whisper`（`word_timestamps=True`）取得單字級時間戳記，與 `pyannote/speaker-diarization-3.1` 的說話區間逐字配對。
- 輸出附說話者的 `.srt` 字幕與 `_transcript.md` 逐字稿。
- 自動呼叫 `agy -p` 產生 `_summary.md`（摘要、決議、含負責人／期限／時間戳記的待辦表格）。

### 非目標

- 不處理即時串流，只處理錄製完成的錄音。
- 不做 GUI，以單一 CLI 交付。
- 不處理重疊語音的多說話者歸屬（見 3.3）。
- 本版不提供本機總結模型；機密會議的地端總結（mlx-lm）列為後續工作。

### 反目標（出現即判定失敗）

- **以句子平均值硬切說話者**：一句話中途換人，必須在換人處切開字幕條。
- **過長字幕**：單條字幕條不得超過 28 字數單位或 6 秒，畫面上最多兩行。
- **雙框架同時佔用記憶體**：Whisper 與 pyannote 各自結束後必須釋放模型與快取。
- **覆寫既有輸出**：任何既有的 `.srt`／逐字稿／總結都不得被覆寫（見 5.4）。
- **產出空白或殘缺的總結檔**：總結失敗時不得留下 `_summary.md`。

## 3. 架構與工程決策

### 3.1 已定案的架構邊界

| 元件 | 選擇 |
|---|---|
| 語音辨識 | `mlx-whisper`，預設模型 `mlx-community/whisper-large-v3-turbo` |
| 說話者辨識 | 模型 `pyannote/speaker-diarization-3.1`，函式庫 `pyannote.audio>=3.3,<4`，PyTorch MPS |
| 繁簡轉換 | OpenCC `s2twp`，逐單字轉換 |
| 會議總結 | Antigravity CLI `agy -p`（headless/print 模式） |

### 3.2 語音辨識參數

- `language="zh"`：不依賴前 30 秒的自動語言偵測。
- `initial_prompt="以下是繁體中文的專案會議記錄，包含專業術語與待辦事項討論。"`：**傾向**輸出繁體與標點；繁體的**保證**由 OpenCC 負責。
- `condition_on_previous_text=False`：阻止重複幻覺迴圈擴散。
- `hallucination_silence_threshold=2.0`：跳過長靜音中的幻覺（需搭配 word timestamps）。
- 幻覺短語黑名單：語音辨識段落文字（轉繁、去標點後）含黑名單短語（如「Amara.org」「點讚訂閱」）時，整段丟棄。黑名單為獨立常數，可持續補充。
- OpenCC 對每個單字個別轉換，不改變單字的時間戳記。

### 3.3 單字對齊說話者

對每個單字：

1. 計算與每個說話區間的交集時長，取交集最大者；**平手時取開始較早的區間**。
2. 交集皆為 0（落在靜音間隙，或單字起訖相同）時，以單字時間中點找距離最近的說話區間；平手同樣取較早者。
3. 完全沒有說話區間時，標為 `SPEAKER_00`。

**已知限制**：兩人同時說話時，Whisper 通常只轉出其中一人，本管線也只歸屬給一位說話者。

### 3.4 字幕條切分

依序累積已標說話者的單字，遇到下列任一條件即開新字幕條：

- 說話者標籤改變
- 與前一單字間隔大於 1.2 秒
- 加入後累積超過 28 字數單位
- 加入後字幕條持續超過 6 秒

字數單位：中文字每字 1、英文單字每個 1.5、標點與空白不計。

**顯示規則**：

- 字幕條超過 14 字數單位時，在使兩行最均衡的單字邊界插入一個換行（最多兩行）；第二行不以標點開頭。
- 最短顯示 0.8 秒：短於此的字幕條延長結束時間，但不超過下一條的開始時間；不與其他字幕條合併。

**併字規則**：中文與中文、中文與標點之間不加空白；英文與英文、中文與英文之間保留一個空白。

### 3.5 說話者標籤與顯示名稱

- 對齊與切分一律使用說話者辨識給出的**說話者標籤**（`SPEAKER_XX`）。
- `--speakers "SPEAKER_00=王經理,SPEAKER_01=李工程師"` 指定的**顯示名稱**只在匯出 `.srt` 與逐字稿時套用；未指定者顯示原標籤。
- `--speakers` 格式錯誤（缺少 `=`）在推論前拒絕；指定了錄音中不存在的標籤時，只在 stderr 警告，照常完成。
- 線上模型在會議總結中推論的角色只出現在總結裡，不回寫字幕或逐字稿。

### 3.6 記憶體釋放

在同一 process 內依序執行兩個引擎：

- Whisper 結束後：清空 `mlx_whisper` 的 `ModelHolder` 模型參照，接著 `gc.collect()` 與 `mx.clear_cache()`。只清快取無法釋放常駐權重。
- pyannote 結束後：刪除 pipeline 參照，接著 `gc.collect()` 與 `torch.mps.empty_cache()`。

### 3.7 Antigravity CLI 呼叫

- 指令：`agy -p "<固定提示詞>" --print-timeout <T> [唯讀模式旗標] [--model <M>]`。**逐字稿經由 stdin 傳入**，不放在命令列參數（避免長度上限與 `ps` 外洩）。
- Python 端逾時 = `--print-timeout` + 30 秒緩衝。
- 判定失敗：找不到 `agy`、逾時、結束碼非 0、**stdout 去空白後為空**（已知 non-TTY 下 stdout 遺失但結束碼為 0 的問題）。
- 寫入：先寫暫存檔，成功後原子更名為最終檔名。
- 失敗時：保留 `.srt` 與逐字稿，不建立總結檔，於 stderr 印出原因與可直接貼上的重跑指令（`--summarize-only`）。
- `--print-timeout` 的值格式、唯讀模式旗標、stdin 是否被讀取，須在 Mac 上以 `agy --help` 與實測確認後寫死；**若 `agy -p` 不讀 stdin，停止實作並回報**，重新決策。

## 4. 資料流

```
[錄音 .m4a/.mp3/.mp4/.wav]
   │
   ▼ 1. FFmpeg 正規化（16kHz, Mono, PCM s16le；tempfile 管理，任何結束路徑皆刪除）
[暫存 WAV]
   │
   ├─► 2a. mlx-whisper → 丟棄幻覺段落 → OpenCC 逐字轉繁 → 單字清單 → 釋放 MLX
   │
   └─► 2b. pyannote 3.1 (MPS) → 說話區間清單 → 釋放 Torch MPS
   │                                   （2a、2b 依序執行，非並行）
   ▼ 3. 對齊（3.3）→ 字幕條切分（3.4）→ 匯出（套用顯示名稱）
   ├─► <stem>.srt
   └─► <stem>_transcript.md
   │
   ▼ 4. agy -p（逐字稿經 stdin；可用 --no-summary 跳過）
   └─► <stem>_summary.md
```

## 5. 介面與輸出規格

### 5.1 CLI

```bash
# 完整處理
python3 meeting_pipeline.py <audio_path> \
  [--num-speakers N | --min-speakers N --max-speakers M] \
  [--speakers "SPEAKER_00=王經理,SPEAKER_01=李工程師"] \
  [--agy-model "<model>"] \
  [--output-dir ./output] \
  [--hf-token <token>] \
  [--no-summary]

# 只重新產生會議總結
python3 meeting_pipeline.py --summarize-only <stem>_transcript.md [--agy-model "<model>"]
```

- `audio_path` 與 `--summarize-only` 必須二擇一；`--summarize-only` 只能搭配 `--agy-model`。
- `--num-speakers` 不可與 `--min-speakers`／`--max-speakers` 併用；`min > max` 拒絕。
- 以上錯誤一律在執行 FFmpeg 之前以非零結束碼拒絕。
- `--output-dir` 預設為錄音所在目錄。
- HF token 來源依序為 `--hf-token`、環境變數 `HF_TOKEN`、`huggingface-cli login` 的快取。使用前須先在 Hugging Face 同意 `pyannote/speaker-diarization-3.1` 與 `pyannote/segmentation-3.0` 兩個 gated 模型的條款。
- 進度以 `[1/4]`～`[4/4]` 印到 stderr。
- 結束碼：全部成功為 0；總結失敗為 1（`.srt` 與逐字稿已保留）；參數錯誤為 2。

### 5.2 SRT（`<stem>.srt`）

```
1
00:00:01,240 --> 00:00:04,820
[SPEAKER_00] 我們今天確認 API 進度。

2
00:00:05,100 --> 00:00:08,450
[李工程師] 目前 OAuth 模組已經完成，
但我週三前需要憑證。
```

### 5.3 逐字稿（`<stem>_transcript.md`）

- 同一說話者標籤的連續字幕條合併成一段；同一人連續超過 60 秒時強制開新段（沿用同一個說話者標頭），讓總結的時間戳記可回溯到約 1 分鐘內。
- 段落格式：`**[HH:MM:SS,mmm - HH:MM:SS,mmm] [顯示名稱或標籤]**`，下一行為發言內容，段落間空一行。

### 5.4 輸出檔命名與防覆寫

- 一次執行的三個輸出共用同一個 stem：`<錄音檔名>`；若三者任一已存在，依序嘗試 `<錄音檔名>_1`、`_2`…，取三者皆不存在的最小編號。
  例：`weekly_1.srt`、`weekly_1_transcript.md`、`weekly_1_summary.md`。
- `--summarize-only x_transcript.md` 的總結檔為 `x_summary.md`；若已存在，依序改用 `x_summary_1.md`、`x_summary_2.md`…。

### 5.5 會議總結（`<stem>_summary.md`）

以繁體中文 Markdown 產出：

1. `## 會議核心摘要`：3 至 5 點。
2. `## 關鍵決議事項 (Decisions)`：會議中定案的結論。
3. `## 待辦事項清單 (Action Items)`：表格欄位為 `負責人 (Owner)`（說話者標籤或顯示名稱，加上依上下文推論的姓名或角色）、`待辦任務內容 (Task)`、`預計完成期限 (Deadline)`、`來源時間戳記 (Timestamp)`（必須對應逐字稿段落時間）。

## 6. 開發與測試環境

- 純邏輯模組（文字、對齊、切分、匯出、命名、總結呼叫、CLI）可在任何平台開發與測試，引擎以 mock 隔離。
- Mac 專用依賴（`mlx`、`mlx-whisper`、`torch`、`pyannote.audio`）放在 `pip install -e ".[mac]"` extras；引擎模組以延遲 import 載入，非 Mac 平台也能 import。
- 真實模型冒煙測試標記為 `mac`，只在 macOS 且設定 `MEETING_SMOKE_AUDIO` 時執行。
- FFmpeg 以 Homebrew 安裝（`brew install ffmpeg`）。

## 7. 驗收

在 Mac 上以一段**自錄的模擬會議**（5～10 分鐘、3 人以上、中英混雜）執行完整流程，人工逐項確認：

- [ ] 說話者換人處字幕條有切開，沒有整句歸錯人
- [ ] 沒有超過 28 字數單位、6 秒或兩行的字幕條
- [ ] 輸出全為繁體中文，沒有「Amara.org」類幻覺文字
- [ ] `--speakers` 的顯示名稱正確出現在 `.srt` 與逐字稿
- [ ] 會議總結的每個待辦事項都有時間戳記，且能在逐字稿中找到對應段落
- [ ] 處理結束後暫存 WAV 已刪除
- [ ] 刻意讓 `agy` 失敗（例如登出）時，`.srt`、逐字稿保留，沒有總結檔，印出的 `--summarize-only` 指令可直接執行成功
- [ ] 記錄效能基準：錄音長度、各階段耗時、Mac 機型與記憶體

通過後可用一般（非機密）真實會議錄音再驗一次。
